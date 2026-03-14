from unittest.mock import Mock, patch

from apps.core.services.market_data.datos_gob_client import DatosGobSeriesClient


@patch("apps.core.services.market_data.datos_gob_client.requests.get")
def test_datos_gob_client_parses_series(mock_get):
    mock_response = Mock()
    mock_response.json.return_value = {
        "data": [
            ["2016-12-01", 100.0],
            ["2017-01-01", 101.5859],
        ]
    }
    mock_get.return_value = mock_response

    rows = DatosGobSeriesClient().fetch_series("145.3_INGNACNAL_DICI_M_15", limit=3)

    assert len(rows) == 2
    assert rows[0]["fecha"].isoformat() == "2016-12-01"
    assert rows[1]["value"] == 101.5859
