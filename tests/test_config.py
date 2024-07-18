# SPDX-FileCopyrightText: 2019-2020 Magenta ApS
# SPDX-License-Identifier: MPL-2.0
"""Test the settings module."""

import pytest
from pydantic import ValidationError
from pytest import MonkeyPatch

from amqp2http.main import Settings


def field_required(fieldname: str) -> str:
    """Convert field name to pydantic field required error message.

    Args:
        fieldname: The field name to emit the error message for.

    Returns:
        The pydantic error message.
    """
    return f"{fieldname}\n  field required (type=value_error.missing)"


def fields_required(fieldnames: list[str]) -> list[str]:
    """Convert a list of field names to a list of pydantic error messages.

    Args:
        fieldnames: The list of field names to convert.

    Returns:
        The list of corresponding error messages.
    """
    return [field_required(fieldname) for fieldname in fieldnames]


@pytest.mark.parametrize(
    "envvars,errors",
    [
        ({}, fields_required(["client_id", "client_secret", "amqp"])),
        # We can give CLIENT_ID directly, although this may change in the future
        ({"CLIENT_ID": "test"}, fields_required(["client_secret", "amqp"])),
        # We should give CLIENT_ID with a prefix
        ({"FASTRAMQPI__CLIENT_ID": "test"}, fields_required(["client_secret", "amqp"])),
    ],
)
async def test_settings_invalid(
    monkeypatch: MonkeyPatch, envvars: dict[str, str], errors: list[str]
) -> None:
    """Test that not providing the minimally required settings yields errors."""
    for key, value in envvars.items():
        monkeypatch.setenv(key, value)

    with pytest.raises(ValidationError) as exc_info:
        Settings()

    for error in errors:
        assert error in str(exc_info.value)


@pytest.mark.usefixtures("minimal_settings")
async def test_minimal_settings() -> None:
    """Test that we can construct settings using our minimal settings."""
    Settings()
