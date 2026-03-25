"""
Patch selectors.py – Zone 5 extraction
  1. Add incremental_planeacion import after incremental_backlog import
  2. Remove _build_portfolio_scope_summary definition
  3. Remove get_decision_engine_summary definition
  4. Remove get_planeacion_incremental_context definition
"""
import sys
from pathlib import Path

TARGET = Path(__file__).parent.parent / "apps" / "dashboard" / "selectors.py"
raw = TARGET.read_bytes()
content = raw.decode("utf-8").replace("\r\n", "\n")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        print(f"ERROR: '{label}' found {count} times (expected 1)", file=sys.stderr)
        sys.exit(1)
    return text.replace(old, new, 1)


# ══════════════════════════════════════════════════════════════════════════
# 1. Add incremental_planeacion import after incremental_backlog import
# ══════════════════════════════════════════════════════════════════════════
OLD_BACKLOG_IMPORT = """\
from apps.dashboard.incremental_backlog import (
    get_incremental_backlog_prioritization,
    get_incremental_decision_executive_summary,
    get_incremental_proposal_history,
)
"""
NEW_BACKLOG_IMPORT = """\
from apps.dashboard.incremental_backlog import (
    get_incremental_backlog_prioritization,
    get_incremental_decision_executive_summary,
    get_incremental_proposal_history,
)
from apps.dashboard.incremental_planeacion import (
    get_decision_engine_summary,
    get_planeacion_incremental_context,
)
"""
content = replace_once(content, OLD_BACKLOG_IMPORT, NEW_BACKLOG_IMPORT, "incremental_backlog import block")

# ══════════════════════════════════════════════════════════════════════════
# 2. Remove _build_portfolio_scope_summary definition
# ══════════════════════════════════════════════════════════════════════════
OLD_SCOPE_SUMMARY = """\
def _build_portfolio_scope_summary() -> Dict:
    \"\"\"Explicita el universo broker vs capital invertido para Planeacion.\"\"\"
    kpis = get_dashboard_kpis()
    resumen = get_latest_resumen_data()
    cash_components = _extract_resumen_cash_components(resumen)
    return build_portfolio_scope_summary(kpis, cash_components)

"""
content = replace_once(content, OLD_SCOPE_SUMMARY, "", "_build_portfolio_scope_summary definition")

# ══════════════════════════════════════════════════════════════════════════
# 3. Remove get_decision_engine_summary block
#    (from def get_decision_engine_summary to before def get_planeacion_incremental_context)
# ══════════════════════════════════════════════════════════════════════════
BLOCK1_START = "\ndef get_decision_engine_summary(\n"
BLOCK1_END   = "\ndef get_planeacion_incremental_context(\n"

idx_start = content.find(BLOCK1_START)
idx_end   = content.find(BLOCK1_END)
if idx_start == -1 or idx_end == -1 or idx_start >= idx_end:
    print(f"ERROR: get_decision_engine_summary block boundaries not found (start={idx_start}, end={idx_end})", file=sys.stderr)
    sys.exit(1)

content = content[:idx_start] + "\n" + content[idx_end:]

# ══════════════════════════════════════════════════════════════════════════
# 4. Remove get_planeacion_incremental_context block
#    (from def get_planeacion_incremental_context to before def _get_active_risk_contribution_result)
# ══════════════════════════════════════════════════════════════════════════
BLOCK2_START = "\ndef get_planeacion_incremental_context(\n"
BLOCK2_END   = "\ndef _get_active_risk_contribution_result("

idx_start2 = content.find(BLOCK2_START)
idx_end2   = content.find(BLOCK2_END)
if idx_start2 == -1 or idx_end2 == -1 or idx_start2 >= idx_end2:
    print(f"ERROR: get_planeacion_incremental_context block boundaries not found (start={idx_start2}, end={idx_end2})", file=sys.stderr)
    sys.exit(1)

content = content[:idx_start2] + "\n" + content[idx_end2:]

# ══════════════════════════════════════════════════════════════════════════
# Write result
# ══════════════════════════════════════════════════════════════════════════
TARGET.write_bytes(content.encode("utf-8"))
lines = content.count("\n")
print(f"OK – selectors.py updated ({lines} lines)")
