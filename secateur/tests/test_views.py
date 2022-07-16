from django.test import override_settings, TestCase
from secateur import models
from waffle.testutils import override_flag


class TestHome(TestCase):
    def test_home(self) -> None:
        r = self.client.get("/")
        assert r.status_code == 200
        self.assertTemplateUsed(r, 'home.html')
        self.assertTemplateUsed(r, 'base.html')
        self.assertTemplateUsed(r, 'bootstrap.html')

    @override_settings(
        CACHES={"default": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"}}
    )
    def test_home_with_user(self) -> None:
        u = _test_user()
        self.client.force_login(u)
        r = self.client.get("/")
        assert r.status_code == 200
        self.assertTemplateUsed(r, 'home.html')
        self.assertTemplateUsed(r, 'base.html')
        self.assertTemplateUsed(r, 'bootstrap.html')


class TestAdmin(TestCase):
    def test_admin(self) -> None:
        r = self.client.get("/admin/")
        self.assertRedirects(
            r, "/admin/login/?next=/admin/", fetch_redirect_response=False
        )
        self.assertTemplateNotUsed(r, 'admin/index.html')
        self.assertTemplateNotUsed(r, 'admin/base_site.html')
        self.assertTemplateNotUsed(r, 'admin/base.html')

    @override_settings(
        CACHES={"default": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"}}
    )
    def test_admin_with_user(self) -> None:
        r = self.client.get("/admin/")
        self.assertRedirects(
            r, "/admin/login/?next=/admin/", fetch_redirect_response=False
        )
        self.assertTemplateNotUsed(r, 'admin/index.html')
        self.assertTemplateNotUsed(r, 'admin/base_site.html')
        self.assertTemplateNotUsed(r, 'admin/base.html')

    @override_settings(
        CACHES={"default": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"}}
    )
    def test_admin_with_admin_user(self) -> None:
        u = _test_user()
        u.is_staff = True
        u.save()
        self.client.force_login(u)
        r = self.client.get("/admin/")
        assert r.status_code == 200
        self.assertTemplateUsed(r, 'admin/index.html')
        self.assertTemplateUsed(r, 'admin/base_site.html')
        self.assertTemplateUsed(r, 'admin/base.html')


class TestBlock(TestCase):
    def test_block(self) -> None:
        r = self.client.get("/block/")
        self.assertRedirects(
            r, "/login/twitter/?next=/block/", fetch_redirect_response=False
        )
        self.assertTemplateNotUsed(r, 'block.html')
        self.assertTemplateNotUsed(r, 'base.html')
        self.assertTemplateNotUsed(r, 'bootstrap.html')

    @override_settings(
        CACHES={"default": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"}}
    )
    def test_block_with_user(self) -> None:
        u = _test_user()
        self.client.force_login(u)
        r = self.client.get("/block/")
        assert r.status_code == 200
        self.assertTemplateUsed(r, 'block.html')
        self.assertTemplateUsed(r, 'base.html')
        self.assertTemplateUsed(r, 'bootstrap.html')


@override_settings(
    CACHES={"default": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"}}
)
class TestBlocked(TestCase):
    def test_blocked(self) -> None:
        r = self.client.get("/blocked/")
        self.assertRedirects(
            r, "/login/twitter/?next=/blocked/", fetch_redirect_response=False
        )
        self.assertTemplateNotUsed(r, 'blocked.html')
        self.assertTemplateNotUsed(r, 'base.html')
        self.assertTemplateNotUsed(r, 'bootstrap.html')

    def test_blocked_with_user(self) -> None:
        u = _test_user()
        self.client.force_login(u)
        r = self.client.get("/blocked/")
        assert r.status_code == 200
        self.assertTemplateUsed(r, 'blocked.html')
        self.assertTemplateUsed(r, 'base.html')
        self.assertTemplateUsed(r, 'bootstrap.html')


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
        self.assertTemplateNotUsed(r, 'unblock-everybody.html')
        self.assertTemplateNotUsed(r, 'base.html')
        self.assertTemplateNotUsed(r, 'bootstrap.html')

    def test_unblock_everybody_with_user(self) -> None:
        u = _test_user()
        self.client.force_login(u)
        r = self.client.get("/unblock-everybody/")
        assert r.status_code == 200
        self.assertTemplateUsed(r, 'unblock-everybody.html')
        self.assertTemplateUsed(r, 'base.html')
        self.assertTemplateUsed(r, 'bootstrap.html')


class TestSearch(TestCase):
    def test_search(self) -> None:
        r = self.client.get("/search/")
        self.assertRedirects(
            r, "/login/twitter/?next=/search/", fetch_redirect_response=False
        )
        self.assertTemplateNotUsed(r, 'search.html')
        self.assertTemplateNotUsed(r, 'base.html')
        self.assertTemplateNotUsed(r, 'bootstrap.html')

    @override_settings(
        CACHES={"default": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"}}
    )
    def test_search_with_user(self) -> None:
        u = _test_user()
        self.client.force_login(u)
        r = self.client.get("/search/")
        assert r.status_code == 200
        self.assertTemplateUsed(r, 'search.html')
        self.assertTemplateUsed(r, 'base.html')
        self.assertTemplateUsed(r, 'bootstrap.html')


class TestLogMessages(TestCase):
    def test_log_messages(self) -> None:
        r = self.client.get("/log-messages/")
        self.assertRedirects(
            r, "/login/twitter/?next=/log-messages/", fetch_redirect_response=False
        )
        self.assertTemplateNotUsed(r, 'log-messages.html')
        self.assertTemplateNotUsed(r, 'base.html')
        self.assertTemplateNotUsed(r, 'bootstrap.html')

    @override_settings(
        CACHES={"default": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"}}
    )
    def test_log_messages_with_user(self) -> None:
        u = _test_user()
        self.client.force_login(u)
        r = self.client.get("/log-messages/")
        assert r.status_code == 200
        self.assertTemplateUsed(r, 'log-messages.html')
        self.assertTemplateUsed(r, 'base.html')
        self.assertTemplateUsed(r, 'bootstrap.html')


class TestBlockMessages(TestCase):
    def test_block_messages(self) -> None:
        r = self.client.get("/block-messages/")
        self.assertRedirects(
            r, "/login/twitter/?next=/block-messages/", fetch_redirect_response=False
        )
        self.assertTemplateNotUsed(r, 'block-messages.html')
        self.assertTemplateNotUsed(r, 'base.html')
        self.assertTemplateNotUsed(r, 'bootstrap.html')

    @override_settings(
        CACHES={"default": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"}}
    )
    def test_block_messages_with_user(self) -> None:
        u = _test_user()
        self.client.force_login(u)
        r = self.client.get("/block-messages/")
        assert r.status_code == 200
        self.assertTemplateUsed(r, 'block-messages.html')
        self.assertTemplateUsed(r, 'base.html')
        self.assertTemplateUsed(r, 'bootstrap.html')


class TestLogout(TestCase):
    def test_logout(self) -> None:
        r = self.client.get("/logout/")
        self.assertRedirects(r, "/", fetch_redirect_response=False)
        self.assertTemplateNotUsed(r, 'logout.html')
        self.assertTemplateNotUsed(r, 'base.html')
        self.assertTemplateNotUsed(r, 'bootstrap.html')

    def test_logout_with_user(self) -> None:
        u = _test_user()
        self.client.force_login(u)
        r = self.client.get("/logout/")
        self.assertRedirects(r, "/", fetch_redirect_response=False)
        self.assertTemplateNotUsed(r, 'logout.html')
        self.assertTemplateNotUsed(r, 'base.html')
        self.assertTemplateNotUsed(r, 'bootstrap.html')


class TestDisconnect(TestCase):
    def test_disconnect(self) -> None:
        r = self.client.get("/disconnect/")
        self.assertRedirects(
            r, "/login/twitter/?next=/disconnect/", fetch_redirect_response=False
        )
        self.assertTemplateNotUsed(r, 'disconnect.html')
        self.assertTemplateNotUsed(r, 'base.html')
        self.assertTemplateNotUsed(r, 'bootstrap.html')

    @override_settings(
        CACHES={"default": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"}}
    )
    def test_disconnect_with_user(self) -> None:
        u = _test_user()
        self.client.force_login(u)
        r = self.client.get("/disconnect/")
        assert r.status_code == 200
        self.assertTemplateUsed(r, 'disconnect.html')
        self.assertTemplateUsed(r, 'base.html')
        self.assertTemplateUsed(r, 'bootstrap.html')


class TestDisconnected(TestCase):
    def test_disconnected(self) -> None:
        r = self.client.get("/disconnected/")
        assert r.status_code == 200
        self.assertTemplateUsed(r, 'disconnected.html')
        self.assertTemplateUsed(r, 'base.html')
        self.assertTemplateUsed(r, 'bootstrap.html')

    @override_settings(
        CACHES={"default": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"}}
    )
    def test_disconnected_with_user(self) -> None:
        u = _test_user()
        self.client.force_login(u)
        r = self.client.get("/disconnected/")
        assert r.status_code == 200
        self.assertTemplateUsed(r, 'disconnected.html')
        self.assertTemplateUsed(r, 'base.html')
        self.assertTemplateUsed(r, 'bootstrap.html')


class TestFollowing(TestCase):
    def test_following(self) -> None:
        r = self.client.get("/following/")
        self.assertRedirects(
            r, "/login/twitter/?next=/following/", fetch_redirect_response=False
        )
        self.assertTemplateNotUsed(r, 'following.html')
        self.assertTemplateNotUsed(r, 'base.html')
        self.assertTemplateNotUsed(r, 'bootstrap.html')

    @override_settings(
        CACHES={"default": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"}}
    )
    def test_following_with_user(self) -> None:
        u = _test_user()
        self.client.force_login(u)
        r = self.client.get("/following/")
        assert r.status_code == 200
        self.assertTemplateUsed(r, 'following.html')
        self.assertTemplateUsed(r, 'base.html')
        self.assertTemplateUsed(r, 'bootstrap.html')


class TestUpdateFollowing(TestCase):
    def test_update_following(self) -> None:
        r = self.client.get("/update-following/")
        self.assertRedirects(
            r, "/login/twitter/?next=/update-following/", fetch_redirect_response=False
        )
        self.assertTemplateNotUsed(r, 'update-following.html')
        self.assertTemplateNotUsed(r, 'base.html')
        self.assertTemplateNotUsed(r, 'bootstrap.html')

    @override_settings(
        CACHES={"default": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"}}
    )
    def test_update_following_with_user(self) -> None:
        u = _test_user()
        self.client.force_login(u)
        r = self.client.get("/update-following/")
        assert r.status_code == 200
        self.assertTemplateUsed(r, 'update-following.html')
        self.assertTemplateUsed(r, 'base.html')
        self.assertTemplateUsed(r, 'bootstrap.html')


def test_imports() -> None:
    import secateur.wsgi
    import secateur.apps


def _test_user() -> models.User():
    account = models.Account(user_id=1)
    account.save()
    user = models.User(account=account)
    user.save()
    return user
