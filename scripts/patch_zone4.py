"""
Patch selectors.py – Zone 4 extraction
  1. Remove incremental_followup import block
  2. Remove incremental_history import block
  3. Trim incremental_future_purchases import to Zone-5-only symbols
  4. Add incremental_backlog import after incremental_simulation import
  5. Remove Zone-4 function block 1 (get_incremental_proposal_history … get_incremental_decision_executive_summary)
  6. Remove Zone-4 function block 2 (get_incremental_followup_executive_summary … get_incremental_adoption_checklist)
"""
import sys
from pathlib import Path

TARGET = Path(__file__).parent.parent / "apps" / "dashboard" / "selectors.py"
raw = TARGET.read_bytes()
content = raw.decode("utf-8").replace("\r\n", "\n")

# ── helpers ────────────────────────────────────────────────────────────────

def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        print(f"ERROR: '{label}' found {count} times (expected 1)", file=sys.stderr)
        sys.exit(1)
    return text.replace(old, new, 1)


# ══════════════════════════════════════════════════════════════════════════
# 1. Remove incremental_followup import block
# ══════════════════════════════════════════════════════════════════════════
OLD_FOLLOWUP_IMPORT = """\
from apps.dashboard.incremental_followup import (
    _build_incremental_adoption_check_item,
    _build_incremental_adoption_checklist_headline,
    _build_incremental_baseline_drift_alerts,
    _build_incremental_baseline_drift_explanation,
    _build_incremental_baseline_drift_summary,
    _build_incremental_followup_headline,
    _build_incremental_followup_summary_items,
    _build_incremental_snapshot_comparison,
    _build_incremental_snapshot_reapply_payload,
    _format_incremental_followup_status,
    _format_incremental_purchase_plan_summary,
    _summarize_incremental_drift_alerts,
)
"""
content = replace_once(content, OLD_FOLLOWUP_IMPORT, "", "incremental_followup import block")

# ══════════════════════════════════════════════════════════════════════════
# 2. Remove incremental_history import block
# ══════════════════════════════════════════════════════════════════════════
OLD_HISTORY_IMPORT = """\
from apps.dashboard.incremental_history import (
    _build_incremental_backlog_front_summary_headline,
    _build_incremental_backlog_front_summary_items,
    _build_incremental_backlog_next_action,
    _build_incremental_backlog_prioritization_explanation,
    _build_incremental_backlog_prioritization_headline,
    _build_incremental_decision_executive_headline,
    _build_incremental_decision_executive_items,
    _build_incremental_history_available_filters,
    _build_incremental_history_headline,
    _build_incremental_manual_decision_headline,
    _build_incremental_operational_semaphore_headline,
    _build_incremental_operational_semaphore_items,
    _build_incremental_pending_backlog_explanation,
    _build_incremental_pending_backlog_headline,
    _classify_incremental_backlog_priority,
    _format_incremental_backlog_priority,
    _format_incremental_history_decision_filter_label,
    _format_incremental_history_deferred_fit_filter_label,
    _format_incremental_history_priority_filter_label,
    _format_incremental_history_sort_mode_label,
    _format_incremental_future_purchase_source_filter_label,
    _format_incremental_manual_decision_status,
    _format_incremental_operational_semaphore,
    _incremental_backlog_priority_order,
    _normalize_incremental_future_purchase_source_filter,
    _normalize_incremental_history_decision_filter,
    _normalize_incremental_history_deferred_fit_filter,
    _normalize_incremental_history_priority_filter,
    _normalize_incremental_history_sort_mode,
)
"""
content = replace_once(content, OLD_HISTORY_IMPORT, "", "incremental_history import block")

