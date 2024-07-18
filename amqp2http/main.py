# SPDX-FileCopyrightText: 2019-2020 Magenta ApS
# SPDX-License-Identifier: MPL-2.0
"""AMQP2HTTP bridge."""

from typing import Any

import structlog
from fastapi import FastAPI
from fastramqpi.main import FastRAMQPI

from .config import Settings

logger = structlog.stdlib.get_logger()


def create_fastramqpi(**kwargs: Any) -> FastRAMQPI:
    """Integration builder.

    Args:
        kwargs: settings overrides.

    Returns:
        FastRAMQPI integration.
    """
    settings = Settings(**kwargs)

    fastramqpi = FastRAMQPI(
        application_name="amqp2http",
        settings=settings.fastramqpi,
        graphql_version=22,
    )
    fastramqpi.add_context(settings=settings)

    return fastramqpi


def create_app(**kwargs: Any) -> FastAPI:
    """Uvicorn entrypoint.

    Args:
        kwargs: arguments to forward to `create_fastramqpi`.

    Returns:
        FastAPI application.
    """
    fastramqpi = create_fastramqpi(**kwargs)
    return fastramqpi.get_app()
