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
