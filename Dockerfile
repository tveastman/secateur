FROM python:3.8

RUN useradd app
# install pipenv and use pipenv to build the environment
RUN set -ex && pip install --upgrade pipenv==2018.11.26
COPY Pipfile Pipfile
COPY Pipfile.lock Pipfile.lock
RUN pipenv install --dev --deploy --system --ignore-pipfile
COPY --chown=app . /app
WORKDIR /app
USER app
RUN python -m compileall . && python manage.py collectstatic --noinput --no-color
