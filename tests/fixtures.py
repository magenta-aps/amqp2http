# SPDX-FileCopyrightText: 2019-2020 Magenta ApS
# SPDX-License-Identifier: MPL-2.0
"""Various shared fixture values."""

import json

EXAMPLE_MAPPING = {
    "integrations": {
        "ldap": {
            "exchanges": {
                "os2mo": {
                    "queues": [
                        {
                            "routing_key": "person",
                            "url": "http://ldap/mo2ldap/person1",
                        },
                        {
                            "routing_key": "person",
                            "url": "http://ldap/mo2ldap/person2",
                        },
                    ],
                },
                "ldap": {
                    "queues": [
                        {
                            "routing_key": "uuid",
                            "url": "http://ldap/ldap2mo/uuid",
                        }
                    ]
                },
            }
        }
    }
}
EXAMPLE_MAPPING_JSON = json.dumps(EXAMPLE_MAPPING)
