from datetime import timedelta
from decimal import Decimal
from typing import Dict
import unicodedata

from django.utils import timezone

from apps.operaciones_iol.selectors import build_operation_execution_analytics_context


def classify_operation_type(tipo: str | None) -> str:
    normalized = unicodedata.normalize("NFKD", str(tipo or "").strip().lower())
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    if normalized == "compra":
        return "buy"
    if normalized == "venta":
        return "sell"
    if "dividend" in normalized:
        return "dividend"
    if "fci" in normalized and ("suscrip" in normalized or "suscripci?" in normalized):
        return "fci_subscription"
    if "fci" in normalized and "rescat" in normalized:
        return "fci_redemption"
    return "other"


def get_effective_operation_amount(op) -> Decimal:
    for candidate in (
        getattr(op, "monto_operado", None),
        getattr(op, "monto_operacion", None),
        getattr(op, "monto", None),
    ):
        if candidate not in (None, ""):
            return Decimal(candidate)

    cantidad_operada = getattr(op, "cantidad_operada", None)
    precio_operado = getattr(op, "precio_operado", None)
    if cantidad_operada not in (None, "") and precio_operado not in (None, ""):
        return Decimal(cantidad_operada) * Decimal(precio_operado)
    return Decimal("0")


def classify_observed_operation_cost(fee_over_amount_pct: Decimal | None) -> tuple[str, str, str]:
    pct = Decimal(str(fee_over_amount_pct or 0))
    if pct >= Decimal("1.00"):
        return ("high", "Costo alto", "warning")
    if pct >= Decimal("0.40"):
        return ("watch", "Costo a vigilar", "secondary")
    if pct > 0:
        return ("low", "Costo visible", "success")
    return ("missing", "Costo no visible", "secondary")


