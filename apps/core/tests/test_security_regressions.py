from unittest.mock import patch

import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse
from rest_framework.test import APIClient

from config.settings.security import validate_production_security


@pytest.fixture
def user(db):
    return User.objects.create_user(username="testuser", password="testpass123")


@pytest.fixture
def staff_user(db):
    return User.objects.create_user(
        username="staffuser",
        password="testpass123",
        is_staff=True,
    )


@pytest.fixture
def web_client():
    return Client(raise_request_exception=False)


@pytest.fixture
def auth_web_client(user):
    client = Client(raise_request_exception=False)
    client.force_login(user)
    return client


@pytest.fixture
def staff_web_client(staff_user):
    client = Client(raise_request_exception=False)
    client.force_login(staff_user)
    return client


@pytest.fixture
def api_client(user):
    client = APIClient(raise_request_exception=False)
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def staff_api_client(staff_user):
    client = APIClient(raise_request_exception=False)
    client.force_authenticate(user=staff_user)
    return client


@pytest.mark.django_db
class TestSecurityAccessRegression:
    @pytest.mark.parametrize(
        "url_name",
        [
            "resumen_iol:resumen_list",
            "portafolio_iol:portafolio_list",
            "operaciones_iol:operaciones_list",
            "parametros:parametros_list",
        ],
    )
    def test_sensitive_list_views_require_login(self, web_client, url_name):
        response = web_client.get(reverse(url_name))
        assert response.status_code == 302
        assert "/accounts/login/" in response["Location"]

    @pytest.mark.parametrize(
        "url_name",
        [
            "dashboard:run_sync",
            "dashboard:generate_snapshot",
        ],
    )
    def test_dashboard_sensitive_actions_require_staff(self, auth_web_client, url_name):
        response = auth_web_client.post(reverse(url_name))
        assert response.status_code == 403

    @pytest.mark.parametrize(
        "url_name",
        [
            "metrics-snapshot-integrity",
            "metrics-sync-audit",
            "metrics-internal-observability",
        ],
    )
    def test_internal_api_endpoints_require_staff(self, api_client, url_name):
        response = api_client.get(reverse(url_name))
        assert response.status_code == 403

    def test_staff_can_access_internal_observability(self, staff_api_client):
        response = staff_api_client.get(reverse("metrics-internal-observability"))
        assert response.status_code in [200, 500]


@pytest.mark.django_db
class TestSecurityErrorRegression:
    def test_dashboard_api_errors_are_sanitized(self, api_client):
        with patch("apps.api.views.get_dashboard_kpis", side_effect=Exception("forced secret")):
            response = api_client.get(reverse("dashboard-kpis"))
        assert response.status_code == 500
        assert response.json()["error"] == "Internal server error"

    def test_staff_parameter_update_errors_are_sanitized(self, staff_api_client):
        with patch(
            "apps.core.models.PortfolioParameters.get_active_parameters",
            side_effect=Exception("forced secret"),
        ):
            response = staff_api_client.post(reverse("portfolio-parameters-update"), {}, format="json")
        assert response.status_code == 500
        assert response.json()["error"] == "Internal server error"


def test_production_security_validation_requires_hardened_settings():
    validate_production_security(
        {
            "DEBUG": False,
            "SECRET_KEY": "a9F!kLm2Qx7#uP0rTz5@vBn8$yH1*cDe4&Gh6Jk9LmNoPqRs7Tu8",
            "IOL_USERNAME": "user",
            "IOL_PASSWORD": "pass",
            "ALLOWED_HOSTS": ["example.com"],
            "SECURE_SSL_REDIRECT": True,
            "SESSION_COOKIE_SECURE": True,
            "CSRF_COOKIE_SECURE": True,
            "SESSION_COOKIE_HTTPONLY": True,
            "SECURE_HSTS_SECONDS": 31536000,
            "SECURE_PROXY_SSL_HEADER": ("HTTP_X_FORWARDED_PROTO", "https"),
        }
    )
