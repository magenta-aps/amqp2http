# SPDX-FileCopyrightText: 2019-2020 Magenta ApS
# SPDX-License-Identifier: MPL-2.0
"""AMQP2HTTP bridge."""

from fastramqpi.config import Settings as FastRAMQPISettings
from pydantic import AnyUrl
from pydantic import BaseModel
from pydantic import BaseSettings
from pydantic import Field


class EventEndpoint(BaseModel):
    """An endpoint to send event http calls to."""

    routing_key: str
    url: AnyUrl = Field(..., description="URL to send events to")


class ExchangeMapping(BaseModel):
    """A list of queues / event listeners to create."""

    queues: list[EventEndpoint]


class IntegrationMapping(BaseModel):
    """An collection of event endpoints for upstream exchanges."""

    exchanges: dict[str, ExchangeMapping]


class EventMapping(BaseModel):
    """A grouping from integration names to integration mappings."""

    integrations: dict[str, IntegrationMapping]


class Settings(BaseSettings):
    """AMQP2HTTP configuration settings."""

    class Config:
        """Settings configuration."""

        frozen = True
        env_nested_delimiter = "__"

    fastramqpi: FastRAMQPISettings = Field(
        default_factory=FastRAMQPISettings, description="FastRAMQPI settings"
    )

    event_mapping: EventMapping = Field(..., description="Event mapping")