def build_operation_execution_feature_context(
    *,
    purchase_plan: list[dict] | None = None,
    lookback_days: int = 180,
    symbol_limit: int = 3,
    safe_percentage,
) -> Dict:
    from django.db.models import Q

    from apps.operaciones_iol.models import OperacionIOL

    plan = list(purchase_plan or [])
    tracked_symbols = []
    for item in plan:
        symbol = str((item or {}).get("symbol") or "").strip().upper()
        if symbol and symbol not in tracked_symbols:
            tracked_symbols.append(symbol)

    if not tracked_symbols:
        return {
            "has_context": False,
            "has_symbols": False,
            "tracked_symbols": [],
            "tracked_symbols_count": 0,
            "rows": [],
            "matched_symbols_count": 0,
            "missing_symbols_count": 0,
            "coverage_pct": Decimal("0"),
            "headline": "",
            "summary": "",
            "alerts": [],
            "execution_analytics": {},
        }

    window_start = timezone.now() - timedelta(days=max(int(lookback_days), 1))
    status_filter = Q(estado__iexact="terminada") | Q(estado_actual__iexact="terminada")
    date_filter = Q(fecha_operada__gte=window_start) | Q(fecha_operada__isnull=True, fecha_orden__gte=window_start)
    queryset = OperacionIOL.objects.filter(status_filter, date_filter).order_by("-fecha_operada", "-fecha_orden", "-id")
    operations = [
        operacion
        for operacion in queryset
        if classify_operation_type(getattr(operacion, "tipo", None)) in {"buy", "sell"}
    ]
    execution_analytics = build_operation_execution_analytics_context(operations)
    observed_cost_status = str(execution_analytics.get("observed_cost_status") or "missing")
    observed_cost_pct = Decimal(str(execution_analytics.get("fee_over_visible_amount_pct") or 0))

    latest_by_symbol = {}
    for operacion in operations:
        symbol = str(getattr(operacion, "simbolo", "") or "").strip().upper()
        if symbol in tracked_symbols and symbol not in latest_by_symbol:
            latest_by_symbol[symbol] = operacion
        if len(latest_by_symbol) == len(tracked_symbols):
            break

    rows = []
    for symbol in tracked_symbols[: max(int(symbol_limit), 1)]:
        operacion = latest_by_symbol.get(symbol)
        if operacion is None:
            continue

        executed_amount = get_effective_operation_amount(operacion)
        fees_ars = Decimal(str(getattr(operacion, "aranceles_ars", None) or 0))
        fees_usd = Decimal(str(getattr(operacion, "aranceles_usd", None) or 0))
        fills = list(getattr(operacion, "operaciones_detalle", None) or [])
        fills_count = len(fills)
        executed_at = getattr(operacion, "fecha_operada", None) or getattr(operacion, "fecha_orden", None)
        fee_over_amount_pct = Decimal("0")
        if executed_amount > 0 and (fees_ars > 0 or fees_usd > 0):
            fee_over_amount_pct = ((fees_ars + fees_usd) / executed_amount * Decimal("100")).quantize(Decimal("0.01"))
        cost_status, cost_label, cost_tone = classify_observed_operation_cost(fee_over_amount_pct)

        rows.append(
            {
                "simbolo": symbol,
                "tipo": operacion.tipo,
                "estado": operacion.estado_actual or operacion.estado,
                "fecha_label": timezone.localtime(executed_at).strftime("%Y-%m-%d %H:%M") if executed_at else "",
                "executed_amount": executed_amount,
                "fees_ars": fees_ars,
                "fees_usd": fees_usd,
                "fills_count": fills_count,
                "is_fragmented": fills_count > 1,
                "has_detail": fills_count > 0 or fees_ars > 0 or fees_usd > 0,
                "fee_over_amount_pct": fee_over_amount_pct,
                "cost_status": cost_status,
                "cost_label": cost_label,
                "cost_tone": cost_tone,
            }
        )

    matched_symbols_count = len(latest_by_symbol)
    missing_symbols_count = max(len(tracked_symbols) - matched_symbols_count, 0)
    coverage_pct = safe_percentage(matched_symbols_count, len(tracked_symbols))
    alerts = []

    if matched_symbols_count == 0:
        headline = "La propuesta sugerida no tiene huella reciente de ejecucion en IOL."
        summary = "Conviene tratar la compra como una idea nueva y validar precio, aranceles y fragmentacion con mayor cautela."
        alerts.append(
            {
                "tone": "warning",
                "title": "Sin ejecucion comparable reciente",
                "message": "No hay compras o ventas terminadas recientes para los simbolos sugeridos dentro de la ventana observada.",
            }
        )
    elif missing_symbols_count > 0:
        headline = "La propuesta mezcla simbolos con y sin huella reciente de ejecucion."
        summary = (
            f"{matched_symbols_count} simbolo(s) tienen referencia reciente y {missing_symbols_count} "
            "siguen sin una ejecucion comparable visible."
        )
        alerts.append(
            {
                "tone": "warning",
                "title": "Cobertura operativa parcial",
                "message": f"{missing_symbols_count} simbolo(s) de la propuesta no tienen ejecucion terminada reciente visible.",
            }
        )
    elif Decimal(str(execution_analytics.get("fragmented_pct") or 0)) >= Decimal("50"):
        headline = "La propuesta tiene huella reciente, pero con fragmentacion operativa relevante."
        summary = "Hay referencias utiles de ejecucion, aunque parte del historial reciente muestra multiples fills."
        alerts.append(
            {
                "tone": "info",
                "title": "Fragmentacion visible",
                "message": f"{execution_analytics.get('fragmented_count', 0)} operacion(es) comparables tuvieron multiples fills.",
            }
        )
    elif observed_cost_status == "high":
        headline = "La propuesta tiene huella reciente, pero con costo observado alto."
        summary = (
            f"Los aranceles visibles recientes equivalen a {observed_cost_pct}% del monto comparable y conviene "
            "validar mejor el costo real antes de priorizar la compra."
        )
        alerts.append(
            {
                "tone": "warning",
                "title": "Costo observado alto",
                "message": f"El costo visible reciente equivale a {observed_cost_pct}% del monto ejecutado comparable.",
            }
        )
    elif observed_cost_status == "watch":
        headline = "La propuesta tiene huella reciente, aunque con costo observado a vigilar."
        summary = (
            f"Los aranceles visibles recientes equivalen a {observed_cost_pct}% del monto comparable y suman una "
            "friccion tactica moderada."
        )
        alerts.append(
            {
                "tone": "secondary",
                "title": "Costo observado a vigilar",
                "message": f"El costo visible reciente equivale a {observed_cost_pct}% del monto ejecutado comparable.",
            }
        )
    else:
        headline = "La propuesta ya tiene huella reciente de ejecucion utilizable."
        summary = "Hay referencias recientes para validar monto ejecutado, aranceles visibles y nivel de fragmentacion antes de comprar."

    if Decimal(str(execution_analytics.get("fee_visible_pct") or 0)) == Decimal("0") and matched_symbols_count > 0:
        alerts.append(
            {
                "tone": "secondary",
                "title": "Aranceles poco visibles",
                "message": "Hay ejecuciones comparables, pero sin aranceles visibles suficientes como para leer costo observado con firmeza.",
            }
        )

    return {
        "has_context": True,
        "has_symbols": True,
        "tracked_symbols": tracked_symbols,
        "tracked_symbols_count": len(tracked_symbols),
        "rows": rows,
        "matched_symbols_count": matched_symbols_count,
        "missing_symbols_count": missing_symbols_count,
        "coverage_pct": coverage_pct,
        "headline": headline,
        "summary": summary,
        "alerts": alerts[:2],
        "execution_analytics": execution_analytics,
    }
