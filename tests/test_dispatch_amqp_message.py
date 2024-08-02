# SPDX-FileCopyrightText: 2019-2020 Magenta ApS
# SPDX-License-Identifier: MPL-2.0
"""Test the dispatch_amqp_message function."""

import string
from contextlib import nullcontext
from functools import partial
from typing import ContextManager
from uuid import UUID
from uuid import uuid4

import hypothesis
import hypothesis.strategies as st
import pytest
from fastapi import status
from fastramqpi.ramqp.utils import RejectMessage
from fastramqpi.ramqp.utils import RequeueMessage
from hypothesis import HealthCheck
from hypothesis import given
from hypothesis.provisional import urls
from hypothesis.strategies import register_type_strategy
from pydantic import AnyHttpUrl
from respx import MockRouter
from structlog.testing import capture_logs

from amqp2http.config import EventEndpoint
from amqp2http.dispatch import dispatch_amqp_message
from tests.utils.amqp_helpers import json2raw
from tests.utils.amqp_helpers import payload2incoming

# NOTE: This list is derived from RFC 3986 section 2.3 (Unreserved Characters)
#       Do note that this does not take into account percentage encoding, thus
#       "!#$&'()*+,/:;=?@[]" are all unfairly disallowed right now.
valid_header_text = partial(
    st.text, alphabet=string.ascii_letters + string.digits + "-_.~"
)
non_empty_valid_header_text = partial(valid_header_text, min_size=1)


# NOTE: RESPX does not seem to accept accept all RFC 3986 URLs.
# It seems to have issues with URLs whose paths starts with multiple slashes.
# This applies both the having the actual '/' and URL encoding '%2F'
# Upstream issue created: https://github.com/lundberg/respx/issues/273
register_type_strategy(
    AnyHttpUrl,
    urls()
    # Remove URL-encoded slashes
    .map(lambda x: x.replace("%2F", ""))
    # Filter strings with multiple occurances of '//'. We only accept 'http(s)://'
    .filter(lambda x: x.count("//") <= 1),
)
register_type_strategy(
    EventEndpoint, st.builds(EventEndpoint, routing_key=non_empty_valid_header_text())
)


@given(
    endpoint=...,
    uuid=...,
    response_content=...,
    correlation_id=...,
    content_type=valid_header_text(),
    content_encoding=valid_header_text(),
    custom_amqp_header=valid_header_text(),
)
@hypothesis.settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
async def test_dispatch_amqp_message(  # noqa: PLR0913
    respx_mock: MockRouter,
    endpoint: EventEndpoint,
    uuid: UUID,
    response_content: bytes,
    correlation_id: UUID,
    content_type: str,
    content_encoding: str,
    custom_amqp_header: str,
) -> None:
    """Test that dispatch_amqp_message works as expected."""
    # Reset the function scoped fixture as it is used with hypothesis
    respx_mock.reset()

    route = respx_mock.post(url=endpoint.url).respond(
        status_code=200, content=response_content
    )

    payload = {"uuid": str(uuid)}
    amqp_message = payload2incoming(payload)

    amqp_message.correlation_id = str(correlation_id)
    amqp_message.content_type = content_type
    amqp_message.content_encoding = content_encoding

    amqp_headers: dict = {custom_amqp_header: "WOW"}
    amqp_message.headers = amqp_headers

    with capture_logs() as cap_logs:
        await dispatch_amqp_message(endpoint, amqp_message)

    assert cap_logs == [
        {
            "log_level": "debug",
            "event": "amqp-to-http request",
            "endpoint_url": endpoint,
            "content": json2raw(payload),
            "headers": {
                "Content-Type": content_type,
                "Content-Encoding": content_encoding,
                "X-Correlation-ID": str(correlation_id),
                "X-Message-ID": amqp_message.message_id,
                "X-Routing-Key": endpoint.routing_key,
                "X-AMQP-HEADER-" + custom_amqp_header: "WOW",
            },
        },
        {
            "log_level": "debug",
            "event": "amqp-to-http response",
            "status_code": 200,
            "content": response_content,
        },
        {"event": "Integration succesfully processed message", "log_level": "debug"},
    ]
    assert route.call_count == 1


