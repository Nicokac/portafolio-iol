from django.contrib import messages
from django.http import HttpRequest, HttpResponse, QueryDict
from django.shortcuts import redirect
from django.urls import reverse


def handle_save_preferred_incremental_proposal(
    *,
    request: HttpRequest,
    get_preferred_incremental_portfolio_proposal,
    get_decision_engine_summary,
    history_service_factory,
    record_sensitive_action,
) -> HttpResponse:
    source_query = request.POST.get("source_query", "")
    query_params = QueryDict(source_query, mutable=False)
    detail = get_preferred_incremental_portfolio_proposal(query_params, capital_amount=600000)
    decision = get_decision_engine_summary(request.user, query_params=query_params, capital_amount=600000)
    preferred = detail.get("preferred")
    redirect_url = reverse("dashboard:planeacion")
    redirect_url = f"{redirect_url}?{source_query}#planeacion-aportes" if source_query else f"{redirect_url}#planeacion-aportes"

    if not preferred:
        record_sensitive_action(
            request,
            action="save_incremental_proposal",
            status="denied",
            details={"reason": "missing_preferred_proposal"},
        )
        messages.error(request, "No hay una propuesta incremental preferida construible para guardar.")
        return redirect(redirect_url)

    try:
        saved = history_service_factory().save_preferred_proposal(
            user=request.user,
            preferred_payload=preferred,
            decision_payload=decision,
            explanation=detail.get("explanation", ""),
            capital_amount=600000,
        )
    except ValueError as exc:
        record_sensitive_action(
            request,
            action="save_incremental_proposal",
            status="failed",
            details={"reason": str(exc)},
        )
        messages.error(request, "No fue posible guardar la propuesta incremental actual.")
        return redirect(redirect_url)

    record_sensitive_action(
        request,
        action="save_incremental_proposal",
        status="success",
        details={
            "proposal_label": saved["proposal_label"],
            "source_key": saved["source_key"],
        },
    )
    messages.success(request, f"Propuesta incremental guardada: {saved['proposal_label']}.")
    return redirect(redirect_url)


def handle_promote_incremental_baseline(
    *,
    request: HttpRequest,
    history_service_factory,
    record_sensitive_action,
    build_redirect_url,
) -> HttpResponse:
    snapshot_id = request.POST.get("snapshot_id")
    redirect_url = build_redirect_url(request.POST)
    try:
        saved = history_service_factory().promote_to_tracking_baseline(
            user=request.user,
            snapshot_id=snapshot_id,
        )
    except ValueError as exc:
        record_sensitive_action(
            request,
            action="promote_incremental_baseline",
            status="failed",
            details={"reason": str(exc), "snapshot_id": snapshot_id},
        )
        messages.error(request, "No fue posible promover el snapshot incremental a baseline de seguimiento.")
        return redirect(redirect_url)

    record_sensitive_action(
        request,
        action="promote_incremental_baseline",
        status="success",
        details={"snapshot_id": saved["id"], "proposal_label": saved["proposal_label"]},
    )
    messages.success(request, f"Baseline incremental activo: {saved['proposal_label']}.")
    return redirect(redirect_url)


def handle_promote_incremental_backlog_front(
    *,
    request: HttpRequest,
    history_service_factory,
    record_sensitive_action,
    build_redirect_url,
) -> HttpResponse:
    snapshot_id = request.POST.get("snapshot_id")
    redirect_url = build_redirect_url(request.POST)
    try:
        promoted = history_service_factory().promote_to_backlog_front(
            user=request.user,
            snapshot_id=snapshot_id,
        )
    except ValueError as exc:
        record_sensitive_action(
            request,
            action="promote_incremental_backlog_front",
            status="failed",
            details={"reason": str(exc), "snapshot_id": snapshot_id},
        )
        messages.error(request, "No fue posible promover el snapshot al frente del backlog incremental.")
        return redirect(redirect_url)

    record_sensitive_action(
        request,
        action="promote_incremental_backlog_front",
        status="success",
        details={"snapshot_id": promoted["id"], "proposal_label": promoted["proposal_label"]},
    )
    messages.success(request, f"Snapshot al frente del backlog: {promoted['proposal_label']}.")
    return redirect(redirect_url)


