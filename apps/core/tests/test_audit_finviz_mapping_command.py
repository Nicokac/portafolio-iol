from io import StringIO

import pytest
from django.core.management import call_command
from django.utils import timezone

from apps.parametros.models import ParametroActivo
from apps.portafolio_iol.models import ActivoPortafolioSnapshot


@pytest.mark.django_db
def test_audit_finviz_mapping_command_reports_metadata_scope():
    ParametroActivo.objects.create(
        simbolo="AAPL",
        sector="Tecnologia",
        bloque_estrategico="Growth",
        pais_exposicion="USA",
        tipo_patrimonial="Equity",
    )

    stdout = StringIO()
    call_command("audit_finviz_mapping", "--scope=metadata", stdout=stdout)
    output = stdout.getvalue()

    assert "[metadata_universe]" in output
    assert "mapped=1" in output


@pytest.mark.django_db
def test_audit_finviz_mapping_command_reports_portfolio_problems():
    ActivoPortafolioSnapshot.objects.create(
        fecha_extraccion=timezone.now(),
        pais_consulta="argentina",
        simbolo="AL30",
        descripcion="Bono AL30",
        cantidad=1,
        comprometido=0,
        disponible_inmediato=1,
        puntos_variacion=0,
        variacion_diaria=0,
        ultimo_precio=1,
        ppc=1,
        ganancia_porcentaje=0,
        ganancia_dinero=0,
        valorizado=100,
        pais_titulo="argentina",
        mercado="bcba",
        tipo="TitulosPublicos",
        plazo="t1",
        moneda="peso_Argentino",
    )

    stdout = StringIO()
    call_command("audit_finviz_mapping", "--scope=portfolio", stdout=stdout)
    output = stdout.getvalue()

    assert "[current_portfolio]" in output
    assert "missing_metadata=1" in output
    assert "AL30 | status=missing_metadata" in output
