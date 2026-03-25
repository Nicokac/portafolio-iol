import hashlib
from decimal import Decimal

from django.core.cache import cache
from django.db.models import Max

from apps.parametros.models import ParametroActivo
from apps.portafolio_iol.models import ActivoPortafolioSnapshot
from apps.resumen_iol.models import ResumenCuentaSnapshot

SELECTOR_CACHE_TTL_SECONDS = 60
DATA_STAMP_CACHE_KEY = "dashboard_selector:data_stamp"


def _safe_percentage(numerator: int, denominator: int) -> Decimal:
    if denominator <= 0:
        return Decimal("0")
    return (Decimal(numerator) / Decimal(denominator) * Decimal("100")).quantize(Decimal("0.01"))


def _get_data_stamp() -> str:
    from apps.operaciones_iol.models import OperacionIOL

    cached = cache.get(DATA_STAMP_CACHE_KEY)
    if cached is not None:
        return cached

    latest_portafolio = ActivoPortafolioSnapshot.objects.aggregate(latest=Max("fecha_extraccion"))["latest"]
    latest_resumen = ResumenCuentaSnapshot.objects.aggregate(latest=Max("fecha_extraccion"))["latest"]
    latest_parametro_id = ParametroActivo.objects.aggregate(latest=Max("id"))["latest"] or 0
    latest_operacion = OperacionIOL.objects.aggregate(latest=Max("fecha_orden"))["latest"]
    stamp = f"{latest_portafolio}|{latest_resumen}|{latest_parametro_id}|{latest_operacion}"
    cache.set(DATA_STAMP_CACHE_KEY, stamp, timeout=SELECTOR_CACHE_TTL_SECONDS)
    return stamp


def _get_cached_selector_result(cache_key_prefix: str, builder):
    stamp = _get_data_stamp()
    stamp_hash = hashlib.md5(stamp.encode("utf-8")).hexdigest()
    cache_key = f"dashboard_selector:{cache_key_prefix}:{stamp_hash}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    value = builder()
    cache.set(cache_key, value, timeout=SELECTOR_CACHE_TTL_SECONDS)
    return value
