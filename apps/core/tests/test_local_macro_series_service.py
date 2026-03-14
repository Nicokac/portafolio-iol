from datetime import date
from unittest.mock import Mock

import pytest

from apps.core.models import MacroSeriesSnapshot
from apps.core.services.local_macro_series_service import LocalMacroSeriesService
from apps.portafolio_iol.models import PortfolioSnapshot


@pytest.mark.django_db
def test_local_macro_series_service_syncs_bcra_series():
    bcra_client = Mock()
    bcra_client.fetch_variable.return_value = [
        {"fecha": date(2026, 3, 12), "value": 1400.5},
        {"fecha": date(2026, 3, 13), "value": 1392.99},
    ]
    service = LocalMacroSeriesService(bcra_client=bcra_client, datos_client=Mock())

    first = service.sync_series("usdars_oficial")
    second = service.sync_series("usdars_oficial")

    assert first["created"] == 2
    assert second["updated"] == 2
    assert MacroSeriesSnapshot.objects.filter(series_key="usdars_oficial").count() == 2


@pytest.mark.django_db
def test_local_macro_series_service_builds_context_summary():
    PortfolioSnapshot.objects.create(
        fecha=date(2025, 12, 31),
        total_iol=1000,
        liquidez_operativa=200,
        cash_management=100,
        portafolio_invertido=700,
        rendimiento_total=0.0,
        exposicion_usa=50.0,
        exposicion_argentina=50.0,
    )
    PortfolioSnapshot.objects.create(
        fecha=date(2026, 2, 15),
        total_iol=1080,
        liquidez_operativa=220,
        cash_management=110,
        portafolio_invertido=750,
        rendimiento_total=8.0,
        exposicion_usa=50.0,
        exposicion_argentina=50.0,
    )
    MacroSeriesSnapshot.objects.create(
        series_key="usdars_oficial",
        source="bcra",
        external_id="5",
        frequency="daily",
        fecha=date(2026, 3, 13),
        value=1392.99,
    )
    MacroSeriesSnapshot.objects.create(
        series_key="ipc_nacional",
        source="datos_gob_ar",
        external_id="145.3_INGNACNAL_DICI_M_15",
        frequency="monthly",
        fecha=date(2025, 2, 1),
        value=150.0,
    )
    MacroSeriesSnapshot.objects.create(
        series_key="ipc_nacional",
        source="datos_gob_ar",
        external_id="145.3_INGNACNAL_DICI_M_15",
        frequency="monthly",
        fecha=date(2025, 12, 1),
        value=200.0,
    )
    MacroSeriesSnapshot.objects.create(
        series_key="ipc_nacional",
        source="datos_gob_ar",
        external_id="145.3_INGNACNAL_DICI_M_15",
        frequency="monthly",
        fecha=date(2026, 1, 1),
        value=210.0,
    )
    MacroSeriesSnapshot.objects.create(
        series_key="ipc_nacional",
        source="datos_gob_ar",
        external_id="145.3_INGNACNAL_DICI_M_15",
        frequency="monthly",
        fecha=date(2026, 2, 1),
        value=214.2,
    )

    context = LocalMacroSeriesService(bcra_client=Mock(), datos_client=Mock()).get_context_summary(total_iol=1392990)

    assert context["usdars_oficial"] == 1392.99
    assert context["total_iol_usd_oficial"] == 1000.0
    assert context["ipc_nacional_variation_mom"] == 2.0
    assert context["ipc_nacional_variation_ytd"] == 7.1
    assert context["ipc_nacional_variation_yoy"] == 42.8
    assert context["portfolio_return_ytd_nominal"] == 8.0
    assert context["portfolio_return_ytd_real"] == 0.84
    assert context["portfolio_return_ytd_is_partial"] is False
    assert context["portfolio_return_ytd_base_date"].isoformat() == "2025-12-31"


@pytest.mark.django_db
def test_local_macro_series_service_marks_partial_portfolio_ytd_when_prior_year_close_missing():
    PortfolioSnapshot.objects.create(
        fecha=date(2026, 1, 10),
        total_iol=1000,
        liquidez_operativa=200,
        cash_management=100,
        portafolio_invertido=700,
        rendimiento_total=0.0,
        exposicion_usa=50.0,
        exposicion_argentina=50.0,
    )
    PortfolioSnapshot.objects.create(
        fecha=date(2026, 2, 15),
        total_iol=1050,
        liquidez_operativa=220,
        cash_management=110,
        portafolio_invertido=720,
        rendimiento_total=5.0,
        exposicion_usa=50.0,
        exposicion_argentina=50.0,
    )
    MacroSeriesSnapshot.objects.create(
        series_key="ipc_nacional",
        source="datos_gob_ar",
        external_id="145.3_INGNACNAL_DICI_M_15",
        frequency="monthly",
        fecha=date(2026, 1, 1),
        value=210.0,
    )
    MacroSeriesSnapshot.objects.create(
        series_key="ipc_nacional",
        source="datos_gob_ar",
        external_id="145.3_INGNACNAL_DICI_M_15",
        frequency="monthly",
        fecha=date(2026, 2, 1),
        value=214.2,
    )

    context = LocalMacroSeriesService(bcra_client=Mock(), datos_client=Mock()).get_context_summary(total_iol=1050)

    assert context["portfolio_return_ytd_nominal"] == 5.0
    assert context["portfolio_return_ytd_is_partial"] is True
    assert context["portfolio_return_ytd_base_date"].isoformat() == "2026-01-10"
