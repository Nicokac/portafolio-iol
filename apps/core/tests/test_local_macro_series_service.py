from datetime import date, timedelta
from unittest.mock import Mock

import pandas as pd
import pytest
from django.utils import timezone

from apps.core.models import MacroSeriesSnapshot
from apps.core.services.local_macro_series_service import LocalMacroSeriesService
from apps.core.services.market_data.fx_json_client import OptionalSourceUnavailableError
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
def test_local_macro_series_service_skips_optional_mep_when_source_is_not_configured():
    fx_client = Mock()
    fx_client.fetch_usdars_mep.side_effect = OptionalSourceUnavailableError("USDARS_MEP_API_URL is required")
    service = LocalMacroSeriesService(bcra_client=Mock(), datos_client=Mock(), fx_client=fx_client)

    result = service.sync_series("usdars_mep")

    assert result["skipped"] is True
    assert result["rows_received"] == 0
    assert result["reason"] == "USDARS_MEP_API_URL is required"
    assert MacroSeriesSnapshot.objects.filter(series_key="usdars_mep").count() == 0


@pytest.mark.django_db
def test_local_macro_series_service_syncs_optional_mep_when_source_is_available():
    fx_client = Mock()
    fx_client.fetch_usdars_mep.return_value = [
        {"fecha": date(2026, 3, 16), "value": 1187.25},
    ]
    service = LocalMacroSeriesService(bcra_client=Mock(), datos_client=Mock(), fx_client=fx_client)

    result = service.sync_series("usdars_mep")

    assert result["created"] == 1
    assert result["updated"] == 0
    snapshot = MacroSeriesSnapshot.objects.get(series_key="usdars_mep")
    assert float(snapshot.value) == 1187.25


@pytest.mark.django_db
def test_local_macro_series_service_syncs_optional_country_risk_when_source_is_available():
    fx_client = Mock()
    fx_client.fetch_riesgo_pais.return_value = [
        {"fecha": date(2026, 3, 16), "value": 1250.0},
    ]
    service = LocalMacroSeriesService(bcra_client=Mock(), datos_client=Mock(), fx_client=fx_client)

    result = service.sync_series("riesgo_pais_arg")

    assert result["created"] == 1
    assert result["updated"] == 0
    snapshot = MacroSeriesSnapshot.objects.get(series_key="riesgo_pais_arg")
    assert float(snapshot.value) == 1250.0


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
        series_key="badlar_privada",
        source="bcra",
        external_id="7",
        frequency="daily",
        fecha=date(2026, 3, 13),
        value=29.5,
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
    assert context["badlar_privada"] == 29.5
    assert context["badlar_ytd"] is not None
    assert context["total_iol_usd_oficial"] == 1000.0
    assert context["ipc_nacional_variation_mom"] == 2.0
    assert context["ipc_nacional_variation_ytd"] == 7.1
    assert context["ipc_nacional_variation_yoy"] == 42.8
    assert context["portfolio_return_ytd_nominal"] == 8.0
    assert context["portfolio_return_ytd_real"] == 0.84
    assert context["portfolio_excess_ytd_vs_badlar"] is not None
    assert context["portfolio_return_ytd_is_partial"] is False
    assert context["portfolio_return_ytd_base_date"].isoformat() == "2025-12-31"


@pytest.mark.django_db
def test_local_macro_series_service_builds_optional_fx_gap_when_mep_exists():
    MacroSeriesSnapshot.objects.create(
        series_key="usdars_oficial",
        source="bcra",
        external_id="5",
        frequency="daily",
        fecha=date(2026, 2, 10),
        value=1000.0,
    )
    MacroSeriesSnapshot.objects.create(
        series_key="usdars_oficial",
        source="bcra",
        external_id="5",
        frequency="daily",
        fecha=date(2026, 3, 13),
        value=1000.0,
    )
    MacroSeriesSnapshot.objects.create(
        series_key="usdars_mep",
        source="manual",
        external_id="mep",
        frequency="daily",
        fecha=date(2026, 2, 10),
        value=1100.0,
    )
    MacroSeriesSnapshot.objects.create(
        series_key="usdars_mep",
        source="manual",
        external_id="mep",
        frequency="daily",
        fecha=date(2026, 3, 13),
        value=1180.0,
    )

    context = LocalMacroSeriesService(bcra_client=Mock(), datos_client=Mock()).get_context_summary()

    assert context["usdars_mep"] == 1180.0
    assert context["fx_gap_pct"] == 18.0
    assert context["fx_gap_change_30d"] == 8.0
    assert context["fx_gap_change_pct_30d"] == 80.0
    assert context["fx_gap_base_date_30d"].isoformat() == "2026-02-10"


