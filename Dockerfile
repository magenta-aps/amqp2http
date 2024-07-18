# SPDX-FileCopyrightText: 2019-2020 Magenta ApS
# SPDX-License-Identifier: MPL-2.0
FROM python:3.11

WORKDIR /app

# Poetry install based on:
# https://github.com/python-poetry/poetry/issues/6288#issuecomment-1235974678
ENV PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    POETRY_VERSION="1.8" \
    POETRY_HOME=/opt/poetry \
    VIRTUAL_ENV="/venv"
ENV PATH="$VIRTUAL_ENV/bin:$POETRY_HOME/bin:$PATH"

# Install poetry in an isolated environment
RUN python -m venv $POETRY_HOME \
    && pip install --no-cache-dir poetry==${POETRY_VERSION}

# Install project in another isolated environment
RUN python -m venv $VIRTUAL_ENV
COPY pyproject.toml poetry.lock* ./
RUN poetry install --no-root

# Copy in our project
COPY amqp2http ./amqp2http

# Default command
CMD [ "uvicorn", "--factory", "amqp2http.main:create_app", "--host", "0.0.0.0" ]

# Add build version to the environment last to avoid build cache misses
ARG COMMIT_TAG
ARG COMMIT_SHA
ENV COMMIT_TAG=${COMMIT_TAG:-HEAD} \
    COMMIT_SHA=${COMMIT_SHA}
