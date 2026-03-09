import pytest
from unittest.mock import Mock, patch

from apps.core.services.iol_api_client import IOLAPIClient


class TestIOLAPIClient:
    @pytest.fixture
    def client(self):
        return IOLAPIClient()

    @patch('apps.core.services.iol_api_client.requests.post')
    def test_login_success(self, mock_post, client):
        mock_response = Mock()
        mock_response.json.return_value = {
            'access_token': 'test_token',
            'refresh_token': 'refresh_token'
        }
        mock_post.return_value = mock_response

        result = client.login()
        assert result is True
        assert client.access_token == 'test_token'
        assert client.refresh_token == 'refresh_token'

    @patch('apps.core.services.iol_api_client.requests.post')
    def test_login_failure(self, mock_post, client):
        mock_post.side_effect = Exception('API Error')

        result = client.login()
        assert result is False

    @patch('apps.core.services.iol_api_client.requests.get')
    def test_get_estado_cuenta(self, mock_get, client):
        client.access_token = 'test_token'
        mock_response = Mock()
        mock_response.json.return_value = {'cuentas': []}
        mock_get.return_value = mock_response

        result = client.get_estado_cuenta()
        assert result == {'cuentas': []}
        mock_get.assert_called_once()

    def test_get_estado_cuenta_no_token(self, client):
        client.access_token = None
        client.refresh_token = None
        client.username = None  # Prevent login attempt
        with pytest.raises(ValueError):
            client.get_estado_cuenta()