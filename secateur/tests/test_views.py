import pytest
from unittest import mock
import django.test.client
from secateur import models


def test_home(client: django.test.client.Client) -> None:
    with mock.patch("request.models.Request.from_http_request") as m:
        r = client.get("/")
    assert r.status_code == 200


def test_block(client: django.test.client.Client) -> None:
    with mock.patch("request.models.Request.from_http_request"):
        r = client.get("/block/")
    assert r.status_code == 302
    assert r.headers["Location"] == "/login/twitter/?next=/block/"


@pytest.mark.django_db
def test_block_with_user(client: django.test.client.Client) -> None:
    u = _test_user()
    client.force_login(u)
    with mock.patch("request.models.Request.from_http_request"):
        r = client.get("/block/")
    assert r.status_code == 200


def test_log_messages(client: django.test.client.Client) -> None:
    with mock.patch("request.models.Request.from_http_request"):
        r = client.get("/log-messages/")
    assert r.status_code == 302
    assert r.headers["Location"] == "/login/twitter/?next=/log-messages/"


def test_imports() -> None:
    import secateur.wsgi
    import secateur.apps


def _test_user() -> models.User():
    account = models.Account(
        user_id = 1
    )
    account.save()
    user = models.User(
        account=account
    )
    user.save()
    return user

