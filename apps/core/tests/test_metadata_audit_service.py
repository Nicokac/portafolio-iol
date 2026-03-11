import pytest
from django.utils import timezone

from apps.core.services.data_quality.metadata_audit import MetadataAuditService
from apps.parametros.models import ParametroActivo
from apps.portafolio_iol.models import ActivoPortafolioSnapshot


def _make_asset(fecha, simbolo):
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
        valorizado=1000,
        pais_titulo="Argentina",
        mercado="BCBA",
        tipo="ACCIONES",
        moneda="peso_Argentino",
    )


@pytest.mark.django_db
def test_metadata_audit_detects_unclassified_and_inconsistent_assets():
    fecha = timezone.now()

    _make_asset(fecha, "AAPL")
    _make_asset(fecha, "AL30")
    _make_asset(fecha, "GGAL")

    ParametroActivo.objects.create(
        simbolo="AAPL",
        sector="Tecnología",
        bloque_estrategico="Growth",
        pais_exposicion="USA",
        tipo_patrimonial="Equity",
    )
    ParametroActivo.objects.create(
        simbolo="AL30",
        sector="",
        bloque_estrategico="Argentina",
        pais_exposicion="Argentina",
        tipo_patrimonial="INVALID_TYPE",
    )

    report = MetadataAuditService().run_audit()

    assert report["total_assets"] == 3
    assert report["unclassified_assets_count"] == 1  # GGAL
    assert report["inconsistent_assets_count"] == 1  # AL30
    assert len(report["unclassified_assets"]) == 1
    assert len(report["inconsistent_assets"]) == 1
