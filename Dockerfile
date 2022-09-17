FROM python:3.10

# install poetry
ENV POETRY_HOME=/opt/poetry \
    POETRY_VERSION=1.2.0 \
    POETRY_VIRTUALENVS_CREATE=0
RUN --mount=type=cache,target=/root/.cache \
    pip install pip==22.2.2 && \
    curl -sSL https://install.python-poetry.org | python3 -

# build venv
RUN python -m venv /venv
ENV VIRTUAL_ENV=/venv           \
    PATH="/venv/bin:$PATH"
COPY poetry.lock pyproject.toml /
RUN --mount=type=cache,target=/root/.cache \
    /opt/poetry/bin/poetry install --no-root

# install secateur
RUN useradd app
COPY --chown=app . /app
WORKDIR /app
RUN python -m compileall -q . && python manage.py collectstatic --noinput --no-color
USER app
