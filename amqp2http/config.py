# SPDX-FileCopyrightText: 2019-2020 Magenta ApS
# SPDX-License-Identifier: MPL-2.0
"""AMQP2HTTP bridge."""

from typing import Annotated

from fastramqpi.config import Settings as FastRAMQPISettings
from pydantic import AnyHttpUrl
from pydantic import BaseModel
from pydantic import BaseSettings
from pydantic import Field

NonEmptyString = Annotated[str, Field(min_length=1)]


class EventEndpoint(BaseModel):
    """An endpoint to send event http calls to."""

    routing_key: NonEmptyString
    url: AnyHttpUrl = Field(..., description="URL to send events to")


class ExchangeMapping(BaseModel):
    """A list of queues / event listeners to create."""

    queues: list[EventEndpoint]


class IntegrationMapping(BaseModel):
    """An collection of event endpoints for upstream exchanges."""

    exchanges: dict[NonEmptyString, ExchangeMapping]


class EventMapping(BaseModel):
    """A grouping from integration names to integration mappings."""

    integrations: dict[NonEmptyString, IntegrationMapping]


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
