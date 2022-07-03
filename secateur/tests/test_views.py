from django.test import override_settings, TestCase
from secateur import models
from waffle.testutils import override_flag


class TestHome(TestCase):
    def test_home(self) -> None:
        r = self.client.get("/")
        assert r.status_code == 200


class TestAdmin(TestCase):
    def test_admin(self) -> None:
        r = self.client.get("/admin/")
        self.assertRedirects(
            r, "/admin/login/?next=/admin/", fetch_redirect_response=False
        )


class TestBlock(TestCase):
    def test_block(self) -> None:
        r = self.client.get("/block/")
        self.assertRedirects(
            r, "/login/twitter/?next=/block/", fetch_redirect_response=False
        )

    @override_settings(
        CACHES={"default": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"}}
    )
    def test_block_with_user(self) -> None:
        u = _test_user()
        self.client.force_login(u)
        r = self.client.get("/block/")
        assert r.status_code == 200


@override_settings(
    CACHES={"default": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"}}
)
class TestBlocked(TestCase):
    def test_blocked(self) -> None:
        r = self.client.get("/blocked/")
        self.assertRedirects(
            r, "/login/twitter/?next=/blocked/", fetch_redirect_response=False
        )

    def test_blocked_toggled_off(self) -> None:
        with override_flag("blocked", active=False):
            r = self.client.get("/blocked/")
            assert r.status_code == 404


@override_settings(
    CACHES={"default": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"}}
)
class TestUnblockEverybody(TestCase):
    def test_unblock_everybody(self) -> None:
        r = self.client.get("/unblock-everybody/")
        self.assertRedirects(
            r,
            "/login/twitter/?next=/unblock-everybody/",
            fetch_redirect_response=False,
        )

    def test_unblock_everybody_toggled_off(self) -> None:
        with override_flag("bloccked", active=False):
            r = self.client.get("/unblock-everybody/")
            assert r.status_code == 404


class TestSearch(TestCase):
    def test_search(self) -> None:
        r = self.client.get("/search/")
        self.assertRedirects(
            r, "/login/twitter/?next=/search/", fetch_redirect_response=False
        )


class TestLogMessages(TestCase):
    def test_log_messages(self) -> None:
        r = self.client.get("/log-messages/")
        self.assertRedirects(
            r, "/login/twitter/?next=/log-messages/", fetch_redirect_response=False
        )


class TestBlockMessages(TestCase):
    def test_block_messages(self) -> None:
        r = self.client.get("/block-messages/")
        self.assertRedirects(
            r, "/login/twitter/?next=/block-messages/", fetch_redirect_response=False
        )


class TestLogout(TestCase):
    def test_logout(self) -> None:
        r = self.client.get("/logout/")
        self.assertRedirects(r, "/", fetch_redirect_response=False)


class TestDisconnect(TestCase):
    def test_disconnect(self) -> None:
        r = self.client.get("/disconnect/")
        self.assertRedirects(
            r, "/login/twitter/?next=/disconnect/", fetch_redirect_response=False
        )


class TestDisconnected(TestCase):
    def test_disconnected(self) -> None:
        r = self.client.get("/disconnected/")
        assert r.status_code == 200


class TestFollowing(TestCase):
    def test_following(self) -> None:
        r = self.client.get("/following/")
        self.assertRedirects(
            r, "/login/twitter/?next=/following/", fetch_redirect_response=False
        )


class TestUpdateFollowing(TestCase):
    def test_update_following(self) -> None:
        r = self.client.get("/update-following/")
        self.assertRedirects(
            r, "/login/twitter/?next=/update-following/", fetch_redirect_response=False
        )


def test_imports() -> None:
    import secateur.wsgi
    import secateur.apps


def _test_user() -> models.User():
    account = models.Account(user_id=1)
    account.save()
    user = models.User(account=account)
    user.save()
    return user
