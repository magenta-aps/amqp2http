# SPDX-FileCopyrightText: 2019-2020 Magenta ApS
# SPDX-License-Identifier: MPL-2.0
"""AMQP2HTTP converter."""

import asyncio

import httpx
import structlog
from fastapi import status
from fastramqpi.ramqp.depends import Message
from fastramqpi.ramqp.utils import RejectMessage
from fastramqpi.ramqp.utils import RequeueMessage

from amqp2http.config import EventEndpoint

logger = structlog.stdlib.get_logger()


async def dispatch_amqp_message(
    endpoint: EventEndpoint,
    message: Message,
) -> None:
    """Dispatch a HTTP POST request corresponding with the incoming message.

    Args:
        endpoint: The endpoint configuration to run this handler for.
        message: The AMQP message we received and forward.

    Raises:
        RejectMessage: If the integration requested it.
        RequeueMessage: If the integration requested it.
    """
    async with httpx.AsyncClient() as client:
        # TODO: Add more headers based on IncomingMessage as required
        potential_headers = {
            "Content-Type": message.content_type,
            "Content-Encoding": message.content_encoding,
            "X-Correlation-ID": message.correlation_id,
            "X-Message-ID": message.message_id,
            "X-Routing-Key": endpoint.routing_key,
        }
        for key, value in message.headers.items():
            potential_headers[f"X-AMQP-HEADER-{key}"] = str(value)

        headers = {
            key: value for key, value in potential_headers.items() if value is not None
        }

        logger.debug(
            "amqp-to-http request",
            endpoint_url=endpoint,
            content=message.body,
            headers=headers,
        )
        response = await client.post(
            endpoint.url, content=message.body, headers=headers
        )
        logger.debug(
            "amqp-to-http response",
            status_code=response.status_code,
            content=response.content,
        )

        match response.status_code:
            # All 200 status-codes are OK
            case _ if (
                status.HTTP_200_OK
                <= response.status_code
                < status.HTTP_300_MULTIPLE_CHOICES
            ):
                logger.debug("Integration succesfully processed message")
                return

            # Handle status-codes indicating that we may be going too fast
            case (
                status.HTTP_408_REQUEST_TIMEOUT
                | status.HTTP_425_TOO_EARLY
                | status.HTTP_429_TOO_MANY_REQUESTS
                | status.HTTP_503_SERVICE_UNAVAILABLE
                | status.HTTP_504_GATEWAY_TIMEOUT
            ):
                # TODO: Maybe only sleep on 503 if it is a redelivery?
                # TODO: Maybe the response should contain the sleep time?
                logger.info("Integration requested us to slow down")
                await asyncio.sleep(30)
                raise RequeueMessage("Was going too fast")

            # Handle legal issues
            case status.HTTP_451_UNAVAILABLE_FOR_LEGAL_REASONS:
                logger.info("Integration requested us to reject the message")
                raise RejectMessage("We legally cannot process this")

            # Any 400 code means we need to reject the message
            # TODO: We should probably distinguish bad AMQP events from bad forwards?
            case _ if (
                status.HTTP_400_BAD_REQUEST
                <= response.status_code
                < status.HTTP_500_INTERNAL_SERVER_ERROR
            ):
                # NOTE: All of these should probably be deadlettered in the future
                logger.info("Integration could not handle the request")
                raise RequeueMessage("We send a bad request")

            # TODO: Do we want to reject or requeue this?
            case status.HTTP_501_NOT_IMPLEMENTED:
                logger.info(
                    "Integration notified us that the endpoint is not implemented"
                )
                raise RequeueMessage("Not implemented")

            # Any other 500 code means we need to retry
            case _ if response.status_code >= status.HTTP_500_INTERNAL_SERVER_ERROR:
                logger.info("Integration could not handle the request")
                raise RequeueMessage("The server done goofed")

            # We intentionally do not handle 100 and 300 codes
            # If we got a 300 code it is probably a misconfiguration
            # NOTE: All of these should probably be deadlettered in the future
            case _:
                logger.info(
                    "Integration send an unknown status-code",
                    status_code=response.status_code,
                )
                raise RequeueMessage(f"Unexpected status-code: {response.status_code}")
