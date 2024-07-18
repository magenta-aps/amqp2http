<!--
SPDX-FileCopyrightText: Magenta ApS <https://magenta.dk>
SPDX-License-Identifier: MPL-2.0
-->

# AMQP2HTTP

AMQP to HTTP bridge service

## Usage

```
docker-compose up -d
```
Configuration is done through environment variables.

Available options can be seen in [amqp2http/config.py].

Complex variables such as dict or lists can be given as JSON strings, as specified by Pydantic's settings parser.


## Testing

```
docker-compose exec amqp2http poetry run pytest tests/
```
This requires the environment to be up and running using the method described in 'Usage'.


## Versioning

This project uses [Semantic Versioning](https://semver.org/) with the following
strategy:

- MAJOR: Incompatible API changes.
- MINOR: Backwards-compatible updates and functionality.
- PATCH: Backwards-compatible bug fixes.


## Authors

Magenta ApS <https://magenta.dk>


## License

- This project: [MPL-2.0](LICENSES/MPL-2.0.txt)

This project uses [REUSE](https://reuse.software) for licensing. All licenses can be found in the [LICENSES folder](LICENSES/) of the project.
