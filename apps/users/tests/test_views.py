import pytest
from django.contrib.auth.models import User
from django.core.cache import cache
from django.urls import reverse


@pytest.fixture(autouse=True)
def clear_login_rate_limit_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def user(db):
    return User.objects.create_user(username="testuser", password="testpass123")


@pytest.fixture(autouse=True)
def configure_login_rate_limit(settings):
    settings.LOGIN_RATE_LIMIT_ATTEMPTS = 2
    settings.LOGIN_RATE_LIMIT_WINDOW_SECONDS = 60
    settings.CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "users-login-tests",
        }
    }


@pytest.mark.django_db
class TestRateLimitedLoginView:
    def test_lockout_after_repeated_failed_attempts(self, client, user):
        url = reverse("login")
        payload = {"username": user.username, "password": "bad-password"}

        first_response = client.post(url, payload)
        second_response = client.post(url, payload)
        locked_response = client.post(url, payload)

        assert first_response.status_code == 200
        assert second_response.status_code == 200
        assert locked_response.status_code == 429
        assert b"Too many login attempts" in locked_response.content

    def test_successful_login_clears_previous_failures(self, client, user):
        url = reverse("login")
        request_kwargs = {"REMOTE_ADDR": "10.0.0.2"}

        failed_response = client.post(
            url,
            {"username": user.username, "password": "bad-password"},
            **request_kwargs,
        )
        successful_response = client.post(
            url,
            {"username": user.username, "password": "testpass123"},
            **request_kwargs,
        )
        next_failed_response = client.post(
            url,
            {"username": user.username, "password": "bad-password"},
            **request_kwargs,
        )

        assert failed_response.status_code == 200
        assert successful_response.status_code == 302
        assert next_failed_response.status_code == 200
