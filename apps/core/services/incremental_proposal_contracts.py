from __future__ import annotations


def build_incremental_purchase_plan_summary(purchase_plan: list[dict] | None) -> str:
    normalized_plan = list(purchase_plan or [])
    if not normalized_plan:
        return ""
    first_items = [
        f"{item.get('symbol')} ({item.get('amount')})"
        for item in normalized_plan[:3]
        if item.get("symbol")
    ]
    return ", ".join(first_items)


def normalize_incremental_proposal_payload(payload: dict | None) -> dict:
    data = dict(payload or {})
    purchase_plan = list(data.get("purchase_plan") or [])
    simulation = dict(data.get("simulation") or {})
    simulation_delta = dict(data.get("simulation_delta") or simulation.get("delta") or {})
    simulation_interpretation = str(
        data.get("simulation_interpretation") or simulation.get("interpretation") or ""
    )
    proposal_label = str(data.get("proposal_label") or data.get("label") or "")
    return {
        **data,
        "proposal_label": proposal_label,
        "label": str(data.get("label") or proposal_label),
        "purchase_plan": purchase_plan,
        "purchase_summary": str(
            data.get("purchase_summary") or build_incremental_purchase_plan_summary(purchase_plan)
        ),
        "simulation": {
            **simulation,
            "delta": simulation_delta,
            "interpretation": simulation_interpretation,
        },
        "simulation_delta": simulation_delta,
        "simulation_interpretation": simulation_interpretation,
    }
