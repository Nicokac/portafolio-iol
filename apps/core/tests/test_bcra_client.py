from unittest.mock import Mock, patch

from apps.core.services.market_data.bcra_client import BCRAClient


@patch("apps.core.services.market_data.bcra_client.requests.get")
def test_bcra_client_parses_variable_series(mock_get):
    mock_response = Mock()
    mock_response.json.return_value = {
        "status": 200,
        "results": [
            {
                "idVariable": 5,
                "detalle": [
                    {"fecha": "2026-03-12", "valor": 1400.5},
                    {"fecha": "2026-03-13", "valor": 1392.99},
                ],
            }
        ],
    }
    mock_get.return_value = mock_response

    rows = BCRAClient().fetch_variable("5", limit=3)

    assert len(rows) == 2
    assert rows[0]["fecha"].isoformat() == "2026-03-12"
    assert rows[1]["value"] == 1392.99
