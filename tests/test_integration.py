# SPDX-FileCopyrightText: 2019-2020 Magenta ApS
# SPDX-License-Identifier: MPL-2.0
"""Integration-test the integration."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import httpx
from fastapi import FastAPI
from more_itertools import one
from uvicorn import Config
from uvicorn import Server
from amqp2http.main import create_app


import pytest


def create_integration_app() -> FastAPI:
    app = FastAPI()

    @app.get("/")
    async def root() -> dict[str, str]:
        return {"message": "Hello, World!"}

    return app


@asynccontextmanager
async def run_server(**kwargs: Any) -> AsyncIterator[Server]:
    assert "port" not in kwargs
    assert "host" not in kwargs
    kwargs["log_level"] = kwargs.get("log_level", "warning")
    # Dynamically allocating a free port using port=0
    config = Config(**kwargs, host="127.0.0.1", port=0)
    server = Server(config=config)
    task = asyncio.create_task(server.serve())
    while server.started is False:
        await asyncio.sleep(0.1)
    try:
        yield server
    finally:
        await server.shutdown()
        task.cancel()


def server2url(server: Server) -> str:
    socket = one(one(server.servers).sockets)
    ip, port = socket.getsockname()
    return f"http://{ip}:{port}"


async def test_start_server() -> None:
    app = create_integration_app()
    async with run_server(app=app) as server:
        url = server2url(server)

        async with httpx.AsyncClient() as client:
            result = await client.get(url)
            assert result.status_code == 200
            assert result.json() == {"message": "Hello, World!"}


@pytest.mark.integration_test
async def test_integration() -> None:
    integration = create_integration_app()
    amqp2http = create_app()

    async with run_server(app=integration) as integration_server:
        integration_url = server2url(integration_server)

        async with run_server(app=amqp2http) as amqp2http_server:
            amqp2http_url = server2url(amqp2http_server)

            async with httpx.AsyncClient() as client:
                result = await client.get(f"{amqp2http_url}")
                assert result.status_code == 200
                assert result.json() == {"message": "Hello, World!"}
