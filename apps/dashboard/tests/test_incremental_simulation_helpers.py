from decimal import Decimal
from unittest.mock import MagicMock, patch

from apps.dashboard.selector_cache import _safe_percentage
from apps.dashboard.incremental_simulation import (
    get_preferred_incremental_portfolio_proposal,
)


# --- _safe_percentage ---

def test_safe_percentage_calculo_normal():
    assert _safe_percentage(30, 100) == Decimal("30.00")


def test_safe_percentage_denominador_cero():
    assert _safe_percentage(50, 0) == Decimal("0")


def test_safe_percentage_denominador_negativo():
    assert _safe_percentage(50, -10) == Decimal("0")


def test_safe_percentage_redondea_a_dos_decimales():
    result = _safe_percentage(1, 3)
    assert result == Decimal("33.33")


def test_safe_percentage_resultado_cien():
    assert _safe_percentage(100, 100) == Decimal("100.00")


# --- get_preferred_incremental_portfolio_proposal ---

def _make_empty_comparator_payload():
    return {
        "proposals": [],
        "best_proposal_key": None,
        "best_label": None,
        "submitted": False,
    }


def _make_comparator_payload_with_best(proposal_key, score, label="Plan A"):
    return {
        "proposals": [{"proposal_key": proposal_key, "label": label, "comparison_score": score}],
        "best_proposal_key": proposal_key,
        "best_label": label,
        "submitted": False,
    }


def _patch_comparators(auto=None, candidate=None, split=None, manual=None):
    """Patchea los 4 comparadores con payloads fijos."""
    return patch.multiple(
        "apps.dashboard.incremental_simulation",
        get_incremental_portfolio_simulation_comparison=MagicMock(return_value=auto or _make_empty_comparator_payload()),
        get_candidate_incremental_portfolio_comparison=MagicMock(return_value=candidate or _make_empty_comparator_payload()),
        get_candidate_split_incremental_portfolio_comparison=MagicMock(return_value=split or _make_empty_comparator_payload()),
        get_manual_incremental_portfolio_simulation_comparison=MagicMock(return_value=manual or _make_empty_comparator_payload()),
    )


@patch("apps.dashboard.incremental_simulation._extract_best_incremental_proposal", return_value=None)
@patch("apps.dashboard.incremental_simulation._build_preferred_incremental_explanation", return_value="sin propuesta")
def test_preferred_todos_vacios_preferred_es_none(mock_exp, mock_extract):
    with _patch_comparators():
        result = get_preferred_incremental_portfolio_proposal({})
    assert result["preferred"] is None
    assert result["candidates"] == []
    assert result["has_manual_override"] is False


@patch("apps.dashboard.incremental_simulation._build_preferred_incremental_explanation", return_value="explicacion")
@patch("apps.dashboard.incremental_simulation._build_preferred_proposal_context", return_value={})
@patch("apps.dashboard.incremental_simulation._preferred_source_priority_rank", return_value=0)
@patch("apps.dashboard.incremental_simulation._normalize_incremental_proposal_item", side_effect=lambda x: x)
@patch("apps.dashboard.incremental_simulation._extract_best_incremental_proposal")
def test_preferred_un_candidato_es_elegido(mock_extract, mock_norm, mock_rank, mock_ctx, mock_exp):
    best_item = {
        "proposal_key": "top_candidate_per_block",
        "label": "Plan A",
        "purchase_plan": [{"symbol": "AAPL", "amount": 100000}],
        "comparison_score": 0.75,
        "simulation": {},
    }
    mock_extract.side_effect = [best_item, None, None, None]

    with _patch_comparators(auto=_make_comparator_payload_with_best("top_candidate_per_block", 0.75)):
        result = get_preferred_incremental_portfolio_proposal({})

    assert result["preferred"] is not None
    assert result["preferred"]["proposal_key"] == "top_candidate_per_block"
    assert len(result["candidates"]) == 1


