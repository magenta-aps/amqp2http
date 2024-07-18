# SPDX-FileCopyrightText: 2019-2020 Magenta ApS
# SPDX-License-Identifier: MPL-2.0
"""Common test fixtures."""

import os
from collections.abc import AsyncIterator
from typing import cast
from unittest import mock

import pytest
from asgi_lifespan import LifespanManager
from asgi_lifespan._types import ASGIApp
from fastapi import FastAPI
from gql.client import AsyncClientSession
from httpx import ASGITransport
from httpx import AsyncClient
from pytest import MonkeyPatch

from amqp2http.main import create_app


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


@pytest.fixture
async def minimal_settings(monkeypatch: MonkeyPatch) -> None:
    """The minimal environmental variables required to construct our settings."""
    minimal_settings = {
        "FASTRAMQPI__AMQP__URL": "amqp://guest:guest@msg-broker",
        "FASTRAMQPI__CLIENT_ID": "amqp2http",
        "FASTRAMQPI__CLIENT_SECRET": "00000000-00000000-00000000-00000000",
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
