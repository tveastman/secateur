import pytest
from unittest import mock
import django.test.client
from django.test import override_settings, TestCase
from secateur import models
from waffle.testutils import override_flag


def test_home(client: django.test.client.Client) -> None:
    with mock.patch("request.models.Request.from_http_request") as m:
        r = client.get("/")
    assert r.status_code == 200


def test_admin(client: django.test.client.Client) -> None:
    with mock.patch("request.models.Request.from_http_request"):
        r = client.get("/admin/")
    assert r.status_code == 302
    assert r.headers["Location"] == "/admin/login/?next=/admin/"


class TestBlock(TestCase):
    def test_block(self) -> None:
        r = self.client.get("/block/")
        self.assertRedirects(r, "/login/twitter/?next=/block/", fetch_redirect_response=False)


    @override_settings(CACHES={'default': {'BACKEND': 'django.core.cache.backends.dummy.DummyCache'}})
    def test_block_with_user(self) -> None:
        u = _test_user()
        self.client.force_login(u)
        r = self.client.get("/block/")
        assert r.status_code == 200


class TestBlocked(TestCase):
    @override_settings(CACHES={'default': {'BACKEND': 'django.core.cache.backends.dummy.DummyCache'}})
    def test_blocked(self) -> None:
        with override_flag("blocked", active=True):
            r = self.client.get("/blocked/")
            self.assertRedirects(r, "/login/twitter/?next=/blocked/", fetch_redirect_response=False)


class TestUnblockEverybody(TestCase):
    @override_settings(CACHES={'default': {'BACKEND': 'django.core.cache.backends.dummy.DummyCache'}})
    def test_unblock_everybody(self) -> None:
        with override_flag("blocked", active=True):
            r = self.client.get("/unblock-everybody/")
            self.assertRedirects(r, "/login/twitter/?next=/unblock-everybody/", fetch_redirect_response=False)


def test_search(client: django.test.client.Client) -> None:
    _check_redirect_when_not_logged_in(client, "search")


def test_log_messages(client: django.test.client.Client) -> None:
    _check_redirect_when_not_logged_in(client, "log-messages")


def test_block_messages(client: django.test.client.Client) -> None:
    _check_redirect_when_not_logged_in(client, "block-messages")


class TestLogout(TestCase):
    def test_logout(self) -> None:
        r = self.client.get("/logout/")
        self.assertRedirects(r, "/", fetch_redirect_response=False)


def test_disconnect(client: django.test.client.Client) -> None:
    _check_redirect_when_not_logged_in(client, "disconnect")


def test_disconnected(client: django.test.client.Client) -> None:
    with mock.patch("request.models.Request.from_http_request"):
        r = client.get("/disconnected/")
    assert r.status_code == 200


def test_following(client: django.test.client.Client) -> None:
    _check_redirect_when_not_logged_in(client, "following")


def test_update_following(client: django.test.client.Client) -> None:
    _check_redirect_when_not_logged_in(client, "update-following")


def test_imports() -> None:
    import secateur.wsgi
    import secateur.apps


def _test_user() -> models.User():
    account = models.Account(user_id=1)
    account.save()
    user = models.User(account=account)
    user.save()
    return user


def _check_redirect_when_not_logged_in(
    client: django.test.client.Client, path: str
) -> None:
    with mock.patch("request.models.Request.from_http_request"):
        r = client.get(f"/{path}/")
    assert r.status_code == 302
    assert r.headers["Location"] == f"/login/twitter/?next=/{path}/"
