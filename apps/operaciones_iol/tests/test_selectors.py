from decimal import Decimal

import pytest
from django.utils import timezone

from apps.core.models import SensitiveActionAudit
from apps.operaciones_iol.models import OperacionIOL
from apps.operaciones_iol.selectors import (
    apply_operation_filters,
    build_operation_audit_summary_context,
    build_operation_execution_analytics_context,
    build_operation_filter_context,
    build_operation_list_context,
    build_operation_universe_coverage_context,
    get_operation_subset_for_country_backfill,
    get_operation_subset_for_detail_enrichment,
    normalize_operation_filters,
)


@pytest.mark.django_db
def test_build_operation_list_context_summarizes_detail_fills_and_fees():
    OperacionIOL.objects.create(
        numero="OP-1",
        pais_consulta="argentina",
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
        pais_consulta="estados_Unidos",
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
    assert context["summary"]["country_resolved_count"] == 2
    assert context["summary"]["country_missing_count"] == 1
    assert context["summary"]["country_resolved_pct"] == Decimal("66.67")
    assert context["summary"]["country_argentina_count"] == 1
    assert context["summary"]["country_estados_unidos_count"] == 1
    assert context["summary"]["fills_count"] == 1
    assert context["summary"]["fragmented_count"] == 1
    assert context["summary"]["fragmented_pct"] == Decimal("100.00")
    assert context["summary"]["fees_visible_count"] == 2
    assert context["summary"]["fees_visible_pct"] == Decimal("66.67")
    assert context["summary"]["fees_ars_total"] == Decimal("523.89")
    assert context["summary"]["fees_usd_total"] == Decimal("0.15")
    assert context["summary"]["type_breakdown"][0]["tipo"] == "Pago de Dividendos"
    assert context["summary"]["type_breakdown"][0]["count"] == 2
    assert context["rows"][0]["country_label"] == "Argentina"
    assert context["rows"][1]["country_label"] == "Estados Unidos"
    assert context["rows"][2]["country_label"] == "Pendiente"
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


def test_normalize_operation_filters_falls_back_for_invalid_state_and_country():
    filters = normalize_operation_filters(
        {
            "numero": "",
            "estado": "desconocido",
            "fechaDesde": "",
            "fechaHasta": None,
            "pais": "brasil",
        }
    )

    assert filters == {
        "numero": "",
        "estado": "todas",
        "fecha_desde": "",
        "fecha_hasta": "",
        "pais": "argentina",
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


def test_build_operation_filter_context_omits_default_filters_from_query_string():
    context = build_operation_filter_context({})

    assert context["has_active_filters"] is False
    assert context["active_count"] == 0
    assert context["query_string"] == ""


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


@pytest.mark.django_db
def test_build_operation_universe_coverage_context_summarizes_filtered_universe():
    OperacionIOL.objects.create(
        numero="HIST-1",
        pais_consulta="argentina",
        fecha_orden=timezone.now(),
        tipo="Compra",
        estado="Terminada",
        estado_actual="terminada",
        mercado="BCBA",
        simbolo="MELI",
        modalidad="precio_Mercado",
        moneda="peso_Argentino",
    )
    OperacionIOL.objects.create(
        numero="HIST-2",
        pais_consulta="estados_Unidos",
        fecha_orden=timezone.now(),
        tipo="Compra",
        estado="Terminada",
        mercado="BCBA",
        simbolo="SPY",
        modalidad="precio_Mercado",
    )
    OperacionIOL.objects.create(
        numero="HIST-3",
        fecha_orden=timezone.now(),
        tipo="Compra",
        estado="Terminada",
        mercado="BCBA",
        simbolo="GGAL",
        modalidad="precio_Mercado",
    )

    context = build_operation_universe_coverage_context(OperacionIOL.objects.order_by("numero"))

    assert context["total_count"] == 3
    assert context["detail_count"] == 1
    assert context["detail_missing_count"] == 2
    assert context["detail_pct"] == Decimal("33.33")
    assert context["country_count"] == 2
    assert context["country_missing_count"] == 1
    assert context["country_pct"] == Decimal("66.67")
    assert context["country_argentina_count"] == 1
    assert context["country_estados_unidos_count"] == 1


@pytest.mark.django_db
def test_build_operation_execution_analytics_context_summarizes_cost_and_fragmentation():
    OperacionIOL.objects.create(
        numero="EXEC-1",
        fecha_orden=timezone.now(),
        tipo="Compra",
        estado="Terminada",
        mercado="BCBA",
        simbolo="MELI",
        modalidad="precio_Mercado",
        monto_operacion=Decimal("78720"),
        aranceles_ars=Decimal("523.89"),
        operaciones_detalle=[
            {"fecha": "2026-03-18T14:05:57", "cantidad": 2, "precio": 19680},
            {"fecha": "2026-03-18T14:05:58", "cantidad": 2, "precio": 19680},
        ],
    )
    OperacionIOL.objects.create(
        numero="EXEC-2",
        fecha_orden=timezone.now(),
        tipo="Pago de Dividendos",
        estado="Terminada",
        mercado="BCBA",
        simbolo="MCD US$",
        modalidad="precio_Mercado",
        monto_operado=Decimal("0.15"),
        aranceles_usd=Decimal("0.01"),
        operaciones_detalle=[
            {"fecha": "2026-03-18T13:56:58.353", "cantidad": 1, "precio": 0.15},
        ],
    )
    OperacionIOL.objects.create(
        numero="EXEC-3",
        fecha_orden=timezone.now(),
        tipo="Compra",
        estado="Terminada",
        mercado="BCBA",
        simbolo="GGAL",
        modalidad="precio_Mercado",
    )

    context = build_operation_execution_analytics_context(OperacionIOL.objects.order_by("numero"))

    assert context["total_count"] == 3
    assert context["fee_visible_count"] == 2
    assert context["fee_visible_pct"] == Decimal("66.67")
    assert context["fees_ars_total"] == Decimal("523.89")
    assert context["fees_usd_total"] == Decimal("0.01")
    assert context["fills_visible_count"] == 2
    assert context["fragmented_count"] == 1
    assert context["fragmented_pct"] == Decimal("50.00")
    assert context["avg_fills_per_visible"] == Decimal("1.50")
    assert context["executed_amount_total"] == Decimal("78720.15")
    assert context["executed_amount_visible_count"] == 2
    assert context["fee_over_visible_amount_pct"] == Decimal("0.67")
    assert context["observed_cost_status"] == "watch"
    assert context["observed_cost_label"] == "Costo a vigilar"
    assert context["type_groups"][0]["label"] in {"Compras", "Dividendos"}


@pytest.mark.django_db
def test_build_operation_execution_analytics_context_groups_by_operation_family():
    OperacionIOL.objects.create(
        numero="TYPE-1",
        fecha_orden=timezone.now(),
        tipo="Compra",
        estado="Terminada",
        mercado="BCBA",
        simbolo="MELI",
        modalidad="precio_Mercado",
        monto_operacion=Decimal("100"),
        aranceles_ars=Decimal("1.50"),
        operaciones_detalle=[{"fecha": "2026-03-18T14:05:57", "cantidad": 1, "precio": 100}],
    )
    OperacionIOL.objects.create(
        numero="TYPE-2",
        fecha_orden=timezone.now(),
        tipo="Venta",
        estado="Terminada",
        mercado="BCBA",
        simbolo="GGAL",
        modalidad="precio_Mercado",
        monto_operacion=Decimal("50"),
        aranceles_ars=Decimal("0.50"),
    )
    OperacionIOL.objects.create(
        numero="TYPE-3",
        fecha_orden=timezone.now(),
        tipo="Pago de Dividendos",
        estado="Terminada",
        mercado="BCBA",
        simbolo="MCD US$",
        modalidad="precio_Mercado",
        monto_operado=Decimal("0.15"),
        aranceles_usd=Decimal("0.01"),
    )
    OperacionIOL.objects.create(
        numero="TYPE-4",
        fecha_orden=timezone.now(),
        tipo="Suscripci??n FCI",
        estado="Terminada",
        mercado="BCBA",
        simbolo="PRPEDOB",
        modalidad="precio_Mercado",
        monto=Decimal("9.19"),
    )

    context = build_operation_execution_analytics_context(OperacionIOL.objects.order_by("numero"))
    groups = {item["key"]: item for item in context["type_groups"]}

    assert groups["buy_trade"]["label"] == "Compras"
    assert groups["buy_trade"]["count"] == 1
    assert groups["buy_trade"]["executed_amount_total"] == Decimal("100")
    assert groups["buy_trade"]["avg_visible_amount"] == Decimal("100.00")
    assert groups["buy_trade"]["fee_visible_pct"] == Decimal("100.00")
    assert groups["buy_trade"]["fills_visible_pct"] == Decimal("100.00")
    assert groups["buy_trade"]["avg_fills_per_visible"] == Decimal("1.00")
    assert groups["buy_trade"]["fee_over_visible_amount_pct"] == Decimal("1.50")
    assert groups["buy_trade"]["fragmented_pct"] == Decimal("0.00")
    assert groups["sell_trade"]["label"] == "Ventas"
    assert groups["sell_trade"]["count"] == 1
    assert groups["sell_trade"]["executed_amount_total"] == Decimal("50")
    assert groups["sell_trade"]["avg_visible_amount"] == Decimal("50.00")
    assert groups["sell_trade"]["fee_visible_pct"] == Decimal("100.00")
    assert groups["sell_trade"]["fills_visible_pct"] == Decimal("0.00")
    assert groups["sell_trade"]["fee_over_visible_amount_pct"] == Decimal("1.00")
    assert groups["sell_trade"]["fragmented_pct"] == Decimal("0.00")
    assert groups["dividend"]["label"] == "Dividendos"
    assert groups["dividend"]["fees_usd_total"] == Decimal("0.01")
    assert groups["dividend"]["avg_visible_amount"] == Decimal("0.15")
    assert groups["dividend"]["fee_visible_pct"] == Decimal("100.00")
    assert groups["dividend"]["fills_visible_pct"] == Decimal("0.00")
    assert groups["dividend"]["fee_over_visible_amount_pct"] == Decimal("6.67")
    assert groups["fci_flow"]["label"] == "Flujos FCI"
    assert groups["fci_flow"]["executed_amount_total"] == Decimal("9.19")
    assert groups["fci_flow"]["avg_visible_amount"] == Decimal("9.19")
    assert groups["fci_flow"]["fee_visible_pct"] == Decimal("0.00")
    assert groups["fci_flow"]["fills_visible_pct"] == Decimal("0.00")
    assert groups["fci_flow"]["fee_over_visible_amount_pct"] == Decimal("0.00")


@pytest.mark.django_db
def test_build_operation_execution_analytics_context_tracks_fragmentation_inside_trade_families():
    OperacionIOL.objects.create(
        numero="FRAG-BUY-1",
        fecha_orden=timezone.now(),
        tipo="Compra",
        estado="Terminada",
        mercado="BCBA",
        simbolo="MELI",
        modalidad="precio_Mercado",
        monto_operacion=Decimal("100"),
        aranceles_ars=Decimal("1.00"),
        operaciones_detalle=[
            {"fecha": "2026-03-18T14:05:57", "cantidad": 1, "precio": 50},
            {"fecha": "2026-03-18T14:05:58", "cantidad": 1, "precio": 50},
        ],
    )
    OperacionIOL.objects.create(
        numero="FRAG-BUY-2",
        fecha_orden=timezone.now(),
        tipo="Compra",
        estado="Terminada",
        mercado="BCBA",
        simbolo="GGAL",
        modalidad="precio_Mercado",
        monto_operacion=Decimal("200"),
        aranceles_ars=Decimal("2.00"),
        operaciones_detalle=[
            {"fecha": "2026-03-18T14:06:00", "cantidad": 2, "precio": 100},
        ],
    )
    OperacionIOL.objects.create(
        numero="FRAG-SELL-1",
        fecha_orden=timezone.now(),
        tipo="Venta",
        estado="Terminada",
        mercado="BCBA",
        simbolo="SPY",
        modalidad="precio_Mercado",
        monto_operacion=Decimal("50"),
        aranceles_ars=Decimal("0.50"),
        operaciones_detalle=[
            {"fecha": "2026-03-18T14:07:00", "cantidad": 1, "precio": 25},
            {"fecha": "2026-03-18T14:07:01", "cantidad": 1, "precio": 25},
        ],
    )

    context = build_operation_execution_analytics_context(OperacionIOL.objects.order_by("numero"))
    groups = {item["key"]: item for item in context["type_groups"]}

    assert groups["buy_trade"]["count"] == 2
    assert groups["buy_trade"]["fills_visible_count"] == 2
    assert groups["buy_trade"]["fragmented_count"] == 1
    assert groups["buy_trade"]["fragmented_pct"] == Decimal("50.00")
    assert groups["buy_trade"]["avg_fills_per_visible"] == Decimal("1.50")
    assert groups["buy_trade"]["fee_over_visible_amount_pct"] == Decimal("1.00")
    assert groups["sell_trade"]["fragmented_count"] == 1
    assert groups["sell_trade"]["fragmented_pct"] == Decimal("100.00")


@pytest.mark.django_db
def test_build_operation_list_context_handles_single_fill_unknown_status_and_other_type():
    OperacionIOL.objects.create(
        numero="OTHER-1",
        pais_consulta="argentina",
        fecha_orden=timezone.now(),
        tipo="Transferencia interna",
        estado="Desconocido",
        mercado="BCBA",
        simbolo="CASH",
        modalidad="precio_Mercado",
        moneda="peso_Argentino",
        operaciones_detalle=[{"fecha": "2026-03-18T14:05:57", "cantidad": 1, "precio": 100}],
    )

    context = build_operation_list_context(OperacionIOL.objects.all())
    row = context["rows"][0]

    assert row["execution_label"] == "Fill unico"
    assert row["status_tone"] == "secondary"
    assert context["summary"]["type_breakdown"][0]["tipo"] == "Transferencia interna"
    assert context["summary"]["type_breakdown"][0]["pct"] == Decimal("100.00")


@pytest.mark.django_db
def test_build_operation_audit_summary_context_returns_latest_rows_per_action(django_user_model):
    user = django_user_model.objects.create_user(username="audit-ops-user", password="testpass123")
    SensitiveActionAudit.objects.create(
        user=user,
        action="sync_operaciones_filtered",
        status="failed",
        details={"page": "1"},
    )
    SensitiveActionAudit.objects.create(
        user=user,
        action="sync_operaciones_filtered",
        status="success",
        details={"page": "2"},
    )
    SensitiveActionAudit.objects.create(
        user=user,
        action="enrich_operaciones_filtered_details",
        status="success",
        details={"selected_count": 3},
    )

    context = build_operation_audit_summary_context()

    assert context["summary"]["tracked_count"] == 3
    assert context["summary"]["success_count"] == 2
    assert context["summary"]["failed_count"] == 0
    assert context["summary"]["missing_count"] == 1
    assert context["rows"][0]["action"] == "sync_operaciones_filtered"
    assert context["rows"][0]["status"] == "success"
    assert context["rows"][0]["user_label"] == "audit-ops-user"
    assert context["rows"][0]["filters_label"] == "Sin filtros activos"
    assert context["rows"][0]["summary_label"] == "Sync remoto ejecutado con los filtros visibles"
    assert context["rows"][1]["action"] == "enrich_operaciones_filtered_details"
    assert context["rows"][1]["status_label"] == "OK"
    assert context["rows"][1]["summary_label"] == "Seleccionadas 3 · enriquecidas 0"
    assert context["rows"][2]["action"] == "backfill_operaciones_filtered_country"
    assert context["rows"][2]["status"] == "missing"
    assert context["rows"][2]["created_at_label"] == "Sin registros"


@pytest.mark.django_db
def test_build_operation_audit_summary_context_formats_filters_and_failures(django_user_model):
    user = django_user_model.objects.create_user(username="audit-ops-user-2", password="testpass123")
    SensitiveActionAudit.objects.create(
        user=user,
        action="enrich_operaciones_filtered_details",
        status="failed",
        details={
            "filters": {
                "numero": "167788363",
                "estado": "terminada",
                "pais": "estados_Unidos",
                "fecha_desde": "2026-03-01",
                "fecha_hasta": "2026-03-21",
            },
            "selected_count": 2,
            "success_count": 1,
            "failed_numbers": ["A", "B", "C", "D"],
        },
    )

    context = build_operation_audit_summary_context()
    enrich_row = next(row for row in context["rows"] if row["action"] == "enrich_operaciones_filtered_details")

    assert "Numero 167788363" in enrich_row["filters_label"]
    assert "Estado terminada" in enrich_row["filters_label"]
    assert "Pais estados_Unidos" in enrich_row["filters_label"]
    assert "Fechas 2026-03-01 a 2026-03-21" in enrich_row["filters_label"]
    assert enrich_row["summary_label"] == "Seleccionadas 2 · enriquecidas 1"
    assert enrich_row["failed_items_label"] == "Fallidas: A, B, C"
@pytest.mark.django_db
def test_build_operation_audit_summary_context_covers_backfill_failures_and_limit():
    SensitiveActionAudit.objects.create(
        action="sync_operaciones_filtered",
        status="success",
        details={"filters": {"estado": "todas"}},
    )
    SensitiveActionAudit.objects.create(
        action="enrich_operaciones_filtered_details",
        status="success",
        details={"selected_count": 2, "success_count": 2},
    )
    SensitiveActionAudit.objects.create(
        action="backfill_operaciones_filtered_country",
        status="failed",
        details={
            "selected_count": 4,
            "resolved_count": 1,
            "unresolved_numbers": ["OP-1", "OP-2", "OP-3", "OP-4"],
        },
    )

    context = build_operation_audit_summary_context(limit=3)

    assert context["summary"]["tracked_count"] == 3
    assert context["summary"]["success_count"] == 2
    assert context["summary"]["failed_count"] == 1
    backfill_row = next(row for row in context["rows"] if row["action"] == "backfill_operaciones_filtered_country")
    assert backfill_row["user_label"] == "system"
    assert "Seleccionadas 4" in backfill_row["summary_label"]
    assert "resueltas 1" in backfill_row["summary_label"]
    assert backfill_row["failed_items_label"] == "Sin resolver: OP-1, OP-2, OP-3"
