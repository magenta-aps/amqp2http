# SPDX-FileCopyrightText: 2019-2020 Magenta ApS
# SPDX-License-Identifier: MPL-2.0
"""Common test fixtures."""

import os
from collections.abc import AsyncIterator
from typing import Any
from typing import Mapping
from typing import cast
from unittest import mock

import pytest
from asgi_lifespan import LifespanManager
from asgi_lifespan._types import ASGIApp
from fastapi import FastAPI
from gql.client import AsyncClientSession
from httpx import ASGITransport
from httpx import AsyncClient
from more_itertools import one
from pytest import MonkeyPatch

from amqp2http.main import create_app


def pytest_configure(config: pytest.Config) -> None:
    """Add our conftest required pytest configuration."""
    config.addinivalue_line(
        "markers", "envvar(mapping): set the specified environmental variables"
    )


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Automatically use fixtures for tests marked without integration_test."""
    for item in items:
        if not item.get_closest_marker("integration_test"):
            # MUST prepend to replicate auto-use fixtures coming first
            item.fixturenames[:0] = [  # type: ignore[attr-defined]
                "empty_environment",
            ]


@pytest.fixture
async def empty_environment() -> AsyncIterator[None]:
    """Clear all environmental variables before running unit-test."""
    with mock.patch.dict(os.environ, clear=True):
        yield


@pytest.fixture(autouse=True)
async def load_marked_envvars(
    monkeypatch: pytest.MonkeyPatch,
    request: Any,
) -> AsyncIterator[None]:
    """Fixture to inject environmental variable via pytest.marks.

    Example:
        ```
        @pytest.mark.envvar({"VAR1": "1", "VAR2": 2})
        @pytest.mark.envvar({"VAR3": "3"})
        def test_load_marked_envvars() -> None:
            assert os.environ.get("VAR1") == "1"
            assert os.environ.get("VAR2") == "2"
            assert os.environ.get("VAR3") == "3"
            assert os.environ.get("VAR4") is None
        ```

    Args:
        monkeypatch: The patcher to use for settings the environmental variables.
        request: The pytest request object used to extract markers.

    Yields:
        None, but keeps the settings overrides active.
    """
    envvars: dict[str, str] = {}
    for mark in request.node.iter_markers("envvar"):
        if not mark.args:
            pytest.fail("envvar mark must take an argument")
        if len(mark.args) > 1:
            pytest.fail("envvar mark must take at most one argument")
        argument = one(mark.args)
        if not isinstance(argument, Mapping):
            pytest.fail("envvar mark argument must be a mapping")
        if any(not isinstance(key, str) for key in argument):
            pytest.fail("envvar mapping keys must be strings")
        if any(not isinstance(value, str) for value in argument.values()):
            pytest.fail("envvar mapping values must be strings")
        envvars.update(**argument)
    for key, value in envvars.items():
        monkeypatch.setenv(key, value)
    yield


@pytest.fixture
async def minimal_settings(monkeypatch: MonkeyPatch) -> None:
    """The minimal environmental variables required to construct our settings."""
    minimal_settings = {
        "FASTRAMQPI__AMQP__URL": "amqp://guest:guest@msg-broker",
        "FASTRAMQPI__CLIENT_ID": "amqp2http",
        "FASTRAMQPI__CLIENT_SECRET": "00000000-00000000-00000000-00000000",
        "EVENT_MAPPING": '{"integrations": {}}',
    }
    for key, value in minimal_settings.items():
        if os.environ.get(key) is None:
            monkeypatch.setenv(key, value)


@pytest.fixture
async def _app(minimal_settings: None) -> FastAPI:
    app = create_app()
    return app


@pytest.fixture
async def asgiapp(_app: FastAPI) -> AsyncIterator[ASGIApp]:
    """ASGI app with lifespan run."""
    async with LifespanManager(_app) as manager:
        yield manager.app


@pytest.fixture
async def app(_app: FastAPI, asgiapp: ASGIApp) -> FastAPI:
    """FastAPI app with lifespan run."""
    return _app


@pytest.fixture
async def test_client(asgiapp: ASGIApp) -> AsyncIterator[AsyncClient]:
    """Create test client with associated lifecycles."""
    transport = ASGITransport(app=asgiapp, client=("1.2.3.4", 123))  # type: ignore
    async with AsyncClient(
        transport=transport, base_url="http://example.com"
    ) as client:
        yield client


@pytest.fixture
async def graphql_client(app: FastAPI) -> AsyncClientSession:
    """Authenticated GraphQL codegen client for OS2mo."""
    return cast(AsyncClientSession, app.state.context["graphql_client"])
