from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock

from apps.core.services.iol_mep_service import IOLMEPService


def test_iol_mep_service_builds_quotes_by_symbols():
    client = Mock()
    client.get_mep_quote.side_effect = [1392.26, None]

    result = IOLMEPService(client=client).get_mep_quotes_by_symbols(["AAPL", "GGAL", "AAPL"])

    assert result == {
        "AAPL": {
            "symbol": "AAPL",
            "mep_price_ars": 1392.26,
            "source": "iol_mep_endpoint",
        }
    }


def test_iol_mep_service_builds_implicit_fx_summary():
    relevant_positions = [
        {
            "activo": SimpleNamespace(valorizado=Decimal("2784.52")),
            "mep_profile": {"mep_price_ars": 1392.26},
        },
        {
            "activo": SimpleNamespace(valorizado=Decimal("1500")),
            "mep_profile": None,
        },
    ]

    result = IOLMEPService().build_implicit_fx_summary(relevant_positions=relevant_positions)

    assert result["total_positions_count"] == 2
    assert result["covered_positions_count"] == 1
    assert result["coverage_pct"] == 50.0
    assert result["covered_value_ars"] == 2784.52
    assert result["implied_usd_value"] == 2.0
    assert result["weighted_mep"] == 1392.26
