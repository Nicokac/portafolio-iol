from datetime import datetime

import pytest
from django.utils import timezone

from apps.core.services.data_quality.daily_snapshot_continuity_service import DailySnapshotContinuityService
from apps.portafolio_iol.models import ActivoPortafolioSnapshot, PortfolioSnapshot
from apps.resumen_iol.models import ResumenCuentaSnapshot


class DummyAuditService:
    def __init__(self, rows, expected_symbols_count=2, usable_observations_count=1):
        self.rows = rows
        self.expected_symbols_count = expected_symbols_count
        self.usable_observations_count = usable_observations_count

    def audit_current_invested_history(self, lookback_days=14):
        return {
            "expected_symbols_count": self.expected_symbols_count,
            "usable_observations_count": self.usable_observations_count,
            "rows": self.rows,
        }


@pytest.mark.django_db
def test_daily_snapshot_continuity_marks_healthy_only_when_all_sources_and_usable_present():
    raw_dt = timezone.make_aware(datetime(2026, 3, 14, 10, 0, 0))
    ActivoPortafolioSnapshot.objects.create(
        fecha_extraccion=raw_dt,
        pais_consulta="argentina",
        simbolo="SPY",
        descripcion="SPY",
        cantidad=1,
        comprometido=0,
        disponible_inmediato=1,
        puntos_variacion=0,
        variacion_diaria=0,
        ultimo_precio=100,
        ppc=100,
        ganancia_porcentaje=0,
        ganancia_dinero=0,
        valorizado=100,
        pais_titulo="usa",
        mercado="nyse",
        tipo="cedear",
        plazo="spot",
        moneda="USD",
    )
    ResumenCuentaSnapshot.objects.create(
        fecha_extraccion=raw_dt,
        numero_cuenta="001",
        tipo_cuenta="comitente",
        moneda="ARS",
        disponible=10,
        comprometido=0,
        saldo=10,
        titulos_valorizados=100,
        total=110,
        margen_descubierto=0,
        estado="ok",
    )
    PortfolioSnapshot.objects.create(
        fecha=raw_dt.date(),
        total_iol=110,
        liquidez_operativa=10,
        cash_management=0,
        portafolio_invertido=100,
        rendimiento_total=0,
        exposicion_usa=100,
        exposicion_argentina=0,
    )

    service = DailySnapshotContinuityService(
        audit_service=DummyAuditService(
            rows=[
                {
                    "date": "2026-03-14",
                    "assets_present": 1,
                    "usable": True,
                }
            ],
            expected_symbols_count=1,
            usable_observations_count=1,
        )
    )

    result = service.build_report(lookback_days=7)

    assert result["overall_status"] == "healthy"
    assert result["status_counts"] == {"healthy": 1, "warning": 0, "broken": 0}
    assert result["rows"][0]["status"] == "healthy"
    assert result["rows"][0]["usable_for_covariance"] is True


@pytest.mark.django_db
def test_daily_snapshot_continuity_marks_warning_when_latest_day_exists_but_is_not_usable():
    raw_dt = timezone.make_aware(datetime(2026, 3, 14, 10, 0, 0))
    ActivoPortafolioSnapshot.objects.create(
        fecha_extraccion=raw_dt,
        pais_consulta="argentina",
        simbolo="SPY",
        descripcion="SPY",
        cantidad=1,
        comprometido=0,
        disponible_inmediato=1,
        puntos_variacion=0,
        variacion_diaria=0,
        ultimo_precio=100,
        ppc=100,
        ganancia_porcentaje=0,
        ganancia_dinero=0,
        valorizado=100,
        pais_titulo="usa",
        mercado="nyse",
        tipo="cedear",
        plazo="spot",
        moneda="USD",
    )
    ResumenCuentaSnapshot.objects.create(
        fecha_extraccion=raw_dt,
        numero_cuenta="001",
        tipo_cuenta="comitente",
        moneda="ARS",
        disponible=10,
        comprometido=0,
        saldo=10,
        titulos_valorizados=100,
        total=110,
        margen_descubierto=0,
        estado="ok",
    )
    PortfolioSnapshot.objects.create(
        fecha=raw_dt.date(),
        total_iol=110,
        liquidez_operativa=10,
        cash_management=0,
        portafolio_invertido=100,
        rendimiento_total=0,
        exposicion_usa=100,
        exposicion_argentina=0,
    )

    service = DailySnapshotContinuityService(
        audit_service=DummyAuditService(
            rows=[
                {
                    "date": "2026-03-14",
                    "assets_present": 1,
                    "usable": False,
                }
            ],
            expected_symbols_count=1,
            usable_observations_count=0,
        )
    )

    result = service.build_report(lookback_days=7)

    assert result["overall_status"] == "warning"
    assert result["rows"][0]["status"] == "warning"


@pytest.mark.django_db
def test_daily_snapshot_continuity_marks_broken_when_latest_day_has_no_sources():
    service = DailySnapshotContinuityService(
        audit_service=DummyAuditService(
            rows=[
                {
                    "date": "2026-03-14",
                    "assets_present": 0,
                    "usable": False,
                }
            ],
            expected_symbols_count=1,
            usable_observations_count=0,
        )
    )

    result = service.build_report(lookback_days=7)

    assert result["overall_status"] == "broken"
    assert result["status_counts"] == {"healthy": 0, "warning": 0, "broken": 1}
    assert result["rows"][0]["status"] == "broken"
