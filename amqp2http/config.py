# SPDX-FileCopyrightText: 2019-2020 Magenta ApS
# SPDX-License-Identifier: MPL-2.0
"""AMQP2HTTP bridge."""

from fastramqpi.config import Settings as FastRAMQPISettings
from pydantic import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """AMQP2HTTP configuration settings."""

    class Config:
        """Settings configuration."""

        frozen = True
        env_nested_delimiter = "__"

    fastramqpi: FastRAMQPISettings = Field(
        default_factory=FastRAMQPISettings, description="FastRAMQPI settings"
    )
