from __future__ import annotations

import logging

from django.db import OperationalError, ProgrammingError
from django.http import HttpRequest

from apps.core.models import SensitiveActionAudit

logger = logging.getLogger(__name__)


def record_sensitive_action(
    request: HttpRequest,
    action: str,
    status: str,
    details: dict | None = None,
) -> SensitiveActionAudit | None:
    user = request.user if getattr(request.user, "is_authenticated", False) else None
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR", "")
    ip_address = forwarded_for.split(",")[0].strip() if forwarded_for else request.META.get(
        "REMOTE_ADDR"
    )
    payload = {
        "path": request.path,
        "method": request.method,
    }
    if details:
        payload.update(details)

    try:
        return SensitiveActionAudit.objects.create(
            user=user,
            action=action,
            status=status,
            ip_address=ip_address or None,
            details=payload,
        )
    except (OperationalError, ProgrammingError):
        logger.warning(
            "SensitiveActionAudit table is unavailable; skipping audit record for action=%s",
            action,
            exc_info=True,
        )
        return None
