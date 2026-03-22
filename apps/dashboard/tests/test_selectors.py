from django.test import TestCase
from decimal import Decimal
from datetime import timedelta
from unittest.mock import ANY, patch
from django.core.cache import cache
from django.db import connection
from django.test import override_settings
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.dashboard.selectors import (
    _build_portfolio_scope_summary,
    get_analytics_mensual,
    get_analytics_v2_dashboard_summary,
    get_concentracion_pais,
    get_concentracion_moneda,
    get_concentracion_moneda_operativa,
    get_concentracion_sector,
    get_concentracion_sector_agregado,
    get_concentracion_tipo_patrimonial,
    get_dashboard_kpis,
    get_distribucion_moneda,
    get_distribucion_moneda_operativa,
    get_distribucion_pais,
    get_distribucion_sector,
    get_distribucion_tipo_patrimonial,
    get_evolucion_historica,
    get_expected_return_detail,
    get_factor_exposure_detail,
    get_incremental_portfolio_simulation,
    get_incremental_portfolio_simulation_comparison,
    get_liquidity_contract_summary,
    get_market_snapshot_feature_context,
    get_market_snapshot_history_feature_context,
    get_portfolio_parking_feature_context,
    get_decision_engine_summary,
    get_candidate_incremental_portfolio_comparison,
    get_preferred_incremental_portfolio_proposal,
    get_incremental_proposal_history,
    get_incremental_proposal_tracking_baseline,
    get_incremental_manual_decision_summary,
    get_incremental_pending_backlog_vs_baseline,
    get_incremental_backlog_prioritization,
    get_incremental_backlog_front_summary,
    get_incremental_backlog_operational_semaphore,
    get_incremental_decision_executive_summary,
    get_planeacion_incremental_context,
    get_incremental_baseline_drift,
    get_incremental_followup_executive_summary,
    get_incremental_adoption_checklist,
    get_candidate_split_incremental_portfolio_comparison,
    get_manual_incremental_portfolio_simulation_comparison,
    get_candidate_asset_ranking,
    get_monthly_allocation_plan,
    get_portafolio_enriquecido_actual,
    get_risk_contribution_detail,
    get_scenario_analysis_detail,
    get_stress_fragility_detail,
    get_riesgo_portafolio,
    get_snapshot_coverage_summary,
    get_riesgo_portafolio_detallado,
    get_senales_rebalanceo,
)
from apps.parametros.models import ParametroActivo
from apps.operaciones_iol.models import OperacionIOL
from apps.portafolio_iol.models import ActivoPortafolioSnapshot
from apps.resumen_iol.models import ResumenCuentaSnapshot
from apps.core.models import IOLMarketSnapshotObservation


def make_activo(fecha, simbolo, valorizado, tipo='ACCIONES', moneda='ARS', **kwargs):
    """Factory helper para crear ActivoPortafolioSnapshot en tests."""
    defaults = dict(
        fecha_extraccion=fecha,
        pais_consulta='argentina',
        simbolo=simbolo,
        descripcion=f'Descripcion {simbolo}',
        cantidad=10,
        comprometido=0,
        disponible_inmediato=10,
        puntos_variacion=0,
        variacion_diaria=0,
        ultimo_precio=valorizado,
        ppc=valorizado,
        ganancia_porcentaje=0,
        ganancia_dinero=0,
        valorizado=valorizado,
        pais_titulo='Argentina',
        mercado='BCBA',
        tipo=tipo,
        moneda=moneda,
    )
    defaults.update(kwargs)
    return ActivoPortafolioSnapshot.objects.create(**defaults)


def make_resumen(fecha, moneda='ARS', disponible=1000.00, **kwargs):
    """Factory helper para crear ResumenCuentaSnapshot en tests."""
    defaults = dict(
        fecha_extraccion=fecha,
        numero_cuenta='123',
        tipo_cuenta='CA',
        moneda=moneda,
        disponible=disponible,
        comprometido=0,
        saldo=disponible,
        titulos_valorizados=0,
        total=disponible,
        total_en_pesos=None,
        saldos_detalle=[],
        estado='activa',
    )
    defaults.update(kwargs)
    return ResumenCuentaSnapshot.objects.create(**defaults)


