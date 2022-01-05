FROM python:3.9 as virtualenv

RUN pip install poetry
RUN python -m venv /venv
ENV POETRY_VIRTUALENVS_CREATE=0 \
    VIRTUAL_ENV=/venv           \
    PATH="/venv/bin:$PATH"

COPY poetry.lock pyproject.toml /
RUN poetry install --no-dev --no-root

RUN useradd app
COPY --chown=app . /app
WORKDIR /app
RUN python -m compileall . && poetry install --no-dev && python manage.py collectstatic --noinput --no-color

USER app