@pytest.mark.parametrize(
    "status_code,log,expected",
    [
        # OK
        *[
            (
                status_code,
                {
                    "event": "Integration succesfully processed message",
                    "log_level": "debug",
                },
                None,
            )
            for status_code in [
                status.HTTP_200_OK,
                status.HTTP_202_ACCEPTED,
                status.HTTP_204_NO_CONTENT,
                status.HTTP_208_ALREADY_REPORTED,
            ]
        ],
        # Going too fast
        *[
            (
                status_code,
                {
                    "event": "Integration requested us to slow down",
                    "log_level": "info",
                },
                RequeueMessage("Was going too fast"),
            )
            for status_code in [
                status.HTTP_408_REQUEST_TIMEOUT,
                status.HTTP_425_TOO_EARLY,
                status.HTTP_429_TOO_MANY_REQUESTS,
                status.HTTP_503_SERVICE_UNAVAILABLE,
                status.HTTP_504_GATEWAY_TIMEOUT,
            ]
        ],
        # Illegal
        (
            status.HTTP_451_UNAVAILABLE_FOR_LEGAL_REASONS,
            {
                "event": "Integration requested us to reject the message",
                "log_level": "info",
            },
            RejectMessage("We legally cannot process this"),
        ),
        # Bad request
        *[
            (
                status_code,
                {
                    "event": "Integration could not handle the request",
                    "log_level": "info",
                },
                RequeueMessage("We send a bad request"),
            )
            for status_code in [
                status.HTTP_400_BAD_REQUEST,
                status.HTTP_401_UNAUTHORIZED,
                status.HTTP_403_FORBIDDEN,
                status.HTTP_404_NOT_FOUND,
                status.HTTP_405_METHOD_NOT_ALLOWED,
            ]
        ],
        # Not implemented
        (
            status.HTTP_501_NOT_IMPLEMENTED,
            {
                "event": "Integration notified us that the endpoint is not implemented",
                "log_level": "info",
            },
            RequeueMessage("Not implemented"),
        ),
        # Server errors
        *[
            (
                status_code,
                {
                    "event": "Integration could not handle the request",
                    "log_level": "info",
                },
                RequeueMessage("The server done goofed"),
            )
            for status_code in [
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                status.HTTP_502_BAD_GATEWAY,
                status.HTTP_507_INSUFFICIENT_STORAGE,
                status.HTTP_508_LOOP_DETECTED,
            ]
        ],
        # Random codes
        *[
            (
                status_code,
                {
                    "event": "Integration send an unknown status-code",
                    "status_code": status_code,
                    "log_level": "info",
                },
                RequeueMessage(f"Unexpected status-code: {status_code}"),
            )
            for status_code in [
                status.HTTP_100_CONTINUE,
                status.HTTP_103_EARLY_HINTS,
                status.HTTP_306_RESERVED,
                status.HTTP_304_NOT_MODIFIED,
            ]
        ],
    ],
)
@pytest.mark.usefixtures("disable_asyncio_sleep")
async def test_dispatch_amqp_message_status_codes(
    respx_mock: MockRouter,
    status_code: int,
    log: dict[str, str],
    expected: Exception | None,
) -> None:
    """Test that dispatch_amqp_message responds to status_codes as expected."""
    routing_key = "person"
    url = "http://integration/trigger/"
    uuid = uuid4()
    response_content = "NO CONTENT"

    route = respx_mock.post(url=url).respond(
        status_code=status_code, content=response_content
    )

    endpoint = EventEndpoint(routing_key=routing_key, url=url)

    payload = {"uuid": str(uuid)}
    amqp_message = payload2incoming(payload)

    contextmanager: ContextManager = nullcontext()
    if expected:
        contextmanager = pytest.raises(type(expected), match=str(expected))

    with capture_logs() as cap_logs, contextmanager:
        await dispatch_amqp_message(endpoint, amqp_message)

    assert cap_logs == [
        {
            "log_level": "debug",
            "event": "amqp-to-http request",
            "endpoint_url": endpoint,
            "content": json2raw(payload),
            "headers": {
                "X-Message-ID": amqp_message.message_id,
                "X-Routing-Key": routing_key,
            },
        },
        {
            "log_level": "debug",
            "event": "amqp-to-http response",
            "status_code": status_code,
            "content": response_content.encode("utf-8"),
        },
        log,
    ]
    assert route.call_count == 1
