# SPDX-FileCopyrightText: 2019-2020 Magenta ApS
# SPDX-License-Identifier: MPL-2.0
"""AMQP2HTTP bridge."""

from functools import partial
from hashlib import sha256
from typing import Any
from typing import cast

import structlog
from fastapi import FastAPI
from fastramqpi.context import Context
from fastramqpi.main import FastRAMQPI
from fastramqpi.ramqp import Router
from fastramqpi.ramqp.amqp import AMQPSystem
from fastramqpi.ramqp.config import AMQPConnectionSettings
from fastramqpi.ramqp.config import StructuredAmqpDsn
from pydantic import AmqpDsn

from amqp2http.dispatch import dispatch_amqp_message

from .config import EventEndpoint
from .config import Settings

logger = structlog.stdlib.get_logger()


async def healthcheck_amqp(amqpsystem: AMQPSystem, context: Context) -> bool:
    """AMQP Healthcheck wrapper.

    Args:
        amqpsystem: The AMQPSystem to check health for.
        context: Unused context dict.

    Returns:
        Whether the AMQPSystem is OK.
    """
    return cast(bool, amqpsystem.healthcheck())


def create_amqpsystem(
    context: Context,
    amqp_url: AmqpDsn | StructuredAmqpDsn,
    integration: str,
    upstream_exchange: str,
    events: list[EventEndpoint],
) -> AMQPSystem:
    """Construct a listener for a given integration and upstream_exchange.

    Args:
        context: The FastRAMQPI context to provide the AMQPSystem.
        amqp_url: URL for the AMQP Broker to connect to.
        integration: The name of the integration we are constructing for.
        upstream_exchange: The name of the upstream exchange we are attaching to.
        events: The list of events to enable listeners to.

    Returns:
        The constructed AMQPSystem.
    """
    # Each AMQPSystem needs a unique name for ramqp to work
    mapping_prefix = f"{integration}_{upstream_exchange}"

    amqp_router = Router()
    for event in events:
        # Each handler needs a unique name for ramqp to work
        url_hash = sha256(event.url.encode("utf-8")).hexdigest()[:8]
        handler_name = f"{mapping_prefix}_{event.routing_key}_{url_hash}"

        callable = partial(dispatch_amqp_message, event)
        callable.__name__ = handler_name  # type: ignore

        amqp_router.register(event.routing_key)(callable)

    amqp_settings = AMQPConnectionSettings(
        url=amqp_url,
        exchange=mapping_prefix,
        upstream_exchange=upstream_exchange,
        queue_prefix=mapping_prefix,
    )
    return AMQPSystem(settings=amqp_settings, router=amqp_router, context=context)


def create_listeners(fastramqpi: FastRAMQPI, settings: Settings) -> None:
    """Construct our AMQPSystem listeners according to the EventMapping.

    Args:
        fastramqpi: The FastRAMQPI instance to construct the listeners on.
        settings: Settings to configure listeners with.
    """
    amqpsystems: dict[str, dict[str, AMQPSystem]] = {}
    for integration, iconf in settings.event_mapping.integrations.items():
        for upstream_exchange, econf in iconf.exchanges.items():
            amqpsystem = create_amqpsystem(
                fastramqpi.get_context(),
                settings.fastramqpi.amqp.url,
                integration,
                upstream_exchange,
                econf.queues,
            )

            fastramqpi.add_lifespan_manager(amqpsystem, priority=1100)
            healthcheck_name = f"AMQP_{integration}_{upstream_exchange}"
            fastramqpi.add_healthcheck(
                name=healthcheck_name, healthcheck=partial(healthcheck_amqp, amqpsystem)
            )

            amqpsystems[integration] = amqpsystems.get(integration, {})
            amqpsystems[integration][upstream_exchange] = amqpsystem

    fastramqpi.add_context(amqpsystems=amqpsystems)


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

    create_listeners(fastramqpi, settings)

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