@pytest.mark.django_db
def test_local_macro_series_service_builds_context_summary_with_country_risk():
    MacroSeriesSnapshot.objects.create(
        series_key="riesgo_pais_arg",
        source="fx_json",
        external_id="riesgo_pais_arg",
        frequency="daily",
        fecha=date(2026, 2, 14),
        value=1200.0,
    )
    MacroSeriesSnapshot.objects.create(
        series_key="riesgo_pais_arg",
        source="fx_json",
        external_id="riesgo_pais_arg",
        frequency="daily",
        fecha=date(2026, 3, 16),
        value=1350.0,
    )

    context = LocalMacroSeriesService(bcra_client=Mock(), datos_client=Mock()).get_context_summary()

    assert context["riesgo_pais_arg"] == 1350.0
    assert context["riesgo_pais_arg_date"].isoformat() == "2026-03-16"
    assert context["riesgo_pais_arg_change_30d"] == 150.0
    assert context["riesgo_pais_arg_change_pct_30d"] == 12.5
    assert context["riesgo_pais_arg_base_date_30d"].isoformat() == "2026-02-14"


@pytest.mark.django_db
def test_local_macro_series_service_builds_status_summary_with_optional_mep_not_configured(settings):
    settings.USDARS_MEP_API_URL = ""
    MacroSeriesSnapshot.objects.create(
        series_key="usdars_oficial",
        source="bcra",
        external_id="5",
        frequency="daily",
        fecha=timezone.localdate(),
        value=1000.0,
    )
    MacroSeriesSnapshot.objects.create(
        series_key="badlar_privada",
        source="bcra",
        external_id="7",
        frequency="daily",
        fecha=timezone.localdate(),
        value=30.0,
    )
    MacroSeriesSnapshot.objects.create(
        series_key="ipc_nacional",
        source="datos_gob_ar",
        external_id="ipc",
        frequency="monthly",
        fecha=timezone.localdate().replace(day=1),
        value=200.0,
    )

    rows = LocalMacroSeriesService(bcra_client=Mock(), datos_client=Mock()).get_status_summary()
    keyed = {row["series_key"]: row for row in rows}

    assert keyed["usdars_oficial"]["status"] == "ready"
    assert keyed["badlar_privada"]["status"] == "ready"
    assert keyed["ipc_nacional"]["status"] == "ready"
    assert keyed["usdars_mep"]["status"] == "not_configured"


@pytest.mark.django_db
def test_local_macro_series_service_marks_series_as_stale_when_latest_date_is_old(settings):
    settings.USDARS_MEP_API_URL = "https://example.test/mep"
    MacroSeriesSnapshot.objects.create(
        series_key="usdars_mep",
        source="fx_json",
        external_id="usdars_mep",
        frequency="daily",
        fecha=timezone.localdate() - timedelta(days=10),
        value=1180.0,
    )

    rows = LocalMacroSeriesService(bcra_client=Mock(), datos_client=Mock(), fx_client=Mock()).get_status_summary()
    keyed = {row["series_key"]: row for row in rows}

    assert keyed["usdars_mep"]["status"] == "stale"


def test_local_macro_series_service_summarizes_sync_result_with_skips_and_failures():
    summary = LocalMacroSeriesService.summarize_sync_result(
        {
            "usdars_oficial": {"success": True, "rows_received": 1},
            "usdars_mep": {"success": True, "rows_received": 0, "skipped": True},
            "badlar_privada": {"success": False, "rows_received": 0},
        }
    )

    assert summary["metric_name"] == LocalMacroSeriesService.SYNC_STATE_METRIC
    assert summary["state"] == "failed"
    assert summary["extra"]["synced_series"] == ["usdars_oficial"]
    assert summary["extra"]["skipped_series"] == ["usdars_mep"]
    assert summary["extra"]["failed_series"] == ["badlar_privada"]


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


