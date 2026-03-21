from decimal import Decimal

import pytest
from django.utils import timezone

from apps.portafolio_iol.models import ActivoPortafolioSnapshot
from apps.portafolio_iol.selectors import build_portafolio_list_context


@pytest.mark.django_db
def test_build_portafolio_list_context_summarizes_parking_visibility():
    ActivoPortafolioSnapshot.objects.create(
        fecha_extraccion=timezone.now(),
        pais_consulta="argentina",
        simbolo="AL30",
        descripcion="Bono AL30",
        cantidad=10,
        comprometido=0,
        disponible_inmediato=5,
        puntos_variacion=0,
        variacion_diaria=0,
        ultimo_precio=100,
        ppc=90,
        ganancia_porcentaje=1,
        ganancia_dinero=10,
        valorizado=1000,
        pais_titulo="Argentina",
        mercado="BCBA",
        tipo="TitulosPublicos",
        moneda="peso_Argentino",
        parking={"cantidad": 5, "fecha": "2026-03-25"},
    )
    ActivoPortafolioSnapshot.objects.create(
        fecha_extraccion=timezone.now(),
        pais_consulta="argentina",
        simbolo="MELI",
        descripcion="Mercado Libre",
        cantidad=2,
        comprometido=0,
        disponible_inmediato=2,
        puntos_variacion=0,
        variacion_diaria=0,
        ultimo_precio=20000,
        ppc=18000,
        ganancia_porcentaje=5,
        ganancia_dinero=4000,
        valorizado=40000,
        pais_titulo="USA",
        mercado="BCBA",
        tipo="CEDEAR",
        moneda="peso_Argentino",
        parking=None,
    )

    context = build_portafolio_list_context(ActivoPortafolioSnapshot.objects.order_by("simbolo"))

    assert context["summary"]["total_count"] == 2
    assert context["summary"]["parking_count"] == 1
    assert context["summary"]["parking_missing_count"] == 1
    assert context["summary"]["parking_pct"] == Decimal("50.00")
    assert context["summary"]["parking_value_total"] == Decimal("1000")
    assert context["summary"]["immediate_available_total"] == Decimal("7")
    assert context["rows"][0]["has_parking"] is True
    assert context["rows"][0]["parking_label"] == "Con parking"
    assert "Cantidad 5" in context["rows"][0]["parking_detail_label"]
    assert context["rows"][1]["parking_label"] == "Sin parking"
    assert context["rows"][1]["parking_detail_label"] == "Sin restricciones visibles"
