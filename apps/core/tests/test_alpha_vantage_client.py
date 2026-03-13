from unittest.mock import Mock, patch

import pytest
from django.test import override_settings

from apps.core.services.market_data.alpha_vantage_client import AlphaVantageClient


@override_settings(ALPHA_VANTAGE_API_KEY="demo-key")
@patch("apps.core.services.market_data.alpha_vantage_client.requests.get")
def test_alpha_vantage_client_parses_daily_adjusted_series(mock_get):
    mock_response = Mock()
    mock_response.json.return_value = {
        "Time Series (Daily)": {
            "2026-03-12": {
                "4. close": "502.11",
                "5. adjusted close": "501.90",
                "6. volume": "1000",
            },
            "2026-03-11": {
                "4. close": "500.00",
                "5. adjusted close": "499.50",
                "6. volume": "900",
            },
        }
    }
    mock_get.return_value = mock_response

    rows = AlphaVantageClient().fetch_daily_adjusted("SPY")

    assert len(rows) == 2
    assert rows[0]["fecha"].isoformat() == "2026-03-11"
    assert rows[1]["adjusted_close"] == 501.9


@override_settings(ALPHA_VANTAGE_API_KEY="")
def test_alpha_vantage_client_requires_api_key():
    with pytest.raises(ValueError, match="ALPHA_VANTAGE_API_KEY"):
        AlphaVantageClient().fetch_daily_adjusted("SPY")
