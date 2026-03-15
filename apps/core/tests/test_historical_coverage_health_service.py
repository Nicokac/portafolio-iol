from datetime import timedelta

import pytest
from django.utils import timezone
from django_celery_beat.models import CrontabSchedule, IntervalSchedule, PeriodicTask

from apps.core.services.data_quality.historical_coverage_health import HistoricalCoverageHealthService
from apps.parametros.models import ParametroActivo
from apps.portafolio_iol.models import ActivoPortafolioSnapshot, PortfolioSnapshot
from apps.resumen_iol.models import ResumenCuentaSnapshot


def _make_asset_snapshot(fecha, simbolo, valorizado, *, tipo="ACCIONES", moneda="dolar_Estadounidense"):
    return ActivoPortafolioSnapshot.objects.create(
        fecha_extraccion=fecha,
        pais_consulta="argentina",
        simbolo=simbolo,
        descripcion=f"Activo {simbolo}",
        cantidad=10,
        comprometido=0,
        disponible_inmediato=10,
        puntos_variacion=0,
        variacion_diaria=0,
        ultimo_precio=100,
        ppc=90,
        ganancia_porcentaje=0,
        ganancia_dinero=0,
        valorizado=valorizado,
        pais_titulo="Argentina",
        mercado="BCBA",
        tipo=tipo,
        moneda=moneda,
    )


def _make_account_snapshot(fecha, moneda="ARS", disponible=1000):
    return ResumenCuentaSnapshot.objects.create(
        fecha_extraccion=fecha,
        numero_cuenta="123",
        tipo_cuenta="CA",
        moneda=moneda,
        disponible=disponible,
        comprometido=0,
        saldo=disponible,
        titulos_valorizados=0,
        total=disponible,
        estado="activa",
    )


def _seed_parametro(simbolo):
    ParametroActivo.objects.create(
        simbolo=simbolo,
        sector="Tecnologia",
        bloque_estrategico="Growth",
        pais_exposicion="USA",
        tipo_patrimonial="Equity",
    )


@pytest.mark.django_db
def test_historical_coverage_health_service_summarizes_recent_gaps():
    now = timezone.now().replace(hour=10, minute=0, second=0, microsecond=0)
    _seed_parametro("AAPL")
    _seed_parametro("MSFT")

    for offset, aapl, msft in [
        (4, 1000, 900),
        (2, 1020, 915),
        (0, 1035, 930),
    ]:
        fecha = now - timedelta(days=offset)
        _make_asset_snapshot(fecha, "AAPL", aapl)
        _make_asset_snapshot(fecha, "MSFT", msft)
        _make_account_snapshot(fecha)

    PortfolioSnapshot.objects.create(
        fecha=(now - timedelta(days=2)).date(),
        total_iol=1000,
        liquidez_operativa=100,
        cash_management=0,
        portafolio_invertido=900,
        rendimiento_total=0,
        exposicion_usa=100,
        exposicion_argentina=0,
    )

    interval_30m, _ = IntervalSchedule.objects.get_or_create(every=30, period=IntervalSchedule.MINUTES)
    daily_6am, _ = CrontabSchedule.objects.get_or_create(
        minute="0",
        hour="6",
        day_of_week="*",
        day_of_month="*",
        month_of_year="*",
        timezone="America/Argentina/Buenos_Aires",
    )
    PeriodicTask.objects.create(name="core.sync_portfolio_data", task="x", interval=interval_30m, enabled=True)
    PeriodicTask.objects.create(name="core.generate_daily_snapshot", task="y", crontab=daily_6am, enabled=False)

    summary = HistoricalCoverageHealthService().build_summary(lookback_days=4)

    assert summary["expected_symbols_count"] == 2
    assert summary["available_price_dates_count"] == 2
    assert summary["usable_observations_count"] == 1
    assert summary["missing_calendar_dates_count"] == 3
    assert len(summary["asset_days_without_portfolio_snapshot"]) >= 1
    assert summary["required_periodic_tasks"] == [
        {"name": "core.sync_portfolio_data", "enabled": True},
        {"name": "core.generate_daily_snapshot", "enabled": False},
    ]
