import pytest


def test_home(client):
    r = client.get("/")
    assert r.status_code == 200


def test_block(client, admin_user):
    client.login(username="admin", password="password")
    r = client.get("/block-accounts/")
    assert r.status_code == 200