# ══════════════════════════════════════════════════════════════════════════
# 3. Trim incremental_future_purchases import to Zone-5-only symbols
# ══════════════════════════════════════════════════════════════════════════
OLD_FP_IMPORT = """\
from apps.dashboard.incremental_future_purchases import (
    _annotate_incremental_future_purchase_recommended_items,
    _build_incremental_backlog_conviction,
    _build_incremental_backlog_deferred_review_summary,
    _build_incremental_backlog_focus_item,
    _build_incremental_backlog_followup,
    _build_incremental_backlog_followup_filter_options,
    _build_incremental_backlog_manual_review_summary,
    _build_incremental_backlog_shortlist_item,
    _build_incremental_future_purchase_history_context,
    _build_incremental_future_purchase_shortlist,
    _build_incremental_future_purchase_source_counts,
    _build_incremental_future_purchase_source_filter_options,
    _build_incremental_future_purchase_source_guidance,
    _build_incremental_future_purchase_source_quality_item,
    _build_incremental_future_purchase_source_quality_summary,
    _build_incremental_future_purchase_source_summary,
    _build_incremental_future_purchase_workflow_summary,
    _build_incremental_history_baseline_trace,
    _build_incremental_history_deferred_fit,
    _build_incremental_history_deferred_fit_counts,
    _build_incremental_history_deferred_fit_filter_options,
    _build_incremental_history_priority,
    _build_incremental_history_priority_counts,
    _build_incremental_history_priority_filter_options,
    _build_incremental_history_sort_options,
    _build_incremental_reactivation_vs_backlog_summary,
    _build_incremental_tactical_trace,
    _format_incremental_backlog_followup_filter_label,
    _is_incremental_history_tactical_clean,
    _normalize_incremental_backlog_followup_filter,
    _sort_incremental_history_items,
    get_incremental_manual_decision_summary,
    get_incremental_proposal_tracking_baseline,
    get_incremental_reactivation_summary,
)
"""
NEW_FP_IMPORT = """\
from apps.dashboard.incremental_future_purchases import (
    _annotate_incremental_future_purchase_recommended_items,
    _build_incremental_future_purchase_shortlist,
    _build_incremental_future_purchase_source_guidance,
    _build_incremental_future_purchase_workflow_summary,
    _build_incremental_reactivation_vs_backlog_summary,
    get_incremental_manual_decision_summary,
    get_incremental_proposal_tracking_baseline,
    get_incremental_reactivation_summary,
)
"""
content = replace_once(content, OLD_FP_IMPORT, NEW_FP_IMPORT, "incremental_future_purchases import block")

# ══════════════════════════════════════════════════════════════════════════
# 4. Add incremental_backlog import after incremental_simulation import
# ══════════════════════════════════════════════════════════════════════════
OLD_SIM_IMPORT = """\
from apps.dashboard.incremental_simulation import (
    get_candidate_asset_ranking,
    get_candidate_incremental_portfolio_comparison,
    get_candidate_split_incremental_portfolio_comparison,
    get_incremental_portfolio_simulation,
    get_incremental_portfolio_simulation_comparison,
    get_manual_incremental_portfolio_simulation_comparison,
    get_monthly_allocation_plan,
    get_operation_execution_feature_context,
    get_preferred_incremental_portfolio_proposal,
)
"""
NEW_SIM_IMPORT = """\
from apps.dashboard.incremental_simulation import (
    get_candidate_asset_ranking,
    get_candidate_incremental_portfolio_comparison,
    get_candidate_split_incremental_portfolio_comparison,
    get_incremental_portfolio_simulation,
    get_incremental_portfolio_simulation_comparison,
    get_manual_incremental_portfolio_simulation_comparison,
    get_monthly_allocation_plan,
    get_operation_execution_feature_context,
    get_preferred_incremental_portfolio_proposal,
)
from apps.dashboard.incremental_backlog import (
    get_incremental_backlog_prioritization,
    get_incremental_decision_executive_summary,
    get_incremental_proposal_history,
)
"""
content = replace_once(content, OLD_SIM_IMPORT, NEW_SIM_IMPORT, "incremental_simulation import block")

# ══════════════════════════════════════════════════════════════════════════
# 5. Remove Zone-4 function block 1: get_incremental_proposal_history …
#    get_incremental_decision_executive_summary
#    (ends just before get_decision_engine_summary)
# ══════════════════════════════════════════════════════════════════════════
BLOCK1_START = "\ndef get_incremental_proposal_history(\n"
BLOCK1_END   = "\ndef get_decision_engine_summary(\n"

idx_start = content.find(BLOCK1_START)
idx_end   = content.find(BLOCK1_END)
if idx_start == -1 or idx_end == -1 or idx_start >= idx_end:
    print(f"ERROR: Zone-4 block-1 boundaries not found (start={idx_start}, end={idx_end})", file=sys.stderr)
    sys.exit(1)

# Keep the leading \n and the start of BLOCK1_END intact
content = content[:idx_start] + "\n" + content[idx_end:]

# ══════════════════════════════════════════════════════════════════════════
# 6. Remove Zone-4 function block 2: get_incremental_followup_executive_summary
#    and get_incremental_adoption_checklist
#    (ends just before _get_active_risk_contribution_result)
# ══════════════════════════════════════════════════════════════════════════
BLOCK2_START = "\ndef get_incremental_followup_executive_summary(\n"
BLOCK2_END   = "\ndef _get_active_risk_contribution_result("

idx_start2 = content.find(BLOCK2_START)
idx_end2   = content.find(BLOCK2_END)
if idx_start2 == -1 or idx_end2 == -1 or idx_start2 >= idx_end2:
    print(f"ERROR: Zone-4 block-2 boundaries not found (start={idx_start2}, end={idx_end2})", file=sys.stderr)
    sys.exit(1)

content = content[:idx_start2] + "\n" + content[idx_end2:]

# ══════════════════════════════════════════════════════════════════════════
# Write result (keep LF — git normalizes on commit)
# ══════════════════════════════════════════════════════════════════════════
TARGET.write_bytes(content.encode("utf-8"))
lines = content.count("\n")
print(f"OK – selectors.py updated ({lines} lines)")