def handle_reactivate_deferred_incremental_proposal(
    *,
    request: HttpRequest,
    history_service_factory,
    record_sensitive_action,
    build_redirect_url,
) -> HttpResponse:
    snapshot_id = request.POST.get("snapshot_id")
    redirect_url = build_redirect_url(request.POST)
    try:
        reactivated = history_service_factory().reactivate_snapshot_to_backlog(
            user=request.user,
            snapshot_id=snapshot_id,
        )
    except ValueError as exc:
        record_sensitive_action(
            request,
            action="reactivate_incremental_deferred_snapshot",
            status="failed",
            details={"reason": str(exc), "snapshot_id": snapshot_id},
        )
        messages.error(request, "No fue posible reactivar la propuesta diferida dentro del backlog incremental.")
        return redirect(redirect_url)

    record_sensitive_action(
        request,
        action="reactivate_incremental_deferred_snapshot",
        status="success",
        details={"snapshot_id": reactivated["id"], "proposal_label": reactivated["proposal_label"]},
    )
    messages.success(
        request,
        f"Propuesta reactivada al backlog incremental: {reactivated['proposal_label']}.",
    )
    return redirect(redirect_url)


def handle_decide_incremental_proposal(
    *,
    request: HttpRequest,
    history_service_factory,
    record_sensitive_action,
    build_redirect_url,
) -> HttpResponse:
    snapshot_id = request.POST.get("snapshot_id")
    decision_status = request.POST.get("decision_status")
    decision_note = request.POST.get("decision_note", "")
    redirect_url = build_redirect_url(request.POST)
    try:
        decided = history_service_factory().decide_snapshot(
            user=request.user,
            snapshot_id=snapshot_id,
            decision_status=decision_status,
            note=decision_note,
        )
    except ValueError as exc:
        record_sensitive_action(
            request,
            action="decide_incremental_proposal",
            status="failed",
            details={"reason": str(exc), "snapshot_id": snapshot_id, "decision_status": decision_status},
        )
        messages.error(request, "No fue posible registrar la decision manual sobre la propuesta incremental.")
        return redirect(redirect_url)

    record_sensitive_action(
        request,
        action="decide_incremental_proposal",
        status="success",
        details={
            "snapshot_id": decided["id"],
            "proposal_label": decided["proposal_label"],
            "decision_status": decided["manual_decision_status"],
        },
    )
    messages.success(
        request,
        f"Decision manual registrada: {decided['proposal_label']} -> {decided['manual_decision_status']}.",
    )
    return redirect(redirect_url)


def handle_bulk_decide_incremental_proposal(
    *,
    request: HttpRequest,
    history_service_factory,
    get_incremental_proposal_history,
    record_sensitive_action,
    build_redirect_url,
) -> HttpResponse:
    decision_status = request.POST.get("decision_status")
    decision_status_filter = request.POST.get("decision_status_filter", "")
    priority_filter = request.POST.get("history_priority_filter", "")
    deferred_fit_filter = request.POST.get("history_deferred_fit_filter", "")
    future_purchase_source_filter = request.POST.get("history_future_purchase_source_filter", "")
    sort_mode = request.POST.get("history_sort", "")
    history = get_incremental_proposal_history(
        user=request.user,
        limit=5,
        decision_status=decision_status_filter or None,
        priority_filter=priority_filter or None,
        deferred_fit_filter=deferred_fit_filter or None,
        future_purchase_source_filter=future_purchase_source_filter or None,
        sort_mode=sort_mode or None,
    )
    snapshot_ids = [item.get("id") for item in history.get("items", []) if item.get("id") is not None]
    redirect_url = build_redirect_url(request.POST)
    try:
        result = history_service_factory().decide_many_snapshots(
            user=request.user,
            snapshot_ids=snapshot_ids,
            decision_status=decision_status,
        )
    except ValueError as exc:
        record_sensitive_action(
            request,
            action="bulk_decide_incremental_proposal",
            status="failed",
            details={
                "reason": str(exc),
                "decision_status": decision_status,
                "filter": decision_status_filter,
                "priority_filter": priority_filter or "all",
                "deferred_fit_filter": deferred_fit_filter or "all",
                "future_purchase_source_filter": future_purchase_source_filter or "all",
                "sort_mode": sort_mode or "newest",
            },
        )
        messages.error(request, "No fue posible registrar la decision masiva sobre el historial incremental visible.")
        return redirect(redirect_url)

    record_sensitive_action(
        request,
        action="bulk_decide_incremental_proposal",
        status="success",
        details={
            "decision_status": result["decision_status"],
            "updated_count": result["updated_count"],
            "filter": decision_status_filter or "all",
            "priority_filter": priority_filter or "all",
            "deferred_fit_filter": deferred_fit_filter or "all",
            "future_purchase_source_filter": future_purchase_source_filter or "all",
            "sort_mode": sort_mode or "newest",
        },
    )
    messages.success(
        request,
        f"Decision masiva aplicada a {result['updated_count']} snapshot(s) visibles.",
    )
    return redirect(redirect_url)
