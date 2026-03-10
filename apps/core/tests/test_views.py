import pytest
from django.urls import reverse


@pytest.mark.django_db
class TestHealthCheck:
    def test_health_check_returns_200(self, client):
        url = reverse('health_check')
        response = client.get(url)
        assert response.status_code == 200

    def test_health_check_returns_json(self, client):
        url = reverse('health_check')
        response = client.get(url)
        data = response.json()
        assert data['status'] == 'ok'
        assert data['db'] == 'ok'