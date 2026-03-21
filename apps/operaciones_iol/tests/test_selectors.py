from decimal import Decimal

import pytest
from django.utils import timezone

from apps.operaciones_iol.models import OperacionIOL
from apps.operaciones_iol.selectors import (
    apply_operation_filters,
    build_operation_filter_context,
    build_operation_list_context,
    get_operation_subset_for_country_backfill,
    get_operation_subset_for_detail_enrichment,
    normalize_operation_filters,
)


@pytest.mark.django_db
def test_build_operation_list_context_summarizes_detail_fills_and_fees():
    OperacionIOL.objects.create(
        numero="OP-1",
        fecha_orden=timezone.now(),
        tipo="Compra",
        estado="Terminada",
        estado_actual="terminada",
        mercado="BCBA",
        simbolo="MELI",
        modalidad="precio_Mercado",
        moneda="peso_Argentino",
        aranceles_ars=Decimal("523.89"),
        operaciones_detalle=[
            {"fecha": "2026-03-18T14:05:57", "cantidad": 1, "precio": 100},
            {"fecha": "2026-03-18T14:05:58", "cantidad": 1, "precio": 101},
        ],
        estados_detalle=[{"detalle": "Terminada", "fecha": "2026-03-18T14:05:58"}],
    )
    OperacionIOL.objects.create(
        numero="OP-2",
        fecha_orden=timezone.now(),
        tipo="Pago de Dividendos",
        estado="Terminada",
        mercado="BCBA",
        simbolo="MCD US$",
        modalidad="precio_Mercado",
    )
    OperacionIOL.objects.create(
        numero="OP-3",
        fecha_orden=timezone.now(),
        tipo="Pago de Dividendos",
        estado="Terminada",
        mercado="BCBA",
        simbolo="MSFT US$",
        modalidad="precio_Mercado",
        aranceles_usd=Decimal("0.15"),
    )

    operaciones = OperacionIOL.objects.order_by("numero")
    context = build_operation_list_context(operaciones)

    assert context["summary"]["total_count"] == 3
    assert context["summary"]["enriched_count"] == 2
    assert context["summary"]["missing_detail_count"] == 1
    assert context["summary"]["enriched_pct"] == Decimal("66.67")
    assert context["summary"]["fills_count"] == 1
    assert context["summary"]["fragmented_count"] == 1
    assert context["summary"]["fragmented_pct"] == Decimal("100.00")
    assert context["summary"]["fees_visible_count"] == 2
    assert context["summary"]["fees_visible_pct"] == Decimal("66.67")
    assert context["summary"]["fees_ars_total"] == Decimal("523.89")
    assert context["summary"]["fees_usd_total"] == Decimal("0.15")
    assert context["summary"]["type_breakdown"][0]["tipo"] == "Pago de Dividendos"
    assert context["summary"]["type_breakdown"][0]["count"] == 2
    assert context["rows"][0]["execution_label"] == "Multiples fills"
    assert context["rows"][1]["detail_status_label"] == "Solo local"


@pytest.mark.django_db
def test_normalize_operation_filters_accepts_internal_and_explicit_keys():
    filters = normalize_operation_filters(
        {
            "filtro.numero": "123",
            "estado": "terminada",
            "fechaDesde": "2026-03-01",
            "fecha_hasta": "2026-03-21",
            "filtro.pais": "estados_Unidos",
        }
    )

    assert filters == {
        "numero": "123",
        "estado": "terminada",
        "fecha_desde": "2026-03-01",
        "fecha_hasta": "2026-03-21",
        "pais": "estados_Unidos",
    }


@pytest.mark.django_db
def test_apply_operation_filters_filters_by_number_state_and_dates():
    OperacionIOL.objects.create(
        numero="167788363",
        pais_consulta="estados_Unidos",
        fecha_orden=timezone.now(),
        tipo="Compra",
        estado="Terminada",
        estado_actual="terminada",
        mercado="BCBA",
        simbolo="MELI",
        modalidad="precio_Mercado",
    )
    OperacionIOL.objects.create(
        numero="167700000",
        pais_consulta="argentina",
        fecha_orden=timezone.now() - timezone.timedelta(days=10),
        tipo="Compra",
        estado="Pendiente",
        mercado="BCBA",
        simbolo="GGAL",
        modalidad="precio_Mercado",
    )

    filters = {
        "numero": "167788",
        "estado": "terminada",
        "fecha_desde": (timezone.now() - timezone.timedelta(days=2)).date().isoformat(),
        "fecha_hasta": timezone.now().date().isoformat(),
        "pais": "estados_Unidos",
    }
    filtered = apply_operation_filters(OperacionIOL.objects.all(), filters)

    assert list(filtered.values_list("numero", flat=True)) == ["167788363"]


def test_build_operation_filter_context_tracks_active_filters():
    context = build_operation_filter_context(
        {
            "numero": "167788363",
            "estado": "terminada",
            "fecha_desde": "",
            "fecha_hasta": "2026-03-21",
            "pais": "estados_Unidos",
        }
    )

    assert context["has_active_filters"] is True
    assert context["active_count"] == 4
    assert "numero=167788363" in context["query_string"]
    assert "estado=terminada" in context["query_string"]
    assert "pais=estados_Unidos" in context["query_string"]


@pytest.mark.django_db
def test_get_operation_subset_for_detail_enrichment_returns_only_current_page_missing_detail():
    for index in range(30):
        payload = {
            "numero": f"OP-{index:02d}",
            "fecha_orden": timezone.now() - timezone.timedelta(minutes=index),
            "tipo": "Compra",
            "estado": "Terminada",
            "mercado": "BCBA",
            "simbolo": f"SYM{index:02d}",
            "modalidad": "precio_Mercado",
        }
        if index == 0:
            payload["moneda"] = "peso_Argentino"
        OperacionIOL.objects.create(**payload)

    queryset = OperacionIOL.objects.all()
    subset_page_1 = get_operation_subset_for_detail_enrichment(queryset, page_number=1, page_size=25)
    subset_page_2 = get_operation_subset_for_detail_enrichment(queryset, page_number=2, page_size=25)

    assert len(subset_page_1) == 24
    assert all(not operacion.moneda for operacion in subset_page_1)
    assert len(subset_page_2) == 5


@pytest.mark.django_db
def test_get_operation_subset_for_country_backfill_returns_only_current_page_missing_country():
    for index in range(30):
        payload = {
            "numero": f"OPC-{index:02d}",
            "fecha_orden": timezone.now() - timezone.timedelta(minutes=index),
            "tipo": "Compra",
            "estado": "Terminada",
            "mercado": "BCBA",
            "simbolo": f"SYM{index:02d}",
            "modalidad": "precio_Mercado",
        }
        if index == 0:
            payload["pais_consulta"] = "argentina"
        OperacionIOL.objects.create(**payload)

    queryset = OperacionIOL.objects.all()
    subset_page_1 = get_operation_subset_for_country_backfill(queryset, page_number=1, page_size=25)
    subset_page_2 = get_operation_subset_for_country_backfill(queryset, page_number=2, page_size=25)

    assert len(subset_page_1) == 24
    assert all(not operacion.pais_consulta for operacion in subset_page_1)
    assert len(subset_page_2) == 5
