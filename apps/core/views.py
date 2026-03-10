from django.http import JsonResponse
from django.db import connection


def health_check(request):
    """Endpoint de healthcheck para monitoreo en Render."""
    try:
        connection.ensure_connection()
        db_status = "ok"
    except Exception:
        db_status = "error"

    status = "ok" if db_status == "ok" else "degraded"
    http_status = 200 if status == "ok" else 503

    return JsonResponse(
        {
            "status": status,
            "db": db_status,
        },
        status=http_status,
    )