class TestDashboardSelectors(TestCase):
    def test_get_portfolio_parking_feature_context_summarizes_visible_parking(self):
        fecha = timezone.now()
        make_activo(fecha, "AL30", Decimal("1000"), tipo="TitulosPublicos", parking={"cantidad": 5, "fecha": "2026-03-25"})
        make_activo(fecha, "MELI", Decimal("5000"), tipo="CEDEARS", parking=None)
        make_activo(fecha, "ADBAICA", Decimal("3000"), tipo="FondoComundeInversion", parking={"detalle": "Bloqueado"})

        context = get_portfolio_parking_feature_context(top_limit=5)

        assert context["has_visible_parking"] is True
        assert context["summary"]["total_positions"] == 3
        assert context["summary"]["parking_count"] == 2
        assert context["summary"]["parking_pct"] == Decimal("66.67")
        assert context["summary"]["parking_value_total"] == Decimal("4000")
        assert len(context["top_rows"]) == 2
        assert context["top_rows"][0]["activo"].simbolo == "ADBAICA"
        assert context["parking_blocks"][0]["label"] == "N/A"
        assert context["alerts"][0]["tone"] == "warning"

    def test_get_decision_engine_summary_adds_parking_signal_to_mode_decision(self):
        class DummyUser:
            pk = 7

        cache.clear()

        with (
            patch("apps.dashboard.selectors._build_portfolio_scope_summary", return_value={"cash_ratio_total": 0.35, "invested_ratio_total": 0.60}),
            patch("apps.dashboard.selectors.get_macro_local_context", return_value={}),
            patch("apps.dashboard.selectors.get_analytics_v2_dashboard_summary", return_value={}),
            patch("apps.dashboard.selectors.get_monthly_allocation_plan", return_value={"recommended_blocks": []}),
            patch("apps.dashboard.selectors.get_candidate_asset_ranking", return_value={"candidate_assets": []}),
            patch("apps.dashboard.selectors.get_preferred_incremental_portfolio_proposal", return_value={"preferred": None}),
            patch("apps.dashboard.selectors.get_incremental_portfolio_simulation", return_value={"delta": {}, "interpretation": ""}),
            patch(
                "apps.dashboard.selectors.get_portfolio_parking_feature_context",
                return_value={
                    "has_visible_parking": True,
                    "summary": {
                        "parking_count": 2,
                        "parking_value_total": Decimal("450000"),
                    },
                    "top_rows": [],
                    "alerts": [],
                },
            ),
        ):
            detail = get_decision_engine_summary(DummyUser(), query_params={}, capital_amount=600000)

        assert detail["parking_signal"]["has_signal"] is True
        assert detail["execution_gate"]["has_blocker"] is True
        assert detail["execution_gate"]["status"] == "review_parking"
        assert detail["execution_gate"]["primary_cta_label"] == "Revisar antes de ejecutar"
        assert detail["parking_signal"]["parking_count"] == 2
        assert "parking visible" in detail["parking_signal"]["summary"].lower()
        assert any(item["type"] == "parking" for item in detail["action_suggestions"])
        assert any("parking visible" in bullet.lower() for bullet in detail["explanation"])

    def test_get_decision_engine_summary_conditions_recommendation_when_parking_overlaps_block(self):
        class DummyUser:
            pk = 8

        cache.clear()

        with (
            patch("apps.dashboard.selectors._build_portfolio_scope_summary", return_value={"cash_ratio_total": 0.35, "invested_ratio_total": 0.60}),
            patch("apps.dashboard.selectors.get_macro_local_context", return_value={}),
            patch("apps.dashboard.selectors.get_analytics_v2_dashboard_summary", return_value={}),
            patch(
                "apps.dashboard.selectors.get_monthly_allocation_plan",
                return_value={
                    "recommended_blocks": [
                        {"label": "Defensive / resiliente", "suggested_amount": 600000, "reason": "Se prioriza resiliencia."}
                    ]
                },
            ),
            patch("apps.dashboard.selectors.get_candidate_asset_ranking", return_value={"candidate_assets": []}),
            patch("apps.dashboard.selectors.get_preferred_incremental_portfolio_proposal", return_value={"preferred": None}),
            patch("apps.dashboard.selectors.get_incremental_portfolio_simulation", return_value={"delta": {}, "interpretation": ""}),
            patch(
                "apps.dashboard.selectors.get_portfolio_parking_feature_context",
                return_value={
                    "has_visible_parking": True,
                    "summary": {"parking_count": 1, "parking_value_total": Decimal("120000")},
                    "parking_blocks": [{"label": "Defensive / resiliente", "value_total": Decimal("120000")}],
                    "top_rows": [],
                    "alerts": [],
                },
            ),
        ):
            detail = get_decision_engine_summary(DummyUser(), query_params={}, capital_amount=600000)

        assert detail["recommendation"]["has_recommendation"] is True
        assert detail["recommendation"]["is_conditioned_by_parking"] is True
        assert detail["recommendation"]["priority_label"] == "Condicionada"
        assert "parking visible dentro de este mismo bloque" in detail["recommendation"]["reason"]

    def test_get_decision_engine_summary_conditions_recommendation_when_market_history_overlaps_block(self):
        class DummyUser:
            pk = 8_1

        cache.clear()

        with (
            patch("apps.dashboard.selectors._build_portfolio_scope_summary", return_value={"cash_ratio_total": 0.35, "invested_ratio_total": 0.60}),
            patch("apps.dashboard.selectors.get_macro_local_context", return_value={}),
            patch("apps.dashboard.selectors.get_analytics_v2_dashboard_summary", return_value={}),
            patch(
                "apps.dashboard.selectors.get_monthly_allocation_plan",
                return_value={
                    "recommended_blocks": [
                        {"label": "Growth USA", "suggested_amount": 600000, "reason": "Se prioriza crecimiento."}
                    ]
                },
            ),
            patch("apps.dashboard.selectors.get_candidate_asset_ranking", return_value={"candidate_assets": []}),
            patch("apps.dashboard.selectors.get_preferred_incremental_portfolio_proposal", return_value={"preferred": None}),
            patch("apps.dashboard.selectors.get_incremental_portfolio_simulation", return_value={"delta": {}, "interpretation": ""}),
            patch("apps.dashboard.selectors.get_portfolio_parking_feature_context", return_value={"has_visible_parking": False, "summary": {}, "parking_blocks": [], "top_rows": [], "alerts": []}),
            patch(
                "apps.dashboard.selectors.get_market_snapshot_history_feature_context",
                return_value={
                    "summary": {"weak_count": 1},
                    "rows": [{"simbolo": "MELI", "bloque_estrategico": "Growth USA", "quality_status": "weak"}],
                    "weak_blocks": [{"label": "Growth USA", "value_total": Decimal("900000")}],
                    "alerts": [],
                    "has_history": True,
                    "lookback_days": 7,
                },
            ),
        ):
            detail = get_decision_engine_summary(DummyUser(), query_params={}, capital_amount=600000)

        assert detail["recommendation"]["has_recommendation"] is True
        assert detail["recommendation"]["is_conditioned_by_parking"] is False
        assert detail["recommendation"]["is_conditioned_by_market_history"] is True
        assert detail["recommendation"]["priority_label"] == "Condicionada"
        assert "liquidez reciente de este bloque viene debil" in detail["recommendation"]["reason"].lower()

    def test_get_decision_engine_summary_promotes_clean_recommendation_when_primary_block_has_weak_liquidity(self):
        class DummyUser:
            pk = 8_2

        cache.clear()

        with (
            patch("apps.dashboard.selectors._build_portfolio_scope_summary", return_value={"cash_ratio_total": 0.35, "invested_ratio_total": 0.60}),
            patch("apps.dashboard.selectors.get_macro_local_context", return_value={}),
            patch("apps.dashboard.selectors.get_analytics_v2_dashboard_summary", return_value={}),
            patch(
                "apps.dashboard.selectors.get_monthly_allocation_plan",
                return_value={
                    "recommended_blocks": [
                        {"label": "Growth USA", "suggested_amount": 350000, "reason": "Se prioriza crecimiento."},
                        {"label": "Indice global", "suggested_amount": 250000, "reason": "Mantiene beta amplia y liquidez mas limpia."},
                    ]
                },
            ),
            patch("apps.dashboard.selectors.get_candidate_asset_ranking", return_value={"candidate_assets": []}),
            patch("apps.dashboard.selectors.get_preferred_incremental_portfolio_proposal", return_value={"preferred": None}),
            patch("apps.dashboard.selectors.get_incremental_portfolio_simulation", return_value={"delta": {}, "interpretation": ""}),
            patch("apps.dashboard.selectors.get_portfolio_parking_feature_context", return_value={"has_visible_parking": False, "summary": {}, "parking_blocks": [], "top_rows": [], "alerts": []}),
            patch(
                "apps.dashboard.selectors.get_market_snapshot_history_feature_context",
                return_value={
                    "summary": {"weak_count": 1},
                    "rows": [{"simbolo": "MELI", "bloque_estrategico": "Growth USA", "quality_status": "weak"}],
                    "weak_blocks": [{"label": "Growth USA", "value_total": Decimal("900000")}],
                    "alerts": [],
                    "has_history": True,
                    "lookback_days": 7,
                },
            ),
        ):
            detail = get_decision_engine_summary(DummyUser(), query_params={}, capital_amount=600000)

        assert detail["recommendation"]["block"] == "Indice global"
        assert detail["recommendation"]["priority_label"] == "Repriorizada por liquidez reciente"
        assert detail["recommendation"]["was_reprioritized_by_market_history"] is True
        assert detail["recommendation"]["original_block_label"] == "Growth USA"
        assert "Growth USA" in detail["recommendation"]["reason"]

    def test_get_decision_engine_summary_conditions_suggested_assets_when_parking_overlaps_block(self):
        class DummyUser:
            pk = 9

        cache.clear()

        with (
            patch("apps.dashboard.selectors._build_portfolio_scope_summary", return_value={"cash_ratio_total": 0.35, "invested_ratio_total": 0.60}),
            patch("apps.dashboard.selectors.get_macro_local_context", return_value={}),
            patch("apps.dashboard.selectors.get_analytics_v2_dashboard_summary", return_value={}),
            patch("apps.dashboard.selectors.get_monthly_allocation_plan", return_value={"recommended_blocks": []}),
            patch(
                "apps.dashboard.selectors.get_candidate_asset_ranking",
                return_value={
                    "candidate_assets": [
                        {"asset": "KO", "block_label": "Defensive / resiliente", "score": 8.4, "main_reason": "defensive_sector_match"},
                        {"asset": "SPY", "block_label": "Indice global", "score": 7.2, "main_reason": "stable_global_exposure"},
                    ]
                },
            ),
            patch("apps.dashboard.selectors.get_preferred_incremental_portfolio_proposal", return_value={"preferred": None}),
            patch("apps.dashboard.selectors.get_incremental_portfolio_simulation", return_value={"delta": {}, "interpretation": ""}),
            patch(
                "apps.dashboard.selectors.get_portfolio_parking_feature_context",
                return_value={
                    "has_visible_parking": True,
                    "summary": {"parking_count": 1, "parking_value_total": Decimal("120000")},
                    "parking_blocks": [{"label": "Defensive / resiliente", "value_total": Decimal("120000")}],
                    "top_rows": [],
                    "alerts": [],
                },
            ),
        ):
            detail = get_decision_engine_summary(DummyUser(), query_params={}, capital_amount=600000)

        assert detail["suggested_assets"][0]["symbol"] == "SPY"
        assert detail["suggested_assets"][0]["is_conditioned_by_parking"] is False
        assert detail["suggested_assets"][1]["symbol"] == "KO"
        assert detail["suggested_assets"][1]["is_conditioned_by_parking"] is True
        assert detail["suggested_assets"][1]["priority_label"] == "Condicionado por parking"

    def test_get_decision_engine_summary_conditions_preferred_proposal_when_purchase_plan_overlaps_parking(self):
        class DummyUser:
            pk = 10

        cache.clear()
        ParametroActivo.objects.create(
            simbolo="KO",
            sector="Consumo",
            bloque_estrategico="Defensive / resiliente",
            pais_exposicion="USA",
            tipo_patrimonial="Equity",
        )

        with (
            patch("apps.dashboard.selectors._build_portfolio_scope_summary", return_value={"cash_ratio_total": 0.35, "invested_ratio_total": 0.60}),
            patch("apps.dashboard.selectors.get_macro_local_context", return_value={}),
            patch("apps.dashboard.selectors.get_analytics_v2_dashboard_summary", return_value={}),
            patch("apps.dashboard.selectors.get_monthly_allocation_plan", return_value={"recommended_blocks": []}),
            patch("apps.dashboard.selectors.get_candidate_asset_ranking", return_value={"candidate_assets": []}),
            patch(
                "apps.dashboard.selectors.get_preferred_incremental_portfolio_proposal",
                return_value={
                    "preferred": {
                        "proposal_label": "Plan KO",
                        "source_label": "Comparador manual",
                        "purchase_plan": [{"symbol": "KO", "amount": 600000}],
                    }
                },
            ),
            patch("apps.dashboard.selectors.get_incremental_portfolio_simulation", return_value={"delta": {}, "interpretation": ""}),
            patch(
                "apps.dashboard.selectors.get_portfolio_parking_feature_context",
                return_value={
                    "has_visible_parking": True,
                    "summary": {"parking_count": 1, "parking_value_total": Decimal("120000")},
                    "parking_blocks": [{"label": "Defensive / resiliente", "value_total": Decimal("120000")}],
                    "top_rows": [],
                    "alerts": [],
                },
            ),
        ):
            detail = get_decision_engine_summary(DummyUser(), query_params={}, capital_amount=600000)

        assert detail["preferred_proposal"]["is_conditioned_by_parking"] is True
        assert detail["preferred_proposal"]["priority_label"] == "Condicionada por parking"
        assert "conviene revisarla antes" in detail["preferred_proposal"]["parking_note"].lower()

    def test_get_decision_engine_summary_promotes_clean_preferred_alternative_when_conditioned_one_is_close(self):
        class DummyUser:
            pk = 11

        cache.clear()
        ParametroActivo.objects.create(
            simbolo="KO",
            sector="Consumo",
            bloque_estrategico="Defensive / resiliente",
            pais_exposicion="USA",
            tipo_patrimonial="Equity",
        )
        ParametroActivo.objects.create(
            simbolo="SPY",
            sector="Indice",
            bloque_estrategico="Indice global",
            pais_exposicion="USA",
            tipo_patrimonial="ETF",
        )

        with (
            patch("apps.dashboard.selectors._build_portfolio_scope_summary", return_value={"cash_ratio_total": 0.35, "invested_ratio_total": 0.60}),
            patch("apps.dashboard.selectors.get_macro_local_context", return_value={}),
            patch("apps.dashboard.selectors.get_analytics_v2_dashboard_summary", return_value={}),
            patch("apps.dashboard.selectors.get_monthly_allocation_plan", return_value={"recommended_blocks": []}),
            patch("apps.dashboard.selectors.get_candidate_asset_ranking", return_value={"candidate_assets": []}),
            patch(
                "apps.dashboard.selectors.get_preferred_incremental_portfolio_proposal",
                return_value={
                    "preferred": {
                        "proposal_key": "plan_ko",
                        "proposal_label": "Plan KO",
                        "source_label": "Comparador manual",
                        "purchase_plan": [{"symbol": "KO", "amount": 600000}],
                        "comparison_score": 4.60,
                        "priority_rank": 4,
                    },
                    "candidates": [
                        {
                            "proposal_key": "plan_ko",
                            "proposal_label": "Plan KO",
                            "source_label": "Comparador manual",
                            "purchase_plan": [{"symbol": "KO", "amount": 600000}],
                            "comparison_score": 4.60,
                            "priority_rank": 4,
                        },
                        {
                            "proposal_key": "plan_spy",
                            "proposal_label": "Plan SPY",
                            "source_label": "Comparador por candidato",
                            "purchase_plan": [{"symbol": "SPY", "amount": 600000}],
                            "comparison_score": 4.50,
                            "priority_rank": 2,
                        },
                    ],
                },
            ),
            patch("apps.dashboard.selectors.get_incremental_portfolio_simulation", return_value={"delta": {}, "interpretation": ""}),
            patch(
                "apps.dashboard.selectors.get_portfolio_parking_feature_context",
                return_value={
                    "has_visible_parking": True,
                    "summary": {"parking_count": 1, "parking_value_total": Decimal("120000")},
                    "parking_blocks": [{"label": "Defensive / resiliente", "value_total": Decimal("120000")}],
                    "top_rows": [],
                    "alerts": [],
                },
            ),
        ):
            detail = get_decision_engine_summary(DummyUser(), query_params={}, capital_amount=600000)

        assert detail["preferred_proposal"]["proposal_label"] == "Plan SPY"
        assert detail["preferred_proposal"]["is_conditioned_by_parking"] is False
        assert detail["preferred_proposal"]["was_reprioritized_by_parking"] is True
        assert detail["preferred_proposal"]["priority_label"] == "Repriorizada por parking"
        assert "se promovio esta alternativa" in detail["preferred_proposal"]["parking_note"].lower()

    def test_get_decision_engine_summary_degrades_score_and_confidence_when_parking_is_visible(self):
        class DummyUser:
            pk = 12

        cache.clear()
        ParametroActivo.objects.create(
            simbolo="SPY",
            sector="Indice",
            bloque_estrategico="Indice global",
            pais_exposicion="USA",
            tipo_patrimonial="ETF",
        )

        with (
            patch("apps.dashboard.selectors._build_portfolio_scope_summary", return_value={"cash_ratio_total": 0.35, "invested_ratio_total": 0.60}),
            patch("apps.dashboard.selectors.get_macro_local_context", return_value={"headline": "ok"}),
            patch(
                "apps.dashboard.selectors.get_analytics_v2_dashboard_summary",
                return_value={
                    "stress_testing": {"fragility_score": 40, "total_loss_pct": -10},
                    "expected_return": {"real_expected_return_pct": 5},
                    "risk_contribution": {"top_asset": {"contribution_pct": 0.10}},
                },
            ),
            patch(
                "apps.dashboard.selectors.get_monthly_allocation_plan",
                return_value={
                    "recommended_blocks": [{"label": "Indice global", "suggested_amount": 600000, "reason": "prioridad limpia"}]
                },
            ),
            patch(
                "apps.dashboard.selectors.get_candidate_asset_ranking",
                return_value={
                    "candidate_assets": [
                        {"asset": "SPY", "block_label": "Indice global", "score": 7.0, "main_reason": "stable_global_exposure"},
                    ]
                },
            ),
            patch(
                "apps.dashboard.selectors.get_preferred_incremental_portfolio_proposal",
                return_value={
                    "preferred": {
                        "proposal_key": "plan_spy",
                        "proposal_label": "Plan SPY",
                        "source_label": "Comparador manual",
                        "purchase_plan": [{"symbol": "SPY", "amount": 600000}],
                        "comparison_score": 4.8,
                        "priority_rank": 4,
                    },
                    "candidates": [
                        {
                            "proposal_key": "plan_spy",
                            "proposal_label": "Plan SPY",
                            "source_label": "Comparador manual",
                            "purchase_plan": [{"symbol": "SPY", "amount": 600000}],
                            "comparison_score": 4.8,
                            "priority_rank": 4,
                        }
                    ],
                },
            ),
            patch(
                "apps.dashboard.selectors.get_incremental_portfolio_simulation",
                return_value={
                    "delta": {
                        "expected_return_change": 0.4,
                        "fragility_change": -0.8,
                        "scenario_loss_change": 0.2,
                    },
                    "interpretation": "Impacto favorable.",
                },
            ),
            patch(
                "apps.dashboard.selectors.get_portfolio_parking_feature_context",
                return_value={
                    "has_visible_parking": True,
                    "summary": {"parking_count": 1, "parking_value_total": Decimal("100000")},
                    "parking_blocks": [{"label": "Defensive / resiliente", "value_total": Decimal("100000")}],
                    "top_rows": [],
                    "alerts": [],
                },
            ),
        ):
            detail = get_decision_engine_summary(DummyUser(), query_params={}, capital_amount=600000)

        assert detail["score"] == 79
        assert detail["confidence"] == "Baja"

    def test_get_market_snapshot_feature_context_uses_cached_payload_for_top_positions(self):
        fecha = timezone.now()
        make_activo(fecha, "MELI", Decimal("900000"), tipo="CEDEARS", mercado="BCBA")
        make_activo(fecha, "GGAL", Decimal("600000"), tipo="ACCIONES", mercado="BCBA")
        make_activo(fecha, "ADBAICA", Decimal("300000"), tipo="FondoComundeInversion", mercado="BCBA")

        cached_payload = {
            "rows": [
                {
                    "simbolo": "MELI",
                    "mercado": "BCBA",
                    "descripcion": "Cedear Mercadolibre Inc.",
                    "snapshot_status": "available",
                    "snapshot_source_key": "cotizacion_detalle",
                    "snapshot_source_label": "CotizacionDetalle",
                    "fecha_hora_label": "2026-03-21 10:00",
                    "ultimo_precio": Decimal("20080"),
                    "variacion": Decimal("-1.66"),
                    "cantidad_operaciones": 5341,
                    "puntas_count": 5,
                    "spread_abs": Decimal("860"),
                    "spread_pct": Decimal("4.29"),
                    "plazo": "t1",
                },
                {
                    "simbolo": "GGAL",
                    "mercado": "BCBA",
                    "descripcion": "Grupo Financiero Galicia",
                    "snapshot_status": "missing",
                    "snapshot_source_key": "",
                    "snapshot_source_label": "",
                    "snapshot_reason": "IOL no devolvio cotizacion puntual para el instrumento.",
                    "fecha_hora_label": "",
                    "ultimo_precio": None,
                    "variacion": None,
                    "cantidad_operaciones": 0,
                    "puntas_count": 0,
                    "spread_abs": None,
                    "spread_pct": None,
                    "plazo": "",
                },
            ],
            "summary": {
                "total_symbols": 2,
                "available_count": 1,
                "missing_count": 1,
                "unsupported_count": 0,
                "detail_count": 1,
                "fallback_count": 0,
                "order_book_count": 1,
                "overall_status": "partial",
            },
            "refreshed_at": "2026-03-21T10:00:00-03:00",
        }

        with patch(
            "apps.dashboard.selectors.IOLHistoricalPriceService.get_cached_current_portfolio_market_snapshot",
            return_value=cached_payload,
        ):
            context = get_market_snapshot_feature_context(top_limit=3)

        assert context["has_cached_snapshot"] is True
        assert context["refreshed_at_label"] == "2026-03-21 10:00"
        assert context["top_rows"][0]["simbolo"] == "MELI"
        assert context["top_rows"][0]["snapshot_status"] == "available"
        assert context["top_rows"][1]["simbolo"] == "GGAL"
        assert context["top_rows"][1]["snapshot_status"] == "missing"
        assert context["top_missing_count"] == 1
        assert context["wide_spread_count"] == 1
        assert any(alert["title"] == "Cobertura parcial en posiciones relevantes" for alert in context["alerts"])

    def test_get_market_snapshot_feature_context_handles_missing_cached_payload(self):
        with patch(
            "apps.dashboard.selectors.IOLHistoricalPriceService.get_cached_current_portfolio_market_snapshot",
            return_value=None,
        ):
            context = get_market_snapshot_feature_context(top_limit=3)

        assert context["has_cached_snapshot"] is False
        assert context["summary"]["total_symbols"] == 0
        assert context["top_rows"] == []
        assert context["alerts"][0]["title"] == "Snapshot puntual pendiente"

    def test_get_market_snapshot_history_feature_context_summarizes_recent_execution_quality(self):
        cache.clear()
        fecha = timezone.now()
        make_activo(fecha, "MELI", Decimal("900000"), tipo="CEDEARS", mercado="BCBA")
        ParametroActivo.objects.create(
            simbolo="MELI",
            sector="Tecnologia",
            bloque_estrategico="Growth USA",
            pais_exposicion="USA",
            tipo_patrimonial="Renta variable",
        )
        IOLMarketSnapshotObservation.objects.create(
            simbolo="MELI",
            mercado="BCBA",
            source_key="cotizacion_detalle",
            snapshot_status="available",
            captured_at=fecha - timedelta(days=1),
            captured_date=(fecha - timedelta(days=1)).date(),
            cantidad_operaciones=40,
            puntas_count=0,
            spread_pct=Decimal("2.20"),
        )
        IOLMarketSnapshotObservation.objects.create(
            simbolo="MELI",
            mercado="BCBA",
            source_key="cotizacion_detalle",
            snapshot_status="available",
            captured_at=fecha - timedelta(days=2),
            captured_date=(fecha - timedelta(days=2)).date(),
            cantidad_operaciones=60,
            puntas_count=1,
            spread_pct=Decimal("1.80"),
        )

        context = get_market_snapshot_history_feature_context(top_limit=3, lookback_days=7)

        assert context["has_history"] is True
        assert context["summary"]["weak_count"] == 1
        assert context["top_rows"][0]["simbolo"] == "MELI"
        assert context["top_rows"][0]["quality_status"] == "weak"
        assert context["weak_blocks"][0]["label"] == "Growth USA"

    def test_get_decision_engine_summary_adds_market_history_signal_when_recommendation_overlaps_weak_block(self):
        cache.clear()

        class DummyUser:
            pk = 1

        with (
            patch("apps.dashboard.selectors._build_portfolio_scope_summary", return_value={"cash_ratio_total": 20}),
            patch("apps.dashboard.selectors.get_macro_local_context", return_value={}),
            patch("apps.dashboard.selectors.get_analytics_v2_dashboard_summary", return_value={}),
            patch("apps.dashboard.selectors.get_monthly_allocation_plan", return_value={"recommended_blocks": []}),
            patch("apps.dashboard.selectors.get_candidate_asset_ranking", return_value={"candidate_assets": []}),
            patch("apps.dashboard.selectors.get_preferred_incremental_portfolio_proposal", return_value={"preferred": None}),
            patch("apps.dashboard.selectors.get_incremental_portfolio_simulation", return_value={"delta": {}, "interpretation": ""}),
            patch("apps.dashboard.selectors._build_decision_macro_state", return_value={"key": "normal", "label": "Normal", "summary": ""}),
            patch("apps.dashboard.selectors._build_decision_portfolio_state", return_value={"key": "ok", "label": "OK", "summary": ""}),
            patch("apps.dashboard.selectors.get_portfolio_parking_feature_context", return_value={"has_visible_parking": False, "summary": {}, "parking_blocks": [], "top_rows": [], "alerts": []}),
            patch(
                "apps.dashboard.selectors.get_market_snapshot_history_feature_context",
                return_value={
                    "summary": {"weak_count": 1},
                    "rows": [{"simbolo": "MELI", "bloque_estrategico": "Growth USA", "quality_status": "weak"}],
                    "weak_blocks": [{"label": "Growth USA", "value_total": Decimal("900000")}],
                    "alerts": [],
                    "has_history": True,
                    "lookback_days": 7,
                },
            ),
            patch(
                "apps.dashboard.selectors._build_decision_recommendation",
                return_value={
                    "block": "Growth USA",
                    "amount": 600000,
                    "reason": "prioridad simple",
                    "has_recommendation": True,
                    "priority_label": "Prioritaria",
                    "priority_tone": "success",
                },
            ),
            patch("apps.dashboard.selectors._build_decision_suggested_assets", return_value=[]),
            patch("apps.dashboard.selectors._build_decision_preferred_proposal", return_value=None),
            patch("apps.dashboard.selectors._build_decision_expected_impact", return_value={"status": "neutral", "summary": ""}),
            patch("apps.dashboard.selectors._build_decision_recommendation_context", return_value="high_cash"),
            patch("apps.dashboard.selectors._build_decision_strategy_bias", return_value="deploy_cash"),
            patch("apps.dashboard.selectors._build_decision_explanation", return_value=[]),
            patch("apps.dashboard.selectors._build_decision_tracking_payload", return_value={}),
        ):
            detail = get_decision_engine_summary(DummyUser(), query_params={}, capital_amount=600000)

        assert detail["market_history_signal"]["has_signal"] is True
        assert "Growth USA" in detail["market_history_signal"]["summary"]
        assert any(item["type"] == "market_history" for item in detail["action_suggestions"])

    def test_get_decision_engine_summary_conditions_suggested_assets_when_market_history_overlaps_block(self):
        class DummyUser:
            pk = 13

        cache.clear()

        with (
            patch("apps.dashboard.selectors._build_portfolio_scope_summary", return_value={"cash_ratio_total": 0.35, "invested_ratio_total": 0.60}),
            patch("apps.dashboard.selectors.get_macro_local_context", return_value={}),
            patch("apps.dashboard.selectors.get_analytics_v2_dashboard_summary", return_value={}),
            patch("apps.dashboard.selectors.get_monthly_allocation_plan", return_value={"recommended_blocks": []}),
            patch(
                "apps.dashboard.selectors.get_candidate_asset_ranking",
                return_value={
                    "candidate_assets": [
                        {"asset": "MELI", "block_label": "Growth USA", "score": 8.4, "main_reason": "growth_quality"},
                        {"asset": "SPY", "block_label": "Indice global", "score": 7.2, "main_reason": "stable_global_exposure"},
                    ]
                },
            ),
            patch("apps.dashboard.selectors.get_preferred_incremental_portfolio_proposal", return_value={"preferred": None}),
            patch("apps.dashboard.selectors.get_incremental_portfolio_simulation", return_value={"delta": {}, "interpretation": ""}),
            patch("apps.dashboard.selectors.get_portfolio_parking_feature_context", return_value={"has_visible_parking": False, "summary": {}, "parking_blocks": [], "top_rows": [], "alerts": []}),
            patch(
                "apps.dashboard.selectors.get_market_snapshot_history_feature_context",
                return_value={
                    "summary": {"weak_count": 1},
                    "rows": [],
                    "weak_blocks": [{"label": "Growth USA", "value_total": Decimal("900000")}],
                    "alerts": [],
                    "has_history": True,
                    "lookback_days": 7,
                },
            ),
        ):
            detail = get_decision_engine_summary(DummyUser(), query_params={}, capital_amount=600000)

        assert detail["suggested_assets"][0]["symbol"] == "SPY"
        assert detail["suggested_assets"][1]["symbol"] == "MELI"
        assert detail["suggested_assets"][1]["is_conditioned_by_market_history"] is True
        assert detail["suggested_assets"][1]["priority_label"] == "Condicionado por liquidez reciente"

    def test_get_decision_engine_summary_conditions_preferred_proposal_when_market_history_overlaps_block(self):
        class DummyUser:
            pk = 14

        cache.clear()
        ParametroActivo.objects.create(
            simbolo="MELI",
            sector="Tecnologia",
            bloque_estrategico="Growth USA",
            pais_exposicion="USA",
            tipo_patrimonial="Equity",
        )

        with (
            patch("apps.dashboard.selectors._build_portfolio_scope_summary", return_value={"cash_ratio_total": 0.35, "invested_ratio_total": 0.60}),
            patch("apps.dashboard.selectors.get_macro_local_context", return_value={}),
            patch("apps.dashboard.selectors.get_analytics_v2_dashboard_summary", return_value={}),
            patch("apps.dashboard.selectors.get_monthly_allocation_plan", return_value={"recommended_blocks": []}),
            patch("apps.dashboard.selectors.get_candidate_asset_ranking", return_value={"candidate_assets": []}),
            patch(
                "apps.dashboard.selectors.get_preferred_incremental_portfolio_proposal",
                return_value={
                    "preferred": {
                        "proposal_label": "Plan MELI",
                        "source_label": "Comparador manual",
                        "purchase_plan": [{"symbol": "MELI", "amount": 600000}],
                    }
                },
            ),
            patch("apps.dashboard.selectors.get_incremental_portfolio_simulation", return_value={"delta": {}, "interpretation": ""}),
            patch("apps.dashboard.selectors.get_portfolio_parking_feature_context", return_value={"has_visible_parking": False, "summary": {}, "parking_blocks": [], "top_rows": [], "alerts": []}),
            patch(
                "apps.dashboard.selectors.get_market_snapshot_history_feature_context",
                return_value={
                    "summary": {"weak_count": 1},
                    "rows": [],
                    "weak_blocks": [{"label": "Growth USA", "value_total": Decimal("900000")}],
                    "alerts": [],
                    "has_history": True,
                    "lookback_days": 7,
                },
            ),
        ):
            detail = get_decision_engine_summary(DummyUser(), query_params={}, capital_amount=600000)

        assert detail["preferred_proposal"]["is_conditioned_by_parking"] is False
        assert detail["preferred_proposal"]["is_conditioned_by_market_history"] is True
        assert detail["preferred_proposal"]["priority_label"] == "Condicionada por liquidez reciente"
        assert "liquidez reciente debil" in detail["preferred_proposal"]["parking_note"].lower()

    def test_get_decision_engine_summary_promotes_clean_preferred_alternative_when_market_history_conditioned_one_is_close(self):
        class DummyUser:
            pk = 14_1

        cache.clear()
        ParametroActivo.objects.create(
            simbolo="MELI",
            sector="Tecnologia",
            bloque_estrategico="Growth USA",
            pais_exposicion="USA",
            tipo_patrimonial="Equity",
        )
        ParametroActivo.objects.create(
            simbolo="SPY",
            sector="Indice",
            bloque_estrategico="Indice global",
            pais_exposicion="USA",
            tipo_patrimonial="ETF",
        )

        with (
            patch("apps.dashboard.selectors._build_portfolio_scope_summary", return_value={"cash_ratio_total": 0.35, "invested_ratio_total": 0.60}),
            patch("apps.dashboard.selectors.get_macro_local_context", return_value={}),
            patch("apps.dashboard.selectors.get_analytics_v2_dashboard_summary", return_value={}),
            patch("apps.dashboard.selectors.get_monthly_allocation_plan", return_value={"recommended_blocks": []}),
            patch("apps.dashboard.selectors.get_candidate_asset_ranking", return_value={"candidate_assets": []}),
            patch(
                "apps.dashboard.selectors.get_preferred_incremental_portfolio_proposal",
                return_value={
                    "preferred": {
                        "proposal_key": "plan_meli",
                        "proposal_label": "Plan MELI",
                        "source_label": "Comparador manual",
                        "purchase_plan": [{"symbol": "MELI", "amount": 600000}],
                        "comparison_score": 4.60,
                        "priority_rank": 4,
                    },
                    "candidates": [
                        {
                            "proposal_key": "plan_meli",
                            "proposal_label": "Plan MELI",
                            "source_label": "Comparador manual",
                            "purchase_plan": [{"symbol": "MELI", "amount": 600000}],
                            "comparison_score": 4.60,
                            "priority_rank": 4,
                        },
                        {
                            "proposal_key": "plan_spy",
                            "proposal_label": "Plan SPY",
                            "source_label": "Comparador por candidato",
                            "purchase_plan": [{"symbol": "SPY", "amount": 600000}],
                            "comparison_score": 4.50,
                            "priority_rank": 2,
                        },
                    ],
                },
            ),
            patch("apps.dashboard.selectors.get_incremental_portfolio_simulation", return_value={"delta": {}, "interpretation": ""}),
            patch("apps.dashboard.selectors.get_portfolio_parking_feature_context", return_value={"has_visible_parking": False, "summary": {}, "parking_blocks": [], "top_rows": [], "alerts": []}),
            patch(
                "apps.dashboard.selectors.get_market_snapshot_history_feature_context",
                return_value={
                    "summary": {"weak_count": 1},
                    "rows": [{"simbolo": "MELI", "bloque_estrategico": "Growth USA", "quality_status": "weak"}],
                    "weak_blocks": [{"label": "Growth USA", "value_total": Decimal("900000")}],
                    "alerts": [],
                    "has_history": True,
                    "lookback_days": 7,
                },
            ),
        ):
            detail = get_decision_engine_summary(DummyUser(), query_params={}, capital_amount=600000)

        assert detail["preferred_proposal"]["proposal_label"] == "Plan SPY"
        assert detail["preferred_proposal"]["is_conditioned_by_market_history"] is False
        assert detail["preferred_proposal"]["was_reprioritized_by_market_history"] is True
        assert detail["preferred_proposal"]["priority_label"] == "Repriorizada por liquidez reciente"
        assert "liquidez reciente debil" in detail["preferred_proposal"]["parking_note"].lower()

    def test_get_decision_engine_summary_tracks_tactical_governance_in_tracking_payload(self):
        class DummyUser:
            pk = 14_2

        cache.clear()
        ParametroActivo.objects.create(
            simbolo="MELI",
            sector="Tecnologia",
            bloque_estrategico="Growth USA",
            pais_exposicion="USA",
            tipo_patrimonial="Equity",
        )
        ParametroActivo.objects.create(
            simbolo="SPY",
            sector="Indice",
            bloque_estrategico="Indice global",
            pais_exposicion="USA",
            tipo_patrimonial="ETF",
        )

        with (
            patch("apps.dashboard.selectors._build_portfolio_scope_summary", return_value={"cash_ratio_total": 0.35, "invested_ratio_total": 0.60}),
            patch("apps.dashboard.selectors.get_macro_local_context", return_value={}),
            patch("apps.dashboard.selectors.get_analytics_v2_dashboard_summary", return_value={}),
            patch(
                "apps.dashboard.selectors.get_monthly_allocation_plan",
                return_value={
                    "recommended_blocks": [
                        {"label": "Growth USA", "suggested_amount": 350000, "reason": "Se prioriza crecimiento."},
                        {"label": "Indice global", "suggested_amount": 250000, "reason": "Mantiene liquidez mas limpia."},
                    ]
                },
            ),
            patch("apps.dashboard.selectors.get_candidate_asset_ranking", return_value={"candidate_assets": []}),
            patch(
                "apps.dashboard.selectors.get_preferred_incremental_portfolio_proposal",
                return_value={
                    "preferred": {
                        "proposal_key": "plan_meli",
                        "proposal_label": "Plan MELI",
                        "source_label": "Comparador manual",
                        "purchase_plan": [{"symbol": "MELI", "amount": 600000}],
                        "comparison_score": 4.60,
                        "priority_rank": 4,
                    },
                    "candidates": [
                        {
                            "proposal_key": "plan_meli",
                            "proposal_label": "Plan MELI",
                            "source_label": "Comparador manual",
                            "purchase_plan": [{"symbol": "MELI", "amount": 600000}],
                            "comparison_score": 4.60,
                            "priority_rank": 4,
                        },
                        {
                            "proposal_key": "plan_spy",
                            "proposal_label": "Plan SPY",
                            "source_label": "Comparador por candidato",
                            "purchase_plan": [{"symbol": "SPY", "amount": 600000}],
                            "comparison_score": 4.50,
                            "priority_rank": 2,
                        },
                    ],
                },
            ),
            patch("apps.dashboard.selectors.get_incremental_portfolio_simulation", return_value={"delta": {}, "interpretation": ""}),
            patch("apps.dashboard.selectors.get_portfolio_parking_feature_context", return_value={"has_visible_parking": False, "summary": {}, "parking_blocks": [], "top_rows": [], "alerts": []}),
            patch(
                "apps.dashboard.selectors.get_market_snapshot_history_feature_context",
                return_value={
                    "summary": {"weak_count": 1},
                    "rows": [{"simbolo": "MELI", "bloque_estrategico": "Growth USA", "quality_status": "weak"}],
                    "weak_blocks": [{"label": "Growth USA", "value_total": Decimal("900000")}],
                    "alerts": [],
                    "has_history": True,
                    "lookback_days": 7,
                },
            ),
        ):
            detail = get_decision_engine_summary(DummyUser(), query_params={}, capital_amount=600000)

        governance = detail["tracking_payload"]["governance"]
        assert governance["market_history_signal_active"] is True
        assert governance["market_history_blocks"] == ["Growth USA"]
        assert governance["recommendation"]["reprioritized_by_market_history"] is True
        assert governance["recommendation"]["original_block_label"] == "Growth USA"
        assert governance["preferred_proposal"]["reprioritized_by_market_history"] is True

    def test_get_incremental_proposal_history_builds_tactical_trace_from_explanation(self):
        class DummyUser:
            is_authenticated = True

        with (
            patch(
                "apps.dashboard.selectors.IncrementalProposalHistoryService.list_recent",
                return_value=[
                    {
                        "id": 1,
                        "proposal_label": "Plan SPY",
                        "purchase_plan": [{"symbol": "SPY", "amount": 600000}],
                        "decision_explanation": [
                            "La liquidez reciente observada por IOL pide revisar la ejecucion antes de comprar.",
                            "La propuesta preferida fue reemplazada por una alternativa con liquidez reciente mas limpia frente a Plan MELI.",
                        ],
                        "manual_decision_status": "pending",
                        "is_backlog_front": False,
                        "is_tracking_baseline": False,
                    }
                ],
            ),
            patch(
                "apps.dashboard.selectors.IncrementalProposalHistoryService.get_decision_counts",
                return_value={"total": 1, "pending": 1, "accepted": 0, "deferred": 0, "rejected": 0},
            ),
        ):
            history = get_incremental_proposal_history(user=DummyUser(), limit=5, decision_status="all")

        trace = history["items"][0]["tactical_trace"]
        assert trace["has_trace"] is True
        assert trace["headline"] == "Se promovio una alternativa mas limpia por liquidez reciente."
        assert [badge["label"] for badge in trace["badges"]] == ["Liquidez reciente", "Alternativa promovida"]

    def test_get_incremental_proposal_history_builds_baseline_trace_for_saved_snapshot(self):
        class DummyUser:
            is_authenticated = True

        with (
            patch(
                "apps.dashboard.selectors.IncrementalProposalHistoryService.list_recent",
                return_value=[
                    {
                        "id": 2,
                        "proposal_label": "Plan SPY",
                        "comparison_score": 4.8,
                        "purchase_plan": [{"symbol": "SPY", "amount": 600000}],
                        "simulation_delta": {
                            "expected_return_change": 0.6,
                            "fragility_change": -1.5,
                            "scenario_loss_change": 0.4,
                        },
                        "decision_explanation": [
                            "La liquidez reciente observada por IOL pide revisar la ejecucion antes de comprar.",
                        ],
                        "manual_decision_status": "pending",
                        "is_backlog_front": False,
                        "is_tracking_baseline": False,
                    }
                ],
            ),
            patch(
                "apps.dashboard.selectors.IncrementalProposalHistoryService.get_decision_counts",
                return_value={"total": 1, "pending": 1, "accepted": 0, "deferred": 0, "rejected": 0},
            ),
            patch(
                "apps.dashboard.selectors.get_incremental_proposal_tracking_baseline",
                return_value={
                    "item": {
                        "id": 1,
                        "proposal_label": "Plan KO",
                        "comparison_score": 4.0,
                        "purchase_plan": [{"symbol": "KO", "amount": 600000}],
                        "simulation_delta": {
                            "expected_return_change": 0.3,
                            "fragility_change": -1.0,
                            "scenario_loss_change": 0.2,
                        },
                    },
                    "has_baseline": True,
                },
            ),
        ):
            history = get_incremental_proposal_history(user=DummyUser(), limit=5, decision_status="all")

        baseline_trace = history["items"][0]["baseline_trace"]
        assert baseline_trace["has_trace"] is True
        assert baseline_trace["headline"] == "Supera al baseline en rentabilidad esperada y balance global."
        assert [badge["label"] for badge in baseline_trace["badges"][:2]] == ["Mejor que baseline", "Mejor retorno"]
        assert history["items"][0]["history_priority"]["priority"] == "medium"
        assert history["items"][0]["history_priority"]["priority_label"] == "Recuperable"

    def test_get_incremental_proposal_history_derives_recoverable_priority_per_snapshot(self):
        class DummyUser:
            is_authenticated = True

        with (
            patch(
                "apps.dashboard.selectors.IncrementalProposalHistoryService.list_recent",
                return_value=[
                    {
                        "id": 2,
                        "proposal_label": "Plan recuperable",
                        "comparison_score": 4.2,
                        "purchase_plan": [{"symbol": "SPY", "amount": 600000}],
                        "simulation_delta": {
                            "expected_return_change": 0.5,
                            "fragility_change": -1.2,
                            "scenario_loss_change": 0.2,
                        },
                        "decision_explanation": [
                            "La liquidez reciente observada por IOL pide revisar la ejecucion antes de comprar.",
                        ],
                        "manual_decision_status": "pending",
                        "is_backlog_front": False,
                        "is_tracking_baseline": False,
                    }
                ],
            ),
            patch(
                "apps.dashboard.selectors.IncrementalProposalHistoryService.get_decision_counts",
                return_value={"total": 1, "pending": 1, "accepted": 0, "deferred": 0, "rejected": 0},
            ),
            patch(
                "apps.dashboard.selectors.get_incremental_proposal_tracking_baseline",
                return_value={
                    "item": {
                        "id": 1,
                        "proposal_label": "Baseline activo",
                        "comparison_score": 4.0,
                        "purchase_plan": [{"symbol": "KO", "amount": 600000}],
                        "simulation_delta": {
                            "expected_return_change": 0.3,
                            "fragility_change": -1.0,
                            "scenario_loss_change": 0.2,
                        },
                    },
                    "has_baseline": True,
                },
            ),
        ):
            history = get_incremental_proposal_history(user=DummyUser(), limit=5, decision_status="all")

        assert history["items"][0]["history_priority"]["priority"] == "medium"
        assert history["items"][0]["history_priority"]["priority_label"] == "Recuperable"

    def test_get_decision_engine_summary_degrades_score_and_confidence_when_market_history_is_visible(self):
        class DummyUser:
            pk = 15

        cache.clear()
        ParametroActivo.objects.create(
            simbolo="MELI",
            sector="Tecnologia",
            bloque_estrategico="Growth USA",
            pais_exposicion="USA",
            tipo_patrimonial="Equity",
        )

        with (
            patch("apps.dashboard.selectors._build_portfolio_scope_summary", return_value={"cash_ratio_total": 0.35, "invested_ratio_total": 0.60}),
            patch("apps.dashboard.selectors.get_macro_local_context", return_value={"headline": "ok"}),
            patch(
                "apps.dashboard.selectors.get_analytics_v2_dashboard_summary",
                return_value={
                    "stress_testing": {"fragility_score": 40, "total_loss_pct": -10},
                    "expected_return": {"real_expected_return_pct": 5},
                    "risk_contribution": {"top_asset": {"contribution_pct": 0.10}},
                },
            ),
            patch(
                "apps.dashboard.selectors.get_monthly_allocation_plan",
                return_value={
                    "recommended_blocks": [{"label": "Growth USA", "suggested_amount": 600000, "reason": "prioridad limpia"}]
                },
            ),
            patch(
                "apps.dashboard.selectors.get_candidate_asset_ranking",
                return_value={
                    "candidate_assets": [
                        {"asset": "MELI", "block_label": "Growth USA", "score": 7.0, "main_reason": "growth_quality"},
                    ]
                },
            ),
            patch(
                "apps.dashboard.selectors.get_preferred_incremental_portfolio_proposal",
                return_value={
                    "preferred": {
                        "proposal_key": "plan_meli",
                        "proposal_label": "Plan MELI",
                        "source_label": "Comparador manual",
                        "purchase_plan": [{"symbol": "MELI", "amount": 600000}],
                        "comparison_score": 4.8,
                        "priority_rank": 4,
                    },
                    "candidates": [
                        {
                            "proposal_key": "plan_meli",
                            "proposal_label": "Plan MELI",
                            "source_label": "Comparador manual",
                            "purchase_plan": [{"symbol": "MELI", "amount": 600000}],
                            "comparison_score": 4.8,
                            "priority_rank": 4,
                        }
                    ],
                },
            ),
            patch(
                "apps.dashboard.selectors.get_incremental_portfolio_simulation",
                return_value={
                    "delta": {
                        "expected_return_change": 0.4,
                        "fragility_change": -0.8,
                        "scenario_loss_change": 0.2,
                    },
                    "interpretation": "Impacto favorable.",
                },
            ),
            patch("apps.dashboard.selectors.get_portfolio_parking_feature_context", return_value={"has_visible_parking": False, "summary": {}, "parking_blocks": [], "top_rows": [], "alerts": []}),
            patch(
                "apps.dashboard.selectors.get_market_snapshot_history_feature_context",
                return_value={
                    "summary": {"weak_count": 1},
                    "rows": [{"simbolo": "MELI", "bloque_estrategico": "Growth USA", "quality_status": "weak"}],
                    "weak_blocks": [{"label": "Growth USA", "value_total": Decimal("900000")}],
                    "alerts": [],
                    "has_history": True,
                    "lookback_days": 7,
                },
            ),
        ):
            detail = get_decision_engine_summary(DummyUser(), query_params={}, capital_amount=600000)

        assert detail["market_history_signal"]["has_signal"] is True
        assert detail["score"] == 80
        assert detail["confidence"] == "Baja"

    def test_get_liquidity_contract_summary_uses_explicit_layers(self):
        summary = get_liquidity_contract_summary(
            {
                "total_patrimonio_modelado": 3000.0,
                "cash_disponible_broker": 200.0,
                "caucion_colocada": 1000.0,
                "liquidez_estrategica": 500.0,
            }
        )

        assert summary["cash_operativo"] == 200.0
        assert summary["caucion_tactica"] == 1000.0
        assert summary["fci_estrategico"] == 500.0
        assert summary["liquidez_desplegable_total"] == 1700.0
        assert round(summary["pct_liquidez_desplegable_total"], 4) == round(1700.0 / 3000.0 * 100, 4)

    def test_get_liquidity_contract_summary_falls_back_to_legacy_payload(self):
        summary = get_liquidity_contract_summary(
            {
                "total_iol": 1000.0,
                "liquidez_operativa": 150.0,
                "fci_cash_management": 100.0,
            }
        )

        assert summary["cash_operativo"] == 150.0
        assert summary["caucion_tactica"] == 0.0
        assert summary["fci_estrategico"] == 100.0
        assert summary["liquidez_desplegable_total"] == 250.0
        assert summary["pct_liquidez_desplegable_total"] == 25.0

    def test_build_portfolio_scope_summary_uses_total_broker_and_cash_ars_only(self):
        class Cuenta:
            def __init__(self, moneda, disponible):
                self.moneda = moneda
                self.disponible = disponible

        with (
            patch(
                "apps.dashboard.selectors.get_dashboard_kpis",
                return_value={
                    "total_iol": 15863589.0,
                    "portafolio_invertido": 13330704.0,
                    "fci_cash_management": 2532885.0,
                    "liquidez_operativa": 11040707.87,
                },
            ),
            patch(
                "apps.dashboard.selectors.get_latest_resumen_data",
                return_value=[Cuenta("ARS", 11039915.47), Cuenta("USD", 0.56)],
            ),
        ):
            detail = _build_portfolio_scope_summary()

        assert detail["portfolio_total_broker"] == 15863589.0
        assert detail["invested_portfolio"] == 13330704.0
        assert detail["caucion_colocada"] == 0.0
        assert detail["cash_management_fci"] == 2532885.0
        assert detail["cash_available_broker"] == 11039915.47
        assert detail["cash_available_broker_ars"] == 11039915.47
        assert detail["cash_available_broker_usd"] == 0.56
        assert round(detail["cash_ratio_total"], 4) == round(11039915.47 / 15863589.0, 4)
        assert detail["caucion_ratio_total"] == 0.0
        assert round(detail["invested_ratio_total"], 4) == round(13330704.0 / 15863589.0, 4)
        assert round(detail["fci_ratio_total"], 4) == round(2532885.0 / 15863589.0, 4)

    def setUp(self):
        cache.clear()

    def test_get_dashboard_kpis_no_data(self):
        kpis = get_dashboard_kpis()
        assert kpis['total_iol'] == 0
        assert kpis['portafolio_invertido'] == 0
        assert kpis['rendimiento_total_porcentaje'] == 0
        assert kpis['rendimiento_total_cost_basis'] == 0
        assert kpis['top_10_concentracion'] == 0
        assert 'methodology' in kpis

    def test_get_dashboard_kpis_with_data(self):
        # Crear datos de prueba
        fecha = timezone.now()
        ResumenCuentaSnapshot.objects.create(
            fecha_extraccion=fecha,
            numero_cuenta='123',
            tipo_cuenta='CA',
            moneda='ARS',
            disponible=1000.00,
            comprometido=0.00,
            saldo=1000.00,
            titulos_valorizados=0.00,
            total=1000.00,
            estado='activa',
        )
        ActivoPortafolioSnapshot.objects.create(
            fecha_extraccion=fecha,
            pais_consulta='argentina',
            simbolo='AAPL',
            descripcion='Apple Inc',
            cantidad=10,
            comprometido=0,
            disponible_inmediato=10,
            puntos_variacion=0,
            variacion_diaria=0,
            ultimo_precio=100.00,
            ppc=90.00,
            ganancia_porcentaje=11.11,
            ganancia_dinero=111.10,
            valorizado=1000.00,
            pais_titulo='Estados Unidos',
            mercado='NASDAQ',
            tipo='ACCIONES',
            moneda='USD',
        )

        kpis = get_dashboard_kpis()
        assert kpis['cash_ars'] == Decimal('1000.00')
        assert kpis['cash_usd'] == Decimal('0.00')
        assert kpis['titulos_valorizados'] == Decimal('1000.00')  # AAPL es ACCIONES
        assert kpis['total_iol'] == Decimal('2000.00')  # 1000 activos + 1000 cash ARS
        assert kpis['liquidez_operativa'] == Decimal('1000.00')  # solo cash ARS
        assert kpis['cash_disponible_broker'] == Decimal('1000.00')
        assert kpis['caucion_colocada'] == Decimal('0.00')
        assert kpis['liquidez_estrategica'] == Decimal('0.00')
        assert kpis['liquidez_total_combinada'] == Decimal('1000.00')
        assert kpis['total_patrimonio_modelado'] == Decimal('2000.00')
        assert kpis['capital_invertido_real'] == Decimal('1000.00')  # total_iol - liquidez_operativa - fci_cash
        assert kpis['rendimiento_total_dinero'] == Decimal('111.10')  # ganancia_dinero del activo
        assert abs(kpis['rendimiento_total_porcentaje'] - Decimal('12.50')) < Decimal('0.01')

    def test_get_dashboard_kpis_uses_total_en_pesos_and_settlement_layers(self):
        fecha = timezone.now()
        make_resumen(
            fecha,
            moneda='peso_Argentino',
            disponible=0.47,
            total=25813062.64,
            total_en_pesos=Decimal('26317309.04'),
            saldos_detalle=[
                {'liquidacion': 'inmediato', 'saldo': 0.47, 'comprometido': 0, 'disponible': 0.47, 'disponibleOperar': 0.47},
                {'liquidacion': 'hrs24', 'saldo': 10063847.36, 'comprometido': 0, 'disponible': 10063847.36, 'disponibleOperar': 10063847.83},
            ],
        )
        make_resumen(
            fecha,
            numero_cuenta='123-USD',
            moneda='dolar_Estadounidense',
            disponible=0.56,
            total=370.77,
            total_en_pesos=Decimal('26317309.04'),
            saldos_detalle=[
                {'liquidacion': 'inmediato', 'saldo': 0.56, 'comprometido': 0, 'disponible': 0.56, 'disponibleOperar': 0.56},
            ],
        )
        make_activo(fecha, 'AAPL', valorizado=1000.00, tipo='ACCIONES', moneda='USD')

        kpis = get_dashboard_kpis()

        assert kpis['cash_ars'] == Decimal('0.47')
        assert kpis['cash_usd'] == Decimal('0.56')
        assert kpis['cash_a_liquidar_ars'] == Decimal('10063847.36')
        assert kpis['cash_a_liquidar_usd'] == Decimal('0.00')
        assert kpis['cash_disponible_broker'] == Decimal('1.03')
        assert kpis['total_broker_en_pesos'] == Decimal('26317309.04')
        assert kpis['total_iol'] == Decimal('26317309.04')
        assert kpis['total_iol_legacy_calculated'] == Decimal('1001.03')

    def test_get_dashboard_kpis_with_percentages(self):
        """Test que los KPIs incluyen los porcentajes de los bloques patrimoniales."""
        fecha = timezone.now()
        ResumenCuentaSnapshot.objects.create(
            fecha_extraccion=fecha,
            numero_cuenta='123',
            tipo_cuenta='CA',
            moneda='ARS',
            disponible=1000.00,
            comprometido=0.00,
            saldo=1000.00,
            titulos_valorizados=0.00,
            total=1000.00,
            estado='activa',
        )
        ActivoPortafolioSnapshot.objects.create(
            fecha_extraccion=fecha,
            pais_consulta='argentina',
            simbolo='AAPL',
            descripcion='Apple Inc',
            cantidad=10,
            comprometido=0,
            disponible_inmediato=10,
            puntos_variacion=0,
            variacion_diaria=0,
            ultimo_precio=100.00,
            ppc=90.00,
            ganancia_porcentaje=11.11,
            ganancia_dinero=111.10,
            valorizado=1000.00,
            pais_titulo='Estados Unidos',
            mercado='NASDAQ',
            tipo='ACCIONES',
            moneda='USD',
        )

        kpis = get_dashboard_kpis()

        # Verificar que se incluyen los porcentajes
        assert 'pct_fci_cash_management' in kpis
        assert 'pct_portafolio_invertido' in kpis
        assert 'pct_liquidez_total' in kpis
        assert 'pct_liquidez_operativa' in kpis
        assert 'pct_caucion_colocada' in kpis
        assert 'pct_liquidez_estrategica' in kpis
        assert 'pct_liquidez_total_combinada' in kpis
        assert 'pct_portafolio_invertido_modelado' in kpis

        # Total IOL = 2000, liquidez operativa = 1000, pct_liquidez ya estaba en riesgo_portafolio
        # pct_fci_cash_management debería ser 0% (no hay FCI cash)
        # pct_portafolio_invertido debería ser 50% (1000/2000)
        assert kpis['pct_fci_cash_management'] == 0.0
        assert kpis['pct_portafolio_invertido'] == 50.0
        assert kpis['pct_liquidez_total'] == 50.0
        assert kpis['pct_liquidez_operativa'] == 50.0
        assert kpis['pct_caucion_colocada'] == 0.0
        assert kpis['pct_liquidez_estrategica'] == 0.0
        assert kpis['pct_liquidez_total_combinada'] == 50.0
        assert kpis['pct_portafolio_invertido_modelado'] == 50.0

    def test_total_patrimonio_modelado_incluye_caucion_como_capa_separada(self):
        fecha = timezone.now()

        make_resumen(fecha, disponible=200.00)
        make_activo(fecha, 'CAU1', valorizado=1000.00, tipo='CAUCIONESPESOS')
        make_activo(fecha, 'ADBAICA', valorizado=500.00, tipo='FondoComundeInversion')
        make_activo(fecha, 'AAPL', valorizado=1300.00, tipo='ACCIONES', moneda='USD')

        kpis = get_dashboard_kpis()

        assert kpis['cash_disponible_broker'] == Decimal('200.00')
        assert kpis['caucion_colocada'] == Decimal('1000.00')
        assert kpis['liquidez_estrategica'] == Decimal('500.00')
        assert kpis['portafolio_invertido'] == Decimal('1300.00')
        assert kpis['total_patrimonio_modelado'] == Decimal('3000.00')
        assert kpis['liquidez_total_combinada'] == Decimal('1700.00')
        assert abs(float(kpis['pct_liquidez_operativa']) - 6.6667) < 0.01
        assert abs(float(kpis['pct_caucion_colocada']) - 33.3333) < 0.01
        assert abs(float(kpis['pct_liquidez_estrategica']) - 16.6667) < 0.01
        assert abs(float(kpis['pct_portafolio_invertido_modelado']) - 43.3333) < 0.01
        assert abs(float(kpis['pct_liquidez_total_combinada']) - 56.6667) < 0.01

    def test_build_portfolio_scope_summary_uses_total_en_pesos_and_cash_settling_layers(self):
        fecha = timezone.now()
        make_resumen(
            fecha,
            moneda='peso_Argentino',
            disponible=0.47,
            total_en_pesos=Decimal('26317309.04'),
            saldos_detalle=[
                {'liquidacion': 'inmediato', 'disponible': 0.47},
                {'liquidacion': 'hrs24', 'disponible': 10063847.36},
            ],
        )
        make_resumen(
            fecha,
            numero_cuenta='123-USD',
            moneda='dolar_Estadounidense',
            disponible=0.56,
            total_en_pesos=Decimal('26317309.04'),
            saldos_detalle=[
                {'liquidacion': 'inmediato', 'disponible': 0.56},
            ],
        )

        with patch(
            "apps.dashboard.selectors.get_dashboard_kpis",
            return_value={
                "total_iol": Decimal('26317309.04'),
                "total_broker_en_pesos": Decimal('26317309.04'),
                "portafolio_invertido": Decimal('13330704.00'),
                "fci_cash_management": Decimal('2532885.00'),
                "caucion_colocada": Decimal('0.00'),
            },
        ):
            detail = _build_portfolio_scope_summary()

        assert detail["portfolio_total_broker"] == 26317309.04
        assert detail["cash_available_broker"] == 0.47
        assert detail["cash_available_broker_ars"] == 0.47
        assert detail["cash_available_broker_usd"] == 0.56
        assert detail["cash_settling_broker"] == 10063847.36
        assert detail["cash_settling_broker_ars"] == 10063847.36
        assert detail["cash_settling_broker_usd"] == 0.0

    def test_pct_liquidez_usa_total_iol_como_base(self):
        fecha = timezone.now()

        ParametroActivo.objects.create(simbolo='AAPL', sector='Tecnología', bloque_estrategico='Growth', pais_exposicion='USA', tipo_patrimonial='Growth')
        ParametroActivo.objects.create(simbolo='CAU1', sector='Liquidez', bloque_estrategico='Liquidez', pais_exposicion='Argentina', tipo_patrimonial='Cash')
        ParametroActivo.objects.create(simbolo='ADBAICA', sector='Cash Mgmt', bloque_estrategico='Liquidez', pais_exposicion='Argentina', tipo_patrimonial='FCI')
        make_activo(fecha, 'AAPL', valorizado=1300.00, tipo='ACCIONES', moneda='USD')
        make_activo(fecha, 'CAU1', valorizado=1000.00, tipo='CAUCIONESPESOS')
        make_activo(fecha, 'ADBAICA', valorizado=500.00, tipo='FondoComundeInversion')
        make_resumen(fecha, disponible=200.00)

        riesgo = get_riesgo_portafolio_detallado()

        assert abs(float(riesgo['pct_liquidez']) - 40.0) < 0.01

    def test_pct_renta_fija_ar_incluye_bonos_argentinos(self):
        fecha = timezone.now()

        ParametroActivo.objects.create(simbolo='GD30', sector='Soberano', bloque_estrategico='Argentina', pais_exposicion='Argentina', tipo_patrimonial='Bond')
        ParametroActivo.objects.create(simbolo='TZX26', sector='CER', bloque_estrategico='Argentina', pais_exposicion='Argentina', tipo_patrimonial='Bond')
        ParametroActivo.objects.create(simbolo='BPOC7', sector='Corporativo', bloque_estrategico='Argentina', pais_exposicion='Argentina', tipo_patrimonial='Bond')
        ParametroActivo.objects.create(simbolo='AAPL', sector='Tecnología', bloque_estrategico='Growth', pais_exposicion='USA', tipo_patrimonial='Growth')
        make_activo(fecha, 'GD30', valorizado=100.00, tipo='TitulosPublicos')
        make_activo(fecha, 'TZX26', valorizado=100.00, tipo='TitulosPublicos')
        make_activo(fecha, 'BPOC7', valorizado=100.00, tipo='TitulosPublicos')
        make_activo(fecha, 'AAPL', valorizado=700.00, tipo='ACCIONES', moneda='USD')

        riesgo = get_riesgo_portafolio_detallado()

        assert abs(float(riesgo['pct_renta_fija_ar']) - 30.0) < 0.01
        assert abs(float(riesgo['pct_bonos_soberanos']) - 30.0) < 0.01

    def test_top_10_concentracion(self):
        """Top 10 debe usar solo portafolio invertido, no liquidez ni cash management."""
        fecha = timezone.now()

        for i in range(12):
            make_activo(fecha, f'ACT{i}', valorizado=1000 - i * 50)

        make_activo(fecha, 'CAU1', valorizado=10000, tipo='CAUCIONESPESOS')
        make_activo(fecha, 'ADBAICA', valorizado=5000, tipo='FondoComundeInversion')

        kpis = get_dashboard_kpis()

        assert abs(float(kpis['top_10_concentracion']) - 89.08) < 0.01

    def test_analytics_v2_dashboard_summary_uses_covariance_model_when_available(self):
        cache.clear()

        covariance_result = {
            "top_contributors": [
                {"symbol": "MSFT", "contribution_pct": 41.2},
            ],
            "by_sector": [
                {"key": "Tecnologia", "contribution_pct": 55.0},
            ],
            "metadata": {"confidence": "medium", "warnings": []},
            "model_variant": "covariance_aware",
            "covariance_observations": 64,
            "coverage_pct": 96.5,
        }
        base_result = {
            "top_contributors": [
                {"symbol": "SPY", "contribution_pct": 25.0},
            ],
            "by_sector": [
                {"key": "Indice", "contribution_pct": 25.0},
            ],
            "metadata": {"confidence": "high", "warnings": []},
        }

        class DummyRiskService:
            def calculate(self):
                return base_result

            def build_recommendation_signals(self, top_n=5):
                return []

        class DummyCovarianceRiskService:
            def __init__(self, base_service=None):
                self.base_service = base_service

            def calculate(self):
                return covariance_result

        class DummyScenarioService:
            def analyze(self, scenario_key):
                return {"total_impact_pct": -5.0, "metadata": {"confidence": "high"}}

            def build_recommendation_signals(self):
                return []

        class DummyFactorService:
            def calculate(self):
                return {
                    "dominant_factor": "growth",
                    "factors": [{"factor": "growth", "exposure_pct": 62.0}],
                    "unknown_assets": [],
                    "metadata": {"confidence": "high"},
                }

            def build_recommendation_signals(self):
                return []

        class DummyStressService:
            def calculate(self, scenario_key):
                return {
                    "scenario_key": scenario_key,
                    "fragility_score": 21.0,
                    "total_loss_pct": -1.2,
                    "metadata": {"confidence": "medium"},
                }

            def build_recommendation_signals(self):
                return []

        class DummyExpectedReturnService:
            def calculate(self):
                return {
                    "expected_return_pct": 8.0,
                    "real_expected_return_pct": 1.0,
                    "metadata": {"confidence": "medium", "warnings": []},
                }

            def build_recommendation_signals(self):
                return []

        class DummyLocalMacroSignalsService:
            def calculate(self):
                return {
                    "summary": {
                        "argentina_weight_pct": 35.0,
                        "cer_weight_pct": 8.0,
                        "badlar_real_carry_pct": -2.0,
                        "usdars_mep": 1180.0,
                        "usdars_ccl": 1230.0,
                        "usdars_financial": 1205.0,
                        "fx_gap_pct": 20.5,
                        "fx_mep_ccl_spread_pct": 4.24,
                        "fx_signal_state": "divergent",
                        "riesgo_pais_arg": 950.0,
                        "uva_annualized_pct_30d": 41.3,
                        "real_rate_badlar_vs_uva_30d": -9.3,
                    },
                    "metadata": {"confidence": "medium", "warnings": []},
                }

            def build_recommendation_signals(self):
                return []

        with (
            patch("apps.dashboard.selectors.RiskContributionService", DummyRiskService),
            patch("apps.dashboard.selectors.CovarianceAwareRiskContributionService", DummyCovarianceRiskService),
            patch("apps.dashboard.selectors.ScenarioAnalysisService", DummyScenarioService),
            patch("apps.dashboard.selectors.FactorExposureService", DummyFactorService),
            patch("apps.dashboard.selectors.StressFragilityService", DummyStressService),
            patch("apps.dashboard.selectors.ExpectedReturnService", DummyExpectedReturnService),
            patch("apps.dashboard.selectors.LocalMacroSignalsService", DummyLocalMacroSignalsService),
        ):
            summary = get_analytics_v2_dashboard_summary()

        assert summary["risk_contribution"]["top_asset"]["symbol"] == "MSFT"
        assert summary["risk_contribution"]["top_sector"]["key"] == "Tecnologia"
        assert summary["risk_contribution"]["model_variant"] == "covariance_aware"
        assert summary["risk_contribution"]["covariance_observations"] == 64
        assert summary["risk_contribution"]["coverage_pct"] == 96.5
        assert "MSFT" in summary["risk_contribution"]["interpretation"]
        assert summary["scenario_analysis"]["interpretation"]
        assert "growth" in summary["factor_exposure"]["interpretation"]
        assert "fragilidad" in summary["stress_testing"]["interpretation"].lower()
        assert "retorno esperado estructural" in summary["expected_return"]["interpretation"].lower()
        assert summary["local_macro"]["usdars_ccl"] == 1230.0
        assert summary["local_macro"]["fx_signal_state"] == "divergent"
        assert summary["local_macro"]["uva_annualized_pct_30d"] == 41.3
        assert summary["local_macro"]["real_rate_badlar_vs_uva_30d"] == -9.3

    def test_get_risk_contribution_detail_returns_mvp_proxy_when_covariance_is_not_active(self):
        cache.clear()

        base_result = {
            "items": [
                {
                    "symbol": "SPY",
                    "sector": "Indice",
                    "country": "USA",
                    "asset_type": "etf",
                    "weight_pct": 25.0,
                    "volatility_proxy": 18.5,
                    "risk_score": 0.04625,
                    "contribution_pct": 40.0,
                    "used_volatility_fallback": False,
                }
            ],
            "top_contributors": [{"symbol": "SPY", "contribution_pct": 40.0}],
            "by_sector": [{"key": "Indice", "contribution_pct": 40.0, "weight_pct": 25.0}],
            "by_country": [{"key": "USA", "contribution_pct": 40.0, "weight_pct": 25.0}],
            "metadata": {
                "confidence": "medium",
                "warnings": ["used_fallback:QQQ:insufficient_history"],
                "methodology": "mvp_methodology",
                "limitations": "mvp_limitations",
            },
        }
        covariance_result = {
            "model_variant": "mvp_proxy",
            "covariance_observations": 6,
            "coverage_pct": 72.0,
            "portfolio_volatility_proxy": None,
            "covered_symbols": ["SPY"],
            "excluded_symbols": ["QQQ"],
        }

        class DummyRiskService:
            def calculate(self):
                return base_result

        class DummyCovarianceRiskService:
            def __init__(self, base_service=None):
                self.base_service = base_service

            def calculate(self):
                return covariance_result

        with (
            patch("apps.dashboard.selectors.RiskContributionService", DummyRiskService),
            patch("apps.dashboard.selectors.CovarianceAwareRiskContributionService", DummyCovarianceRiskService),
        ):
            detail = get_risk_contribution_detail()

        assert detail["model_variant"] == "mvp_proxy"
        assert detail["covariance_observations"] == 6
        assert detail["coverage_pct"] == 72.0
        assert detail["portfolio_volatility_proxy"] is None
        assert detail["top_asset"]["symbol"] == "SPY"
        assert detail["top_sector"]["key"] == "Indice"
        assert detail["items"][0]["symbol"] == "SPY"
        assert detail["items"][0]["rank"] == 1
        assert detail["items"][0]["risk_score"] == 0.04625
        assert detail["items"][0]["risk_vs_weight_delta"] == 15.0
        assert detail["by_country"][0]["risk_vs_weight_delta"] == 15.0
        assert detail["warnings"] == ["used_fallback:QQQ:insufficient_history"]

    def test_get_risk_contribution_detail_returns_covariance_variant_when_available(self):
        cache.clear()

        base_result = {
            "items": [],
            "top_contributors": [],
            "by_sector": [],
            "metadata": {"confidence": "low", "warnings": []},
        }
        covariance_result = {
            "items": [
                {
                    "symbol": "MSFT",
                    "sector": "Tecnologia",
                    "country": "USA",
                    "asset_type": "equity",
                    "weight_pct": 18.5,
                    "volatility_proxy": 24.2,
                    "risk_score": 0.081234,
                    "contribution_pct": 44.1,
                    "used_volatility_fallback": False,
                }
            ],
            "top_contributors": [{"symbol": "MSFT", "contribution_pct": 44.1}],
            "by_sector": [{"key": "Tecnologia", "contribution_pct": 44.1, "weight_pct": 18.5}],
            "by_country": [{"key": "USA", "contribution_pct": 44.1, "weight_pct": 18.5}],
            "metadata": {
                "confidence": "high",
                "warnings": [],
                "methodology": "covariance_methodology",
                "limitations": "covariance_limitations",
            },
            "model_variant": "covariance_aware",
            "covariance_observations": 64,
            "coverage_pct": 96.5,
            "portfolio_volatility_proxy": 17.9,
            "covered_symbols": ["MSFT", "SPY", "AAPL"],
            "excluded_symbols": [],
        }

        class DummyRiskService:
            def calculate(self):
                return base_result

        class DummyCovarianceRiskService:
            def __init__(self, base_service=None):
                self.base_service = base_service

            def calculate(self):
                return covariance_result

        with (
            patch("apps.dashboard.selectors.RiskContributionService", DummyRiskService),
            patch("apps.dashboard.selectors.CovarianceAwareRiskContributionService", DummyCovarianceRiskService),
        ):
            detail = get_risk_contribution_detail()

        assert detail["model_variant"] == "covariance_aware"
        assert detail["covariance_observations"] == 64
        assert detail["coverage_pct"] == 96.5
        assert detail["portfolio_volatility_proxy"] == 17.9
        assert detail["top_asset"]["symbol"] == "MSFT"
        assert detail["top_sector"]["key"] == "Tecnologia"
        assert detail["items"][0]["symbol"] == "MSFT"
        assert detail["items"][0]["contribution_pct"] == 44.1
        assert detail["items"][0]["risk_vs_weight_delta"] == 25.6
        assert detail["by_country"][0]["risk_vs_weight_delta"] == 25.6
        assert detail["covered_symbols"] == ["MSFT", "SPY", "AAPL"]

    def test_get_scenario_analysis_detail_returns_ranked_scenarios_and_worst_breakdown(self):
        cache.clear()

        scenario_catalog = [
            {
                "scenario_key": "argentina_stress",
                "label": "Argentina Stress",
                "description": "Shock local severo",
            },
            {
                "scenario_key": "tech_shock",
                "label": "Tech Shock",
                "description": "Caida concentrada en tecnologia",
            },
        ]
        scenario_results = {
            "argentina_stress": {
                "total_impact_pct": -4.3,
                "total_impact_money": -4300.0,
                "by_asset": [
                    {
                        "symbol": "GD30",
                        "market_value": 1000.0,
                        "estimated_impact_pct": -12.0,
                        "estimated_impact_money": -120.0,
                        "transmission_channel": "country",
                    }
                ],
                "by_sector": [{"key": "Soberano", "impact_pct": -7.2, "impact_money": -720.0}],
                "by_country": [{"key": "Argentina", "impact_pct": -9.1, "impact_money": -910.0}],
                "top_negative_contributors": [{"symbol": "GD30"}],
                "metadata": {
                    "confidence": "high",
                    "warnings": [],
                    "methodology": "scenario_methodology",
                    "limitations": "scenario_limitations",
                },
            },
            "tech_shock": {
                "total_impact_pct": -8.1,
                "total_impact_money": -8100.0,
                "by_asset": [
                    {
                        "symbol": "AAPL",
                        "market_value": 1500.0,
                        "estimated_impact_pct": -14.0,
                        "estimated_impact_money": -210.0,
                        "transmission_channel": "sector",
                    }
                ],
                "by_sector": [{"key": "Tecnologia", "impact_pct": -11.5, "impact_money": -1150.0}],
                "by_country": [{"key": "USA", "impact_pct": -8.8, "impact_money": -880.0}],
                "top_negative_contributors": [{"symbol": "AAPL"}],
                "metadata": {
                    "confidence": "medium",
                    "warnings": ["partial_coverage"],
                    "methodology": "scenario_methodology",
                    "limitations": "scenario_limitations",
                },
            },
        }

        class DummyCatalogService:
            def list_scenarios(self):
                return scenario_catalog

        class DummyScenarioService:
            def analyze(self, scenario_key):
                return scenario_results[scenario_key]

        with (
            patch("apps.dashboard.selectors.ScenarioCatalogService", DummyCatalogService),
            patch("apps.dashboard.selectors.ScenarioAnalysisService", DummyScenarioService),
        ):
            detail = get_scenario_analysis_detail()

        assert [row["scenario_key"] for row in detail["scenarios"]] == ["tech_shock", "argentina_stress"]
        assert detail["scenarios"][0]["severity_rank"] == 1
        assert detail["worst_scenario"]["scenario_key"] == "tech_shock"
        assert detail["worst_scenario"]["top_sector"]["key"] == "Tecnologia"
        assert detail["worst_scenario"]["top_country"]["key"] == "USA"
        assert detail["worst_assets"][0]["symbol"] == "AAPL"
        assert detail["worst_assets"][0]["market_value"] == 1500.0
        assert detail["worst_sectors"][0]["key"] == "Tecnologia"
        assert detail["worst_countries"][0]["key"] == "USA"
        assert detail["confidence"] == "medium"
        assert detail["warnings"] == ["partial_coverage"]

    def test_get_scenario_analysis_detail_handles_empty_or_incomplete_results(self):
        cache.clear()

        scenario_catalog = [
            {
                "scenario_key": "flat_scenario",
                "label": "Flat Scenario",
                "description": "",
            }
        ]

        class DummyCatalogService:
            def list_scenarios(self):
                return scenario_catalog

        class DummyScenarioService:
            def analyze(self, scenario_key):
                assert scenario_key == "flat_scenario"
                return {
                    "total_impact_pct": 0,
                    "total_impact_money": 0,
                    "metadata": {"confidence": "low", "warnings": ["missing_shock"]},
                }

        with (
            patch("apps.dashboard.selectors.ScenarioCatalogService", DummyCatalogService),
            patch("apps.dashboard.selectors.ScenarioAnalysisService", DummyScenarioService),
        ):
            detail = get_scenario_analysis_detail()

        assert len(detail["scenarios"]) == 1
        assert detail["scenarios"][0]["severity_rank"] == 1
        assert detail["scenarios"][0]["total_impact_pct"] == 0.0
        assert detail["worst_scenario"]["scenario_key"] == "flat_scenario"
        assert detail["worst_assets"] == []
        assert detail["worst_sectors"] == []
        assert detail["worst_countries"] == []
        assert detail["warnings"] == ["missing_shock"]

    def test_get_factor_exposure_detail_returns_ranked_factors_and_unknown_assets(self):
        cache.clear()

        factor_result = {
            "factors": [
                {"factor": "value", "exposure_pct": 20.0, "confidence": "medium"},
                {"factor": "growth", "exposure_pct": 55.0, "confidence": "high"},
                {"factor": "defensive", "exposure_pct": 0.0, "confidence": "low"},
            ],
            "dominant_factor": "growth",
            "underrepresented_factors": ["defensive", "dividend"],
            "unknown_assets": ["XYZ", "ABC"],
            "metadata": {
                "confidence": "medium",
                "warnings": ["unknown_assets_count:2"],
                "methodology": "factor_methodology",
                "limitations": "factor_limitations",
            },
        }

        class DummyFactorService:
            def calculate(self):
                return factor_result

        class DummyExplanationService:
            def build_factor_exposure_explanation(self, result):
                assert result is factor_result
                return "Interpretacion factorial"

        with (
            patch("apps.dashboard.selectors.FactorExposureService", DummyFactorService),
            patch("apps.dashboard.selectors.AnalyticsExplanationService", DummyExplanationService),
        ):
            detail = get_factor_exposure_detail()

        assert [row["factor"] for row in detail["factors"]] == ["growth", "value", "defensive"]
        assert detail["factors"][0]["rank"] == 1
        assert detail["factors"][0]["contribution_relative_pct"] == 55.0
        assert detail["dominant_factor"]["factor"] == "growth"
        assert detail["underrepresented_factors"] == ["defensive", "dividend"]
        assert detail["unknown_assets_count"] == 2
        assert detail["unknown_assets"][0]["symbol"] == "XYZ"
        assert detail["interpretation"] == "Interpretacion factorial"
        assert detail["warnings"] == ["unknown_assets_count:2"]

    def test_get_factor_exposure_detail_handles_empty_or_partial_result(self):
        cache.clear()

        factor_result = {
            "factors": [],
            "dominant_factor": None,
            "underrepresented_factors": [],
            "unknown_assets": [],
            "metadata": {"confidence": "low", "warnings": ["empty_portfolio"]},
        }

        class DummyFactorService:
            def calculate(self):
                return factor_result

        class DummyExplanationService:
            def build_factor_exposure_explanation(self, result):
                return ""

        with (
            patch("apps.dashboard.selectors.FactorExposureService", DummyFactorService),
            patch("apps.dashboard.selectors.AnalyticsExplanationService", DummyExplanationService),
        ):
            detail = get_factor_exposure_detail()

        assert detail["factors"] == []
        assert detail["dominant_factor"] is None
        assert detail["unknown_assets"] == []
        assert detail["unknown_assets_count"] == 0
        assert detail["confidence"] == "low"
        assert detail["warnings"] == ["empty_portfolio"]

    def test_get_stress_fragility_detail_returns_ranked_stresses_and_breakdowns(self):
        cache.clear()

        stress_catalog = [
            {
                "stress_key": "usa_crash_severe",
                "label": "Crash USA severo",
                "description": "Stress USA",
            },
            {
                "stress_key": "local_crisis_severe",
                "label": "Crisis local severa",
                "description": "Stress local",
            },
        ]
        stress_results = {
            "usa_crash_severe": {
                "scenario_key": "usa_crash_severe",
                "fragility_score": 18.0,
                "total_loss_pct": -5.1,
                "total_loss_money": -5100.0,
                "vulnerable_assets": [
                    {
                        "symbol": "SPY",
                        "market_value": 1000.0,
                        "estimated_impact_pct": -12.0,
                        "estimated_impact_money": -120.0,
                        "transmission_channel": "market",
                    }
                ],
                "vulnerable_sectors": [{"key": "Indice", "impact_pct": -4.8, "impact_money": -480.0}],
                "vulnerable_countries": [{"key": "USA", "impact_pct": -5.1, "impact_money": -510.0}],
                "metadata": {
                    "confidence": "high",
                    "warnings": [],
                    "methodology": "stress_methodology",
                    "limitations": "stress_limitations",
                },
            },
            "local_crisis_severe": {
                "scenario_key": "local_crisis_severe",
                "fragility_score": 42.0,
                "total_loss_pct": -12.4,
                "total_loss_money": -12400.0,
                "vulnerable_assets": [
                    {
                        "symbol": "GD30",
                        "market_value": 900.0,
                        "estimated_impact_pct": -18.0,
                        "estimated_impact_money": -162.0,
                        "transmission_channel": "country+fx",
                    }
                ],
                "vulnerable_sectors": [{"key": "Soberano", "impact_pct": -8.2, "impact_money": -820.0}],
                "vulnerable_countries": [{"key": "Argentina", "impact_pct": -12.4, "impact_money": -1240.0}],
                "metadata": {
                    "confidence": "medium",
                    "warnings": ["legacy_mappings:argentina_crisis"],
                    "methodology": "stress_methodology",
                    "limitations": "stress_limitations",
                },
            },
        }

        class DummyStressCatalogService:
            def list_stresses(self):
                return stress_catalog

        class DummyStressService:
            def calculate(self, stress_key):
                return stress_results[stress_key]

        class DummyExplanationService:
            def build_stress_fragility_explanation(self, result):
                assert result["scenario_key"] == "local_crisis_severe"
                return "Interpretacion stress"

        with (
            patch("apps.dashboard.selectors.StressCatalogService", DummyStressCatalogService),
            patch("apps.dashboard.selectors.StressFragilityService", DummyStressService),
            patch("apps.dashboard.selectors.AnalyticsExplanationService", DummyExplanationService),
        ):
            detail = get_stress_fragility_detail()

        assert [row["stress_key"] for row in detail["stresses"]] == ["local_crisis_severe", "usa_crash_severe"]
        assert detail["stresses"][0]["severity_rank"] == 1
        assert detail["worst_stress"]["stress_key"] == "local_crisis_severe"
        assert detail["worst_stress"]["top_sector"]["key"] == "Soberano"
        assert detail["worst_stress"]["top_country"]["key"] == "Argentina"
        assert detail["worst_assets"][0]["symbol"] == "GD30"
        assert detail["worst_sectors"][0]["key"] == "Soberano"
        assert detail["worst_countries"][0]["key"] == "Argentina"
        assert detail["confidence"] == "medium"
        assert detail["warnings"] == ["legacy_mappings:argentina_crisis"]
        assert detail["interpretation"] == "Interpretacion stress"

    def test_get_stress_fragility_detail_handles_empty_or_partial_result(self):
        cache.clear()

        stress_catalog = [
            {
                "stress_key": "flat_stress",
                "label": "Flat Stress",
                "description": "",
            }
        ]

        class DummyStressCatalogService:
            def list_stresses(self):
                return stress_catalog

        class DummyStressService:
            def calculate(self, stress_key):
                assert stress_key == "flat_stress"
                return {
                    "scenario_key": "flat_stress",
                    "fragility_score": 0,
                    "total_loss_pct": 0,
                    "total_loss_money": 0,
                    "metadata": {"confidence": "low", "warnings": ["empty_portfolio"]},
                }

        class DummyExplanationService:
            def build_stress_fragility_explanation(self, result):
                return ""

        with (
            patch("apps.dashboard.selectors.StressCatalogService", DummyStressCatalogService),
            patch("apps.dashboard.selectors.StressFragilityService", DummyStressService),
            patch("apps.dashboard.selectors.AnalyticsExplanationService", DummyExplanationService),
        ):
            detail = get_stress_fragility_detail()

        assert len(detail["stresses"]) == 1
        assert detail["stresses"][0]["severity_rank"] == 1
        assert detail["stresses"][0]["total_loss_pct"] == 0.0
        assert detail["worst_stress"]["stress_key"] == "flat_stress"
        assert detail["worst_assets"] == []
        assert detail["worst_sectors"] == []
        assert detail["worst_countries"] == []
        assert detail["warnings"] == ["empty_portfolio"]

    def test_get_expected_return_detail_returns_ranked_buckets_and_dominant_bucket(self):
        cache.clear()

        expected_return_result = {
            "expected_return_pct": 18.4,
            "real_expected_return_pct": 2.1,
            "basis_reference": "weighted_bucket_baseline_current_positions",
            "by_bucket": [
                {
                    "bucket_key": "fixed_income_ar",
                    "label": "Renta fija AR",
                    "weight_pct": 30.0,
                    "expected_return_pct": 14.0,
                    "basis_reference": "benchmark:bonos_ar:daily_trailing_100",
                },
                {
                    "bucket_key": "equity_beta",
                    "label": "Equity beta / CEDEAR",
                    "weight_pct": 55.0,
                    "expected_return_pct": 22.0,
                    "basis_reference": "benchmark:cedear_usa:daily_trailing_180",
                },
            ],
            "metadata": {
                "confidence": "high",
                "warnings": ["missing_badlar"],
                "methodology": "expected_return_methodology",
                "limitations": "expected_return_limitations",
            },
        }

        class DummyExpectedReturnService:
            def calculate(self):
                return expected_return_result

        class DummyExplanationService:
            def build_expected_return_explanation(self, result):
                assert result is expected_return_result
                return "Interpretacion expected return"

        with (
            patch("apps.dashboard.selectors.ExpectedReturnService", DummyExpectedReturnService),
            patch("apps.dashboard.selectors.AnalyticsExplanationService", DummyExplanationService),
        ):
            detail = get_expected_return_detail()

        assert detail["expected_return_pct"] == 18.4
        assert detail["real_expected_return_pct"] == 2.1
        assert [row["bucket_key"] for row in detail["bucket_rows"]] == ["equity_beta", "fixed_income_ar"]
        assert detail["bucket_rows"][0]["rank"] == 1
        assert detail["bucket_rows"][0]["contribution_relative_pct"] == 12.1
        assert detail["dominant_bucket"]["bucket_key"] == "equity_beta"
        assert detail["main_warning"] == "missing_badlar"
        assert detail["interpretation"] == "Interpretacion expected return"
        assert detail["asset_rows"] == []

    def test_get_expected_return_detail_handles_empty_or_partial_result(self):
        cache.clear()

        expected_return_result = {
            "expected_return_pct": 0,
            "real_expected_return_pct": None,
            "basis_reference": "weighted_bucket_baseline_current_positions",
            "by_bucket": [],
            "metadata": {"confidence": "low", "warnings": []},
        }

        class DummyExpectedReturnService:
            def calculate(self):
                return expected_return_result

        class DummyExplanationService:
            def build_expected_return_explanation(self, result):
                return ""

        with (
            patch("apps.dashboard.selectors.ExpectedReturnService", DummyExpectedReturnService),
            patch("apps.dashboard.selectors.AnalyticsExplanationService", DummyExplanationService),
        ):
            detail = get_expected_return_detail()

        assert detail["expected_return_pct"] == 0
        assert detail["real_expected_return_pct"] is None
        assert detail["bucket_rows"] == []
        assert detail["dominant_bucket"] is None
        assert detail["main_warning"] is None
        assert detail["warnings"] == []
        assert detail["confidence"] == "low"

    def test_get_monthly_allocation_plan_reuses_service_output(self):
        cache.clear()

        expected_plan = {
            "capital_total": 600000,
            "recommended_blocks_count": 2,
            "criterion": "rules_based_analytics_v2_mvp",
            "recommended_blocks": [
                {
                    "bucket": "defensive",
                    "suggested_amount": 350000,
                    "score_breakdown": {"positive_signals": [], "negative_signals": [], "notes": ""},
                },
                {
                    "bucket": "dividend",
                    "suggested_amount": 250000,
                    "score_breakdown": {"positive_signals": [], "negative_signals": [], "notes": ""},
                },
            ],
            "avoided_blocks": [{"bucket": "tech_growth"}],
            "explanation": "Plan incremental",
        }

        class DummyMonthlyAllocationService:
            def build_plan(self, capital_amount):
                assert capital_amount == 600000
                return expected_plan

        with patch("apps.dashboard.selectors.MonthlyAllocationService", DummyMonthlyAllocationService):
            detail = get_monthly_allocation_plan()

        assert detail["capital_total"] == 600000
        assert detail["recommended_blocks_count"] == 2
        assert detail["recommended_blocks"][0]["bucket"] == "defensive"
        assert "score_breakdown" in detail["recommended_blocks"][0]
        assert detail["avoided_blocks"][0]["bucket"] == "tech_growth"

    def test_get_candidate_asset_ranking_reuses_service_output(self):
        cache.clear()

        expected_ranking = {
            "capital_total": 600000,
            "candidate_assets_count": 2,
            "candidate_assets": [
                {
                    "asset": "KO",
                    "block": "defensive",
                    "block_label": "Defensive / resiliente",
                    "score": 8.4,
                    "rank": 1,
                    "reasons": ["defensive_sector_match"],
                    "main_reason": "defensive_sector_match",
                },
                {
                    "asset": "SPY",
                    "block": "global_index",
                    "block_label": "Indice global",
                    "score": 6.8,
                    "rank": 1,
                    "reasons": ["stable_global_exposure"],
                    "main_reason": "stable_global_exposure",
                },
            ],
            "by_block": [],
            "explanation": "Ranking incremental",
        }

        class DummyCandidateAssetRankingService:
            def build_ranking(self, capital_amount):
                assert capital_amount == 600000
                return expected_ranking

        with patch("apps.dashboard.selectors.CandidateAssetRankingService", DummyCandidateAssetRankingService):
            detail = get_candidate_asset_ranking()

        assert detail["capital_total"] == 600000
        assert detail["candidate_assets_count"] == 2
        assert detail["candidate_assets"][0]["asset"] == "KO"
        assert detail["candidate_assets"][0]["main_reason"] == "defensive_sector_match"

    def test_get_incremental_portfolio_simulation_builds_default_purchase_plan(self):
        cache.clear()

        monthly_plan = {
            "capital_total": 600000,
            "recommended_blocks": [
                {"bucket": "defensive", "label": "Defensive / resiliente", "suggested_amount": 350000},
                {"bucket": "global_index", "label": "Indice global", "suggested_amount": 250000},
            ],
        }
        candidate_ranking = {
            "by_block": [
                {
                    "block": "defensive",
                    "candidates": [{"asset": "KO", "score": 8.4, "main_reason": "defensive_sector_match"}],
                },
                {
                    "block": "global_index",
                    "candidates": [{"asset": "SPY", "score": 6.8, "main_reason": "stable_global_exposure"}],
                },
            ]
        }
        simulator_result = {
            "capital_amount": 600000.0,
            "purchase_plan": [
                {"symbol": "KO", "amount": 350000.0},
                {"symbol": "SPY", "amount": 250000.0},
            ],
            "before": {"expected_return_pct": 8.0},
            "after": {"expected_return_pct": 8.6},
            "delta": {
                "expected_return_change": 0.6,
                "real_expected_return_change": 0.2,
                "fragility_change": -3.0,
                "scenario_loss_change": 0.7,
                "risk_concentration_change": -1.4,
            },
            "interpretation": "La compra reduce la fragilidad del portafolio.",
            "warnings": [],
        }

        class DummyIncrementalPortfolioSimulator:
            def simulate(self, proposal):
                assert proposal["capital_amount"] == 600000
                assert proposal["purchase_plan"] == [
                    {"symbol": "KO", "amount": 350000.0},
                    {"symbol": "SPY", "amount": 250000.0},
                ]
                return simulator_result

        with (
            patch("apps.dashboard.selectors.get_monthly_allocation_plan", lambda capital_amount=600000: monthly_plan),
            patch("apps.dashboard.selectors.get_candidate_asset_ranking", lambda capital_amount=600000: candidate_ranking),
            patch("apps.dashboard.selectors.IncrementalPortfolioSimulator", DummyIncrementalPortfolioSimulator),
        ):
            detail = get_incremental_portfolio_simulation()

        assert detail["selected_candidates"][0]["symbol"] == "KO"
        assert detail["selected_candidates"][1]["symbol"] == "SPY"
        assert detail["delta"]["fragility_change"] == -3.0
        assert detail["selection_basis"] == "top_candidate_per_recommended_block"

    def test_get_incremental_portfolio_simulation_comparison_ranks_variants(self):
        cache.clear()

        monthly_plan = {
            "capital_total": 600000,
            "recommended_blocks": [
                {"bucket": "defensive", "label": "Defensive / resiliente", "suggested_amount": 400000},
                {"bucket": "global_index", "label": "Indice global", "suggested_amount": 200000},
            ],
        }
        candidate_ranking = {
            "by_block": [
                {
                    "block": "defensive",
                    "candidates": [
                        {"asset": "KO", "score": 8.4, "main_reason": "defensive_sector_match"},
                        {"asset": "PEP", "score": 8.0, "main_reason": "dividend_profile"},
                    ],
                },
                {
                    "block": "global_index",
                    "candidates": [
                        {"asset": "SPY", "score": 6.8, "main_reason": "stable_global_exposure"},
                    ],
                },
            ]
        }

        class DummyIncrementalPortfolioSimulator:
            def simulate(self, proposal):
                purchase_plan = proposal["purchase_plan"]
                symbols = {item["symbol"] for item in purchase_plan}
                if symbols == {"KO", "SPY"} and len(purchase_plan) == 2:
                    return {
                        "before": {},
                        "after": {},
                        "delta": {
                            "expected_return_change": 0.4,
                            "real_expected_return_change": 0.1,
                            "fragility_change": -2.0,
                            "scenario_loss_change": 0.5,
                            "risk_concentration_change": -0.8,
                        },
                        "interpretation": "Top candidato por bloque.",
                    }
                if symbols == {"PEP", "SPY"}:
                    return {
                        "before": {},
                        "after": {},
                        "delta": {
                            "expected_return_change": 0.3,
                            "real_expected_return_change": 0.1,
                            "fragility_change": -1.0,
                            "scenario_loss_change": 0.2,
                            "risk_concentration_change": -0.3,
                        },
                        "interpretation": "Runner up.",
                    }
                return {
                    "before": {},
                    "after": {},
                    "delta": {
                        "expected_return_change": 0.6,
                        "real_expected_return_change": 0.2,
                        "fragility_change": -3.0,
                        "scenario_loss_change": 0.8,
                        "risk_concentration_change": -1.0,
                    },
                    "interpretation": "Split del bloque mayor.",
                }

        with (
            patch("apps.dashboard.selectors.get_monthly_allocation_plan", lambda capital_amount=600000: monthly_plan),
            patch("apps.dashboard.selectors.get_candidate_asset_ranking", lambda capital_amount=600000: candidate_ranking),
            patch("apps.dashboard.selectors.IncrementalPortfolioSimulator", DummyIncrementalPortfolioSimulator),
        ):
            detail = get_incremental_portfolio_simulation_comparison()

        assert len(detail["proposals"]) == 3
        assert detail["best_proposal_key"] == "split_largest_block_top_two"
        assert detail["proposals"][0]["comparison_score"] >= detail["proposals"][1]["comparison_score"]
        assert detail["proposals"][0]["proposal_label"] == detail["proposals"][0]["label"]
        assert "expected_return_change" in detail["proposals"][0]["simulation_delta"]
        assert detail["proposals"][0]["purchase_summary"]

    def test_get_manual_incremental_portfolio_simulation_comparison_ranks_manual_plans(self):
        cache.clear()

        class DummyIncrementalPortfolioSimulator:
            def simulate(self, proposal):
                symbols = {item["symbol"] for item in proposal["purchase_plan"]}
                if symbols == {"KO", "MCD"}:
                    return {
                        "before": {},
                        "after": {},
                        "delta": {
                            "expected_return_change": 0.7,
                            "real_expected_return_change": 0.2,
                            "fragility_change": -3.0,
                            "scenario_loss_change": 0.9,
                            "risk_concentration_change": -1.2,
                        },
                        "interpretation": "Plan manual A mejora el perfil defensivo.",
                        "warnings": [],
                    }
                return {
                    "before": {},
                    "after": {},
                    "delta": {
                        "expected_return_change": 0.2,
                        "real_expected_return_change": 0.0,
                        "fragility_change": -1.0,
                        "scenario_loss_change": 0.1,
                        "risk_concentration_change": -0.1,
                    },
                    "interpretation": "Plan manual B aporta mejora acotada.",
                    "warnings": [],
                }

        query_params = {
            "manual_compare": "1",
            "plan_a_capital": "600000",
            "plan_a_symbol_1": "KO",
            "plan_a_amount_1": "300000",
            "plan_a_symbol_2": "MCD",
            "plan_a_amount_2": "300000",
            "plan_b_capital": "600000",
            "plan_b_symbol_1": "SPY",
            "plan_b_amount_1": "600000",
        }

        with patch("apps.dashboard.selectors.IncrementalPortfolioSimulator", DummyIncrementalPortfolioSimulator):
            detail = get_manual_incremental_portfolio_simulation_comparison(query_params)

        assert detail["submitted"] is True
        assert len(detail["proposals"]) == 2
        assert detail["best_proposal_key"] == "plan_a"
        assert detail["proposals"][0]["comparison_score"] >= detail["proposals"][1]["comparison_score"]
        assert detail["proposals"][0]["purchase_plan"][0]["symbol"] == "KO"
        assert detail["proposals"][0]["proposal_label"] == "Plan manual A"
        assert detail["proposals"][0]["simulation_delta"]["expected_return_change"] == 0.7

    def test_get_manual_incremental_portfolio_simulation_comparison_handles_empty_input(self):
        cache.clear()

        detail = get_manual_incremental_portfolio_simulation_comparison({"manual_compare": "1"})

        assert detail["submitted"] is True
        assert detail["proposals"] == []
        assert detail["best_proposal_key"] is None

    def test_get_candidate_incremental_portfolio_comparison_ranks_candidates_within_block(self):
        cache.clear()

        monthly_plan = {
            "capital_total": 600000,
            "recommended_blocks": [
                {"bucket": "defensive", "label": "Defensive / resiliente", "suggested_amount": 300000},
                {"bucket": "global_index", "label": "Indice global", "suggested_amount": 300000},
            ],
        }
        candidate_ranking = {
            "by_block": [
                {
                    "block": "defensive",
                    "candidates": [
                        {"asset": "KO", "score": 8.4, "main_reason": "defensive_sector_match"},
                        {"asset": "MCD", "score": 7.7, "main_reason": "dividend_profile"},
                        {"asset": "XLU", "score": 7.1, "main_reason": "utilities_defensive"},
                    ],
                },
                {
                    "block": "global_index",
                    "candidates": [
                        {"asset": "SPY", "score": 6.8, "main_reason": "stable_global_exposure"},
                    ],
                },
            ]
        }

        class DummyIncrementalPortfolioSimulator:
            def simulate(self, proposal):
                symbol = proposal["purchase_plan"][0]["symbol"]
                if symbol == "KO":
                    return {
                        "before": {},
                        "after": {},
                        "delta": {
                            "expected_return_change": 0.5,
                            "real_expected_return_change": 0.2,
                            "fragility_change": -2.5,
                            "scenario_loss_change": 0.7,
                            "risk_concentration_change": -0.8,
                        },
                        "interpretation": "KO mejora más la resiliencia.",
                        "warnings": [],
                    }
                if symbol == "MCD":
                    return {
                        "before": {},
                        "after": {},
                        "delta": {
                            "expected_return_change": 0.4,
                            "real_expected_return_change": 0.1,
                            "fragility_change": -1.5,
                            "scenario_loss_change": 0.5,
                            "risk_concentration_change": -0.4,
                        },
                        "interpretation": "MCD mejora moderadamente.",
                        "warnings": [],
                    }
                return {
                    "before": {},
                    "after": {},
                    "delta": {
                        "expected_return_change": 0.2,
                        "real_expected_return_change": 0.0,
                        "fragility_change": -0.9,
                        "scenario_loss_change": 0.2,
                        "risk_concentration_change": -0.2,
                    },
                    "interpretation": "XLU aporta mejora acotada.",
                    "warnings": [],
                }

        with (
            patch("apps.dashboard.selectors.get_monthly_allocation_plan", lambda capital_amount=600000: monthly_plan),
            patch("apps.dashboard.selectors.get_candidate_asset_ranking", lambda capital_amount=600000: candidate_ranking),
            patch("apps.dashboard.selectors.IncrementalPortfolioSimulator", DummyIncrementalPortfolioSimulator),
        ):
            detail = get_candidate_incremental_portfolio_comparison(
                {"candidate_compare": "1", "candidate_compare_block": "defensive"}
            )

        assert detail["submitted"] is True
        assert detail["selected_block"] == "defensive"
        assert detail["best_proposal_key"] == "KO"
        assert len(detail["proposals"]) == 3
        assert detail["proposals"][0]["comparison_score"] >= detail["proposals"][1]["comparison_score"]
        assert detail["proposals"][0]["proposal_label"] == "KO"
        assert detail["proposals"][0]["simulation_delta"]["fragility_change"] == -2.5

    def test_get_candidate_incremental_portfolio_comparison_handles_no_candidates(self):
        cache.clear()

        with (
            patch("apps.dashboard.selectors.get_monthly_allocation_plan", lambda capital_amount=600000: {"recommended_blocks": []}),
            patch("apps.dashboard.selectors.get_candidate_asset_ranking", lambda capital_amount=600000: {"by_block": []}),
        ):
            detail = get_candidate_incremental_portfolio_comparison({"candidate_compare": "1"})

        assert detail["submitted"] is True
        assert detail["available_blocks"] == []
        assert detail["proposals"] == []

    def test_get_candidate_split_incremental_portfolio_comparison_prefers_split_when_better(self):
        cache.clear()

        monthly_plan = {
            "capital_total": 600000,
            "recommended_blocks": [
                {"bucket": "defensive", "label": "Defensive / resiliente", "suggested_amount": 300000},
            ],
        }
        candidate_ranking = {
            "by_block": [
                {
                    "block": "defensive",
                    "candidates": [
                        {"asset": "KO", "score": 8.4, "main_reason": "defensive_sector_match"},
                        {"asset": "MCD", "score": 7.7, "main_reason": "dividend_profile"},
                    ],
                },
            ]
        }

        class DummyIncrementalPortfolioSimulator:
            def simulate(self, proposal):
                symbols = {item["symbol"] for item in proposal["purchase_plan"]}
                if symbols == {"KO"}:
                    return {
                        "before": {},
                        "after": {},
                        "delta": {
                            "expected_return_change": 0.3,
                            "real_expected_return_change": 0.1,
                            "fragility_change": -1.2,
                            "scenario_loss_change": 0.3,
                            "risk_concentration_change": -0.2,
                        },
                        "interpretation": "KO solo mejora de forma acotada.",
                        "warnings": [],
                    }
                return {
                    "before": {},
                    "after": {},
                    "delta": {
                        "expected_return_change": 0.5,
                        "real_expected_return_change": 0.2,
                        "fragility_change": -2.1,
                        "scenario_loss_change": 0.7,
                        "risk_concentration_change": -0.6,
                    },
                    "interpretation": "El split mejora mejor el balance riesgo/retorno.",
                    "warnings": [],
                }

        with (
            patch("apps.dashboard.selectors.get_monthly_allocation_plan", lambda capital_amount=600000: monthly_plan),
            patch("apps.dashboard.selectors.get_candidate_asset_ranking", lambda capital_amount=600000: candidate_ranking),
            patch("apps.dashboard.selectors.IncrementalPortfolioSimulator", DummyIncrementalPortfolioSimulator),
        ):
            detail = get_candidate_split_incremental_portfolio_comparison(
                {"candidate_split_compare": "1", "candidate_split_block": "defensive"}
            )

        assert detail["submitted"] is True
        assert detail["selected_block"] == "defensive"
        assert detail["best_proposal_key"] == "split_top_two"
        assert len(detail["proposals"]) == 2
        assert detail["proposals"][0]["proposal_label"] == detail["proposals"][0]["label"]
        assert detail["proposals"][0]["simulation_delta"]["expected_return_change"] == 0.5

    def test_get_candidate_split_incremental_portfolio_comparison_handles_missing_top_two(self):
        cache.clear()

        with (
            patch("apps.dashboard.selectors.get_monthly_allocation_plan", lambda capital_amount=600000: {"recommended_blocks": []}),
            patch("apps.dashboard.selectors.get_candidate_asset_ranking", lambda capital_amount=600000: {"by_block": []}),
        ):
            detail = get_candidate_split_incremental_portfolio_comparison({"candidate_split_compare": "1"})

        assert detail["submitted"] is True
        assert detail["available_blocks"] == []
        assert detail["proposals"] == []

    def test_get_preferred_incremental_portfolio_proposal_prefers_manual_when_present(self):
        cache.clear()

        with (
            patch("apps.dashboard.selectors.get_incremental_portfolio_simulation_comparison", lambda capital_amount=600000: {
                "best_proposal_key": "auto",
                "proposals": [
                    {
                        "proposal_key": "auto",
                        "label": "Top candidato por bloque",
                        "purchase_plan": [{"symbol": "KO", "amount": 300000}],
                        "simulation": {"delta": {}, "interpretation": "Auto."},
                        "comparison_score": 4.0,
                    }
                ],
            }),
            patch("apps.dashboard.selectors.get_candidate_incremental_portfolio_comparison", lambda query_params, capital_amount=600000: {
                "best_proposal_key": "KO",
                "selected_label": "Defensive / resiliente",
                "proposals": [
                    {
                        "proposal_key": "KO",
                        "label": "KO",
                        "purchase_plan": [{"symbol": "KO", "amount": 300000}],
                        "simulation": {"delta": {}, "interpretation": "Candidate."},
                        "comparison_score": 4.2,
                    }
                ],
            }),
            patch("apps.dashboard.selectors.get_candidate_split_incremental_portfolio_comparison", lambda query_params, capital_amount=600000: {
                "best_proposal_key": "split_top_two",
                "selected_label": "Defensive / resiliente",
                "proposals": [
                    {
                        "proposal_key": "split_top_two",
                        "label": "Split KO + MCD",
                        "purchase_plan": [{"symbol": "KO", "amount": 150000}, {"symbol": "MCD", "amount": 150000}],
                        "simulation": {"delta": {}, "interpretation": "Split."},
                        "comparison_score": 4.5,
                    }
                ],
            }),
            patch("apps.dashboard.selectors.get_manual_incremental_portfolio_simulation_comparison", lambda query_params, default_capital_amount=600000: {
                "submitted": True,
                "best_proposal_key": "plan_a",
                "proposals": [
                    {
                        "proposal_key": "plan_a",
                        "label": "Plan manual A",
                        "purchase_plan": [{"symbol": "SPY", "amount": 600000}],
                        "simulation": {"delta": {}, "interpretation": "Manual."},
                        "comparison_score": 4.5,
                    }
                ],
            }),
        ):
            detail = get_preferred_incremental_portfolio_proposal({"manual_compare": "1"})

        assert detail["preferred"]["source_key"] == "manual_plan"
        assert detail["preferred"]["proposal_label"] == "Plan manual A"
        assert detail["has_manual_override"] is True
        assert detail["preferred"]["label"] == "Plan manual A"
        assert detail["preferred"]["simulation_delta"] == {}
        assert detail["preferred"]["purchase_summary"] == "SPY (600000)"

    def test_get_preferred_incremental_portfolio_proposal_handles_no_candidates(self):
        cache.clear()

        with (
            patch("apps.dashboard.selectors.get_incremental_portfolio_simulation_comparison", lambda capital_amount=600000: {"best_proposal_key": None, "proposals": []}),
            patch("apps.dashboard.selectors.get_candidate_incremental_portfolio_comparison", lambda query_params, capital_amount=600000: {"best_proposal_key": None, "proposals": []}),
            patch("apps.dashboard.selectors.get_candidate_split_incremental_portfolio_comparison", lambda query_params, capital_amount=600000: {"best_proposal_key": None, "proposals": []}),
            patch("apps.dashboard.selectors.get_manual_incremental_portfolio_simulation_comparison", lambda query_params, default_capital_amount=600000: {"submitted": False, "best_proposal_key": None, "proposals": []}),
        ):
            detail = get_preferred_incremental_portfolio_proposal({})

        assert detail["preferred"] is None

    def test_get_incremental_proposal_history_wraps_recent_items(self):
        class DummyUser:
            is_authenticated = True

        with patch(
            "apps.dashboard.selectors.IncrementalProposalHistoryService.list_recent",
            return_value=[
                {
                    "proposal_label": "Plan manual A",
                    "capital_amount": 600000,
                    "purchase_plan": [
                        {"symbol": "ko", "amount": 200000},
                        {"symbol": "mcd", "amount": 200000},
                        {"symbol": "xlu", "amount": 200000},
                        {"symbol": "ko", "amount": 1000},
                    ],
                },
                {"proposal_label": "Split KO + MCD", "capital_amount": 300000, "purchase_plan": []},
            ],
        ) as mocked, patch(
            "apps.dashboard.selectors.IncrementalProposalHistoryService.get_decision_counts",
            return_value={"total": 2, "pending": 1, "accepted": 1, "deferred": 0, "rejected": 0},
        ):
            detail = get_incremental_proposal_history(user=DummyUser(), limit=5)

        mocked.assert_called_once()
        assert detail["count"] == 2
        assert detail["has_history"] is True
        assert detail["active_filter"] == "all"
        assert detail["items"][0]["proposal_label"] == "Plan manual A"
        assert detail["items"][0]["label"] == "Plan manual A"
        assert detail["items"][0]["purchase_summary"] == "ko (200000), mcd (200000), xlu (200000)"
        assert detail["items"][0]["simulation_delta"] == {}
        assert "manual_compare=1" in detail["items"][0]["reapply_querystring"]
        assert "plan_a_symbol_1=KO" in detail["items"][0]["reapply_querystring"]
        assert detail["items"][0]["reapply_truncated"] is True

    def test_get_incremental_proposal_history_supports_manual_decision_filter(self):
        class DummyUser:
            is_authenticated = True

        user = DummyUser()

        with patch(
            "apps.dashboard.selectors.IncrementalProposalHistoryService.list_recent",
            return_value=[
                {
                    "proposal_label": "Plan manual A",
                    "manual_decision_status": "accepted",
                    "capital_amount": 600000,
                    "purchase_plan": [],
                }
            ],
        ) as mocked, patch(
            "apps.dashboard.selectors.IncrementalProposalHistoryService.get_decision_counts",
            return_value={"total": 3, "pending": 1, "accepted": 1, "deferred": 1, "rejected": 0},
        ):
            detail = get_incremental_proposal_history(user=user, limit=5, decision_status="accepted")

        mocked.assert_called_once_with(user=user, limit=10, decision_status="accepted")
        assert detail["active_filter"] == "accepted"
        assert detail["active_filter_label"] == "Aceptada"
        assert detail["decision_counts"]["accepted"] == 1
        assert "decision aceptada" in detail["headline"].lower()

    def test_get_incremental_proposal_history_supports_priority_filter_and_sort(self):
        class DummyUser:
            is_authenticated = True

        user = DummyUser()

        with patch(
            "apps.dashboard.selectors.IncrementalProposalHistoryService.list_recent",
            return_value=[
                {
                    "id": 1,
                    "proposal_label": "Observacion",
                    "comparison_score": 3.9,
                    "purchase_plan": [{"symbol": "KO", "amount": 400000}],
                    "simulation_delta": {
                        "expected_return_change": 0.3,
                        "fragility_change": -1.0,
                        "scenario_loss_change": 0.2,
                    },
                    "manual_decision_status": "pending",
                },
                {
                    "id": 2,
                    "proposal_label": "Alta prioridad",
                    "comparison_score": 4.8,
                    "purchase_plan": [{"symbol": "MCD", "amount": 400000}],
                    "simulation_delta": {
                        "expected_return_change": 0.7,
                        "fragility_change": -1.5,
                        "scenario_loss_change": 0.4,
                    },
                    "manual_decision_status": "pending",
                },
            ],
        ) as mocked, patch(
            "apps.dashboard.selectors.IncrementalProposalHistoryService.get_decision_counts",
            return_value={"total": 2, "pending": 2, "accepted": 0, "deferred": 0, "rejected": 0},
        ), patch(
            "apps.dashboard.selectors.get_incremental_proposal_tracking_baseline",
            return_value={
                "item": {
                    "id": 10,
                    "proposal_label": "Baseline activo",
                    "comparison_score": 4.0,
                    "purchase_plan": [{"symbol": "SPY", "amount": 400000}],
                    "simulation_delta": {
                        "expected_return_change": 0.4,
                        "fragility_change": -1.0,
                        "scenario_loss_change": 0.2,
                    },
                },
                "has_baseline": True,
            },
        ):
            detail = get_incremental_proposal_history(
                user=user,
                limit=5,
                priority_filter="high",
                sort_mode="priority",
            )

        mocked.assert_called_once_with(user=user, limit=10, decision_status=None)
        assert detail["active_priority_filter"] == "high"
        assert detail["active_sort_mode"] == "priority"
        assert detail["count"] == 1
        assert detail["items"][0]["proposal_label"] == "Alta prioridad"
        assert detail["items"][0]["history_priority"]["priority"] == "high"
        assert "prioridad: alta" in detail["headline"].lower()
        assert "ordenados por prioridad operativa" in detail["headline"].lower()

    def test_get_incremental_proposal_tracking_baseline_wraps_single_item(self):
        class DummyUser:
            is_authenticated = True
            pk = 1

        with patch(
            "apps.dashboard.selectors.IncrementalProposalHistoryService.get_tracking_baseline",
            return_value={"proposal_label": "Plan baseline", "is_tracking_baseline": True},
        ) as mocked:
            detail = get_incremental_proposal_tracking_baseline(user=DummyUser())

        mocked.assert_called_once()
        assert detail["has_baseline"] is True
        assert detail["item"]["proposal_label"] == "Plan baseline"

    def test_get_incremental_baseline_drift_classifies_metric_direction(self):
        class DummyUser:
            is_authenticated = True

        with (
            patch(
                "apps.dashboard.selectors.get_incremental_proposal_tracking_baseline",
                return_value={
                    "item": {
                        "proposal_label": "Baseline defensivo",
                        "comparison_score": 4.0,
                        "simulation_delta": {
                            "expected_return_change": 0.3,
                            "real_expected_return_change": 0.1,
                            "fragility_change": -1.0,
                            "scenario_loss_change": 0.2,
                            "risk_concentration_change": -0.4,
                        },
                    },
                    "has_baseline": True,
                },
            ),
            patch(
                "apps.dashboard.selectors.get_preferred_incremental_portfolio_proposal",
                return_value={
                    "preferred": {
                        "proposal_label": "Propuesta actual",
                        "comparison_score": 4.8,
                        "simulation": {
                            "delta": {
                                "expected_return_change": 0.5,
                                "real_expected_return_change": 0.05,
                                "fragility_change": -1.8,
                                "scenario_loss_change": 0.4,
                                "risk_concentration_change": -0.2,
                            }
                        },
                    }
                },
            ),
        ):
            detail = get_incremental_baseline_drift({}, user=DummyUser(), capital_amount=600000)

        assert detail["has_drift"] is True
        assert detail["summary"]["status"] == "mixed"
        assert detail["summary"]["favorable_count"] == 3
        assert detail["summary"]["unfavorable_count"] == 2
        assert detail["has_alerts"] is True
        assert detail["alerts"][0]["severity"] == "warning"
        assert "drift mixto" in detail["alerts"][0]["title"].lower()
        assert detail["comparison"]["winner"] == "current"
        directions = {item["key"]: item["direction"] for item in detail["summary"]["material_metrics"]}
        assert directions["expected_return_change"] == "favorable"
        assert directions["fragility_change"] == "favorable"
        assert directions["real_expected_return_change"] == "unfavorable"
        assert "se desvia del baseline activo" in detail["explanation"]

    def test_get_incremental_baseline_drift_handles_missing_baseline(self):
        class DummyUser:
            is_authenticated = True

        with (
            patch(
                "apps.dashboard.selectors.get_incremental_proposal_tracking_baseline",
                return_value={"item": None, "has_baseline": False},
            ),
            patch(
                "apps.dashboard.selectors.get_preferred_incremental_portfolio_proposal",
                return_value={"preferred": {"proposal_label": "Propuesta actual"}},
            ),
        ):
            detail = get_incremental_baseline_drift({}, user=DummyUser(), capital_amount=600000)

        assert detail["has_drift"] is False
        assert detail["summary"]["status"] == "unavailable"
        assert detail["alerts"] == []
        assert "Todavia no hay un baseline incremental activo" in detail["explanation"]

    def test_get_incremental_followup_executive_summary_synthesizes_review_state(self):
        class DummyUser:
            is_authenticated = True

        with (
            patch(
                "apps.dashboard.selectors.get_preferred_incremental_portfolio_proposal",
                return_value={
                    "preferred": {
                        "proposal_label": "Propuesta actual",
                        "comparison_score": 3.8,
                    }
                },
            ),
            patch(
                "apps.dashboard.selectors.get_incremental_proposal_tracking_baseline",
                return_value={
                    "item": {
                        "proposal_label": "Baseline defensivo",
                        "comparison_score": 4.5,
                    },
                    "has_baseline": True,
                },
            ),
            patch(
                "apps.dashboard.selectors.get_incremental_baseline_drift",
                return_value={
                    "summary": {
                        "status": "unfavorable",
                        "favorable_count": 1,
                        "unfavorable_count": 3,
                    }
                },
            ),
        ):
            detail = get_incremental_followup_executive_summary({}, user=DummyUser(), capital_amount=600000)

        assert detail["status"] == "review"
        assert detail["has_summary"] is True
        assert "conviene revisarla" in detail["headline"]
        summary = {item["label"]: item["value"] for item in detail["summary_items"]}
        assert summary["Propuesta actual"] == "Propuesta actual"
        assert summary["Baseline activo"] == "Baseline defensivo"
        assert summary["Estado de drift"] == "Drift desfavorable"
        assert summary["Score actual - baseline"] == -0.7

    def test_get_incremental_followup_executive_summary_handles_missing_preferred(self):
        class DummyUser:
            is_authenticated = True

        with (
            patch(
                "apps.dashboard.selectors.get_preferred_incremental_portfolio_proposal",
                return_value={"preferred": None},
            ),
            patch(
                "apps.dashboard.selectors.get_incremental_proposal_tracking_baseline",
                return_value={"item": None, "has_baseline": False},
            ),
            patch(
                "apps.dashboard.selectors.get_incremental_baseline_drift",
                return_value={"summary": {"status": "unavailable", "favorable_count": 0, "unfavorable_count": 0}},
            ),
        ):
            detail = get_incremental_followup_executive_summary({}, user=DummyUser(), capital_amount=600000)

        assert detail["status"] == "pending"
        assert detail["has_summary"] is False
        assert "Todavia no hay una propuesta incremental preferida" in detail["headline"]

    def test_get_incremental_adoption_checklist_marks_review_when_drift_is_unfavorable(self):
        class DummyUser:
            is_authenticated = True

        with (
            patch(
                "apps.dashboard.selectors.get_preferred_incremental_portfolio_proposal",
                return_value={
                    "preferred": {
                        "proposal_label": "Propuesta actual",
                        "purchase_plan": [{"symbol": "KO", "amount": 300000}],
                    }
                },
            ),
            patch(
                "apps.dashboard.selectors.get_incremental_proposal_tracking_baseline",
                return_value={"item": {"proposal_label": "Baseline activo"}, "has_baseline": True},
            ),
            patch(
                "apps.dashboard.selectors.get_incremental_baseline_drift",
                return_value={
                    "summary": {"status": "unfavorable"},
                    "alerts": [{"severity": "critical", "title": "Drift critico"}],
                },
            ),
            patch(
                "apps.dashboard.selectors.get_incremental_followup_executive_summary",
                return_value={"headline": "Conviene revisarla antes de adoptarla."},
            ),
        ):
            detail = get_incremental_adoption_checklist({}, user=DummyUser(), capital_amount=600000)

        assert detail["status"] == "review"
        assert detail["adoption_ready"] is False
        assert detail["passed_count"] == 3
        checks = {item["key"]: item for item in detail["items"]}
        assert checks["preferred_available"]["passed"] is True
        assert checks["purchase_plan_available"]["passed"] is True
        assert checks["drift_not_unfavorable"]["passed"] is False
        assert checks["critical_drift_alerts"]["passed"] is False

    def test_get_incremental_adoption_checklist_marks_ready_when_checks_pass(self):
        class DummyUser:
            is_authenticated = True

        with (
            patch(
                "apps.dashboard.selectors.get_preferred_incremental_portfolio_proposal",
                return_value={
                    "preferred": {
                        "proposal_label": "Propuesta actual",
                        "purchase_plan": [{"symbol": "KO", "amount": 300000}],
                    }
                },
            ),
            patch(
                "apps.dashboard.selectors.get_incremental_proposal_tracking_baseline",
                return_value={"item": {"proposal_label": "Baseline activo"}, "has_baseline": True},
            ),
            patch(
                "apps.dashboard.selectors.get_incremental_baseline_drift",
                return_value={
                    "summary": {"status": "favorable"},
                    "alerts": [{"severity": "info", "title": "Sin drift material"}],
                },
            ),
            patch(
                "apps.dashboard.selectors.get_incremental_followup_executive_summary",
                return_value={"headline": "La propuesta actual supera el checklist."},
            ),
        ):
            detail = get_incremental_adoption_checklist({}, user=DummyUser(), capital_amount=600000)

        assert detail["status"] == "ready"
        assert detail["adoption_ready"] is True
        assert detail["passed_count"] == 5
        assert "puede pasar a decision manual" in detail["headline"]

    def test_get_incremental_manual_decision_summary_returns_latest_decision(self):
        class DummyUser:
            is_authenticated = True

        with patch(
            "apps.dashboard.selectors.IncrementalProposalHistoryService.get_latest_manual_decision",
            return_value={
                "proposal_label": "Plan manual A",
                "manual_decision_status": "accepted",
                "manual_decision_note": "Lista para ejecutar",
                "manual_decided_at": timezone.now(),
            },
        ):
            detail = get_incremental_manual_decision_summary(user=DummyUser())

        assert detail["has_decision"] is True
        assert detail["status"] == "accepted"
        assert detail["status_label"] == "Aceptada"
        assert "Plan manual A" in detail["headline"]

    def test_get_incremental_manual_decision_summary_handles_missing_decision(self):
        class DummyUser:
            is_authenticated = True

        with patch(
            "apps.dashboard.selectors.IncrementalProposalHistoryService.get_latest_manual_decision",
            return_value=None,
        ):
            detail = get_incremental_manual_decision_summary(user=DummyUser())

        assert detail["has_decision"] is False
        assert detail["status"] == "pending"
        assert "Todavia no registraste" in detail["headline"]

    def test_get_incremental_pending_backlog_vs_baseline_compares_pending_snapshots(self):
        class DummyUser:
            is_authenticated = True

        with (
            patch(
                "apps.dashboard.selectors.get_incremental_proposal_tracking_baseline",
                return_value={
                    "item": {
                        "proposal_label": "Baseline activo",
                        "comparison_score": 4.0,
                        "simulation_delta": {
                            "expected_return_change": 0.4,
                            "real_expected_return_change": 0.1,
                            "fragility_change": -1.0,
                            "scenario_loss_change": 0.2,
                            "risk_concentration_change": -0.4,
                        },
                    },
                    "has_baseline": True,
                },
            ),
            patch(
                "apps.dashboard.selectors.get_incremental_proposal_history",
                return_value={
                    "items": [
                        {
                            "proposal_label": "Pendiente A",
                            "selected_context": "Defensive / resiliente",
                            "comparison_score": 5.1,
                            "simulation_delta": {
                                "expected_return_change": 0.7,
                                "real_expected_return_change": 0.2,
                                "fragility_change": -1.5,
                                "scenario_loss_change": 0.5,
                                "risk_concentration_change": -0.8,
                            },
                        },
                        {
                            "proposal_label": "Pendiente B",
                            "comparison_score": 3.5,
                            "simulation_delta": {
                                "expected_return_change": 0.2,
                                "real_expected_return_change": 0.05,
                                "fragility_change": -0.7,
                                "scenario_loss_change": 0.1,
                                "risk_concentration_change": -0.1,
                            },
                        },
                    ],
                    "count": 2,
                    "decision_counts": {"total": 4, "pending": 2, "accepted": 1, "deferred": 1, "rejected": 0},
                },
            ),
        ):
            detail = get_incremental_pending_backlog_vs_baseline(user=DummyUser(), limit=5)

        assert detail["has_baseline"] is True
        assert detail["has_pending_backlog"] is True
        assert detail["better_count"] == 1
        assert detail["worse_count"] == 1
        assert detail["tie_count"] == 0
        assert detail["best_candidate"]["snapshot"]["proposal_label"] == "Pendiente A"
        assert "superan el baseline" in detail["headline"]
        assert "alternativa superior" in detail["explanation"]

    def test_get_incremental_pending_backlog_vs_baseline_handles_missing_baseline(self):
        class DummyUser:
            is_authenticated = True

        with (
            patch(
                "apps.dashboard.selectors.get_incremental_proposal_tracking_baseline",
                return_value={"item": None, "has_baseline": False},
            ),
            patch(
                "apps.dashboard.selectors.get_incremental_proposal_history",
                return_value={
                    "items": [{"proposal_label": "Pendiente A", "comparison_score": 5.1, "simulation_delta": {}}],
                    "count": 1,
                    "decision_counts": {"total": 1, "pending": 1, "accepted": 0, "deferred": 0, "rejected": 0},
                },
            ),
        ):
            detail = get_incremental_pending_backlog_vs_baseline(user=DummyUser(), limit=5)

        assert detail["has_baseline"] is False
        assert detail["has_pending_backlog"] is True
        assert detail["has_comparable_items"] is False
        assert detail["better_count"] == 0
        assert "todavia no existe baseline activo" in detail["headline"].lower()
        assert "Conviene fijar un baseline" in detail["explanation"]

    def test_get_incremental_backlog_prioritization_orders_items_by_priority(self):
        class DummyUser:
            is_authenticated = True

        with patch(
            "apps.dashboard.selectors.get_incremental_pending_backlog_vs_baseline",
            return_value={
                "baseline": {"proposal_label": "Baseline activo"},
                "items": [
                    {
                        "snapshot": {"proposal_label": "Pendiente baja", "is_backlog_front": False},
                        "score_difference": -0.4,
                        "beats_baseline": False,
                        "loses_vs_baseline": True,
                        "ties_baseline": False,
                        "improves_profitability": False,
                        "protects_fragility": False,
                        "tactical_clean": False,
                    },
                    {
                        "snapshot": {"proposal_label": "Pendiente alta", "is_backlog_front": False},
                        "score_difference": 0.6,
                        "beats_baseline": True,
                        "loses_vs_baseline": False,
                        "ties_baseline": False,
                        "improves_profitability": True,
                        "protects_fragility": True,
                        "tactical_clean": True,
                    },
                    {
                        "snapshot": {"proposal_label": "Pendiente media", "is_backlog_front": False},
                        "score_difference": 0.0,
                        "beats_baseline": False,
                        "loses_vs_baseline": False,
                        "ties_baseline": True,
                        "improves_profitability": False,
                        "protects_fragility": True,
                        "tactical_clean": True,
                    },
                ],
                "has_baseline": True,
                "has_pending_backlog": True,
            },
        ):
            detail = get_incremental_backlog_prioritization(user=DummyUser(), limit=5)

        assert detail["has_priorities"] is True
        assert detail["counts"] == {"high": 1, "medium": 0, "watch": 1, "low": 1}
        assert [item["snapshot"]["proposal_label"] for item in detail["items"]] == [
            "Pendiente alta",
            "Pendiente media",
            "Pendiente baja",
        ]
        assert detail["top_item"]["priority"] == "high"
        assert "Backlog priorizado" in detail["headline"]

    def test_get_incremental_backlog_prioritization_marks_recoverable_when_beats_baseline_but_tactical_fit_is_weaker(self):
        class DummyUser:
            is_authenticated = True

        with patch(
            "apps.dashboard.selectors.get_incremental_pending_backlog_vs_baseline",
            return_value={
                "baseline": {"proposal_label": "Baseline activo"},
                "items": [
                    {
                        "snapshot": {"proposal_label": "Pendiente recuperable", "is_backlog_front": False},
                        "score_difference": 0.2,
                        "beats_baseline": True,
                        "loses_vs_baseline": False,
                        "ties_baseline": False,
                        "improves_profitability": True,
                        "protects_fragility": True,
                        "tactical_clean": False,
                    },
                ],
                "has_baseline": True,
                "has_pending_backlog": True,
            },
        ):
            detail = get_incremental_backlog_prioritization(user=DummyUser(), limit=5)

        assert detail["items"][0]["priority"] == "medium"
        assert detail["items"][0]["priority_label"] == "Recuperable"
        assert "recuperable" in detail["items"][0]["next_action"].lower()
        assert "alternativas recuperables" in detail["explanation"].lower()

    def test_get_incremental_backlog_prioritization_handles_missing_inputs(self):
        class DummyUser:
            is_authenticated = True

        with patch(
            "apps.dashboard.selectors.get_incremental_pending_backlog_vs_baseline",
            return_value={
                "baseline": None,
                "items": [],
                "has_baseline": False,
                "has_pending_backlog": False,
            },
        ):
            detail = get_incremental_backlog_prioritization(user=DummyUser(), limit=5)

        assert detail["has_priorities"] is False
        assert detail["top_item"] is None
        assert "Todavia no hay backlog pendiente priorizable" in detail["headline"]
        assert "Todavia no hay insumos" in detail["explanation"]

    def test_get_incremental_backlog_prioritization_prefers_manual_front_snapshot(self):
        class DummyUser:
            is_authenticated = True

        with patch(
            "apps.dashboard.selectors.get_incremental_pending_backlog_vs_baseline",
            return_value={
                "baseline": {"proposal_label": "Baseline activo"},
                "items": [
                    {
                        "snapshot": {"proposal_label": "Pendiente alta", "is_backlog_front": False},
                        "score_difference": 0.6,
                        "beats_baseline": True,
                        "loses_vs_baseline": False,
                        "ties_baseline": False,
                    },
                    {
                        "snapshot": {"proposal_label": "Pendiente manual", "is_backlog_front": True},
                        "score_difference": 0.0,
                        "beats_baseline": False,
                        "loses_vs_baseline": False,
                        "ties_baseline": True,
                    },
                ],
                "has_baseline": True,
                "has_pending_backlog": True,
            },
        ):
            detail = get_incremental_backlog_prioritization(user=DummyUser(), limit=5)

        assert detail["top_item"]["snapshot"]["proposal_label"] == "Pendiente manual"
        assert detail["items"][0]["priority"] == "watch"
        assert "frente manual" in detail["headline"].lower()
        assert "promovido manualmente" in detail["explanation"].lower()

    def test_get_incremental_backlog_front_summary_summarizes_baseline_and_front(self):
        class DummyUser:
            is_authenticated = True

        with (
            patch(
                "apps.dashboard.selectors.get_incremental_proposal_tracking_baseline",
                return_value={"item": {"proposal_label": "Baseline activo"}, "has_baseline": True},
            ),
            patch(
                "apps.dashboard.selectors.get_incremental_backlog_prioritization",
                return_value={
                    "counts": {"high": 1, "medium": 0, "low": 1},
                    "top_item": {
                        "snapshot": {"proposal_label": "Pendiente A", "is_backlog_front": True},
                        "priority": "high",
                        "priority_label": "Alta",
                        "score_difference": 0.7,
                    },
                },
            ),
        ):
            detail = get_incremental_backlog_front_summary(user=DummyUser(), limit=5)

        assert detail["status"] == "manual_front"
        assert detail["has_summary"] is True
        assert detail["items"][0]["value"] == "Baseline activo"
        assert detail["items"][1]["value"] == "Pendiente A"
        assert "lidera el backlog" in detail["headline"].lower()

    def test_get_incremental_backlog_front_summary_handles_empty_state(self):
        class DummyUser:
            is_authenticated = True

        with (
            patch(
                "apps.dashboard.selectors.get_incremental_proposal_tracking_baseline",
                return_value={"item": None, "has_baseline": False},
            ),
            patch(
                "apps.dashboard.selectors.get_incremental_backlog_prioritization",
                return_value={"counts": {"high": 0, "medium": 0, "low": 0}, "top_item": None},
            ),
        ):
            detail = get_incremental_backlog_front_summary(user=DummyUser(), limit=5)

        assert detail["status"] == "empty"
        assert detail["has_summary"] is False
        assert "Todavia no hay baseline activo" in detail["headline"]

    def test_get_incremental_backlog_operational_semaphore_marks_red_with_unfavorable_drift(self):
        class DummyUser:
            is_authenticated = True

        with (
            patch(
                "apps.dashboard.selectors.get_incremental_baseline_drift",
                return_value={
                    "summary": {"status": "unfavorable"},
                    "has_baseline": True,
                    "explanation": "La propuesta actual empeora frente al baseline.",
                },
            ),
            patch(
                "apps.dashboard.selectors.get_incremental_backlog_front_summary",
                return_value={"status": "baseline_only", "has_summary": True, "front_item": None, "headline": "Baseline activo sin backlog urgente."},
            ),
            patch(
                "apps.dashboard.selectors.get_incremental_backlog_prioritization",
                return_value={"counts": {"high": 0, "medium": 0, "low": 0}},
            ),
        ):
            detail = get_incremental_backlog_operational_semaphore({}, user=DummyUser(), capital_amount=600000, limit=5)

        assert detail["status"] == "red"
        assert detail["label"] == "Rojo"
        assert "Semáforo rojo" in detail["headline"]

    def test_get_incremental_backlog_operational_semaphore_marks_yellow_with_high_priority_backlog(self):
        class DummyUser:
            is_authenticated = True

        with (
            patch(
                "apps.dashboard.selectors.get_incremental_baseline_drift",
                return_value={
                    "summary": {"status": "stable"},
                    "has_baseline": True,
                    "explanation": "Sin drift material.",
                },
            ),
            patch(
                "apps.dashboard.selectors.get_incremental_backlog_front_summary",
                return_value={
                    "status": "candidate_over_baseline",
                    "has_summary": True,
                    "front_item": {"snapshot": {"proposal_label": "Pendiente A"}},
                    "headline": "Pendiente A ya supera al baseline activo.",
                },
            ),
            patch(
                "apps.dashboard.selectors.get_incremental_backlog_prioritization",
                return_value={"counts": {"high": 1, "medium": 0, "low": 0}},
            ),
        ):
            detail = get_incremental_backlog_operational_semaphore({}, user=DummyUser(), capital_amount=600000, limit=5)

        assert detail["status"] == "yellow"
        assert detail["label"] == "Amarillo"
        assert "Pendiente A" in detail["headline"]

    def test_get_incremental_backlog_operational_semaphore_marks_green_when_baseline_holds(self):
        class DummyUser:
            is_authenticated = True

        with (
            patch(
                "apps.dashboard.selectors.get_incremental_baseline_drift",
                return_value={
                    "summary": {"status": "favorable"},
                    "has_baseline": True,
                    "explanation": "La propuesta actual mejora el baseline activo.",
                },
            ),
            patch(
                "apps.dashboard.selectors.get_incremental_backlog_front_summary",
                return_value={"status": "baseline_only", "has_summary": True, "front_item": None, "headline": "Baseline activo sin backlog urgente."},
            ),
            patch(
                "apps.dashboard.selectors.get_incremental_backlog_prioritization",
                return_value={"counts": {"high": 0, "medium": 0, "low": 0}},
            ),
        ):
            detail = get_incremental_backlog_operational_semaphore({}, user=DummyUser(), capital_amount=600000, limit=5)

        assert detail["status"] == "green"
        assert detail["label"] == "Verde"
        assert "Semáforo verde" in detail["headline"]

    def test_get_incremental_decision_executive_summary_marks_adopt_when_green_and_ready(self):
        class DummyUser:
            is_authenticated = True

        with (
            patch(
                "apps.dashboard.selectors.get_incremental_backlog_operational_semaphore",
                return_value={
                    "status": "green",
                    "label": "Verde",
                    "headline": "Semaforo verde: el baseline sigue firme.",
                    "items": [],
                    "has_signal": True,
                },
            ),
            patch(
                "apps.dashboard.selectors.get_incremental_followup_executive_summary",
                return_value={
                    "status": "aligned",
                    "headline": "La propuesta actual sigue alineada.",
                    "has_summary": True,
                },
            ),
            patch(
                "apps.dashboard.selectors.get_incremental_adoption_checklist",
                return_value={
                    "status": "ready",
                    "passed_count": 5,
                    "total_count": 5,
                    "headline": "Checklist completo.",
                },
            ),
            patch(
                "apps.dashboard.selectors.get_incremental_backlog_front_summary",
                return_value={
                    "has_summary": True,
                    "front_item": {"snapshot": {"proposal_label": "Pendiente A"}},
                },
            ),
        ):
            detail = get_incremental_decision_executive_summary({}, user=DummyUser(), capital_amount=600000, limit=5)

        assert detail["status"] == "adopt"
        assert detail["has_summary"] is True
        assert detail["items"][0]["label"] == "Semáforo operativo"
        assert detail["items"][0]["value"] == "Verde"
        assert "adop" in detail["headline"].lower()

    def test_get_incremental_decision_executive_summary_marks_review_backlog_when_yellow(self):
        class DummyUser:
            is_authenticated = True

        with (
            patch(
                "apps.dashboard.selectors.get_incremental_backlog_operational_semaphore",
                return_value={
                    "status": "yellow",
                    "label": "Amarillo",
                    "headline": "Hay backlog incremental que merece revision.",
                    "items": [],
                    "has_signal": True,
                },
            ),
            patch(
                "apps.dashboard.selectors.get_incremental_followup_executive_summary",
                return_value={
                    "status": "watch",
                    "headline": "Seguir de cerca la propuesta actual.",
                    "has_summary": True,
                },
            ),
            patch(
                "apps.dashboard.selectors.get_incremental_adoption_checklist",
                return_value={
                    "status": "review",
                    "passed_count": 3,
                    "total_count": 5,
                    "headline": "Checklist incompleto.",
                },
            ),
            patch(
                "apps.dashboard.selectors.get_incremental_backlog_front_summary",
                return_value={
                    "headline": "Pendiente A lidera el backlog frente al baseline.",
                    "has_summary": True,
                    "front_item": {"snapshot": {"proposal_label": "Pendiente A"}},
                },
            ),
        ):
            detail = get_incremental_decision_executive_summary({}, user=DummyUser(), capital_amount=600000, limit=5)

        assert detail["status"] == "review_backlog"
        assert detail["items"][3]["value"] == "Pendiente A"
        assert "Pendiente A lidera el backlog" in detail["headline"]

    def test_get_planeacion_incremental_context_concentrates_incremental_contract(self):
        class DummyUser:
            is_authenticated = True

        with (
            patch(
                "apps.dashboard.selectors._build_portfolio_scope_summary",
                return_value={"portfolio_total_broker": 1500000.0, "cash_available_broker": 250000.0},
            ) as portfolio_scope,
            patch(
                "apps.dashboard.selectors.get_monthly_allocation_plan",
                return_value={"capital_total": 600000},
            ) as monthly_plan,
            patch(
                "apps.dashboard.selectors.get_candidate_asset_ranking",
                return_value={"candidate_assets_count": 2},
            ) as candidate_ranking,
            patch(
                "apps.dashboard.selectors.get_incremental_portfolio_simulation",
                return_value={"interpretation": "ok"},
            ) as simulation,
            patch(
                "apps.dashboard.selectors.get_incremental_portfolio_simulation_comparison",
                return_value={"best_label": "Top candidato por bloque"},
            ) as simulation_comparison,
            patch(
                "apps.dashboard.selectors.get_candidate_incremental_portfolio_comparison",
                return_value={"selected_block": "defensive"},
            ) as candidate_comparison,
            patch(
                "apps.dashboard.selectors.get_candidate_split_incremental_portfolio_comparison",
                return_value={"selected_block": "defensive"},
            ) as split_comparison,
            patch(
                "apps.dashboard.selectors.get_manual_incremental_portfolio_simulation_comparison",
                return_value={"submitted": False},
            ) as manual_comparison,
            patch(
                "apps.dashboard.selectors.get_preferred_incremental_portfolio_proposal",
                return_value={"preferred": {"proposal_label": "Split KO + MCD"}},
            ) as preferred,
            patch(
                "apps.dashboard.selectors.get_decision_engine_summary",
                return_value={"score": 78, "confidence": "Alta"},
            ) as decision_engine,
            patch(
                "apps.dashboard.selectors.get_incremental_proposal_history",
                return_value={"count": 1, "active_filter": "pending"},
            ) as history,
            patch(
                "apps.dashboard.selectors.get_incremental_proposal_tracking_baseline",
                return_value={"has_baseline": True},
            ) as baseline,
            patch(
                "apps.dashboard.selectors.get_incremental_manual_decision_summary",
                return_value={"has_decision": True},
            ) as decision_summary,
            patch(
                "apps.dashboard.selectors.get_incremental_decision_executive_summary",
                return_value={"status": "review_backlog"},
            ) as executive_summary,
        ):
            detail = get_planeacion_incremental_context(
                {"decision_status_filter": "pending"},
                user=DummyUser(),
                capital_amount=700000,
                history_limit=7,
            )

        assert detail["portfolio_scope_summary"]["portfolio_total_broker"] == 1500000.0
        assert detail["monthly_allocation_plan"]["capital_total"] == 600000
        assert detail["candidate_asset_ranking"]["candidate_assets_count"] == 2
        assert detail["incremental_portfolio_simulation"]["interpretation"] == "ok"
        assert detail["incremental_portfolio_simulation_comparison"]["best_label"] == "Top candidato por bloque"
        assert detail["candidate_incremental_portfolio_comparison"]["selected_block"] == "defensive"
        assert detail["candidate_split_incremental_portfolio_comparison"]["selected_block"] == "defensive"
        assert detail["manual_incremental_portfolio_simulation_comparison"]["submitted"] is False
        assert detail["preferred_incremental_portfolio_proposal"]["preferred"]["proposal_label"] == "Split KO + MCD"
        assert detail["decision_engine_summary"]["score"] == 78
        assert detail["incremental_proposal_history"]["active_filter"] == "pending"
        assert detail["incremental_proposal_tracking_baseline"]["has_baseline"] is True
        assert detail["incremental_manual_decision_summary"]["has_decision"] is True
        assert detail["incremental_decision_executive_summary"]["status"] == "review_backlog"

        portfolio_scope.assert_called_once_with()
        monthly_plan.assert_called_once_with(capital_amount=700000)
        candidate_ranking.assert_called_once_with(capital_amount=700000)
        simulation.assert_called_once_with(capital_amount=700000)
        simulation_comparison.assert_called_once_with(capital_amount=700000)
        candidate_comparison.assert_called_once_with({"decision_status_filter": "pending"}, capital_amount=700000)
        split_comparison.assert_called_once_with({"decision_status_filter": "pending"}, capital_amount=700000)
        manual_comparison.assert_called_once_with({"decision_status_filter": "pending"}, default_capital_amount=700000)
        preferred.assert_called_once_with({"decision_status_filter": "pending"}, capital_amount=700000)
        decision_engine.assert_called_once_with(ANY, query_params={"decision_status_filter": "pending"}, capital_amount=700000)
        assert history.call_count == 2
        history.assert_any_call(user=ANY, limit=7, decision_status="pending")
        assert baseline.call_count == 2
        baseline.assert_any_call(user=ANY)
        decision_summary.assert_called_once_with(user=ANY)
        executive_summary.assert_called_once_with({"decision_status_filter": "pending"}, user=ANY, capital_amount=700000, limit=7)

    def test_concentracion_por_pais(self):
        """Debe distinguir base invertida vs base total IOL."""
        fecha = timezone.now()

        ParametroActivo.objects.create(
            simbolo='AAPL',
            sector='Tecnología',
            bloque_estrategico='Inversión',
            pais_exposicion='Estados Unidos',
            tipo_patrimonial='Growth',
        )
        ParametroActivo.objects.create(
            simbolo='YPF',
            sector='Energía',
            bloque_estrategico='Inversión',
            pais_exposicion='Argentina',
            tipo_patrimonial='Equity',
        )
        ParametroActivo.objects.create(
            simbolo='ADBAICA',
            sector='Cash Mgmt',
            bloque_estrategico='Liquidez',
            pais_exposicion='Argentina',
            tipo_patrimonial='FCI',
        )
        ParametroActivo.objects.create(
            simbolo='CAU1',
            sector='Liquidez',
            bloque_estrategico='Liquidez',
            pais_exposicion='Argentina',
            tipo_patrimonial='Cash',
        )
        make_activo(fecha, 'AAPL', valorizado=1000.00, moneda='USD')
        make_activo(fecha, 'YPF', valorizado=500.00)
        make_activo(fecha, 'ADBAICA', valorizado=200.00, tipo='FondoComundeInversion')
        make_activo(fecha, 'CAU1', valorizado=300.00, tipo='CAUCIONESPESOS')
        make_resumen(fecha, disponible=400.00)

        concentracion = get_concentracion_pais()
        concentracion_total_iol = get_concentracion_pais(base='total_iol')

        assert abs(concentracion['USA'] - 66.67) < 0.01
        assert abs(concentracion['Argentina'] - 33.33) < 0.01
        assert abs(concentracion_total_iol['USA'] - 41.67) < 0.01
        assert abs(concentracion_total_iol['Argentina'] - 58.33) < 0.01

    def test_rendimiento_total_usa_solo_portafolio_invertido_sobre_costo_estimado(self):
        fecha = timezone.now()

        make_activo(fecha, 'AAPL', valorizado=1000.00, ganancia_dinero=200.00, tipo='ACCIONES', moneda='USD')
        make_activo(fecha, 'ADBAICA', valorizado=500.00, ganancia_dinero=50.00, tipo='FondoComundeInversion')
        make_activo(fecha, 'CAU1', valorizado=1500.00, ganancia_dinero=10.00, tipo='CAUCIONESPESOS')

        kpis = get_dashboard_kpis()

        assert abs(float(kpis['rendimiento_total_porcentaje']) - 25.0) < 0.01

    def test_concentracion_por_tipo_patrimonial(self):
        """Test cálculo de concentración por tipo patrimonial."""
        fecha = timezone.now()

        ParametroActivo.objects.create(
            simbolo='AAPL',
            sector='Tecnología',
            bloque_estrategico='Inversión',
            pais_exposicion='USA',
            tipo_patrimonial='Growth',
        )
        make_activo(fecha, 'AAPL', valorizado=1000.00, moneda='USD')

        concentracion = get_concentracion_tipo_patrimonial()
        assert 'Growth' in concentracion
        assert concentracion['Growth'] == 100.0

    def test_concentracion_sector_agregado_unifica_subsectores_tecnologicos(self):
        fecha = timezone.now()

        ParametroActivo.objects.create(
            simbolo='AAPL',
            sector='Tecnología',
            bloque_estrategico='Growth',
            pais_exposicion='USA',
            tipo_patrimonial='Growth',
        )
        ParametroActivo.objects.create(
            simbolo='MELI',
            sector='Tecnología / E-commerce',
            bloque_estrategico='Growth',
            pais_exposicion='Latam',
            tipo_patrimonial='Growth',
        )
        ParametroActivo.objects.create(
            simbolo='AMD',
            sector='Tecnología / Semiconductores',
            bloque_estrategico='Growth',
            pais_exposicion='USA',
            tipo_patrimonial='Growth',
        )
        ParametroActivo.objects.create(
            simbolo='KO',
            sector='Consumo defensivo',
            bloque_estrategico='Dividendos',
            pais_exposicion='USA',
            tipo_patrimonial='Equity',
        )
        make_activo(fecha, 'AAPL', valorizado=400.00, tipo='CEDEARS', moneda='USD')
        make_activo(fecha, 'MELI', valorizado=300.00, tipo='CEDEARS', moneda='USD')
        make_activo(fecha, 'AMD', valorizado=100.00, tipo='CEDEARS', moneda='USD')
        make_activo(fecha, 'KO', valorizado=200.00, tipo='CEDEARS', moneda='USD')

        concentracion = get_concentracion_sector_agregado()

        assert abs(float(concentracion['Tecnologia Total']) - 80.0) < 0.01
        assert abs(float(concentracion['Consumo defensivo']) - 20.0) < 0.01

    def test_distribucion_moneda_vs_moneda_operativa(self):
        """Test diferencia entre exposición económica vs operativa."""
        fecha = timezone.now()

        ParametroActivo.objects.create(
            simbolo='AAPL',
            sector='Tecnología',
            bloque_estrategico='Inversión',
            pais_exposicion='USA',
            tipo_patrimonial='Growth',
        )
        make_activo(fecha, 'AAPL', valorizado=1000.00, tipo='CEDEARS', moneda='peso_Argentino')

        # Moneda económica (exposición real)
        distribucion_economica = get_distribucion_moneda()
        assert distribucion_economica['USD'] == 1000.00  # Exposición real USD

        # Moneda operativa (cotización)
        distribucion_operativa = get_distribucion_moneda_operativa()
        assert distribucion_operativa['ARS'] == 1000.00  # Cotiza en ARS

        concentracion_economica = get_concentracion_moneda()
        concentracion_operativa = get_concentracion_moneda_operativa()
        assert concentracion_economica['USD'] == 100.0
        assert concentracion_operativa['ARS'] == 100.0

    def test_senales_rebalanceo_objetivos(self):
        """Test señales de rebalanceo basadas en objetivos."""
        fecha = timezone.now()

        ParametroActivo.objects.create(
            simbolo='AAPL',
            sector='Tecnología',
            bloque_estrategico='Inversión',
            pais_exposicion='USA',
            tipo_patrimonial='Growth',
        )
        make_activo(fecha, 'AAPL', valorizado=20000.00, tipo='CEDEARS', moneda='peso_Argentino', cantidad=100)
        make_resumen(fecha, disponible=50000.00)

        senales = get_senales_rebalanceo()

        # Debería haber señales de sobreponderación
        assert len(senales['sectorial_sobreponderado']) > 0 or len(senales['patrimonial_sobreponderado']) > 0

        # Verificar estructura de señales
        for senal in senales['sectorial_sobreponderado'] + senales['sectorial_subponderado']:
            assert 'categoria' in senal or 'sector' in senal
            assert 'porcentaje' in senal
            assert 'objetivo' in senal
            assert 'diferencia' in senal

    def test_evolucion_historica_fallback(self):
        """Test que evolución histórica muestra mensaje cuando no hay datos suficientes."""
        evolucion = get_evolucion_historica()

        # Sin datos históricos, debería mostrar mensaje
        assert not evolucion['tiene_datos']
        assert 'mensaje' in evolucion
        assert 'Aún no hay historial suficiente' in evolucion['mensaje']

    def test_analytics_mensual_calculos(self):
        """Test cálculos de analytics mensual."""
        fecha = timezone.now()

        # Crear datos históricos para analytics
        for i in range(3):
            fecha_mes = fecha.replace(month=fecha.month - i, day=1)
            make_activo(fecha_mes, 'AAPL', valorizado=1000.00 + i * 100, tipo='CEDEARS', moneda='peso_Argentino')

        analytics = get_analytics_mensual()

        # Debería tener datos de analytics
        assert isinstance(analytics, dict)
        assert len(analytics) > 0  # Al menos algún cálculo

    def test_analytics_mensual_expands_recent_operational_flow(self):
        fecha = timezone.now().replace(day=10, hour=12, minute=0, second=0, microsecond=0)

        OperacionIOL.objects.create(
            numero='1',
            fecha_orden=fecha,
            fecha_operada=fecha,
            tipo='Compra',
            estado='Terminada',
            estado_actual='Terminada',
            mercado='BCBA',
            simbolo='MELI',
            modalidad='precio_Mercado',
            monto_operado=Decimal('120000'),
            plazo='a24horas',
        )
        OperacionIOL.objects.create(
            numero='2',
            fecha_orden=fecha,
            fecha_operada=fecha,
            tipo='Venta',
            estado='Terminada',
            estado_actual='Terminada',
            mercado='BCBA',
            simbolo='GGAL',
            modalidad='precio_Mercado',
            monto_operado=Decimal('50000'),
            plazo='inmediata',
        )
        OperacionIOL.objects.create(
            numero='3',
            fecha_orden=fecha,
            fecha_operada=fecha,
            tipo='Pago de Dividendos',
            estado='Terminada',
            estado_actual='Terminada',
            mercado='BCBA',
            simbolo='MCD US$',
            modalidad='precio_Mercado',
            monto_operado=Decimal('0.15'),
            plazo='inmediata',
        )
        OperacionIOL.objects.create(
            numero='4',
            fecha_orden=fecha,
            fecha_operada=fecha,
            tipo='Suscripci?n FCI',
            estado='Terminada',
            estado_actual='Terminada',
            mercado='BCBA',
            simbolo='PRPEDOB',
            modalidad='precio_Mercado',
            monto_operado=Decimal('9.19'),
            plazo='inmediata',
        )

        analytics = get_analytics_mensual()

        assert analytics['compras_mes'] == Decimal('120000')
        assert analytics['ventas_mes'] == Decimal('50000')
        assert analytics['dividendos_mes'] == Decimal('0.15')
        assert analytics['suscripciones_fci_mes'] == Decimal('9.19')
        assert analytics['compras_count'] == 1
        assert analytics['ventas_count'] == 1
        assert analytics['dividendos_count'] == 1
        assert analytics['suscripciones_fci_count'] == 1
        assert analytics['operaciones_ejecutadas_count'] == 4
        assert analytics['aporte_mensual_ejecutado'] == Decimal('70000')
        assert len(analytics['recent_operations']) == 4

    def test_evolucion_historica_con_datos(self):
        """Test evolución histórica cuando hay datos suficientes."""
        from django.utils import timezone
        from dateutil.relativedelta import relativedelta

        now = timezone.now()
        fecha1 = now - relativedelta(days=5)
        fecha2 = now - relativedelta(days=3)

        make_activo(fecha1, 'AAPL', valorizado=1000.00, tipo='CEDEARS', moneda='USD')
        make_activo(fecha2, 'AAPL', valorizado=1100.00, tipo='CEDEARS', moneda='USD')
        make_resumen(fecha1, disponible=500.00)
        make_resumen(fecha2, disponible=600.00)

        evolucion = get_evolucion_historica()
        assert evolucion['tiene_datos'] is True
        assert len(evolucion['fechas']) >= 2
        assert len(evolucion['total_iol']) >= 2

    def test_riesgo_portafolio_detallado_con_parametros(self):
        """Test métricas de riesgo con ParametroActivo populado."""
        fecha = timezone.now()

        ParametroActivo.objects.create(
            simbolo='AAPL',
            sector='Tecnología',
            bloque_estrategico='Growth',
            pais_exposicion='USA',
            tipo_patrimonial='Growth',
        )
        ParametroActivo.objects.create(
            simbolo='YPF',
            sector='Energía',
            bloque_estrategico='Defensivo',
            pais_exposicion='Argentina',
            tipo_patrimonial='Bond',
        )
        make_activo(fecha, 'AAPL', valorizado=2000.00, tipo='CEDEARS', moneda='USD')
        make_activo(fecha, 'YPF', valorizado=1000.00)
        make_resumen(fecha, disponible=500.00)

        riesgo = get_riesgo_portafolio_detallado()
        assert 'pct_usa' in riesgo
        assert 'pct_argentina' in riesgo
        assert 'pct_tech' in riesgo
        assert riesgo['pct_usa'] > 0
        assert riesgo['pct_argentina'] > 0
        assert riesgo['pct_tech'] > 0

    def test_pct_tech_agrega_subsectores_tecnologicos(self):
        fecha = timezone.now()

        ParametroActivo.objects.create(
            simbolo='AAPL',
            sector='Tecnología',
            bloque_estrategico='Growth',
            pais_exposicion='USA',
            tipo_patrimonial='Growth',
        )
        ParametroActivo.objects.create(
            simbolo='MELI',
            sector='Tecnología / E-commerce',
            bloque_estrategico='Growth',
            pais_exposicion='Latam',
            tipo_patrimonial='Growth',
        )
        ParametroActivo.objects.create(
            simbolo='AMD',
            sector='Tecnología / Semiconductores',
            bloque_estrategico='Growth',
            pais_exposicion='USA',
            tipo_patrimonial='Growth',
        )
        ParametroActivo.objects.create(
            simbolo='KO',
            sector='Consumo defensivo',
            bloque_estrategico='Dividendos',
            pais_exposicion='USA',
            tipo_patrimonial='Equity',
        )

        make_activo(fecha, 'AAPL', valorizado=400.00, tipo='CEDEARS', moneda='USD')
        make_activo(fecha, 'MELI', valorizado=300.00, tipo='CEDEARS', moneda='USD')
        make_activo(fecha, 'AMD', valorizado=100.00, tipo='CEDEARS', moneda='USD')
        make_activo(fecha, 'KO', valorizado=200.00, tipo='CEDEARS', moneda='USD')

        riesgo = get_riesgo_portafolio_detallado()

        assert abs(float(riesgo['pct_tech']) - 80.0) < 0.01

    def test_riesgo_portafolio_con_parametros(self):
        """Test métricas de riesgo simplificadas con ParametroActivo."""
        fecha = timezone.now()

        ParametroActivo.objects.create(
            simbolo='AAPL',
            sector='Tecnología',
            bloque_estrategico='Growth',
            pais_exposicion='USA',
            tipo_patrimonial='Growth',
        )
        make_activo(fecha, 'AAPL', valorizado=1000.00, tipo='CEDEARS', moneda='USD')
        make_resumen(fecha, disponible=200.00)

        riesgo = get_riesgo_portafolio()
        assert 'volatilidad_estimada' in riesgo
        assert 'exposicion_usa' in riesgo
        assert riesgo['exposicion_usa'] > 0
        assert riesgo['volatilidad_status'] == 'insufficient_history'
        assert riesgo['volatilidad_estimada'] is None

    def test_distribucion_sector_con_datos(self):
        """Test distribución por sector con ParametroActivo."""
        fecha = timezone.now()

        ParametroActivo.objects.create(
            simbolo='AAPL',
            sector='Tecnología',
            bloque_estrategico='Growth',
            pais_exposicion='USA',
            tipo_patrimonial='Growth',
        )
        make_activo(fecha, 'AAPL', valorizado=1000.00)

        distribucion = get_distribucion_sector()
        assert 'Tecnología' in distribucion
        assert distribucion['Tecnología'] == 1000.00

    def test_portafolio_enriquecido_con_tipos(self):
        """Test clasificación de portafolio con distintos tipos de activo."""
        fecha = timezone.now()

        make_activo(fecha, 'AAPL', valorizado=1000.00, tipo='CEDEARS')
        make_activo(fecha, 'GGAL', valorizado=500.00, tipo='ACCIONES')
        make_activo(fecha, 'AL30', valorizado=300.00, tipo='TitulosPublicos')

        portafolio = get_portafolio_enriquecido_actual()
        assert 'inversion' in portafolio
        assert 'liquidez' in portafolio
        assert 'fci_cash_management' in portafolio
        assert len(portafolio['inversion']) == 3

    def test_distribucion_moneda_ramas_alternativas(self):
        """Cubre ramas de inferencia de moneda (Hard Assets, ARS default)."""
        fecha = timezone.now()

        # Hard Assets — sin pais_exposicion USA, tipo_patrimonial Hard Assets
        pa_hard = ParametroActivo.objects.create(
            simbolo='ORO',
            sector='Commodities',
            bloque_estrategico='Defensivo',
            pais_exposicion='Global',
            tipo_patrimonial='Hard Assets',
        )
        # Activo con moneda ambigua (no dolar ni peso)
        make_activo(fecha, 'ORO', valorizado=500.00, moneda='otro')
        # Activo ARS explícito
        make_activo(fecha, 'GFGC', valorizado=200.00, moneda='peso_Argentino')

        distribucion = get_distribucion_moneda()
        assert 'Hard Assets' in distribucion or 'ARS' in distribucion

    def test_riesgo_portafolio_ramas_volatilidad(self):
        """Sin snapshots suficientes no debe inventar una volatilidad robusta."""
        fecha = timezone.now()

        ParametroActivo.objects.create(
            simbolo='ORO', sector='Commodities', bloque_estrategico='Defensivo',
            pais_exposicion='Global', tipo_patrimonial='Hard Assets',
        )
        ParametroActivo.objects.create(
            simbolo='AL30', sector='Bonos', bloque_estrategico='Renta Fija',
            pais_exposicion='Argentina', tipo_patrimonial='Bond',
        )
        ParametroActivo.objects.create(
            simbolo='CASH', sector='Liquidez', bloque_estrategico='Liquidez',
            pais_exposicion='Argentina', tipo_patrimonial='Cash',
        )
        ParametroActivo.objects.create(
            simbolo='GGAL', sector='Financiero', bloque_estrategico='Growth',
            pais_exposicion='Argentina', tipo_patrimonial='Equity',
        )
        make_activo(fecha, 'ORO', valorizado=1000.00)
        make_activo(fecha, 'AL30', valorizado=1000.00)
        make_activo(fecha, 'CASH', valorizado=500.00)
        make_activo(fecha, 'GGAL', valorizado=500.00)
        make_resumen(fecha, disponible=200.00)

        riesgo = get_riesgo_portafolio()
        assert 'volatilidad_estimada' in riesgo
        assert riesgo['volatilidad_estimada'] is None
        assert riesgo['volatilidad_status'] == 'insufficient_history'

    def test_senales_rebalanceo_sin_metadata(self):
        """Cubre rama de activos sin metadata completa."""
        fecha = timezone.now()

        # Activo con ParametroActivo con valores N/A
        ParametroActivo.objects.create(
            simbolo='UNKNOWN',
            sector='N/A',
            bloque_estrategico='N/A',
            pais_exposicion='N/A',
            tipo_patrimonial='N/A',
        )
        make_activo(fecha, 'UNKNOWN', valorizado=1000.00)
        make_resumen(fecha, disponible=100.00)

        senales = get_senales_rebalanceo()
        assert isinstance(senales, dict)

    @override_settings(
        CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
    )
    def test_dashboard_kpis_uses_cache_on_second_call(self):
        cache.clear()
        fecha = timezone.now()
        make_resumen(fecha, disponible=1000.00)
        make_activo(fecha, 'AAPL', valorizado=2000.00, tipo='ACCIONES', moneda='USD')

        with CaptureQueriesContext(connection) as first_call_queries:
            get_dashboard_kpis()

        with CaptureQueriesContext(connection) as second_call_queries:
            get_dashboard_kpis()

        assert len(first_call_queries) > 0
        assert len(second_call_queries) < len(first_call_queries)

    def test_snapshot_coverage_summary_with_sparse_history(self):
        fecha = timezone.now().date()

        from apps.portafolio_iol.models import PortfolioSnapshot

        for offset, total in [(5, 1000), (1, 1100), (0, 1200)]:
            PortfolioSnapshot.objects.create(
                fecha=fecha - timedelta(days=offset),
                total_iol=total,
                liquidez_operativa=200,
                cash_management=100,
                portafolio_invertido=700,
                rendimiento_total=0,
                exposicion_usa=50,
                exposicion_argentina=50,
            )

        summary = get_snapshot_coverage_summary(days=30)
        assert summary['snapshots_count'] == 3
        assert summary['status'] == 'insufficient_history'
        assert summary['max_gap_days'] >= 1
        assert summary['latest_snapshot_at'] is not None