@patch("apps.dashboard.incremental_simulation._build_preferred_incremental_explanation", return_value="explicacion")
@patch("apps.dashboard.incremental_simulation._build_preferred_proposal_context", return_value={})
@patch("apps.dashboard.incremental_simulation._preferred_source_priority_rank", return_value=0)
@patch("apps.dashboard.incremental_simulation._normalize_incremental_proposal_item", side_effect=lambda x: x)
@patch("apps.dashboard.incremental_simulation._extract_best_incremental_proposal")
def test_preferred_mayor_score_gana(mock_extract, mock_norm, mock_rank, mock_ctx, mock_exp):
    item_bajo = {
        "proposal_key": "runner_up",
        "label": "Plan B",
        "purchase_plan": [],
        "comparison_score": 0.30,
        "simulation": {},
    }
    item_alto = {
        "proposal_key": "top_candidate",
        "label": "Plan A",
        "purchase_plan": [],
        "comparison_score": 0.85,
        "simulation": {},
    }
    mock_extract.side_effect = [item_bajo, item_alto, None, None]

    with _patch_comparators(
        auto=_make_comparator_payload_with_best("runner_up", 0.30),
        candidate=_make_comparator_payload_with_best("top_candidate", 0.85),
    ):
        result = get_preferred_incremental_portfolio_proposal({})

    assert result["preferred"]["proposal_key"] == "top_candidate"
    assert len(result["candidates"]) == 2


@patch("apps.dashboard.incremental_simulation._build_preferred_incremental_explanation", return_value="")
@patch("apps.dashboard.incremental_simulation._build_preferred_proposal_context", return_value={})
@patch("apps.dashboard.incremental_simulation._preferred_source_priority_rank", return_value=0)
@patch("apps.dashboard.incremental_simulation._normalize_incremental_proposal_item", side_effect=lambda x: x)
@patch("apps.dashboard.incremental_simulation._extract_best_incremental_proposal")
def test_preferred_score_none_no_gana_sobre_score_valido(mock_extract, mock_norm, mock_rank, mock_ctx, mock_exp):
    item_none = {
        "proposal_key": "sin_score",
        "label": "Sin score",
        "purchase_plan": [],
        "comparison_score": None,
        "simulation": {},
    }
    item_valido = {
        "proposal_key": "con_score",
        "label": "Con score",
        "purchase_plan": [],
        "comparison_score": 0.01,
        "simulation": {},
    }
    mock_extract.side_effect = [item_none, item_valido, None, None]

    with _patch_comparators(
        auto=_make_comparator_payload_with_best("sin_score", None),
        candidate=_make_comparator_payload_with_best("con_score", 0.01),
    ):
        result = get_preferred_incremental_portfolio_proposal({})

    assert result["preferred"]["proposal_key"] == "con_score"


def test_preferred_has_manual_override_cuando_submitted_y_proposals():
    manual_payload = {
        "proposals": [{"proposal_key": "manual_a", "label": "Manual A", "comparison_score": 0.5}],
        "best_proposal_key": "manual_a",
        "best_label": "Manual A",
        "submitted": True,
    }
    with _patch_comparators(manual=manual_payload):
        with patch("apps.dashboard.incremental_simulation._extract_best_incremental_proposal", return_value=None):
            with patch("apps.dashboard.incremental_simulation._build_preferred_incremental_explanation", return_value=""):
                result = get_preferred_incremental_portfolio_proposal({})

    assert result["has_manual_override"] is True


def test_preferred_has_manual_override_false_cuando_no_submitted():
    manual_payload = {
        "proposals": [{"proposal_key": "manual_a"}],
        "submitted": False,
    }
    with _patch_comparators(manual=manual_payload):
        with patch("apps.dashboard.incremental_simulation._extract_best_incremental_proposal", return_value=None):
            with patch("apps.dashboard.incremental_simulation._build_preferred_incremental_explanation", return_value=""):
                result = get_preferred_incremental_portfolio_proposal({})

    assert result["has_manual_override"] is False
