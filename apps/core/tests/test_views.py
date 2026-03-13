import pytest
from django.urls import reverse
from unittest.mock import patch


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

    @patch('apps.core.views.connection.ensure_connection', side_effect=Exception('db down'))
    def test_health_check_returns_503_when_database_fails(self, _mock_connection, client):
        url = reverse('health_check')

        response = client.get(url)

        assert response.status_code == 503
        assert response.json() == {'status': 'degraded', 'db': 'error'}
