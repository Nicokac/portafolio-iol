from datetime import date
from unittest.mock import Mock, patch

import pytest

from apps.core.services.market_data.fx_json_client import FXJSONClient, OptionalSourceUnavailableError


def test_fx_json_client_requires_url(settings):
    settings.USDARS_MEP_API_URL = ""
    client = FXJSONClient()

    with pytest.raises(OptionalSourceUnavailableError):
        client.fetch_usdars_mep()


@patch("apps.core.services.market_data.fx_json_client.requests.get")
def test_fx_json_client_fetches_mep_quote_from_configured_json(mock_get, settings):
    settings.USDARS_MEP_API_URL = "https://example.test/mep"
    settings.USDARS_MEP_API_VALUE_PATH = "mep.venta"
    settings.USDARS_MEP_API_DATE_PATH = "updated_at"

    mock_response = Mock()
    mock_response.json.return_value = {
        "mep": {"venta": 1187.25},
        "updated_at": "2026-03-16T18:30:00-03:00",
    }
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response

    rows = FXJSONClient().fetch_usdars_mep()

    assert rows == [{"fecha": date(2026, 3, 16), "value": 1187.25}]
    mock_get.assert_called_once_with("https://example.test/mep", timeout=30)


@patch("apps.core.services.market_data.fx_json_client.requests.get")
def test_fx_json_client_fetches_country_risk_from_configured_json(mock_get, settings):
    settings.RIESGO_PAIS_API_URL = "https://example.test/riesgo-pais"
    settings.RIESGO_PAIS_API_VALUE_PATH = "data.valor"
    settings.RIESGO_PAIS_API_DATE_PATH = "meta.updated_at"
    settings.RIESGO_PAIS_API_KEY = "secret"
    settings.RIESGO_PAIS_API_KEY_HEADER = "X-API-KEY"

    mock_response = Mock()
    mock_response.json.return_value = {
        "data": {"valor": 1250},
        "meta": {"updated_at": "2026-03-16"},
    }
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response

    rows = FXJSONClient().fetch_riesgo_pais()

    assert rows == [{"fecha": date(2026, 3, 16), "value": 1250.0}]
    mock_get.assert_called_once_with(
        "https://example.test/riesgo-pais",
        headers={"X-API-KEY": "secret"},
        timeout=30,
    )


@patch("apps.core.services.market_data.fx_json_client.requests.get")
def test_fx_json_client_fetches_country_risk_from_argentinadatos_shape_without_api_key(mock_get, settings):
    settings.RIESGO_PAIS_API_URL = "https://api.argentinadatos.com/v1/finanzas/indices/riesgo-pais"
    settings.RIESGO_PAIS_API_VALUE_PATH = "valor"
    settings.RIESGO_PAIS_API_DATE_PATH = "fecha"
    settings.RIESGO_PAIS_API_KEY = ""

    mock_response = Mock()
    mock_response.json.return_value = [
        {"fecha": "2026-03-16", "valor": 730},
        {"fecha": "2026-03-17", "valor": 742},
    ]
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response

    rows = FXJSONClient().fetch_riesgo_pais()

    assert rows == [
        {"fecha": date(2026, 3, 16), "value": 730.0},
        {"fecha": date(2026, 3, 17), "value": 742.0},
    ]
    mock_get.assert_called_once_with(
        "https://api.argentinadatos.com/v1/finanzas/indices/riesgo-pais",
        timeout=30,
    )
