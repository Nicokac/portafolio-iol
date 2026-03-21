from unittest.mock import MagicMock, Mock, patch

import pytest
import requests
from django.utils import timezone

from apps.core.models import IOLToken
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
        result = client.get_estado_cuenta()
        assert result is None
        assert client.last_error.get("error_type") == "unexpected_error"

    def test_get_headers_requires_token(self, client):
        client.token_manager.get_valid_token.return_value = None

        with pytest.raises(ValueError):
            client._get_headers()

    def test_build_auth_context_without_saved_token(self, client):
        context = client._build_auth_context()

        assert context["has_saved_token"] is False
        assert context["token_expired"] is None

    def test_build_auth_context_with_saved_token(self, client):
        IOLToken.objects.create(
            access_token='legacy-token',
            refresh_token='legacy-refresh',
            expires_at=timezone.now() + timezone.timedelta(minutes=30),
        )

        context = client._build_auth_context()

        assert context["has_saved_token"] is True
        assert context["has_refresh_token"] is True
        assert context["token_expired"] is False
        assert context["seconds_to_expiry"] > 0

    @patch('apps.core.services.iol_api_client.requests.post')
    def test_refresh_access_token_success(self, mock_post, client):
        mock_token = MagicMock()
        mock_token.get_refresh_token.return_value = 'old_refresh'
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
        mock_token.get_refresh_token.return_value = 'old_refresh'
        client.token_manager._current_token = mock_token
        mock_post.side_effect = Exception('Network error')

        result = client.refresh_access_token()
        assert result is False

    def test_refresh_access_token_no_refresh_token(self, client):
        client.token_manager._current_token = None
        result = client.refresh_access_token()
        assert result is False

    def test_ensure_valid_token_tries_refresh_then_login(self, client):
        token = MagicMock()
        token.refresh_token = 'refresh'
        client.token_manager.get_valid_token.return_value = None
        client.token_manager._current_token = token
        client.refresh_access_token = MagicMock(return_value=False)
        client.login = MagicMock(return_value=True)

        client._ensure_valid_token()

        client.refresh_access_token.assert_called_once()
        client.login.assert_called_once()

    def test_ensure_valid_token_logs_in_when_no_current_token(self, client):
        client.token_manager.get_valid_token.return_value = None
        client.token_manager._current_token = None
        client.login = MagicMock(return_value=True)

        client._ensure_valid_token()

        client.login.assert_called_once()

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
        mock_get.side_effect = requests.RequestException('error')

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
        assert mock_get.call_args.kwargs['params'] == {'filtro.fechaDesde': '2025-01-01'}

    @patch('apps.core.services.iol_api_client.requests.get')
    def test_get_operaciones_normalizes_internal_filters(self, mock_get, client):
        client.token_manager.get_valid_token.return_value = 'test_token'
        mock_response = Mock()
        mock_response.json.return_value = [{'tipo': 'compra'}]
        mock_get.return_value = mock_response

        result = client.get_operaciones({
            'numero': 167788363,
            'estado': 'todas',
            'fecha_desde': '2026-03-01',
            'fecha_hasta': '2026-03-21',
            'pais': 'argentina',
        })

        assert result == [{'tipo': 'compra'}]
        assert mock_get.call_args.kwargs['params'] == {
            'filtro.numero': 167788363,
            'filtro.estado': 'todas',
            'filtro.fechaDesde': '2026-03-01',
            'filtro.fechaHasta': '2026-03-21',
            'filtro.pais': 'argentina',
        }

    @patch('apps.core.services.iol_api_client.requests.get')
    def test_get_operaciones_preserves_explicit_filter_keys(self, mock_get, client):
        client.token_manager.get_valid_token.return_value = 'test_token'
        mock_response = Mock()
        mock_response.json.return_value = [{'tipo': 'compra'}]
        mock_get.return_value = mock_response

        result = client.get_operaciones({
            'filtro.estado': 'terminadas',
            'filtro.pais': 'argentina',
            'filtro.fechaDesde': '2026-03-01',
        })

        assert result == [{'tipo': 'compra'}]
        assert mock_get.call_args.kwargs['params'] == {
            'filtro.estado': 'terminadas',
            'filtro.pais': 'argentina',
            'filtro.fechaDesde': '2026-03-01',
        }

    @patch('apps.core.services.iol_api_client.requests.get')
    def test_get_operaciones_failure(self, mock_get, client):
        client.token_manager.get_valid_token.return_value = 'test_token'
        mock_get.side_effect = requests.RequestException('error')

        result = client.get_operaciones()
        assert result is None

    @patch('apps.core.services.iol_api_client.requests.get')
    def test_get_operacion_success(self, mock_get, client):
        client.token_manager.get_valid_token.return_value = 'test_token'
        mock_response = Mock()
        mock_response.json.return_value = {'numero': 167788363, 'simbolo': 'MCD'}
        mock_get.return_value = mock_response

        result = client.get_operacion(167788363)

        assert result == {'numero': 167788363, 'simbolo': 'MCD'}
        assert mock_get.call_args.args[0].endswith('/api/v2/operaciones/167788363')

    @patch('apps.core.services.iol_api_client.requests.get')
    def test_get_operacion_failure(self, mock_get, client):
        client.token_manager.get_valid_token.return_value = 'test_token'
        mock_get.side_effect = requests.RequestException('error')

        result = client.get_operacion(167788363)
        assert result is None

    @patch('apps.core.services.iol_api_client.requests.get')
    def test_get_titulo_historicos_success(self, mock_get, client):
        client.token_manager.get_valid_token.return_value = 'test_token'
        mock_response = Mock()
        mock_response.json.return_value = [{'fechaHora': '2026-03-19T17:00:00', 'ultimoPrecio': 100.0}]
        mock_get.return_value = mock_response

        result = client.get_titulo_historicos('bCBA', 'GGAL', {'fechaDesde': '2026-01-01', 'fechaHasta': '2026-03-19'})

        assert result == [{'fechaHora': '2026-03-19T17:00:00', 'ultimoPrecio': 100.0}]
        called_url = mock_get.call_args.args[0]
        assert '/api/v2/bCBA/Titulos/GGAL/Cotizacion/seriehistorica/' in called_url
        assert '2026-01-01T00%3A00%3A00' in called_url
        assert '2026-03-19T23%3A59%3A59' in called_url
        assert called_url.endswith('/ajustada')
        assert mock_get.call_args.kwargs['params'] is None

    @patch('apps.core.services.iol_api_client.requests.get')
    def test_get_titulo_historicos_rejects_non_list_payload(self, mock_get, client):
        client.token_manager.get_valid_token.return_value = 'test_token'
        mock_response = Mock()
        mock_response.json.return_value = {'unexpected': 'shape'}
        mock_get.return_value = mock_response

        result = client.get_titulo_historicos('bCBA', 'GGAL')

        assert result is None

    @patch('apps.core.services.iol_api_client.requests.get')
    def test_get_titulo_returns_metadata_dict(self, mock_get, client):
        client.token_manager.get_valid_token.return_value = 'test_token'
        mock_response = Mock()
        mock_response.json.return_value = {'simbolo': 'GGAL', 'mercado': 'BCBA', 'tipo': 'ACCIONES'}
        mock_get.return_value = mock_response

        result = client.get_titulo('BCBA', 'GGAL')

        assert result == {'simbolo': 'GGAL', 'mercado': 'BCBA', 'tipo': 'ACCIONES'}
        assert mock_get.call_args.args[0].endswith('/api/v2/BCBA/Titulos/GGAL')

    @patch('apps.core.services.iol_api_client.requests.get')
    def test_get_fci_returns_metadata_dict(self, mock_get, client):
        client.token_manager.get_valid_token.return_value = 'test_token'
        mock_response = Mock()
        mock_response.json.return_value = {'simbolo': 'ADBAICA', 'tipoFondo': 'money_market'}
        mock_get.return_value = mock_response

        result = client.get_fci('ADBAICA')

        assert result == {'simbolo': 'ADBAICA', 'tipoFondo': 'money_market'}
        assert mock_get.call_args.args[0].endswith('/api/v2/Titulos/FCI/ADBAICA')

    @patch('apps.core.services.iol_api_client.requests.get')
    def test_get_titulo_cotizacion_returns_dict(self, mock_get, client):
        client.token_manager.get_valid_token.return_value = 'test_token'
        mock_response = Mock()
        mock_response.json.return_value = {
            'ultimoPrecio': 602.9,
            'moneda': 'peso_Argentino',
            'descripcionTitulo': 'Petroleo Brasileiro',
        }
        mock_get.return_value = mock_response

        result = client.get_titulo_cotizacion('bCBA', 'APBR')

        assert result == {
            'ultimoPrecio': 602.9,
            'moneda': 'peso_Argentino',
            'descripcionTitulo': 'Petroleo Brasileiro',
        }
        assert mock_get.call_args.args[0].endswith('/api/v2/bCBA/Titulos/APBR/Cotizacion')
        assert mock_get.call_args.kwargs['params'] == {
            'model.simbolo': 'APBR',
            'model.mercado': 'bCBA',
            'model.plazo': 't0',
        }

    @patch('apps.core.services.iol_api_client.requests.get')
    def test_get_titulo_cotizacion_normalizes_alias_params(self, mock_get, client):
        client.token_manager.get_valid_token.return_value = 'test_token'
        mock_response = Mock()
        mock_response.json.return_value = {'ultimoPrecio': 602.9}
        mock_get.return_value = mock_response

        result = client.get_titulo_cotizacion(
            'BCBA',
            'APBR',
            {
                'mercado': 'bCBA',
                'simbolo': 'APBR',
                'plazo': 'T0',
            },
        )

        assert result == {'ultimoPrecio': 602.9}
        assert mock_get.call_args.kwargs['params'] == {
            'model.simbolo': 'APBR',
            'model.mercado': 'bCBA',
            'model.plazo': 'T0',
        }

    @patch('apps.core.services.iol_api_client.requests.get')
    def test_get_titulo_cotizacion_rejects_non_dict_payload(self, mock_get, client):
        client.token_manager.get_valid_token.return_value = 'test_token'
        mock_response = Mock()
        mock_response.json.return_value = [{'unexpected': 'shape'}]
        mock_get.return_value = mock_response

        result = client.get_titulo_cotizacion('bCBA', 'APBR')

        assert result is None

    @patch('apps.core.services.iol_api_client.requests.get')
    def test_get_titulo_cotizacion_detalle_returns_dict(self, mock_get, client):
        client.token_manager.get_valid_token.return_value = 'test_token'
        mock_response = Mock()
        mock_response.json.return_value = {
            'simbolo': 'MELI',
            'mercado': 'bcba',
            'tipo': 'cedears',
            'cantidadMinima': 1,
        }
        mock_get.return_value = mock_response

        result = client.get_titulo_cotizacion_detalle('bCBA', 'MELI')

        assert result == {
            'simbolo': 'MELI',
            'mercado': 'bcba',
            'tipo': 'cedears',
            'cantidadMinima': 1,
        }
        assert mock_get.call_args.args[0].endswith('/api/v2/bCBA/Titulos/MELI/CotizacionDetalle')
        assert mock_get.call_args.kwargs['params'] is None

    @patch('apps.core.services.iol_api_client.requests.get')
    def test_get_titulo_cotizacion_detalle_rejects_non_dict_payload(self, mock_get, client):
        client.token_manager.get_valid_token.return_value = 'test_token'
        mock_response = Mock()
        mock_response.json.return_value = [{'unexpected': 'shape'}]
        mock_get.return_value = mock_response

        result = client.get_titulo_cotizacion_detalle('bCBA', 'MELI')

        assert result is None

    def test_get_titulo_market_snapshot_prefers_cotizacion_detalle(self, client):
        client.get_titulo_cotizacion_detalle = MagicMock(return_value={
            'simbolo': 'MELI',
            'tipo': 'cedears',
            'puntas': [{'precioCompra': 20040}],
        })
        client.get_titulo_cotizacion = MagicMock(return_value={'ultimoPrecio': 20040})

        result = client.get_titulo_market_snapshot('bCBA', 'MELI')

        assert result == {
            'simbolo': 'MELI',
            'tipo': 'cedears',
            'puntas': [{'precioCompra': 20040}],
        }
        client.get_titulo_cotizacion_detalle.assert_called_once_with('bCBA', 'MELI')
        client.get_titulo_cotizacion.assert_not_called()

    def test_get_titulo_market_snapshot_falls_back_to_cotizacion(self, client):
        client.get_titulo_cotizacion_detalle = MagicMock(return_value=None)
        client.get_titulo_cotizacion = MagicMock(return_value={
            'ultimoPrecio': 20040,
            'descripcionTitulo': 'Cedear Mercadolibre Inc.',
        })

        result = client.get_titulo_market_snapshot('bCBA', 'MELI', params={'plazo': 't0'})

        assert result == {
            'ultimoPrecio': 20040,
            'descripcionTitulo': 'Cedear Mercadolibre Inc.',
        }
        client.get_titulo_cotizacion_detalle.assert_called_once_with('bCBA', 'MELI')
        client.get_titulo_cotizacion.assert_called_once_with('bCBA', 'MELI', params={'plazo': 't0'})

    @patch('apps.core.services.iol_api_client.requests.get')
    def test_request_json_retries_once_on_401_and_then_succeeds(self, mock_get, client):
        client._ensure_valid_token = MagicMock()
        client.token_manager.invalidate_current_token = MagicMock()
        client.token_manager.get_valid_token.return_value = 'test-token'

        first = Mock()
        first.raise_for_status.side_effect = requests.HTTPError(response=Mock(status_code=401))
        second = Mock()
        second.raise_for_status.return_value = None
        second.json.return_value = {'ok': True}
        mock_get.side_effect = [first, second]

        result = client._request_json(operation='test', url='https://iol.test/resource')

        assert result == {'ok': True}
        client.token_manager.invalidate_current_token.assert_called_once()
        assert client.last_error == {}

    @patch('apps.core.services.iol_api_client.requests.get')
    def test_request_json_returns_http_error_after_retry(self, mock_get, client):
        client._ensure_valid_token = MagicMock()
        client.token_manager.invalidate_current_token = MagicMock()
        client.token_manager.get_valid_token.return_value = 'test-token'

        first = Mock()
        first.raise_for_status.side_effect = requests.HTTPError(response=Mock(status_code=401))
        second = Mock()
        second.raise_for_status.side_effect = requests.HTTPError(response=Mock(status_code=403))
        mock_get.side_effect = [first, second]

        result = client._request_json(operation='test', url='https://iol.test/resource')

        assert result is None
        assert client.last_error["error_type"] == "http_error_after_retry"
        assert client.last_error["status_code"] == 403

    @patch('apps.core.services.iol_api_client.requests.get')
    def test_request_json_handles_http_error_without_retry(self, mock_get, client):
        client._ensure_valid_token = MagicMock()
        client.token_manager.get_valid_token.return_value = 'test-token'

        response = Mock()
        response.raise_for_status.side_effect = requests.HTTPError(response=Mock(status_code=500))
        mock_get.return_value = response

        result = client._request_json(operation='test', url='https://iol.test/resource')

        assert result is None
        assert client.last_error["error_type"] == "http_error"
        assert client.last_error["status_code"] == 500

    @patch('apps.core.services.iol_api_client.requests.get')
    def test_request_json_handles_request_exception(self, mock_get, client):
        client._ensure_valid_token = MagicMock()
        client.token_manager.get_valid_token.return_value = 'test-token'
        mock_get.side_effect = requests.RequestException('network down')

        result = client._request_json(operation='test', url='https://iol.test/resource')

        assert result is None
        assert client.last_error["error_type"] == "request_error"

    @patch('apps.core.services.iol_api_client.requests.get')
    def test_request_json_handles_unexpected_error(self, mock_get, client):
        client._ensure_valid_token = MagicMock()
        client.token_manager.get_valid_token.return_value = 'test-token'
        mock_get.side_effect = RuntimeError('boom')

        result = client._request_json(operation='test', url='https://iol.test/resource')

        assert result is None
        assert client.last_error["error_type"] == "unexpected_error"
