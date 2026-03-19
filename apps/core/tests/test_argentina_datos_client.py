from unittest.mock import Mock, patch

import pytest

from apps.core.services.market_data.argentina_datos_client import ArgentinaDatosClient


@patch("apps.core.services.market_data.argentina_datos_client.requests.get")
def test_argentina_datos_client_fetches_status_payload(mock_get):
    mock_response = Mock()
    mock_response.json.return_value = {
        "status": "ok",
        "message": "service healthy",
    }
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response

    payload = ArgentinaDatosClient().fetch_status()

    assert payload["status"] == "ok"
    assert payload["message"] == "service healthy"
    mock_get.assert_called_once_with("https://api.argentinadatos.com/v1/estado", timeout=10)


@patch("apps.core.services.market_data.argentina_datos_client.requests.get")
def test_argentina_datos_client_requires_json_object(mock_get):
    mock_response = Mock()
    mock_response.json.return_value = []
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response

    with pytest.raises(ValueError):
        ArgentinaDatosClient().fetch_status()
