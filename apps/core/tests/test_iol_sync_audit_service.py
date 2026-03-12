from datetime import timedelta

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
        assert result["issues_count"] == 0
