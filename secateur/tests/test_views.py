import pytest
from unittest import mock


def test_home(client):
    with mock.patch("request.models.Request.from_http_request") as m:
        r = client.get("/")
    assert r.status_code == 200


def test_get_block(client, admin_user):
    client.login(username="admin", password="password")
    r = client.get("/block/")
    assert r.status_code == 200


def test_imports():
    import secateur.wsgi
    import secateur.apps
