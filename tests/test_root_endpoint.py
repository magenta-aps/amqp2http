# SPDX-FileCopyrightText: 2019-2020 Magenta ApS
# SPDX-License-Identifier: MPL-2.0
"""Test the default endpoint."""

import pytest
from fastapi import status
from httpx import AsyncClient


@pytest.mark.integration_test
async def test_root(test_client: AsyncClient) -> None:
    """Ensure the root endpoint returns out integration name."""
    result = await test_client.get("/")
    assert result.status_code == status.HTTP_200_OK
    assert result.json() == {"name": "amqp2http"}


@pytest.mark.parametrize("url", ("/health/live", "/health/ready"))
@pytest.mark.integration_test
async def test_health(test_client: AsyncClient, url: str) -> None:
    """Ensure the health endpoint checks the expected services."""
    result = await test_client.get(url)
    assert result.status_code == status.HTTP_200_OK
    assert result.json() == {"AMQP": True}
