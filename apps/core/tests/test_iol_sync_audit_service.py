from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest
from django.utils import timezone

from apps.core.models import IOLToken
from apps.core.services.iol_sync_audit import IOLSyncAuditService
from apps.operaciones_iol.models import OperacionIOL
from apps.portafolio_iol.models import ActivoPortafolioSnapshot
from apps.resumen_iol.models import ResumenCuentaSnapshot


@pytest.mark.django_db
class TestIOLSyncAuditService:
    def test_reports_warning_when_data_missing(self):
        result = IOLSyncAuditService().run_audit(freshness_hours=24)
        assert result["status"] == "warning"
        assert result["issues_count"] >= 1

    def test_reports_ok_when_recent_and_complete_data(self):
        now = timezone.now()
        IOLToken.objects.create(
            access_token="token",
            refresh_token="refresh",
            expires_at=now + timedelta(hours=2),
        )

        ActivoPortafolioSnapshot.objects.create(
            fecha_extraccion=now,
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
            pais_titulo="USA",
            mercado="NYSE",
            tipo="CEDEARS",
            plazo="T0",
            moneda="ARS",
        )

        ResumenCuentaSnapshot.objects.create(
            fecha_extraccion=now,
            numero_cuenta="1",
            tipo_cuenta="ca",
            moneda="ARS",
            disponible=1000,
            comprometido=0,
            saldo=1000,
            titulos_valorizados=100,
            total=1100,
            margen_descubierto=0,
            estado="activa",
        )

        OperacionIOL.objects.create(
            numero="abc-1",
            fecha_orden=now,
            tipo="Compra",
            estado="Terminada",
            mercado="BCBA",
            simbolo="SPY",
            cantidad=1,
            monto=100,
            modalidad="precio_limite",
        )

        result = IOLSyncAuditService().run_audit(freshness_hours=24)
        assert result["status"] == "ok"
        assert result["patrimonial_status"] == "ok"
        assert result["issues_count"] == 0

    def test_reports_expired_token_and_stale_data(self):
        now = timezone.now()
        IOLToken.objects.create(
            access_token="token",
            refresh_token="refresh",
            expires_at=now - timedelta(minutes=5),
        )

        stale_time = now - timedelta(days=2)
        ActivoPortafolioSnapshot.objects.create(
            fecha_extraccion=stale_time,
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
            pais_titulo="USA",
            mercado="NYSE",
            tipo="CEDEARS",
            plazo="T0",
            moneda="ARS",
        )
        ResumenCuentaSnapshot.objects.create(
            fecha_extraccion=stale_time,
            numero_cuenta="1",
            tipo_cuenta="ca",
            moneda="ARS",
            disponible=1000,
            comprometido=0,
            saldo=1000,
            titulos_valorizados=100,
            total=1100,
            margen_descubierto=0,
            estado="activa",
        )
        OperacionIOL.objects.create(
            numero="abc-2",
            fecha_orden=stale_time,
            tipo="Compra",
            estado="Terminada",
            mercado="BCBA",
            simbolo="SPY",
            cantidad=1,
            monto=100,
            modalidad="precio_limite",
        )

        result = IOLSyncAuditService().run_audit(freshness_hours=24)

        assert result["status"] == "warning"
        assert result["patrimonial_status"] == "warning"
        assert result["token"]["reason"] == "expired_token"
        assert "stale_snapshots" in result["snapshots"]["reasons"]
        assert result["operations"]["reason"] == "stale_operations"

    def test_keeps_patrimonial_status_ok_when_only_operations_are_stale(self):
        now = timezone.now()
        IOLToken.objects.create(
            access_token="token",
            refresh_token="refresh",
            expires_at=now + timedelta(hours=2),
        )

        ActivoPortafolioSnapshot.objects.create(
            fecha_extraccion=now,
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
            pais_titulo="USA",
            mercado="NYSE",
            tipo="CEDEARS",
            plazo="T0",
            moneda="ARS",
        )
        ResumenCuentaSnapshot.objects.create(
            fecha_extraccion=now,
            numero_cuenta="1",
            tipo_cuenta="ca",
            moneda="ARS",
            disponible=1000,
            comprometido=0,
            saldo=1000,
            titulos_valorizados=100,
            total=1100,
            margen_descubierto=0,
            estado="activa",
        )
        OperacionIOL.objects.create(
            numero="abc-ops-stale",
            fecha_orden=now - timedelta(days=2),
            tipo="Compra",
            estado="Terminada",
            mercado="BCBA",
            simbolo="SPY",
            cantidad=1,
            monto=100,
            modalidad="precio_limite",
        )

        result = IOLSyncAuditService().run_audit(freshness_hours=24)

        assert result["status"] == "warning"
        assert result["patrimonial_status"] == "ok"
        assert result["operations_status"] == "warning"
        assert result["issues"] == ["operations"]
        assert result["patrimonial_issues"] == []

    def test_audit_operations_handles_naive_datetime(self):
        stale_time = timezone.now().replace(tzinfo=None) - timedelta(days=2)
        OperacionIOL.objects.create(
            numero="abc-3",
            fecha_orden=stale_time,
            tipo="Compra",
            estado="Terminada",
            mercado="BCBA",
            simbolo="SPY",
            cantidad=1,
            monto=100,
            modalidad="precio_limite",
        )

        result = IOLSyncAuditService._audit_operations(timezone.now() - timedelta(hours=24))

        assert result["status"] == "warning"
        assert result["reason"] == "stale_operations"

    def test_audit_operations_reports_missing_operations(self):
        result = IOLSyncAuditService._audit_operations(timezone.now() - timedelta(hours=24))

        assert result == {"status": "warning", "reason": "missing_operations"}

    def test_audit_snapshots_reports_incomplete_sets(self):
        now = timezone.now()
        with patch("apps.core.services.iol_sync_audit.ActivoPortafolioSnapshot.objects") as portfolio_objects, patch(
            "apps.core.services.iol_sync_audit.ResumenCuentaSnapshot.objects"
        ) as account_objects:
            portfolio_objects.order_by.return_value.first.return_value = MagicMock(fecha_extraccion=now)
            account_objects.order_by.return_value.first.return_value = MagicMock(fecha_extraccion=now)
            portfolio_objects.filter.return_value.count.return_value = 0
            account_objects.filter.return_value.count.return_value = 1

            result = IOLSyncAuditService._audit_snapshots(now - timedelta(hours=1))

        assert result["status"] == "warning"
        assert "incomplete_snapshots" in result["reasons"]
