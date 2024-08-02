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

app = FastAPI()


@app.get("/")
async def root() -> dict[str, str]:
    return {"message": "Hello, World!"}


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
    async with run_server(app=app) as server:
        url = server2url(server)

        async with httpx.AsyncClient() as client:
            result = await client.get(url)
            assert result.status_code == 200
            assert result.json() == {"message": "Hello, World!"}
