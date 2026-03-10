import pytest
from unittest.mock import Mock, patch, MagicMock
from apps.core.services.iol_api_client import IOLAPIClient


@pytest.mark.django_db
class TestIOLAPIClient:
    @pytest.fixture
    def client(self):
        client = IOLAPIClient()
        # Reemplazar token_manager con mock para aislar tests de la DB
        client.token_manager = MagicMock()
        return client

    @patch('apps.core.services.iol_api_client.requests.post')
    def test_login_success(self, mock_post, client):
        mock_response = Mock()
        mock_response.json.return_value = {
            'access_token': 'test_token',
            'refresh_token': 'refresh_token',
        }
        mock_post.return_value = mock_response
        result = client.login()
        assert result is True
        assert client.access_token == 'test_token'
        assert client.refresh_token == 'refresh_token'
        client.token_manager.save_token.assert_called_once()

    @patch('apps.core.services.iol_api_client.requests.post')
    def test_login_failure(self, mock_post, client):
        mock_post.side_effect = Exception('API Error')
        result = client.login()
        assert result is False

    @patch('apps.core.services.iol_api_client.requests.get')
    def test_get_estado_cuenta(self, mock_get, client):
        # Token manager retorna token válido
        client.token_manager.get_valid_token.return_value = 'test_token'
        mock_response = Mock()
        mock_response.json.return_value = {'cuentas': []}
        mock_get.return_value = mock_response
        result = client.get_estado_cuenta()
        assert result == {'cuentas': []}
        mock_get.assert_called_once()

    def test_get_estado_cuenta_no_token(self, client):
        # Token manager no retorna token y login falla
        client.token_manager.get_valid_token.return_value = None
        client.token_manager._current_token = None
        client.username = None
        with pytest.raises(ValueError):
            client.get_estado_cuenta()

    @patch('apps.core.services.iol_api_client.requests.post')
    def test_refresh_access_token_success(self, mock_post, client):
        mock_token = MagicMock()
        mock_token.refresh_token = 'old_refresh'
        client.token_manager._current_token = mock_token

        mock_response = Mock()
        mock_response.json.return_value = {
            'access_token': 'new_token',
            'refresh_token': 'new_refresh',
        }
        mock_post.return_value = mock_response

        result = client.refresh_access_token()
        assert result is True
        assert client.access_token == 'new_token'

    @patch('apps.core.services.iol_api_client.requests.post')
    def test_refresh_access_token_failure(self, mock_post, client):
        mock_token = MagicMock()
        mock_token.refresh_token = 'old_refresh'
        client.token_manager._current_token = mock_token
        mock_post.side_effect = Exception('Network error')

        result = client.refresh_access_token()
        assert result is False

    def test_refresh_access_token_no_refresh_token(self, client):
        client.token_manager._current_token = None
        result = client.refresh_access_token()
        assert result is False

    @patch('apps.core.services.iol_api_client.requests.get')
    def test_get_portafolio_success(self, mock_get, client):
        client.token_manager.get_valid_token.return_value = 'test_token'
        mock_response = Mock()
        mock_response.json.return_value = {'activos': []}
        mock_get.return_value = mock_response

        result = client.get_portafolio()
        assert result == {'activos': []}

    @patch('apps.core.services.iol_api_client.requests.get')
    def test_get_portafolio_failure(self, mock_get, client):
        client.token_manager.get_valid_token.return_value = 'test_token'
        import requests as req
        mock_get.side_effect = req.RequestException('error')

        result = client.get_portafolio()
        assert result is None

    @patch('apps.core.services.iol_api_client.requests.get')
    def test_get_operaciones_success(self, mock_get, client):
        client.token_manager.get_valid_token.return_value = 'test_token'
        mock_response = Mock()
        mock_response.json.return_value = [{'tipo': 'compra'}]
        mock_get.return_value = mock_response

        result = client.get_operaciones({'fechaDesde': '2025-01-01'})
        assert result == [{'tipo': 'compra'}]

    @patch('apps.core.services.iol_api_client.requests.get')
    def test_get_operaciones_failure(self, mock_get, client):
        client.token_manager.get_valid_token.return_value = 'test_token'
        import requests as req
        mock_get.side_effect = req.RequestException('error')

        result = client.get_operaciones()
        assert result is None