@pytest.mark.django_db
def test_local_macro_series_service_builds_macro_comparison():
    PortfolioSnapshot.objects.create(
        fecha=date(2026, 3, 10),
        total_iol=1000,
        liquidez_operativa=200,
        cash_management=100,
        portafolio_invertido=700,
        rendimiento_total=0.0,
        exposicion_usa=50.0,
        exposicion_argentina=50.0,
    )
    PortfolioSnapshot.objects.create(
        fecha=date(2026, 3, 11),
        total_iol=1050,
        liquidez_operativa=210,
        cash_management=100,
        portafolio_invertido=740,
        rendimiento_total=5.0,
        exposicion_usa=50.0,
        exposicion_argentina=50.0,
    )
    PortfolioSnapshot.objects.create(
        fecha=date(2026, 3, 12),
        total_iol=1100,
        liquidez_operativa=220,
        cash_management=100,
        portafolio_invertido=780,
        rendimiento_total=10.0,
        exposicion_usa=50.0,
        exposicion_argentina=50.0,
    )
    for current_date, value in [
        (date(2026, 3, 10), 1000.0),
        (date(2026, 3, 11), 1010.0),
        (date(2026, 3, 12), 1020.0),
    ]:
        MacroSeriesSnapshot.objects.create(
            series_key="usdars_oficial",
            source="bcra",
            external_id="5",
            frequency="daily",
            fecha=current_date,
            value=value,
        )
    for current_date, value in [
        (date(2026, 2, 1), 200.0),
        (date(2026, 3, 1), 204.0),
    ]:
        MacroSeriesSnapshot.objects.create(
            series_key="ipc_nacional",
            source="datos_gob_ar",
            external_id="145.3_INGNACNAL_DICI_M_15",
            frequency="monthly",
            fecha=current_date,
            value=value,
        )

    result = LocalMacroSeriesService(bcra_client=Mock(), datos_client=Mock()).build_macro_comparison(days=30)

    assert result["observations"] == 3
    assert result["series"][0]["portfolio"] == 100.0
    assert result["series"][0]["portfolio_real"] == 100.0
    assert result["series"][0]["usdars_oficial"] == 100.0
    assert result["series"][0]["ipc_nacional"] == 100.0
    assert "max_drawdown_real" in result
    assert result["max_drawdown_real"] <= 0


@pytest.mark.django_db
def test_local_macro_series_service_builds_real_historical_metrics():
    for current_date, total_iol in [
        (date(2026, 3, 10), 1000),
        (date(2026, 3, 11), 950),
        (date(2026, 3, 12), 1100),
    ]:
        PortfolioSnapshot.objects.create(
            fecha=current_date,
            total_iol=total_iol,
            liquidez_operativa=200,
            cash_management=100,
            portafolio_invertido=700,
            rendimiento_total=0.0,
            exposicion_usa=50.0,
            exposicion_argentina=50.0,
        )
    for current_date, value in [
        (date(2026, 3, 10), 1000.0),
        (date(2026, 3, 11), 1005.0),
        (date(2026, 3, 12), 1010.0),
    ]:
        MacroSeriesSnapshot.objects.create(
            series_key="usdars_oficial",
            source="bcra",
            external_id="5",
            frequency="daily",
            fecha=current_date,
            value=value,
        )
    for current_date, value in [
        (date(2026, 2, 1), 200.0),
        (date(2026, 3, 1), 210.0),
    ]:
        MacroSeriesSnapshot.objects.create(
            series_key="ipc_nacional",
            source="datos_gob_ar",
            external_id="145.3_INGNACNAL_DICI_M_15",
            frequency="monthly",
            fecha=current_date,
            value=value,
        )

    result = LocalMacroSeriesService(bcra_client=Mock(), datos_client=Mock()).get_real_historical_metrics(days=30)

    assert result["real_history_observations"] == 3
    assert result["max_drawdown_real"] < 0


@pytest.mark.django_db
def test_local_macro_series_service_builds_rate_returns_from_badlar():
    for current_date, value in [
        (date(2026, 3, 10), 30.0),
        (date(2026, 3, 11), 30.0),
        (date(2026, 3, 12), 30.0),
    ]:
        MacroSeriesSnapshot.objects.create(
            series_key="badlar_privada",
            source="bcra",
            external_id="7",
            frequency="daily",
            fecha=current_date,
            value=value,
        )

    returns = LocalMacroSeriesService(bcra_client=Mock(), datos_client=Mock()).build_rate_returns(
        "badlar_privada",
        pd.to_datetime(["2026-03-11", "2026-03-12"]),
        periods_per_year=252,
    )

    assert len(returns) == 2
    assert round(float(returns.iloc[0]), 6) == round(0.30 / 252, 6)
