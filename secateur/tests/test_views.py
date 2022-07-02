import pytest
from unittest import mock
import django.test.client


def test_home(client: django.test.client.Client) -> None:
    with mock.patch("request.models.Request.from_http_request") as m:
        r = client.get("/")
    assert r.status_code == 200


def test_block(client: django.test.client.Client) -> None:
    with mock.patch("request.models.Request.from_http_request"):
        r = client.get("/block/")
    assert r.status_code == 302
    assert r.headers["Location"] == "/login/twitter/?next=/block/"


def test_imports() -> None:
    import secateur.wsgi
    import secateur.apps
