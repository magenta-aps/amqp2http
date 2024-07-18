# SPDX-FileCopyrightText: 2019-2020 Magenta ApS
# SPDX-License-Identifier: MPL-2.0
"""Test the settings module."""

import pytest
from more_itertools import one
from pydantic import ValidationError
from pytest import MonkeyPatch

from amqp2http.main import Settings

from .fixtures import EXAMPLE_MAPPING_JSON


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


@pytest.mark.envvar({"EVENT_MAPPING": EXAMPLE_MAPPING_JSON})
@pytest.mark.usefixtures("minimal_settings")
async def test_integration_mapping() -> None:
    """Test event mappings parse as expected."""
    settings = Settings()

    assert settings.event_mapping.integrations.keys() == {"ldap"}
    exchanges = settings.event_mapping.integrations["ldap"].exchanges

    assert exchanges.keys() == {"os2mo", "ldap"}
    mo2ldap_queues = exchanges["os2mo"].queues
    person1, person2 = mo2ldap_queues

    ldap2mo_queues = exchanges["ldap"].queues
    uuid = one(ldap2mo_queues)

    assert person1.routing_key == "person"
    assert person1.url == "http://ldap/mo2ldap/person1"

    assert person2.routing_key == "person"
    assert person2.url == "http://ldap/mo2ldap/person2"

    assert uuid.routing_key == "uuid"
    assert uuid.url == "http://ldap/ldap2mo/uuid"
