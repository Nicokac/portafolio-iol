from typing import Dict, List
from datetime import timedelta
from decimal import Decimal
import hashlib
import json
from urllib.parse import urlencode
import unicodedata
from django.core.cache import cache
from django.db.models import Max, Sum
from django.utils import timezone

from apps.parametros.models import ParametroActivo
from apps.portafolio_iol.selectors import build_portafolio_row
from apps.portafolio_iol.models import ActivoPortafolioSnapshot, PortfolioSnapshot
from apps.resumen_iol.models import ResumenCuentaSnapshot
from apps.core.models import Alert, IncrementalProposalSnapshot, SensitiveActionAudit
from apps.core.services.iol_historical_price_service import IOLHistoricalPriceService
from apps.core.services.risk.cvar_service import CVaRService
from apps.core.services.risk.stress_test_service import StressTestService
from apps.core.services.risk.var_service import VaRService
from apps.core.services.risk.volatility_service import VolatilityService
from apps.core.services.performance.tracking_error import TrackingErrorService
from apps.core.services.liquidity.liquidity_service import LiquidityService
from apps.core.services.data_quality.metadata_audit import MetadataAuditService
from apps.core.services.local_macro_series_service import LocalMacroSeriesService
from apps.core.services.candidate_asset_ranking_service import CandidateAssetRankingService
from apps.core.services.incremental_proposal_contracts import (
    build_incremental_purchase_plan_summary,
    normalize_incremental_proposal_payload,
)
from apps.core.services.incremental_portfolio_simulator import IncrementalPortfolioSimulator
from apps.core.services.incremental_proposal_history_service import IncrementalProposalHistoryService
from apps.core.services.monthly_allocation_service import MonthlyAllocationService
from apps.core.services.analytics_v2 import (
    AnalyticsExplanationService,
    CovarianceAwareRiskContributionService,
    ExpectedReturnService,
    FactorExposureService,
    LocalMacroSignalsService,
    RiskContributionService,
    ScenarioCatalogService,
    ScenarioAnalysisService,
    StressCatalogService,
    StressFragilityService,
)


SELECTOR_CACHE_TTL_SECONDS = 60


def _safe_percentage(numerator: int, denominator: int) -> Decimal:
    if denominator <= 0:
        return Decimal("0")
    return (Decimal(numerator) / Decimal(denominator) * Decimal("100")).quantize(Decimal("0.01"))


def _get_data_stamp() -> str:
    latest_portafolio = ActivoPortafolioSnapshot.objects.aggregate(latest=Max("fecha_extraccion"))["latest"]
    latest_resumen = ResumenCuentaSnapshot.objects.aggregate(latest=Max("fecha_extraccion"))["latest"]
    latest_parametro_id = ParametroActivo.objects.aggregate(latest=Max("id"))["latest"] or 0
    return f"{latest_portafolio}|{latest_resumen}|{latest_parametro_id}"


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


def get_latest_portafolio_data() -> List[ActivoPortafolioSnapshot]:
    """Obtiene los datos más recientes del portafolio."""
    latest_date = ActivoPortafolioSnapshot.objects.aggregate(
        latest=Max('fecha_extraccion')
    )['latest']
    if not latest_date:
        return []
    return list(ActivoPortafolioSnapshot.objects.filter(
        fecha_extraccion=latest_date
    ))


def get_latest_resumen_data() -> List[ResumenCuentaSnapshot]:
    """Obtiene los datos más recientes del resumen de cuenta."""
    latest_date = ResumenCuentaSnapshot.objects.aggregate(
        latest=Max('fecha_extraccion')
    )['latest']
    if not latest_date:
        return []
    return list(ResumenCuentaSnapshot.objects.filter(
        fecha_extraccion=latest_date
    ))


def get_market_snapshot_feature_context(*, top_limit: int = 5) -> Dict:
    payload = IOLHistoricalPriceService.get_cached_current_portfolio_market_snapshot() or {}
    cached_rows = payload.get("rows") or []
    summary = payload.get("summary") or IOLHistoricalPriceService.summarize_market_snapshot_rows(cached_rows)
    refreshed_at_label = IOLHistoricalPriceService._format_snapshot_datetime(payload.get("refreshed_at"))

    relevant_positions = get_portafolio_enriquecido_actual()["inversion"][: max(int(top_limit or 0), 1)]
    snapshot_rows_by_key = {
        (
            str(row.get("simbolo") or "").strip().upper(),
            str(row.get("mercado") or "").strip().upper(),
        ): row
        for row in cached_rows
    }

    top_rows = []
    for item in relevant_positions:
        activo = item["activo"]
        snapshot_row = snapshot_rows_by_key.get(
            (
                str(activo.simbolo or "").strip().upper(),
                str(activo.mercado or "").strip().upper(),
            )
        )
        snapshot_status = str((snapshot_row or {}).get("snapshot_status") or "missing")
        top_rows.append(
            {
                "simbolo": activo.simbolo,
                "mercado": activo.mercado,
                "descripcion": (snapshot_row or {}).get("descripcion") or activo.descripcion,
                "peso_porcentual": item.get("peso_porcentual") or 0,
                "valorizado": activo.valorizado,
                "snapshot_status": snapshot_status,
                "snapshot_status_label": {
                    "available": "Disponible",
                    "unsupported": "No elegible",
                    "missing": "Sin snapshot",
                }.get(snapshot_status, "Sin snapshot"),
                "snapshot_source_key": (snapshot_row or {}).get("snapshot_source_key") or "",
                "snapshot_source_label": (snapshot_row or {}).get("snapshot_source_label") or "",
                "snapshot_reason": (snapshot_row or {}).get("snapshot_reason") or "",
                "fecha_hora_label": (snapshot_row or {}).get("fecha_hora_label") or "",
                "ultimo_precio": (snapshot_row or {}).get("ultimo_precio"),
                "variacion": (snapshot_row or {}).get("variacion"),
                "cantidad_operaciones": int((snapshot_row or {}).get("cantidad_operaciones") or 0),
                "puntas_count": int((snapshot_row or {}).get("puntas_count") or 0),
                "spread_abs": (snapshot_row or {}).get("spread_abs"),
                "spread_pct": (snapshot_row or {}).get("spread_pct"),
                "plazo": (snapshot_row or {}).get("plazo") or "",
                "has_order_book": int((snapshot_row or {}).get("puntas_count") or 0) > 0,
            }
        )

    top_available_count = sum(1 for row in top_rows if row["snapshot_status"] == "available")
    top_missing_count = sum(1 for row in top_rows if row["snapshot_status"] == "missing")
    wide_spread_rows = [
        row for row in top_rows
        if row["snapshot_status"] == "available"
        and row.get("spread_pct") is not None
        and Decimal(str(row["spread_pct"])) >= Decimal("1.0")
    ]

    alerts = []
    if not payload:
        alerts.append(
            {
                "tone": "secondary",
                "title": "Snapshot puntual pendiente",
                "message": "Todavía no hay market snapshot IOL cacheado para enriquecer la lectura táctica de estas pantallas.",
            }
        )
    else:
        if top_missing_count > 0:
            alerts.append(
                {
                    "tone": "warning",
                    "title": "Cobertura parcial en posiciones relevantes",
                    "message": f"{top_missing_count} posicion(es) relevantes siguen sin snapshot puntual disponible.",
                }
            )
        if wide_spread_rows:
            alerts.append(
                {
                    "tone": "warning",
                    "title": "Spreads anchos en posiciones relevantes",
                    "message": ", ".join(row["simbolo"] for row in wide_spread_rows[:3]),
                }
            )
        if int(summary.get("fallback_count") or 0) > 0:
            alerts.append(
                {
                    "tone": "info",
                    "title": "Parte de la cobertura viene por fallback",
                    "message": f"{summary['fallback_count']} simbolo(s) usan Cotizacion simple en lugar de CotizacionDetalle.",
                }
            )
        if int(summary.get("order_book_count") or 0) == 0 and int(summary.get("available_count") or 0) > 0:
            alerts.append(
                {
                    "tone": "secondary",
                    "title": "Sin libro visible",
                    "message": "Hay precios puntuales disponibles, pero sin puntas visibles para lectura de spread.",
                }
            )

    return {
        "has_cached_snapshot": bool(payload),
        "refreshed_at_label": refreshed_at_label,
        "summary": summary,
        "top_rows": top_rows,
        "top_available_count": top_available_count,
        "top_missing_count": top_missing_count,
        "wide_spread_count": len(wide_spread_rows),
        "alerts": alerts[:3],
    }


def get_market_snapshot_history_feature_context(*, top_limit: int = 5, lookback_days: int = 7) -> Dict:
    def build():
        service = IOLHistoricalPriceService()
        history_rows = service.get_recent_market_history_rows(lookback_days=lookback_days)
        summary = service.summarize_recent_market_history_rows(history_rows)

        current_portafolio = get_portafolio_enriquecido_actual()
        position_rows = current_portafolio["inversion"] + current_portafolio["fci_cash_management"]
        metadata_by_key = {
            (
                str(item["activo"].simbolo or "").strip().upper(),
                str(item["activo"].mercado or "").strip().upper(),
            ): {
                "valorizado": item["activo"].valorizado,
                "peso_porcentual": item.get("peso_porcentual") or 0,
                "bloque_estrategico": item.get("bloque_estrategico") or "N/A",
            }
            for item in position_rows
        }

        enriched_rows = []
        weak_blocks = {}
        for row in history_rows:
            metadata = metadata_by_key.get(
                (
                    str(row.get("simbolo") or "").strip().upper(),
                    str(row.get("mercado") or "").strip().upper(),
                ),
                {},
            )
            enriched_row = {
                **row,
                "valorizado": metadata.get("valorizado") or Decimal("0"),
                "peso_porcentual": metadata.get("peso_porcentual") or 0,
                "bloque_estrategico": metadata.get("bloque_estrategico") or "N/A",
            }
            enriched_rows.append(enriched_row)
            if enriched_row["quality_status"] == "weak" and enriched_row["bloque_estrategico"] != "N/A":
                weak_blocks[enriched_row["bloque_estrategico"]] = (
                    weak_blocks.get(enriched_row["bloque_estrategico"], Decimal("0")) + enriched_row["valorizado"]
                )

        severity_order = {"weak": 0, "watch": 1, "insufficient": 2, "strong": 3}
        top_rows = sorted(
            enriched_rows,
            key=lambda item: (
                severity_order.get(str(item.get("quality_status") or ""), 9),
                -(item.get("valorizado") or Decimal("0")),
                str(item.get("simbolo") or ""),
            ),
        )[: max(int(top_limit or 0), 1)]
        weak_block_rows = [
            {"label": label, "value_total": value_total}
            for label, value_total in sorted(weak_blocks.items(), key=lambda item: item[1], reverse=True)
        ]

        alerts = []
        if int(summary.get("weak_count") or 0) > 0:
            alerts.append(
                {
                    "tone": "warning",
                    "title": "Liquidez reciente debil en posiciones actuales",
                    "message": f"{summary['weak_count']} simbolo(s) muestran spread o actividad reciente debil para reforzar compras.",
                }
            )
        if int(summary.get("insufficient_count") or 0) > 0:
            alerts.append(
                {
                    "tone": "secondary",
                    "title": "Historial puntual todavia corto",
                    "message": f"{summary['insufficient_count']} simbolo(s) todavia no acumulan observaciones suficientes para lectura reciente.",
                }
            )

        return {
            "lookback_days": lookback_days,
            "summary": summary,
            "rows": enriched_rows,
            "top_rows": top_rows,
            "weak_blocks": weak_block_rows,
            "alerts": alerts[:3],
            "has_history": bool(enriched_rows),
        }

    return _get_cached_selector_result(f"market_snapshot_history_feature:{int(lookback_days)}", build)


def get_portfolio_parking_feature_context(*, top_limit: int = 5) -> Dict:
    def build():
        portafolio = get_portafolio_enriquecido_actual()
        relevant_items = portafolio["inversion"] + portafolio["fci_cash_management"]
        rows = []
        parking_blocks: Dict[str, Decimal] = {}
        for item in relevant_items:
            row = build_portafolio_row(item["activo"])
            row["bloque_estrategico"] = item.get("bloque_estrategico") or "N/A"
            rows.append(row)
            if row["has_parking"]:
                block_label = str(item.get("bloque_estrategico") or "N/A")
                parking_blocks[block_label] = parking_blocks.get(block_label, Decimal("0")) + row["valorizado"]
        total_positions = len(rows)
        parking_rows = [row for row in rows if row["has_parking"]]
        parking_count = len(parking_rows)
        parking_value_total = sum((row["valorizado"] for row in parking_rows), Decimal("0"))
        top_rows = sorted(parking_rows, key=lambda row: row["valorizado"], reverse=True)[: max(int(top_limit or 0), 1)]
        parking_block_summary = [
            {"label": label, "value_total": value_total}
            for label, value_total in sorted(parking_blocks.items(), key=lambda item: item[1], reverse=True)
        ]

        alerts = []
        if parking_count > 0:
            alerts.append(
                {
                    "tone": "warning",
                    "title": "Parking visible en posiciones actuales",
                    "message": f"{parking_count} posicion(es) del portafolio invertido siguen mostrando parking visible en IOL.",
                }
            )

        return {
            "has_visible_parking": parking_count > 0,
            "summary": {
                "total_positions": total_positions,
                "parking_count": parking_count,
                "parking_pct": _safe_percentage(parking_count, total_positions),
                "parking_value_total": parking_value_total,
            },
            "parking_blocks": parking_block_summary,
            "top_rows": top_rows,
            "alerts": alerts,
        }

    return _get_cached_selector_result("portfolio_parking_feature", build)


def get_portafolio_enriquecido_actual() -> Dict[str, List[Dict]]:
    """Obtiene el portafolio actual enriquecido con metadata, separado en liquidez e inversión."""
    def build():
        portafolio = get_latest_portafolio_data()
        simbolos = [activo.simbolo for activo in portafolio]
        parametros = {p.simbolo: p for p in ParametroActivo.objects.filter(simbolo__in=simbolos)}

        # Calcular total del portafolio para pesos porcentuales
        total_portafolio = sum(activo.valorizado for activo in portafolio)

        # Traducciones de tipos
        tipo_traducciones = {
            'CEDEARS': 'CEDEAR',
            'ACCIONES': 'Acción',
            'TitulosPublicos': 'Título Público',
            'FondoComundeInversion': 'FCI',
            'CAUCIONESPESOS': 'Caución',
        }

        # Traducciones de monedas
        moneda_traducciones = {
            'peso_Argentino': 'ARS',
            'dolar_Estadounidense': 'USD',
        }

        liquidez = []
        inversion = []
        fci_cash_management = []  # Categoría intermedia para FCI de cash management

        for activo in portafolio:
            param = parametros.get(activo.simbolo)
            tipo_traducido = tipo_traducciones.get(activo.tipo, activo.tipo)
            moneda_traducida = moneda_traducciones.get(activo.moneda, activo.moneda)

            # Calcular peso porcentual
            peso_porcentual = (activo.valorizado / total_portafolio * 100) if total_portafolio > 0 else 0

            item = {
                'activo': activo,
                'sector': param.sector if param else 'N/A',
                'bloque_estrategico': param.bloque_estrategico if param else 'N/A',
                'pais_exposicion': param.pais_exposicion if param else 'N/A',
                'tipo_patrimonial': param.tipo_patrimonial if param else 'N/A',
                'observaciones': param.observaciones if param else '',
                'tipo_traducido': tipo_traducido,
                'moneda_traducida': moneda_traducida,
                'peso_porcentual': peso_porcentual,
            }

            # Clasificación refinada
            simbolo_upper = activo.simbolo.upper()
            if activo.tipo == 'CAUCIONESPESOS' or 'CAUCIÓN' in simbolo_upper:
                # Caución como liquidez operativa
                liquidez.append(item)
            elif simbolo_upper in ['ADBAICA', 'IOLPORA', 'PRPEDOB']:
                # FCI de cash management como categoría intermedia
                fci_cash_management.append(item)
            elif activo.tipo == 'FondoComundeInversion':
                # Otros FCI van al portafolio invertido
                inversion.append(item)
            elif activo.tipo in ['CEDEARS', 'ACCIONES', 'TitulosPublicos'] or 'ETF' in simbolo_upper:
                # Activos tradicionales van al portafolio invertido
                inversion.append(item)
            else:
                # Resto va al portafolio invertido por defecto
                inversion.append(item)

        # Ordenar inversión por valorizado descendente
        inversion.sort(key=lambda x: x['activo'].valorizado, reverse=True)
        fci_cash_management.sort(key=lambda x: x['activo'].valorizado, reverse=True)

        return {
            'liquidez': liquidez,
            'fci_cash_management': fci_cash_management,
            'inversion': inversion,
            'total_portafolio': total_portafolio,
        }

    return _get_cached_selector_result("portafolio_enriquecido_actual", build)


def _get_activos_invertidos() -> List[Dict]:
    return get_portafolio_enriquecido_actual()['inversion']


def _get_activos_valorizados_con_metadata() -> List[Dict]:
    portafolio = get_portafolio_enriquecido_actual()
    return portafolio['liquidez'] + portafolio['fci_cash_management'] + portafolio['inversion']


def _build_distribution_from_items(items: List[Dict], field: str) -> Dict[str, float]:
    distribucion: Dict[str, float] = {}
    for item in items:
        key = item.get(field) or 'Sin clasificar'
        if field == 'pais_exposicion' and key in {'Estados Unidos', 'USA'}:
            key = 'USA'
        distribucion[key] = distribucion.get(key, 0) + float(item['activo'].valorizado)
    return distribucion


def _is_technology_sector(sector: str | None) -> bool:
    if not sector:
        return False
    normalized = str(sector).strip().lower()
    return normalized.startswith('tecnolog')




def _aggregate_sector_labels(distribucion: Dict[str, float]) -> Dict[str, float]:
    aggregated: Dict[str, float] = {}
    for sector, valor in distribucion.items():
        label = 'Tecnologia Total' if _is_technology_sector(sector) else sector
        aggregated[label] = aggregated.get(label, 0) + float(valor)
    return aggregated


def _get_resumen_cash_distribution_by_country() -> Dict[str, float]:
    distribucion: Dict[str, float] = {}
    for cuenta in get_latest_resumen_data():
        monto = float(cuenta.disponible)
        if monto <= 0:
            continue
        pais = 'USA' if _normalize_account_currency(cuenta.moneda) == 'USD' else 'Argentina'
        distribucion[pais] = distribucion.get(pais, 0) + monto
    return distribucion


def _normalize_account_currency(moneda: str | None) -> str:
    normalized = str(moneda or '').strip()
    mapping = {
        'ARS': 'ARS',
        'peso_Argentino': 'ARS',
        'USD': 'USD',
        'dolar_Estadounidense': 'USD',
    }
    return mapping.get(normalized, normalized)


def _extract_resumen_cash_components(resumen: List[ResumenCuentaSnapshot]) -> Dict[str, Decimal]:
    cash_immediate_ars = Decimal('0')
    cash_immediate_usd = Decimal('0')
    cash_pending_ars = Decimal('0')
    cash_pending_usd = Decimal('0')
    fallback_cash_ars = Decimal('0')
    fallback_cash_usd = Decimal('0')
    total_broker_en_pesos = None

    for cuenta in resumen:
        currency_code = _normalize_account_currency(cuenta.moneda)
        disponible = Decimal(cuenta.disponible or 0)
        if currency_code == 'ARS':
            fallback_cash_ars += disponible
        elif currency_code == 'USD':
            fallback_cash_usd += disponible

        if total_broker_en_pesos is None and getattr(cuenta, 'total_en_pesos', None) is not None:
            total_broker_en_pesos = Decimal(cuenta.total_en_pesos)

        saldos_detalle = getattr(cuenta, 'saldos_detalle', None) or []
        if not saldos_detalle:
            continue

        immediate_found = False
        for saldo_row in saldos_detalle:
            liquidacion = str(saldo_row.get('liquidacion') or '').strip()
            disponible_row = Decimal(str(saldo_row.get('disponible', 0) or 0))
            if liquidacion == 'inmediato':
                immediate_found = True
                if currency_code == 'ARS':
                    cash_immediate_ars += disponible_row
                elif currency_code == 'USD':
                    cash_immediate_usd += disponible_row
            else:
                if currency_code == 'ARS':
                    cash_pending_ars += disponible_row
                elif currency_code == 'USD':
                    cash_pending_usd += disponible_row

        if not immediate_found:
            if currency_code == 'ARS':
                cash_immediate_ars += disponible
            elif currency_code == 'USD':
                cash_immediate_usd += disponible

    if cash_immediate_ars == 0 and fallback_cash_ars > 0:
        cash_immediate_ars = fallback_cash_ars
    if cash_immediate_usd == 0 and fallback_cash_usd > 0:
        cash_immediate_usd = fallback_cash_usd

    return {
        'cash_immediate_ars': cash_immediate_ars,
        'cash_immediate_usd': cash_immediate_usd,
        'cash_pending_ars': cash_pending_ars,
        'cash_pending_usd': cash_pending_usd,
        'cash_disponible_ars': fallback_cash_ars,
        'cash_disponible_usd': fallback_cash_usd,
        'total_broker_en_pesos': total_broker_en_pesos or Decimal('0'),
    }


def get_dashboard_kpis() -> Dict:
    """Calcula los KPIs principales del dashboard con métricas separadas por categoría."""
    def build():
        portafolio = get_latest_portafolio_data()
        resumen = get_latest_resumen_data()

        # Obtener clasificación del portafolio
        portafolio_clasificado = get_portafolio_enriquecido_actual()

        # Cash inmediato y a liquidar desde estadocuenta
        cash_components = _extract_resumen_cash_components(resumen)
        cash_ars = cash_components['cash_immediate_ars']
        cash_usd = cash_components['cash_immediate_usd']
        cash_a_liquidar_ars = cash_components['cash_pending_ars']
        cash_a_liquidar_usd = cash_components['cash_pending_usd']
        total_broker_en_pesos = cash_components['total_broker_en_pesos']

        # 1. Total IOL = SUM(valorizado de todos los activos) + cash ARS + cash USD
        total_activos_valorizados = sum(activo.valorizado for activo in portafolio)
        total_iol_calculado = total_activos_valorizados + cash_ars + cash_usd
        total_iol = total_broker_en_pesos if total_broker_en_pesos > 0 else total_iol_calculado

        # KPIs separados por categoría
        # 2. Liquidez Operativa = caución + saldo ARS disponible + saldo USD disponible
        caucion_valor = sum(item['activo'].valorizado for item in portafolio_clasificado['liquidez'] if item['tipo_traducido'] == 'Caución')
        liquidez_operativa = caucion_valor + cash_ars + cash_usd

        # 3. FCI Cash Management = suma de FCI de cash management
        fci_cash_valor = sum(item['activo'].valorizado for item in portafolio_clasificado['fci_cash_management'])

        # 4. Portafolio Invertido = activos de inversión (CEDEAR, acciones, bonos, ETF, otros FCI)
        portafolio_invertido = sum(item['activo'].valorizado for item in portafolio_clasificado['inversion'])

        cash_disponible_broker = cash_ars + cash_usd
        caucion_colocada = caucion_valor
        liquidez_estrategica = fci_cash_valor
        liquidez_total_combinada = cash_disponible_broker + caucion_colocada + liquidez_estrategica
        total_patrimonio_modelado = (
            portafolio_invertido
            + liquidez_estrategica
            + cash_disponible_broker
            + caucion_colocada
        )

        # KPIs heredados para compatibilidad
        titulos_valorizados = sum(
            activo.valorizado for activo in portafolio
            if activo.tipo in ['CEDEARS', 'ACCIONES', 'TitulosPublicos'] or 'ETF' in activo.simbolo.upper()
        )
        capital_invertido_real = total_iol - liquidez_operativa - fci_cash_valor

        # Rendimiento simple sobre costo estimado del capital realmente invertido.
        inversion = portafolio_clasificado['inversion']
        rendimiento_total_dinero = sum(item['activo'].ganancia_dinero for item in inversion)
        costo_estimado_invertido = portafolio_invertido - rendimiento_total_dinero
        rendimiento_total_porcentaje = (
            rendimiento_total_dinero / costo_estimado_invertido * 100
        ) if costo_estimado_invertido > 0 else 0

        # Concentraci?n de posiciones sobre portafolio invertido.
        portafolio_ordenado = sorted(
            (item['activo'] for item in inversion),
            key=lambda activo: activo.valorizado,
            reverse=True,
        )
        top_5_valor = sum(activo.valorizado for activo in portafolio_ordenado[:5])
        top_5_concentracion = (top_5_valor / portafolio_invertido * 100) if portafolio_invertido else 0

        # Top 10 concentraci?n
        top_10_valor = sum(activo.valorizado for activo in portafolio_ordenado[:10])
        top_10_concentracion = (top_10_valor / portafolio_invertido * 100) if portafolio_invertido else 0

        # Porcentajes de los bloques patrimoniales
        pct_fci_cash_management = (fci_cash_valor / total_iol * 100) if total_iol else 0
        pct_portafolio_invertido = (portafolio_invertido / total_iol * 100) if total_iol else 0
        pct_liquidez_total = ((liquidez_operativa + fci_cash_valor) / total_iol * 100) if total_iol else 0
        pct_liquidez_operativa = (cash_disponible_broker / total_patrimonio_modelado * 100) if total_patrimonio_modelado else 0
        pct_caucion_colocada = (caucion_colocada / total_patrimonio_modelado * 100) if total_patrimonio_modelado else 0
        pct_liquidez_estrategica = (liquidez_estrategica / total_patrimonio_modelado * 100) if total_patrimonio_modelado else 0
        pct_liquidez_total_combinada = (liquidez_total_combinada / total_patrimonio_modelado * 100) if total_patrimonio_modelado else 0
        pct_portafolio_invertido_modelado = (portafolio_invertido / total_patrimonio_modelado * 100) if total_patrimonio_modelado else 0

        return {
            'total_iol': total_iol,
            'total_iol_legacy_calculated': total_iol_calculado,
            'total_broker_en_pesos': total_broker_en_pesos,
            'total_patrimonio_modelado': total_patrimonio_modelado,
            'titulos_valorizados': titulos_valorizados,
            'cash_ars': cash_ars,
            'cash_usd': cash_usd,
            'cash_a_liquidar_ars': cash_a_liquidar_ars,
            'cash_a_liquidar_usd': cash_a_liquidar_usd,
            'cash_a_liquidar_broker': cash_a_liquidar_ars + cash_a_liquidar_usd,
            'cash_disponible_broker': cash_disponible_broker,
            'caucion_valor': caucion_valor,
            'caucion_colocada': caucion_colocada,
            'liquidez_operativa': liquidez_operativa,
            'liquidez_estrategica': liquidez_estrategica,
            'liquidez_total_combinada': liquidez_total_combinada,
            'fci_cash_management': fci_cash_valor,
            'portafolio_invertido': portafolio_invertido,
            'capital_invertido_real': capital_invertido_real,
            'rendimiento_total_porcentaje': rendimiento_total_porcentaje,
            'rendimiento_total_dinero': rendimiento_total_dinero,
            'rendimiento_total_cost_basis': costo_estimado_invertido,
            'top_5_concentracion': top_5_concentracion,
            'top_10_concentracion': top_10_concentracion,
            'pct_liquidez_operativa': pct_liquidez_operativa,
            'pct_caucion_colocada': pct_caucion_colocada,
            'pct_liquidez_estrategica': pct_liquidez_estrategica,
            'pct_liquidez_total_combinada': pct_liquidez_total_combinada,
            'pct_fci_cash_management': pct_fci_cash_management,
            'pct_portafolio_invertido': pct_portafolio_invertido,
            'pct_portafolio_invertido_modelado': pct_portafolio_invertido_modelado,
            'pct_liquidez_total': pct_liquidez_total,
            'methodology': {
                'top_5_concentracion': 'sum(top_5 valorizado del portafolio invertido) / portafolio invertido',
                'top_10_concentracion': 'sum(top_10 valorizado del portafolio invertido) / portafolio invertido',
                'top_positions_basis': 'portafolio_invertido',
                'rendimiento_total_porcentaje': 'ganancia acumulada / costo estimado del portafolio invertido',
                'rendimiento_total_basis': 'portafolio_invertido_costo_estimado',
                'pct_liquidez_total': '(liquidez operativa + cash management) / total iol',
                'pct_portafolio_invertido': 'portafolio invertido / total iol',
                'total_iol': 'si existe total_en_pesos desde estadocuenta se usa como ancla broker; si no, fallback a activos + cash inmediato',
                'total_patrimonio_modelado': 'portafolio invertido + cash disponible broker + caucion colocada + fci cash management',
                'pct_liquidez_operativa': 'cash disponible broker / total patrimonio modelado',
                'pct_caucion_colocada': 'caucion colocada / total patrimonio modelado',
                'pct_liquidez_estrategica': 'fci cash management / total patrimonio modelado',
                'pct_liquidez_total_combinada': '(cash disponible broker + caucion colocada + fci cash management) / total patrimonio modelado',
                'pct_portafolio_invertido_modelado': 'portafolio invertido / total patrimonio modelado',
            },
        }

    return _get_cached_selector_result("dashboard_kpis", build)


def get_macro_local_context(total_iol: float | None = None) -> Dict:
    """Obtiene contexto macro local persistido para enriquecer el analisis."""

    def build():
        return LocalMacroSeriesService().get_context_summary(total_iol=total_iol)

    total_stamp = round(float(total_iol), 2) if total_iol is not None else "none"
    return _get_cached_selector_result(f"macro_local_context:{total_stamp}", build)


def get_liquidity_contract_summary(kpis: Dict | None = None) -> Dict:
    """Normaliza el contrato de liquidez para consumidores heredados."""

    kpis = kpis or get_dashboard_kpis()

    total = float(kpis.get("total_patrimonio_modelado") or kpis.get("total_iol") or 0.0)
    cash_operativo = float(kpis.get("cash_disponible_broker") or 0.0)
    caucion_tactica = float(kpis.get("caucion_colocada") or 0.0)
    fci_estrategico = float(
        kpis.get("liquidez_estrategica")
        if kpis.get("liquidez_estrategica") is not None
        else (kpis.get("fci_cash_management") or 0.0)
    )

    # Fallback para payloads viejos que solo exponen liquidez_operativa.
    if (
        "cash_disponible_broker" not in kpis
        and "caucion_colocada" not in kpis
        and "liquidez_operativa" in kpis
    ):
        cash_operativo = float(kpis.get("liquidez_operativa") or 0.0)
        caucion_tactica = 0.0

    liquidez_desplegable_total = cash_operativo + caucion_tactica + fci_estrategico

    return {
        "cash_operativo": cash_operativo,
        "caucion_tactica": caucion_tactica,
        "fci_estrategico": fci_estrategico,
        "liquidez_desplegable_total": liquidez_desplegable_total,
        "pct_cash_operativo": (cash_operativo / total * 100) if total > 0 else 0.0,
        "pct_caucion_tactica": (caucion_tactica / total * 100) if total > 0 else 0.0,
        "pct_fci_estrategico": (fci_estrategico / total * 100) if total > 0 else 0.0,
        "pct_liquidez_desplegable_total": (
            liquidez_desplegable_total / total * 100
        ) if total > 0 else 0.0,
        "total_base": total,
        "methodology": {
            "cash_operativo": "cash disponible broker",
            "caucion_tactica": "caucion colocada",
            "fci_estrategico": "fci cash management",
            "liquidez_desplegable_total": "cash operativo + caucion tactica + fci estrategico",
            "total_base": "total patrimonio modelado",
        },
    }


def _build_portfolio_scope_summary() -> Dict:
    """Explicita el universo broker vs capital invertido para Planeacion."""

    kpis = get_dashboard_kpis()
    resumen = get_latest_resumen_data()

    cash_components = _extract_resumen_cash_components(resumen)
    cash_ars = float(cash_components['cash_immediate_ars'])
    cash_usd = float(cash_components['cash_immediate_usd'])
    cash_a_liquidar_ars = float(cash_components['cash_pending_ars'])
    cash_a_liquidar_usd = float(cash_components['cash_pending_usd'])
    portfolio_total_broker = float(kpis.get("total_broker_en_pesos") or kpis.get("total_iol") or 0.0)
    invested_portfolio = float(kpis.get("portafolio_invertido") or 0.0)
    caucion_colocada = float(kpis.get("caucion_colocada") or 0.0)
    cash_management_fci = float(kpis.get("fci_cash_management") or 0.0)
    cash_available_broker = cash_ars

    cash_ratio_total = (cash_available_broker / portfolio_total_broker) if portfolio_total_broker > 0 else 0.0
    caucion_ratio_total = (caucion_colocada / portfolio_total_broker) if portfolio_total_broker > 0 else 0.0
    invested_ratio_total = (invested_portfolio / portfolio_total_broker) if portfolio_total_broker > 0 else 0.0
    fci_ratio_total = (cash_management_fci / portfolio_total_broker) if portfolio_total_broker > 0 else 0.0

    return {
        "portfolio_total_broker": portfolio_total_broker,
        "invested_portfolio": invested_portfolio,
        "caucion_colocada": caucion_colocada,
        "cash_management_fci": cash_management_fci,
        "cash_available_broker": cash_available_broker,
        "cash_available_broker_ars": cash_ars,
        "cash_available_broker_usd": cash_usd,
        "cash_settling_broker": cash_a_liquidar_ars,
        "cash_settling_broker_ars": cash_a_liquidar_ars,
        "cash_settling_broker_usd": cash_a_liquidar_usd,
        "cash_ratio_total": cash_ratio_total,
        "caucion_ratio_total": caucion_ratio_total,
        "invested_ratio_total": invested_ratio_total,
        "fci_ratio_total": fci_ratio_total,
    }


def get_distribucion_sector(base: str = 'total_activos') -> Dict[str, float]:
    """Obtiene la distribuci?n por sector o bloque patrimonial seg?n la base."""
    if base == 'portafolio_invertido':
        return _build_distribution_from_items(_get_activos_invertidos(), 'sector')
    return _build_distribution_from_items(_get_activos_valorizados_con_metadata(), 'sector')


def get_distribucion_pais(base: str = 'portafolio_invertido') -> Dict[str, float]:
    """Obtiene la distribuci?n por pa?s de exposici?n real."""
    if base == 'total_iol':
        distribucion = _build_distribution_from_items(_get_activos_valorizados_con_metadata(), 'pais_exposicion')
        for pais, monto in _get_resumen_cash_distribution_by_country().items():
            distribucion[pais] = distribucion.get(pais, 0) + monto
        return distribucion
    return _build_distribution_from_items(_get_activos_invertidos(), 'pais_exposicion')


def get_distribucion_tipo_patrimonial(base: str = 'total_activos') -> Dict[str, float]:
    """Obtiene la distribuci?n por tipo patrimonial."""
    if base == 'portafolio_invertido':
        return _build_distribution_from_items(_get_activos_invertidos(), 'tipo_patrimonial')
    return _build_distribution_from_items(_get_activos_valorizados_con_metadata(), 'tipo_patrimonial')


def get_distribucion_moneda() -> Dict[str, float]:
    """Obtiene la distribución por moneda de exposición real/económica."""
    portafolio = get_latest_portafolio_data()
    resumen = get_latest_resumen_data()
    simbolos = [activo.simbolo for activo in portafolio]
    parametros = {p.simbolo: p for p in ParametroActivo.objects.filter(simbolo__in=simbolos)}
    distribucion = {}
    # Agregar activos del portafolio
    for activo in portafolio:
        parametro = parametros.get(activo.simbolo)

        # Moneda económica/subyacente (exposición real)
        if parametro and parametro.pais_exposicion in ['USA', 'Estados Unidos']:
            moneda = 'USD'
        elif activo.moneda == 'dolar_Estadounidense':
            moneda = 'USD'
        elif activo.moneda == 'peso_Argentino':
            moneda = 'ARS'
        else:
            # Para otros casos, intentar inferir de tipo_patrimonial
            if parametro and parametro.tipo_patrimonial == 'Hard Assets':
                moneda = 'Hard Assets'
            else:
                moneda = 'ARS'  # Default a ARS

        distribucion[moneda] = distribucion.get(moneda, 0) + float(activo.valorizado)

    # Agregar cash disponible
    for cuenta in resumen:
        if cuenta.moneda == 'ARS':
            distribucion['ARS'] = distribucion.get('ARS', 0) + float(cuenta.disponible)
        elif cuenta.moneda == 'USD':
            distribucion['USD'] = distribucion.get('USD', 0) + float(cuenta.disponible)

    return distribucion


def get_distribucion_moneda_operativa() -> Dict[str, float]:
    """Obtiene la distribución por moneda operativa (de cotización)."""
    portafolio = get_latest_portafolio_data()
    resumen = get_latest_resumen_data()
    distribucion = {}

    # Agregar activos del portafolio por moneda de cotización
    for activo in portafolio:
        if activo.moneda == 'dolar_Estadounidense':
            moneda = 'USD'
        elif activo.moneda == 'peso_Argentino':
            moneda = 'ARS'
        else:
            moneda = 'ARS'  # Default

        distribucion[moneda] = distribucion.get(moneda, 0) + float(activo.valorizado)

    # Agregar cash disponible
    for cuenta in resumen:
        if cuenta.moneda == 'ARS':
            distribucion['ARS'] = distribucion.get('ARS', 0) + float(cuenta.disponible)
        elif cuenta.moneda == 'USD':
            distribucion['USD'] = distribucion.get('USD', 0) + float(cuenta.disponible)

    return distribucion


def get_concentracion_patrimonial() -> Dict[str, float]:
    """Obtiene la concentración por bloque patrimonial (Liquidez, Cash Management, Invertido)."""
    kpis = get_dashboard_kpis()
    total_iol = kpis['total_iol']

    if total_iol == 0:
        return {}

    return {
        'Liquidez': (kpis['liquidez_operativa'] / total_iol * 100),
        'Cash Management': (kpis['fci_cash_management'] / total_iol * 100),
        'Invertido': (kpis['portafolio_invertido'] / total_iol * 100),
    }


def get_concentracion_sectorial() -> Dict[str, float]:
    """Obtiene la concentración por sector económico (excluyendo liquidez)."""
    # Solo considerar activos de inversión (excluir liquidez y cash management)
    portafolio_invertido = get_portafolio_enriquecido_actual()['inversion']
    distribucion = {}

    for item in portafolio_invertido:
        sector = item['sector']
        if sector and sector != 'N/A':
            distribucion[sector] = distribucion.get(sector, 0) + float(item['activo'].valorizado)

    total = sum(distribucion.values())
    if total == 0:
        return {}
    return {sector: (valor / total * 100) for sector, valor in distribucion.items()}


def get_concentracion_sector() -> Dict[str, float]:
    """Calcula la concentraci?n sectorial pura del capital invertido."""
    distribucion = get_distribucion_sector(base='portafolio_invertido')
    total = sum(distribucion.values())
    if total == 0:
        return {}

    return {sector: (valor / total * 100) for sector, valor in distribucion.items()}




def get_concentracion_sector_agregado() -> Dict[str, float]:
    """Calcula concentracion sectorial agregando subsectores tecnol?gicos."""
    distribucion = _aggregate_sector_labels(get_distribucion_sector(base='portafolio_invertido'))
    total = sum(distribucion.values())
    if total == 0:
        return {}

    return {sector: (valor / total * 100) for sector, valor in distribucion.items()}


def get_concentracion_pais(base: str = 'portafolio_invertido') -> Dict[str, float]:
    """Calcula la concentraci?n por pa?s en porcentajes."""
    distribucion = get_distribucion_pais(base=base)
    total = sum(distribucion.values())
    if total == 0:
        return {}

    return {pais: (valor / total * 100) for pais, valor in distribucion.items()}


def get_concentracion_tipo_patrimonial(base: str = 'total_activos') -> Dict[str, float]:
    """Calcula la concentraci?n por tipo patrimonial en porcentajes."""
    distribucion = get_distribucion_tipo_patrimonial(base=base)
    total = sum(distribucion.values())
    if total == 0:
        return {}

    return {tipo: (valor / total * 100) for tipo, valor in distribucion.items()}


def get_concentracion_moneda() -> Dict[str, float]:
    """Calcula la concentracion por moneda economica en porcentajes."""
    distribucion = get_distribucion_moneda()
    total = sum(distribucion.values())
    if total == 0:
        return {}

    return {moneda: (valor / total * 100) for moneda, valor in distribucion.items()}


def get_concentracion_moneda_operativa() -> Dict[str, float]:
    """Calcula la concentracion por moneda operativa en porcentajes."""
    distribucion = get_distribucion_moneda_operativa()
    total = sum(distribucion.values())
    if total == 0:
        return {}

    return {moneda: (valor / total * 100) for moneda, valor in distribucion.items()}


def get_riesgo_portafolio_detallado() -> Dict[str, float]:
    """Calcula métricas detalladas de riesgo del portafolio."""
    portafolio = [item['activo'] for item in _get_activos_invertidos()]
    resumen = get_latest_resumen_data()
    portafolio_clasificado = get_portafolio_enriquecido_actual()
    kpis = get_dashboard_kpis()

    total_portafolio = sum(activo.valorizado for activo in portafolio)
    total_iol = kpis.get('total_iol', 0)

    simbolos = [activo.simbolo for activo in portafolio]
    parametros = {p.simbolo: p for p in ParametroActivo.objects.filter(simbolo__in=simbolos)}

    # Exposición geográfica
    exposicion_usa = 0
    exposicion_argentina = 0
    for activo in portafolio:
        parametro = parametros.get(activo.simbolo)
        if parametro and parametro.pais_exposicion in ['USA', 'Estados Unidos']:
            exposicion_usa += activo.valorizado
        elif parametro and parametro.pais_exposicion == 'Argentina':
            exposicion_argentina += activo.valorizado

    # Exposición por tipo
    exposicion_tech = 0
    exposicion_renta_fija_ar = 0
    exposicion_defensivo = 0
    exposicion_growth = 0

    for activo in portafolio:
        parametro = parametros.get(activo.simbolo)
        if parametro:
            if _is_technology_sector(parametro.sector):
                exposicion_tech += activo.valorizado
            if parametro.tipo_patrimonial == 'Bond' and parametro.pais_exposicion == 'Argentina':
                exposicion_renta_fija_ar += activo.valorizado
            if parametro.bloque_estrategico == 'Defensivo':
                exposicion_defensivo += activo.valorizado
            if parametro.bloque_estrategico == 'Growth':
                exposicion_growth += activo.valorizado

    # Liquidez total
    liquidez_total = kpis.get('liquidez_operativa', 0)


    # Calcular porcentajes
    pct_usa = (exposicion_usa / total_portafolio * 100) if total_portafolio > 0 else 0
    pct_argentina = (exposicion_argentina / total_portafolio * 100) if total_portafolio > 0 else 0
    pct_tech = (exposicion_tech / total_portafolio * 100) if total_portafolio > 0 else 0
    pct_renta_fija_ar = (exposicion_renta_fija_ar / total_portafolio * 100) if total_portafolio > 0 else 0
    pct_defensivo = (exposicion_defensivo / total_portafolio * 100) if total_portafolio > 0 else 0
    pct_growth = (exposicion_growth / total_portafolio * 100) if total_portafolio > 0 else 0
    pct_liquidez = (liquidez_total / total_iol * 100) if total_iol > 0 else 0

    return {
        'pct_usa': pct_usa,
        'pct_argentina': pct_argentina,
        'pct_tech': pct_tech,
        'pct_bonos_soberanos': pct_renta_fija_ar,
        'pct_renta_fija_ar': pct_renta_fija_ar,
        'pct_defensivo': pct_defensivo,
        'pct_growth': pct_growth,
        'pct_liquidez': pct_liquidez,
        'methodology': {
            'pct_usa': 'exposicion USA / portafolio invertido',
            'pct_argentina': 'exposicion Argentina / portafolio invertido',
            'pct_tech': 'sectores que comienzan con Tecnología / portafolio invertido',
            'pct_renta_fija_ar': 'Bonos argentinos (soberanos, CER y corporativos) / portafolio invertido',
            'pct_defensivo': 'bloque Defensivo / portafolio invertido',
            'pct_growth': 'bloque Growth / portafolio invertido',
            'pct_liquidez': 'liquidez operativa / total iol',
        },
    }


def get_riesgo_portafolio() -> Dict[str, float]:
    """Calcula métricas de riesgo del portafolio (versión simplificada para compatibilidad)."""
    portafolio = [item['activo'] for item in _get_activos_invertidos()]
    resumen = get_latest_resumen_data()
    portafolio_clasificado = get_portafolio_enriquecido_actual()
    kpis = get_dashboard_kpis()

    total_portafolio = sum(activo.valorizado for activo in portafolio)
    total_iol = kpis.get('total_iol', 0)

    simbolos = [activo.simbolo for activo in portafolio]
    parametros = {p.simbolo: p for p in ParametroActivo.objects.filter(simbolo__in=simbolos)}

    # Exposición USA
    exposicion_usa = 0
    for activo in portafolio:
        parametro = parametros.get(activo.simbolo)
        if parametro and parametro.pais_exposicion in ['USA', 'Estados Unidos']:
            exposicion_usa += activo.valorizado
    exposicion_usa_pct = (exposicion_usa / total_portafolio * 100) if total_portafolio > 0 else 0

    # Exposición Argentina
    exposicion_argentina = 0
    for activo in portafolio:
        parametro = parametros.get(activo.simbolo)
        if parametro and parametro.pais_exposicion == 'Argentina':
            exposicion_argentina += activo.valorizado
    exposicion_argentina_pct = (exposicion_argentina / total_portafolio * 100) if total_portafolio > 0 else 0

    # Liquidez total
    liquidez_total = kpis.get('liquidez_operativa', 0)

    liquidez_pct = (liquidez_total / total_iol * 100) if total_iol > 0 else 0

    volatility_metrics = VolatilityService().calculate_volatility(days=90)
    var_metrics = VaRService().calculate_var_set(confidence=0.95, lookback_days=252)
    cvar_metrics = CVaRService().calculate_cvar_set(confidence=0.95, lookback_days=252)
    stress_metrics = StressTestService().run_all()
    benchmarking = TrackingErrorService().calculate(days=90)
    liquidity = LiquidityService().analyze_portfolio_liquidity()
    metadata_quality = MetadataAuditService().run_audit()
    volatilidad_pct = volatility_metrics.get('annualized_volatility')

    result = {
        'volatilidad_estimada': volatilidad_pct,
        'volatilidad_status': 'ok' if volatilidad_pct is not None else 'insufficient_history',
        'volatilidad_warning': volatility_metrics.get('warning'),
        'volatilidad_observations': volatility_metrics.get('observations'),
        'volatilidad_required_min_observations': volatility_metrics.get('required_min_observations'),
        'exposicion_usa': exposicion_usa_pct,
        'exposicion_argentina': exposicion_argentina_pct,
        'liquidez': liquidez_pct,
    }
    result.update(var_metrics)
    result.update(cvar_metrics)
    result.update(benchmarking)
    if liquidity:
        result["liquidity_score"] = liquidity.get("portfolio_liquidity_score")
        result["days_to_liquidate"] = liquidity.get("days_to_liquidate")
    if metadata_quality:
        result["metadata_unclassified_count"] = metadata_quality.get("unclassified_assets_count", 0)
        result["metadata_inconsistent_count"] = metadata_quality.get("inconsistent_assets_count", 0)
    if stress_metrics:
        worst_case = min(
            stress_metrics.values(),
            key=lambda scenario: scenario.get("impact_portfolio_pct", 0)
        )
        result["stress_worst_case_label"] = worst_case["label"]
        result["stress_worst_case_pct"] = worst_case["impact_portfolio_pct"]
    return result


def get_analytics_mensual() -> Dict[str, float]:
    """Calcula m?tricas operativas del mes actual a partir de operaciones ejecutadas."""
    from apps.operaciones_iol.models import OperacionIOL
    from apps.parametros.models import ConfiguracionDashboard
    from django.utils import timezone
    from dateutil.relativedelta import relativedelta

    hoy = timezone.now()
    inicio_mes = hoy.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    fin_mes = (inicio_mes + relativedelta(months=1)) - timezone.timedelta(seconds=1)

    operaciones_mes = OperacionIOL.objects.filter(
        fecha_operada__gte=inicio_mes,
        fecha_operada__lte=fin_mes,
        estado__in=['terminada', 'Terminada', 'TERMINADA']
    )

    if not operaciones_mes.exists():
        operaciones_mes = OperacionIOL.objects.filter(
            fecha_orden__gte=inicio_mes,
            fecha_orden__lte=fin_mes,
            estado__in=['terminada', 'Terminada', 'TERMINADA']
        )

    operaciones_mes_list = list(operaciones_mes.order_by('-fecha_operada', '-fecha_orden'))
    monto_compras = Decimal('0')
    monto_ventas = Decimal('0')
    dividendos_mes = Decimal('0')
    suscripciones_fci_mes = Decimal('0')
    rescates_fci_mes = Decimal('0')
    compras_count = 0
    ventas_count = 0
    dividendos_count = 0
    suscripciones_fci_count = 0
    rescates_fci_count = 0
    recent_operations = []

    for op in operaciones_mes_list:
        operation_type_key = _classify_operation_type(op.tipo)
        effective_amount = _get_effective_operation_amount(op)

        if operation_type_key == 'buy':
            compras_count += 1
            monto_compras += effective_amount
        elif operation_type_key == 'sell':
            ventas_count += 1
            monto_ventas += effective_amount
        elif operation_type_key == 'dividend':
            dividendos_count += 1
            dividendos_mes += effective_amount
        elif operation_type_key == 'fci_subscription':
            suscripciones_fci_count += 1
            suscripciones_fci_mes += effective_amount
        elif operation_type_key == 'fci_redemption':
            rescates_fci_count += 1
            rescates_fci_mes += effective_amount

        if len(recent_operations) < 5:
            event_at = op.fecha_operada or op.fecha_orden
            recent_operations.append(
                {
                    'numero': op.numero,
                    'simbolo': op.simbolo,
                    'tipo': op.tipo,
                    'tipo_key': operation_type_key,
                    'estado': op.estado_actual or op.estado,
                    'fecha_label': timezone.localtime(event_at).strftime("%Y-%m-%d %H:%M") if event_at else '',
                    'monto': effective_amount,
                    'plazo': op.plazo or '',
                    'moneda': op.moneda or '',
                }
            )

    try:
        config_objetivo = ConfiguracionDashboard.objects.get(clave='contribucion_mensual')
        aporte_mensual_objetivo = float(config_objetivo.valor)
    except (ConfiguracionDashboard.DoesNotExist, ValueError):
        aporte_mensual_objetivo = 50000.0

    aporte_mensual_objetivo = Decimal(str(aporte_mensual_objetivo))
    aporte_ejecutado = monto_compras - monto_ventas
    aporte_pendiente = aporte_mensual_objetivo - aporte_ejecutado

    return {
        'compras_mes': monto_compras,
        'ventas_mes': monto_ventas,
        'compras_count': compras_count,
        'ventas_count': ventas_count,
        'dividendos_mes': dividendos_mes,
        'dividendos_count': dividendos_count,
        'suscripciones_fci_mes': suscripciones_fci_mes,
        'suscripciones_fci_count': suscripciones_fci_count,
        'rescates_fci_mes': rescates_fci_mes,
        'rescates_fci_count': rescates_fci_count,
        'operaciones_ejecutadas_count': len(operaciones_mes_list),
        'aporte_mensual_ejecutado': aporte_ejecutado,
        'aporte_pendiente': max(0, aporte_pendiente),
        'recent_operations': recent_operations,
    }


def _classify_operation_type(tipo: str | None) -> str:
    normalized = unicodedata.normalize("NFKD", str(tipo or "").strip().lower())
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    if normalized == 'compra':
        return 'buy'
    if normalized == 'venta':
        return 'sell'
    if 'dividend' in normalized:
        return 'dividend'
    if 'fci' in normalized and ('suscrip' in normalized or 'suscripci?' in normalized):
        return 'fci_subscription'
    if 'fci' in normalized and 'rescat' in normalized:
        return 'fci_redemption'
    return 'other'


def _get_effective_operation_amount(op) -> Decimal:
    for candidate in (
        getattr(op, 'monto_operado', None),
        getattr(op, 'monto_operacion', None),
        getattr(op, 'monto', None),
    ):
        if candidate not in (None, ''):
            return Decimal(candidate)

    cantidad_operada = getattr(op, 'cantidad_operada', None)
    precio_operado = getattr(op, 'precio_operado', None)
    if cantidad_operada not in (None, '') and precio_operado not in (None, ''):
        return Decimal(cantidad_operada) * Decimal(precio_operado)
    return Decimal('0')


def get_portafolio_clasificado_fecha(portafolio_fecha) -> Dict[str, List[Dict]]:
    """Clasifica un portafolio histórico en categorías (versión simplificada para evolución histórica)."""
    simbolos = [activo.simbolo for activo in portafolio_fecha]
    parametros = {p.simbolo: p for p in ParametroActivo.objects.filter(simbolo__in=simbolos)}

    liquidez = []
    fci_cash_management = []
    inversion = []

    for activo in portafolio_fecha:
        parametro = parametros.get(activo.simbolo)

        # Determinar tipo traducido
        tipo_traducido = 'Desconocido'
        if activo.tipo == 'CEDEARS':
            tipo_traducido = 'CEDEAR'
        elif activo.tipo == 'ACCIONES':
            tipo_traducido = 'Acción'
        elif activo.tipo == 'TitulosPublicos':
            tipo_traducido = 'Título Público'
        elif activo.tipo == 'FondoComundeInversion':
            tipo_traducido = 'FCI'
        elif activo.tipo == 'CAUCIONESPESOS':
            tipo_traducido = 'Caución'

        item = {
            'activo': activo,
            'tipo_traducido': tipo_traducido,
            'parametro': parametro
        }

        # Clasificar por bloque estratégico
        if parametro and parametro.bloque_estrategico == 'Liquidez':
            liquidez.append(item)
        elif parametro and parametro.bloque_estrategico == 'FCI Cash Management':
            fci_cash_management.append(item)
        else:
            # Por defecto va a inversión
            inversion.append(item)

    return {
        'liquidez': liquidez,
        'fci_cash_management': fci_cash_management,
        'inversion': inversion,
    }


def get_evolucion_historica(days: int = 30, max_points: int = 14) -> Dict[str, list]:
    """Obtiene evolución histórica consolidada por día calendario."""
    from collections import defaultdict
    from apps.portafolio_iol.models import ActivoPortafolioSnapshot, PortfolioSnapshot
    from apps.resumen_iol.models import ResumenCuentaSnapshot
    from django.utils import timezone
    from dateutil.relativedelta import relativedelta

    fecha_fin = timezone.now()
    fecha_inicio = fecha_fin - relativedelta(days=days)

    portafolio_snapshots = ActivoPortafolioSnapshot.objects.filter(
        fecha_extraccion__gte=fecha_inicio,
        fecha_extraccion__lte=fecha_fin,
    ).order_by("fecha_extraccion")
    resumen_snapshots = ResumenCuentaSnapshot.objects.filter(
        fecha_extraccion__gte=fecha_inicio,
        fecha_extraccion__lte=fecha_fin,
    ).order_by("fecha_extraccion")

    portafolio_por_dia = defaultdict(list)
    for activo in portafolio_snapshots:
        portafolio_por_dia[activo.fecha_extraccion.date()].append(activo)

    resumen_por_dia = defaultdict(list)
    for cuenta in resumen_snapshots:
        resumen_por_dia[cuenta.fecha_extraccion.date()].append(cuenta)

    fechas_unicas = sorted(set(portafolio_por_dia.keys()) | set(resumen_por_dia.keys()))
    if len(fechas_unicas) < 2:
        return {
            "tiene_datos": False,
            "mensaje": "Aún no hay historial suficiente para mostrar evolución",
            "fechas": [],
            "total_iol": [],
            "liquidez_operativa": [],
            "portafolio_invertido": [],
            "cash_management": [],
        }

    fechas_a_procesar = fechas_unicas[-max_points:] if max_points and max_points > 0 else fechas_unicas

    fechas_str = []
    total_iol_vals = []
    liquidez_vals = []
    portafolio_vals = []
    cash_vals = []

    for fecha in fechas_a_procesar:
        portafolio_fecha = portafolio_por_dia.get(fecha, [])
        resumen_fecha = resumen_por_dia.get(fecha, [])

        total_portafolio = sum(activo.valorizado for activo in portafolio_fecha)
        total_cash = sum(cuenta.disponible for cuenta in resumen_fecha)
        total_iol = total_portafolio + total_cash

        portafolio_clasificado = get_portafolio_clasificado_fecha(portafolio_fecha)

        caucion_valor = sum(
            item["activo"].valorizado
            for item in portafolio_clasificado.get("liquidez", [])
            if item["tipo_traducido"] == "Caución"
        )
        cash_ars = sum(cuenta.disponible for cuenta in resumen_fecha if cuenta.moneda == "ARS")
        cash_usd = sum(cuenta.disponible for cuenta in resumen_fecha if cuenta.moneda == "USD")
        liquidez_operativa = caucion_valor + cash_ars + cash_usd
        portafolio_invertido = sum(
            item["activo"].valorizado for item in portafolio_clasificado.get("inversion", [])
        )
        cash_management = sum(
            item["activo"].valorizado
            for item in portafolio_clasificado.get("fci_cash_management", [])
        )

        fechas_str.append(fecha.strftime("%Y-%m-%d"))
        total_iol_vals.append(float(total_iol))
        liquidez_vals.append(float(liquidez_operativa))
        portafolio_vals.append(float(portafolio_invertido))
        cash_vals.append(float(cash_management))

    return {
        "tiene_datos": True,
        "fechas": fechas_str,
        "total_iol": total_iol_vals,
        "liquidez_operativa": liquidez_vals,
        "portafolio_invertido": portafolio_vals,
        "cash_management": cash_vals,
    }


def get_objetivos_rebalanceo() -> Dict[str, Dict[str, float]]:
    """Define objetivos de asignación por bloque patrimonial y sectorial."""
    return {
        'patrimonial': {
            'Liquidez': 25.0,        # Objetivo: 20-30%
            'Cash Management': 7.5,  # Objetivo: 5-10%
            'Invertido': 67.5,       # Objetivo: 60-75%
        },
        'sectorial': {
            'Tecnología': 17.5,      # Objetivo: 15-20%
            'ETF core': 22.5,        # Objetivo: 20-25% (Índice, etc.)
            'Argentina': 12.5,       # Objetivo: 10-15%
            'Bonos': 12.5,           # Objetivo: 10-15% (Soberano, Corporativo)
            'Defensivos': 12.5,      # Objetivo: 10-15% (Consumo defensivo, Utilities)
            # Otros sectores se evalúan vs umbral mínimo
        }
    }


def mapear_sector_a_categoria(sector: str) -> str:
    """Mapea sectores específicos a categorías objetivo."""
    mapeo = {
        # ETF core
        'Índice': 'ETF core',
        'ETF': 'ETF core',
        # Bonos
        'Soberano': 'Bonos',
        'Corporativo': 'Bonos',
        'Título Público': 'Bonos',
        # Defensivos
        'Consumo defensivo': 'Defensivos',
        'Utilities': 'Defensivos',
        'Finanzas': 'Defensivos',
        # Argentina
        'Argentina': 'Argentina',
        # Tecnología (mantener como está)
        'Tecnología': 'Tecnología',
        'Tecnología / E-commerce': 'Tecnología',
        'Tecnología / Semiconductores': 'Tecnología',
    }
    return mapeo.get(sector, sector)


def get_senales_rebalanceo() -> Dict[str, list]:
    """Genera señales de rebalanceo basadas en objetivos definidos."""
    concentracion_patrimonial = get_concentracion_patrimonial()
    concentracion_sectorial = get_concentracion_sectorial()
    objetivos = get_objetivos_rebalanceo()

    # Umbrales para evaluación
    TOLERANCIA_SOBRE = 5.0   # +5% sobre objetivo = sobreponderado
    TOLERANCIA_SUB = 3.0     # -3% bajo objetivo = subponderado
    UMBRAL_MINIMO = 2.0      # Sectores sin objetivo: <2% = subponderado
    UMBRAL_POSICION_ALTA = 10.0  # >10% = posición alta

    # A. Rebalanceo patrimonial (vs objetivos definidos)
    patrimonial_sobreponderado = []
    patrimonial_subponderado = []

    for categoria, actual in concentracion_patrimonial.items():
        objetivo = objetivos['patrimonial'].get(categoria, actual)  # Si no hay objetivo, usar actual como baseline

        if actual > objetivo + TOLERANCIA_SOBRE:
            patrimonial_sobreponderado.append({
                'categoria': categoria,
                'porcentaje': float(actual),
                'objetivo': float(objetivo),
                'diferencia': float(actual) - float(objetivo)
            })
        elif actual < objetivo - TOLERANCIA_SUB:
            patrimonial_subponderado.append({
                'categoria': categoria,
                'porcentaje': float(actual),
                'objetivo': float(objetivo),
                'diferencia': float(objetivo) - float(actual)
            })

    # B. Rebalanceo sectorial (vs objetivos definidos o umbral mínimo)
    # Primero agrupar por categorías objetivo
    concentracion_agrupada = {}
    for sector, actual in concentracion_sectorial.items():
        categoria = mapear_sector_a_categoria(sector)
        concentracion_agrupada[categoria] = concentracion_agrupada.get(categoria, 0) + actual

    sectorial_sobreponderado = []
    sectorial_subponderado = []

    for categoria, actual in concentracion_agrupada.items():
        objetivo = objetivos['sectorial'].get(categoria)

        if objetivo is not None:
            # Categoría con objetivo definido
            if actual > objetivo + TOLERANCIA_SOBRE:
                sectorial_sobreponderado.append({
                    'sector': categoria,
                    'porcentaje': float(actual),
                    'objetivo': float(objetivo),
                    'diferencia': float(actual) - float(objetivo)
                })
            elif actual < objetivo - TOLERANCIA_SUB:
                sectorial_subponderado.append({
                    'sector': categoria,
                    'porcentaje': float(actual),
                    'objetivo': float(objetivo),
                    'diferencia': float(objetivo) - float(actual)
                })
        else:
            # Categoría sin objetivo definido: evaluar vs umbral mínimo
            if actual < UMBRAL_MINIMO:
                sectorial_subponderado.append({
                    'sector': categoria,
                    'porcentaje': actual,
                    'objetivo': None,
                    'diferencia': UMBRAL_MINIMO - actual
                })

    # Activos sin metadata (mantener igual)
    portafolio = get_latest_portafolio_data()
    simbolos = [activo.simbolo for activo in portafolio]
    parametros = {p.simbolo: p for p in ParametroActivo.objects.filter(simbolo__in=simbolos)}
    activos_sin_metadata = []
    for activo in portafolio:
        parametro = parametros.get(activo.simbolo)
        if not parametro or not all([
            parametro.sector != 'N/A',
            parametro.bloque_estrategico != 'N/A',
            parametro.pais_exposicion != 'N/A',
            parametro.tipo_patrimonial != 'N/A'
        ]):
            activos_sin_metadata.append({
                'simbolo': activo.simbolo,
                'valorizado': float(activo.valorizado)
            })

    # Posiciones con mayor peso (mantener igual)
    total_portafolio = sum(activo.valorizado for activo in portafolio)
    posiciones_altas = [
        {
            'simbolo': activo.simbolo,
            'peso': (activo.valorizado / total_portafolio * 100) if total_portafolio > 0 else 0,
            'valorizado': float(activo.valorizado)
        }
        for activo in portafolio
        if (activo.valorizado / total_portafolio * 100) > UMBRAL_POSICION_ALTA
    ]
    posiciones_altas.sort(key=lambda x: x['peso'], reverse=True)

    return {
        'patrimonial_sobreponderado': patrimonial_sobreponderado,
        'patrimonial_subponderado': patrimonial_subponderado,
        'sectorial_sobreponderado': sectorial_sobreponderado,
        'sectorial_subponderado': sectorial_subponderado,
        'activos_sin_metadata': activos_sin_metadata,
        'posiciones_mayor_peso': posiciones_altas,
    }


def get_snapshot_coverage_summary(days: int = 90) -> Dict[str, float | int | str | bool | None]:
    """Resume la cobertura reciente de snapshots para diagnosticar metricas temporales."""
    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=days)

    snapshots = list(
        PortfolioSnapshot.objects.filter(fecha__range=(start_date, end_date)).order_by("fecha")
    )

    count = len(snapshots)
    if count == 0:
        return {
            "requested_days": days,
            "snapshots_count": 0,
            "latest_snapshot_date": None,
            "history_span_days": 0,
            "missing_days_estimate": days,
            "max_gap_days": None,
            "is_sufficient_for_volatility": False,
            "status": "insufficient_history",
        }

    latest_snapshot = snapshots[-1]
    earliest_snapshot = snapshots[0]
    history_span_days = (latest_snapshot.fecha - earliest_snapshot.fecha).days if count >= 2 else 0

    max_gap_days = 0
    for prev, curr in zip(snapshots, snapshots[1:]):
        gap_days = (curr.fecha - prev.fecha).days
        if gap_days > max_gap_days:
            max_gap_days = gap_days

    missing_days_estimate = max(days - count, 0)
    is_sufficient = count >= 5 and history_span_days >= 7

    return {
        "requested_days": days,
        "snapshots_count": count,
        "latest_snapshot_date": latest_snapshot.fecha.isoformat() if latest_snapshot else None,
        "latest_snapshot_at": (
            timezone.localtime(latest_snapshot.updated_at).strftime("%Y-%m-%d %H:%M")
            if latest_snapshot and latest_snapshot.updated_at
            else None
        ),
        "history_span_days": history_span_days,
        "missing_days_estimate": missing_days_estimate,
        "max_gap_days": max_gap_days if count >= 2 else None,
        "is_sufficient_for_volatility": is_sufficient,
        "status": "ok" if is_sufficient else "insufficient_history",
    }


def get_active_alerts() -> list:
    """Obtiene todas las alertas activas ordenadas por severidad y fecha."""
    from django.db.models import Case, When, IntegerField

    # Ordenar por severidad (critical > warning > info) y luego por fecha
    severity_order = Case(
        When(severidad='critical', then=3),
        When(severidad='warning', then=2),
        When(severidad='info', then=1),
        default=0,
        output_field=IntegerField(),
    )

    alerts = Alert.objects.filter(is_active=True).order_by(
        -severity_order, '-created_at'
    )

    return list(alerts.values(
        'id', 'tipo', 'mensaje', 'severidad', 'valor',
        'simbolo', 'sector', 'pais', 'created_at', 'is_acknowledged'
    ))


def _get_active_risk_contribution_result() -> Dict:
    base_risk_service = RiskContributionService()
    covariance_risk_service = CovarianceAwareRiskContributionService(base_service=base_risk_service)
    base_risk_result = base_risk_service.calculate()
    covariance_risk_result = covariance_risk_service.calculate()
    active_result = (
        covariance_risk_result
        if covariance_risk_result.get("model_variant") == "covariance_aware"
        else base_risk_result
    )
    return {
        "base_result": base_risk_result,
        "covariance_result": covariance_risk_result,
        "active_result": active_result,
    }


def get_risk_contribution_detail() -> Dict:
    """Devuelve el drill-down completo del modelo de risk contribution activo."""

    def build():
        resolved = _get_active_risk_contribution_result()
        result = resolved["active_result"]
        covariance_result = resolved["covariance_result"]
        by_sector = [
            {
                "rank": index,
                "key": item.get("key"),
                "weight_pct": item.get("weight_pct"),
                "contribution_pct": item.get("contribution_pct"),
                "risk_vs_weight_delta": round(
                    float(item.get("contribution_pct") or 0.0) - float(item.get("weight_pct") or 0.0),
                    2,
                ),
            }
            for index, item in enumerate(result.get("by_sector", []), start=1)
        ]
        by_country = [
            {
                "rank": index,
                "key": item.get("key"),
                "weight_pct": item.get("weight_pct"),
                "contribution_pct": item.get("contribution_pct"),
                "risk_vs_weight_delta": round(
                    float(item.get("contribution_pct") or 0.0) - float(item.get("weight_pct") or 0.0),
                    2,
                ),
            }
            for index, item in enumerate(result.get("by_country", []), start=1)
        ]

        items = [
            {
                "rank": index,
                "symbol": item.get("symbol"),
                "sector": item.get("sector"),
                "country": item.get("country"),
                "asset_type": item.get("asset_type"),
                "weight_pct": item.get("weight_pct"),
                "volatility_proxy": item.get("volatility_proxy"),
                "risk_score": item.get("risk_score"),
                "contribution_pct": item.get("contribution_pct"),
                "risk_vs_weight_delta": round(
                    float(item.get("contribution_pct") or 0.0) - float(item.get("weight_pct") or 0.0),
                    2,
                ),
                "used_volatility_fallback": item.get("used_volatility_fallback", False),
            }
            for index, item in enumerate(result.get("items", []), start=1)
        ]

        metadata = result.get("metadata", {})
        top_asset = result.get("top_contributors", [{}])[0] if result.get("top_contributors") else None
        top_sector = result.get("by_sector", [{}])[0] if result.get("by_sector") else None

        return {
            "items": items,
            "by_sector": by_sector,
            "by_country": by_country,
            "top_asset": top_asset,
            "top_sector": top_sector,
            "model_variant": covariance_result.get("model_variant", "mvp_proxy"),
            "covariance_observations": int(covariance_result.get("covariance_observations") or 0),
            "coverage_pct": float(covariance_result.get("coverage_pct") or 0.0),
            "portfolio_volatility_proxy": covariance_result.get("portfolio_volatility_proxy"),
            "confidence": metadata.get("confidence", "low"),
            "warnings": metadata.get("warnings", []),
            "methodology": metadata.get("methodology"),
            "limitations": metadata.get("limitations"),
            "covered_symbols": covariance_result.get("covered_symbols", []),
            "excluded_symbols": covariance_result.get("excluded_symbols", []),
        }

    return _get_cached_selector_result("risk_contribution_detail", build)


def get_scenario_analysis_detail() -> Dict:
    """Devuelve el drill-down analítico completo de scenario analysis."""

    def build():
        scenario_service = ScenarioAnalysisService()
        catalog_service = ScenarioCatalogService()
        scenario_rows = []

        for scenario in catalog_service.list_scenarios():
            result = scenario_service.analyze(scenario["scenario_key"])
            top_sector = result.get("by_sector", [{}])[0] if result.get("by_sector") else None
            top_country = result.get("by_country", [{}])[0] if result.get("by_country") else None
            scenario_rows.append(
                {
                    "scenario_key": scenario["scenario_key"],
                    "label": scenario.get("label"),
                    "description": scenario.get("description"),
                    "category": scenario.get("category"),
                    "total_impact_pct": float(result.get("total_impact_pct") or 0.0),
                    "total_impact_money": float(result.get("total_impact_money") or 0.0),
                    "top_sector": top_sector,
                    "top_country": top_country,
                    "by_asset": result.get("by_asset", []),
                    "by_sector": result.get("by_sector", []),
                    "by_country": result.get("by_country", []),
                    "top_negative_contributors": result.get("top_negative_contributors", []),
                    "metadata": result.get("metadata", {}),
                }
            )

        sorted_rows = sorted(
            scenario_rows,
            key=lambda item: float(item.get("total_impact_pct") or 0.0),
        )
        ranked_rows = [
            {
                **item,
                "severity_rank": index,
            }
            for index, item in enumerate(sorted_rows, start=1)
        ]
        worst_scenario = ranked_rows[0] if ranked_rows else None

        worst_assets = []
        worst_sectors = []
        worst_countries = []
        if worst_scenario:
            worst_assets = [
                {
                    "rank": index,
                    "symbol": item.get("symbol"),
                    "market_value": item.get("market_value"),
                    "estimated_impact_pct": item.get("estimated_impact_pct"),
                    "estimated_impact_money": item.get("estimated_impact_money"),
                    "transmission_channel": item.get("transmission_channel"),
                }
                for index, item in enumerate(worst_scenario.get("by_asset", []), start=1)
            ]
            worst_sectors = [
                {
                    "rank": index,
                    "key": item.get("key"),
                    "impact_pct": item.get("impact_pct"),
                    "impact_money": item.get("impact_money"),
                }
                for index, item in enumerate(worst_scenario.get("by_sector", []), start=1)
            ]
            worst_countries = [
                {
                    "rank": index,
                    "key": item.get("key"),
                    "impact_pct": item.get("impact_pct"),
                    "impact_money": item.get("impact_money"),
                }
                for index, item in enumerate(worst_scenario.get("by_country", []), start=1)
            ]

        return {
            "scenarios": ranked_rows,
            "worst_scenario": worst_scenario,
            "worst_assets": worst_assets,
            "worst_sectors": worst_sectors,
            "worst_countries": worst_countries,
            "confidence": (worst_scenario or {}).get("metadata", {}).get("confidence", "low"),
            "warnings": (worst_scenario or {}).get("metadata", {}).get("warnings", []),
            "methodology": (worst_scenario or {}).get("metadata", {}).get("methodology"),
            "limitations": (worst_scenario or {}).get("metadata", {}).get("limitations"),
        }

    return _get_cached_selector_result("scenario_analysis_detail", build)


def get_factor_exposure_detail() -> Dict:
    """Devuelve el drill-down analitico completo de factor exposure."""

    def build():
        factor_service = FactorExposureService()
        explanation_service = AnalyticsExplanationService()
        result = factor_service.calculate()

        factor_rows = [
            {
                "rank": index,
                "factor": item.get("factor"),
                "exposure_pct": float(item.get("exposure_pct") or 0.0),
                "contribution_relative_pct": float(item.get("exposure_pct") or 0.0),
                "confidence": item.get("confidence", "low"),
            }
            for index, item in enumerate(
                sorted(
                    result.get("factors", []),
                    key=lambda entry: float(entry.get("exposure_pct") or 0.0),
                    reverse=True,
                ),
                start=1,
            )
        ]
        dominant_factor_key = result.get("dominant_factor")
        dominant_factor = next(
            (item for item in factor_rows if item.get("factor") == dominant_factor_key),
            None,
        )
        unknown_assets = [
            {
                "rank": index,
                "symbol": symbol,
            }
            for index, symbol in enumerate(result.get("unknown_assets", []), start=1)
        ]
        metadata = result.get("metadata", {})

        return {
            "factors": factor_rows,
            "dominant_factor": dominant_factor,
            "dominant_factor_key": dominant_factor_key,
            "underrepresented_factors": result.get("underrepresented_factors", []),
            "unknown_assets": unknown_assets,
            "unknown_assets_count": len(unknown_assets),
            "confidence": metadata.get("confidence", "low"),
            "warnings": metadata.get("warnings", []),
            "methodology": metadata.get("methodology"),
            "limitations": metadata.get("limitations"),
            "interpretation": explanation_service.build_factor_exposure_explanation(result),
        }

    return _get_cached_selector_result("factor_exposure_detail", build)


def get_stress_fragility_detail() -> Dict:
    """Devuelve el drill-down analitico completo de stress fragility."""

    def build():
        stress_service = StressFragilityService()
        stress_catalog_service = StressCatalogService()
        explanation_service = AnalyticsExplanationService()

        stress_rows = []
        for stress in stress_catalog_service.list_stresses():
            result = stress_service.calculate(stress["stress_key"])
            top_sector = result.get("vulnerable_sectors", [{}])[0] if result.get("vulnerable_sectors") else None
            top_country = result.get("vulnerable_countries", [{}])[0] if result.get("vulnerable_countries") else None
            stress_rows.append(
                {
                    "stress_key": stress["stress_key"],
                    "scenario_key": result.get("scenario_key", stress["stress_key"]),
                    "label": stress.get("label"),
                    "description": stress.get("description"),
                    "fragility_score": float(result.get("fragility_score") or 0.0),
                    "total_loss_pct": float(result.get("total_loss_pct") or 0.0),
                    "total_loss_money": float(result.get("total_loss_money") or 0.0),
                    "top_sector": top_sector,
                    "top_country": top_country,
                    "vulnerable_assets": result.get("vulnerable_assets", []),
                    "vulnerable_sectors": result.get("vulnerable_sectors", []),
                    "vulnerable_countries": result.get("vulnerable_countries", []),
                    "metadata": result.get("metadata", {}),
                }
            )

        sorted_rows = sorted(
            stress_rows,
            key=lambda item: float(item.get("total_loss_pct") or 0.0),
        )
        ranked_rows = [
            {
                **item,
                "severity_rank": index,
            }
            for index, item in enumerate(sorted_rows, start=1)
        ]
        worst_stress = ranked_rows[0] if ranked_rows else None

        worst_assets = []
        worst_sectors = []
        worst_countries = []
        if worst_stress:
            worst_assets = [
                {
                    "rank": index,
                    "symbol": item.get("symbol"),
                    "market_value": item.get("market_value"),
                    "estimated_impact_pct": item.get("estimated_impact_pct"),
                    "estimated_impact_money": item.get("estimated_impact_money"),
                    "transmission_channel": item.get("transmission_channel"),
                }
                for index, item in enumerate(worst_stress.get("vulnerable_assets", []), start=1)
            ]
            worst_sectors = [
                {
                    "rank": index,
                    "key": item.get("key"),
                    "impact_pct": item.get("impact_pct"),
                    "impact_money": item.get("impact_money"),
                }
                for index, item in enumerate(worst_stress.get("vulnerable_sectors", []), start=1)
            ]
            worst_countries = [
                {
                    "rank": index,
                    "key": item.get("key"),
                    "impact_pct": item.get("impact_pct"),
                    "impact_money": item.get("impact_money"),
                }
                for index, item in enumerate(worst_stress.get("vulnerable_countries", []), start=1)
            ]

        return {
            "stresses": ranked_rows,
            "worst_stress": worst_stress,
            "worst_assets": worst_assets,
            "worst_sectors": worst_sectors,
            "worst_countries": worst_countries,
            "confidence": (worst_stress or {}).get("metadata", {}).get("confidence", "low"),
            "warnings": (worst_stress or {}).get("metadata", {}).get("warnings", []),
            "methodology": (worst_stress or {}).get("metadata", {}).get("methodology"),
            "limitations": (worst_stress or {}).get("metadata", {}).get("limitations"),
            "interpretation": explanation_service.build_stress_fragility_explanation(worst_stress or {}),
        }

    return _get_cached_selector_result("stress_fragility_detail", build)


def get_expected_return_detail() -> Dict:
    """Devuelve el drill-down analitico completo de expected return."""

    def build():
        expected_return_service = ExpectedReturnService()
        explanation_service = AnalyticsExplanationService()
        result = expected_return_service.calculate()

        bucket_rows = [
            {
                "rank": index,
                "bucket_key": item.get("bucket_key"),
                "label": item.get("label"),
                "weight_pct": item.get("weight_pct"),
                "expected_return_pct": item.get("expected_return_pct"),
                "real_expected_return_pct": None,
                "contribution_relative_pct": (
                    round(
                        (float(item.get("weight_pct") or 0.0) / 100.0)
                        * float(item.get("expected_return_pct") or 0.0),
                        2,
                    )
                    if item.get("expected_return_pct") is not None
                    else None
                ),
                "basis_reference": item.get("basis_reference"),
            }
            for index, item in enumerate(
                sorted(
                    result.get("by_bucket", []),
                    key=lambda entry: float(entry.get("weight_pct") or 0.0),
                    reverse=True,
                ),
                start=1,
            )
        ]

        dominant_bucket = bucket_rows[0] if bucket_rows else None
        metadata = result.get("metadata", {})
        warnings = metadata.get("warnings", [])

        return {
            "expected_return_pct": result.get("expected_return_pct"),
            "real_expected_return_pct": result.get("real_expected_return_pct"),
            "basis_reference": result.get("basis_reference"),
            "dominant_bucket": dominant_bucket,
            "bucket_rows": bucket_rows,
            "asset_rows": [],
            "confidence": metadata.get("confidence", "low"),
            "warnings": warnings,
            "main_warning": warnings[0] if warnings else None,
            "methodology": metadata.get("methodology"),
            "limitations": metadata.get("limitations"),
            "assumptions": [
                "El modelo agrupa posiciones actuales en buckets estructurales.",
                "Las referencias usan SPY, EMB o BADLAR con fallbacks explícitos cuando falta historia suficiente.",
                "El retorno real depende de una referencia de inflación disponible al momento del cálculo.",
            ],
            "interpretation": explanation_service.build_expected_return_explanation(result),
        }

    return _get_cached_selector_result("expected_return_detail", build)


def get_monthly_allocation_plan(capital_amount: int | float = 600000) -> Dict:
    """Devuelve la propuesta mvp de asignacion mensual incremental."""

    cache_key = f"monthly_allocation_plan:{int(capital_amount)}"

    def build():
        service = MonthlyAllocationService()
        return service.build_plan(capital_amount)

    return _get_cached_selector_result(cache_key, build)


def get_candidate_asset_ranking(capital_amount: int | float = 600000) -> Dict:
    """Devuelve el ranking de activos candidatos dentro de los bloques recomendados."""

    cache_key = f"candidate_asset_ranking:{int(capital_amount)}"

    def build():
        service = CandidateAssetRankingService()
        return service.build_ranking(capital_amount)

    return _get_cached_selector_result(cache_key, build)


def get_incremental_portfolio_simulation(capital_amount: int | float = 600000) -> Dict:
    """Construye una simulacion incremental default usando top candidato por bloque recomendado."""

    cache_key = f"incremental_portfolio_simulation:{int(capital_amount)}"

    def build():
        monthly_plan = get_monthly_allocation_plan(capital_amount=capital_amount)
        candidate_ranking = get_candidate_asset_ranking(capital_amount=capital_amount)
        proposal = _build_top_candidate_purchase_plan(monthly_plan, candidate_ranking)
        if not proposal["purchase_plan"]:
            return {
                "capital_amount": float(capital_amount),
                "purchase_plan": [],
                "selected_candidates": [],
                "unmapped_blocks": proposal["unmapped_blocks"],
                "before": {},
                "after": {},
                "delta": {
                    "expected_return_change": None,
                    "real_expected_return_change": None,
                    "fragility_change": None,
                    "scenario_loss_change": None,
                    "risk_concentration_change": None,
                },
                "interpretation": "No hay candidatos suficientes para simular una propuesta incremental por defecto.",
                "warnings": ["no_candidate_purchase_plan"],
            }

        result = IncrementalPortfolioSimulator().simulate(
            {
                "capital_amount": capital_amount,
                "purchase_plan": proposal["purchase_plan"],
            }
        )
        result["selected_candidates"] = proposal["selected_candidates"]
        result["unmapped_blocks"] = proposal["unmapped_blocks"]
        result["selection_basis"] = "top_candidate_per_recommended_block"
        return result

    return _get_cached_selector_result(cache_key, build)


def get_incremental_portfolio_simulation_comparison(capital_amount: int | float = 600000) -> Dict:
    """Compara variantes simples de propuestas incrementales sobre el mismo capital mensual."""

    cache_key = f"incremental_portfolio_simulation_comparison:{int(capital_amount)}"

    def build():
        monthly_plan = get_monthly_allocation_plan(capital_amount=capital_amount)
        candidate_ranking = get_candidate_asset_ranking(capital_amount=capital_amount)
        simulator = IncrementalPortfolioSimulator()

        proposals = []
        for proposal_key, label, builder in (
            ("top_candidate_per_block", "Top candidato por bloque", _build_top_candidate_purchase_plan),
            ("runner_up_when_available", "Segundo candidato si existe", _build_runner_up_purchase_plan),
            ("split_largest_block_top_two", "Split del bloque más grande", _build_split_largest_block_purchase_plan),
        ):
            proposal = builder(monthly_plan, candidate_ranking)
            if not proposal["purchase_plan"]:
                proposals.append(
                    _normalize_incremental_proposal_item(
                        {
                            "proposal_key": proposal_key,
                            "label": label,
                            "purchase_plan": [],
                            "selected_candidates": [],
                            "unmapped_blocks": proposal["unmapped_blocks"],
                            "simulation": {
                                "before": {},
                                "after": {},
                                "delta": {
                                    "expected_return_change": None,
                                    "real_expected_return_change": None,
                                    "fragility_change": None,
                                    "scenario_loss_change": None,
                                    "risk_concentration_change": None,
                                },
                                "interpretation": "No hay candidatos suficientes para construir esta variante.",
                            },
                            "comparison_score": None,
                        }
                    )
                )
                continue

            simulation = simulator.simulate(
                {
                    "capital_amount": capital_amount,
                    "purchase_plan": proposal["purchase_plan"],
                }
            )
            proposals.append(
                _normalize_incremental_proposal_item(
                    {
                        "proposal_key": proposal_key,
                        "label": label,
                        "purchase_plan": proposal["purchase_plan"],
                        "selected_candidates": proposal["selected_candidates"],
                        "unmapped_blocks": proposal["unmapped_blocks"],
                        "simulation": {
                            "before": simulation["before"],
                            "after": simulation["after"],
                            "delta": simulation["delta"],
                            "interpretation": simulation["interpretation"],
                        },
                        "comparison_score": _score_incremental_simulation(simulation),
                    }
                )
            )

        ranked = sorted(
            proposals,
            key=lambda item: float("-inf") if item["comparison_score"] is None else float(item["comparison_score"]),
            reverse=True,
        )
        best = next((item for item in ranked if item["comparison_score"] is not None), None)
        return {
            "capital_amount": float(capital_amount),
            "proposals": ranked,
            "best_proposal_key": best["proposal_key"] if best else None,
            "best_label": best["label"] if best else None,
        }

    return _get_cached_selector_result(cache_key, build)


def get_manual_incremental_portfolio_simulation_comparison(
    query_params,
    *,
    default_capital_amount: int | float = 600000,
) -> Dict:
    """Compara planes incrementales definidos manualmente desde Planeacion."""

    form_state = _build_manual_incremental_comparison_form_state(
        query_params,
        default_capital_amount=default_capital_amount,
    )
    normalized_plans = form_state["normalized_plans"]
    if not normalized_plans:
        return {
            "submitted": form_state["submitted"],
            "form_state": form_state,
            "proposals": [],
            "best_proposal_key": None,
            "best_label": None,
        }

    signature = hashlib.md5(
        json.dumps(
            [
                {
                    "proposal_key": plan["proposal_key"],
                    "capital_amount": plan["capital_amount"],
                    "purchase_plan": plan["purchase_plan"],
                }
                for plan in normalized_plans
            ],
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
    cache_key = f"manual_incremental_portfolio_simulation_comparison:{signature}"

    def build():
        simulator = IncrementalPortfolioSimulator()
        proposals = []
        for plan in normalized_plans:
            simulation = simulator.simulate(
                {
                    "capital_amount": plan["capital_amount"],
                    "purchase_plan": plan["purchase_plan"],
                }
            )
            proposals.append(
                _normalize_incremental_proposal_item(
                    {
                        "proposal_key": plan["proposal_key"],
                        "label": plan["label"],
                        "purchase_plan": plan["purchase_plan"],
                        "capital_amount": plan["capital_amount"],
                        "input_warnings": plan["warnings"],
                        "simulation": {
                            "before": simulation["before"],
                            "after": simulation["after"],
                            "delta": simulation["delta"],
                            "interpretation": simulation["interpretation"],
                            "warnings": simulation.get("warnings", []),
                        },
                        "comparison_score": _score_incremental_simulation(simulation),
                    }
                )
            )

        ranked = sorted(
            proposals,
            key=lambda item: float("-inf") if item["comparison_score"] is None else float(item["comparison_score"]),
            reverse=True,
        )
        best = next((item for item in ranked if item["comparison_score"] is not None), None)
        return {
            "submitted": form_state["submitted"],
            "form_state": form_state,
            "proposals": ranked,
            "best_proposal_key": best["proposal_key"] if best else None,
            "best_label": best["label"] if best else None,
        }

    return _get_cached_selector_result(cache_key, build)


def get_candidate_incremental_portfolio_comparison(
    query_params,
    *,
    capital_amount: int | float = 600000,
) -> Dict:
    """Compara candidatos individuales dentro de un bloque recomendado."""

    monthly_plan = get_monthly_allocation_plan(capital_amount=capital_amount)
    candidate_ranking = get_candidate_asset_ranking(capital_amount=capital_amount)
    comparable_blocks = _build_comparable_candidate_blocks(monthly_plan, candidate_ranking)
    requested_block = str(_query_param_value(query_params, "candidate_compare_block", "")).strip()
    submitted = str(_query_param_value(query_params, "candidate_compare", "")).strip() == "1"

    selected_block = requested_block if requested_block in {item["bucket"] for item in comparable_blocks} else None
    if selected_block is None and comparable_blocks:
        selected_block = comparable_blocks[0]["bucket"]

    if selected_block is None:
        return {
            "submitted": submitted,
            "available_blocks": comparable_blocks,
            "selected_block": None,
            "selected_label": None,
            "block_amount": None,
            "proposals": [],
            "best_proposal_key": None,
            "best_label": None,
        }

    selected_block_data = next(item for item in comparable_blocks if item["bucket"] == selected_block)
    signature = hashlib.md5(
        json.dumps(
            {
                "selected_block": selected_block,
                "block_amount": selected_block_data["suggested_amount"],
                "candidates": selected_block_data["candidates"],
            },
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
    cache_key = f"candidate_incremental_portfolio_comparison:{signature}"

    def build():
        simulator = IncrementalPortfolioSimulator()
        proposals = []
        for candidate in selected_block_data["candidates"][:3]:
            purchase_plan = [
                {
                    "symbol": candidate["asset"],
                    "amount": round(float(selected_block_data["suggested_amount"]), 2),
                }
            ]
            simulation = simulator.simulate(
                {
                    "capital_amount": float(selected_block_data["suggested_amount"]),
                    "purchase_plan": purchase_plan,
                }
            )
            proposals.append(
                _normalize_incremental_proposal_item(
                    {
                        "proposal_key": candidate["asset"],
                        "label": candidate["asset"],
                        "candidate": candidate,
                        "purchase_plan": purchase_plan,
                        "simulation": {
                            "before": simulation["before"],
                            "after": simulation["after"],
                            "delta": simulation["delta"],
                            "interpretation": simulation["interpretation"],
                            "warnings": simulation.get("warnings", []),
                        },
                        "comparison_score": _score_incremental_simulation(simulation),
                    }
                )
            )

        ranked = sorted(
            proposals,
            key=lambda item: float("-inf") if item["comparison_score"] is None else float(item["comparison_score"]),
            reverse=True,
        )
        best = next((item for item in ranked if item["comparison_score"] is not None), None)
        return {
            "submitted": submitted,
            "available_blocks": comparable_blocks,
            "selected_block": selected_block,
            "selected_label": selected_block_data["label"],
            "block_amount": selected_block_data["suggested_amount"],
            "proposals": ranked,
            "best_proposal_key": best["proposal_key"] if best else None,
            "best_label": best["label"] if best else None,
        }

    return _get_cached_selector_result(cache_key, build)


def get_candidate_split_incremental_portfolio_comparison(
    query_params,
    *,
    capital_amount: int | float = 600000,
) -> Dict:
    """Compara concentrar el bloque en un candidato vs repartirlo entre top 2."""

    monthly_plan = get_monthly_allocation_plan(capital_amount=capital_amount)
    candidate_ranking = get_candidate_asset_ranking(capital_amount=capital_amount)
    comparable_blocks = _build_comparable_candidate_blocks(monthly_plan, candidate_ranking)
    split_blocks = [block for block in comparable_blocks if len(block["candidates"]) >= 2]
    requested_block = str(_query_param_value(query_params, "candidate_split_block", "")).strip()
    submitted = str(_query_param_value(query_params, "candidate_split_compare", "")).strip() == "1"

    selected_block = requested_block if requested_block in {item["bucket"] for item in split_blocks} else None
    if selected_block is None and split_blocks:
        selected_block = split_blocks[0]["bucket"]

    if selected_block is None:
        return {
            "submitted": submitted,
            "available_blocks": split_blocks,
            "selected_block": None,
            "selected_label": None,
            "block_amount": None,
            "proposals": [],
            "best_proposal_key": None,
            "best_label": None,
        }

    selected_block_data = next(item for item in split_blocks if item["bucket"] == selected_block)
    signature = hashlib.md5(
        json.dumps(
            {
                "selected_block": selected_block,
                "block_amount": selected_block_data["suggested_amount"],
                "candidates": selected_block_data["candidates"][:2],
            },
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
    cache_key = f"candidate_split_incremental_portfolio_comparison:{signature}"

    def build():
        simulator = IncrementalPortfolioSimulator()
        top_candidate = selected_block_data["candidates"][0]
        runner_up = selected_block_data["candidates"][1]
        total_amount = round(float(selected_block_data["suggested_amount"]), 2)
        half_amount = round(total_amount / 2.0, 2)
        remainder_amount = round(total_amount - half_amount, 2)

        variants = [
            {
                "proposal_key": "single_top_candidate",
                "label": f"Concentrado en {top_candidate['asset']}",
                "purchase_plan": [{"symbol": top_candidate["asset"], "amount": total_amount}],
                "composition": [top_candidate["asset"]],
            },
            {
                "proposal_key": "split_top_two",
                "label": f"Split {top_candidate['asset']} + {runner_up['asset']}",
                "purchase_plan": [
                    {"symbol": top_candidate["asset"], "amount": half_amount},
                    {"symbol": runner_up["asset"], "amount": remainder_amount},
                ],
                "composition": [top_candidate["asset"], runner_up["asset"]],
            },
        ]

        proposals = []
        for variant in variants:
            simulation = simulator.simulate(
                {
                    "capital_amount": total_amount,
                    "purchase_plan": variant["purchase_plan"],
                }
            )
            proposals.append(
                _normalize_incremental_proposal_item(
                    {
                        "proposal_key": variant["proposal_key"],
                        "label": variant["label"],
                        "purchase_plan": variant["purchase_plan"],
                        "composition": variant["composition"],
                        "simulation": {
                            "before": simulation["before"],
                            "after": simulation["after"],
                            "delta": simulation["delta"],
                            "interpretation": simulation["interpretation"],
                            "warnings": simulation.get("warnings", []),
                        },
                        "comparison_score": _score_incremental_simulation(simulation),
                    }
                )
            )

        ranked = sorted(
            proposals,
            key=lambda item: float("-inf") if item["comparison_score"] is None else float(item["comparison_score"]),
            reverse=True,
        )
        best = next((item for item in ranked if item["comparison_score"] is not None), None)
        return {
            "submitted": submitted,
            "available_blocks": split_blocks,
            "selected_block": selected_block,
            "selected_label": selected_block_data["label"],
            "block_amount": total_amount,
            "proposals": ranked,
            "best_proposal_key": best["proposal_key"] if best else None,
            "best_label": best["label"] if best else None,
        }

    return _get_cached_selector_result(cache_key, build)


def get_preferred_incremental_portfolio_proposal(
    query_params,
    *,
    capital_amount: int | float = 600000,
) -> Dict:
    """Sintetiza la mejor propuesta incremental disponible entre los comparadores activos."""

    auto = get_incremental_portfolio_simulation_comparison(capital_amount=capital_amount)
    candidate = get_candidate_incremental_portfolio_comparison(query_params, capital_amount=capital_amount)
    split = get_candidate_split_incremental_portfolio_comparison(query_params, capital_amount=capital_amount)
    manual = get_manual_incremental_portfolio_simulation_comparison(
        query_params,
        default_capital_amount=capital_amount,
    )

    candidates = []
    for source_key, label, payload in (
        ("automatic_variants", "Comparador automático", auto),
        ("candidate_block", "Comparador por candidato", candidate),
        ("candidate_split", "Comparador por split", split),
        ("manual_plan", "Comparador manual", manual),
    ):
        best_item = _extract_best_incremental_proposal(payload)
        if best_item is None:
            continue
        candidates.append(
            _normalize_incremental_proposal_item(
                {
                    "source_key": source_key,
                    "source_label": label,
                    "proposal_key": best_item["proposal_key"],
                    "proposal_label": best_item.get("proposal_label") or best_item.get("label"),
                    "purchase_plan": best_item.get("purchase_plan", []),
                    "comparison_score": best_item.get("comparison_score"),
                    "simulation": best_item.get("simulation", {}),
                    "selected_context": _build_preferred_proposal_context(source_key, payload),
                    "priority_rank": _preferred_source_priority_rank(source_key, payload),
                }
            )
        )

    best = None
    if candidates:
        best = sorted(
            candidates,
            key=lambda item: (
                float(item["comparison_score"] if item["comparison_score"] is not None else float("-inf")),
                item["priority_rank"],
            ),
            reverse=True,
        )[0]

    return {
        "candidates": candidates,
        "preferred": best,
        "has_manual_override": bool(manual.get("submitted") and manual.get("proposals")),
        "explanation": _build_preferred_incremental_explanation(best, manual),
    }


def get_incremental_proposal_history(
    *,
    user,
    limit: int = 5,
    decision_status: str | None = None,
    priority_filter: str | None = None,
    deferred_fit_filter: str | None = None,
    future_purchase_source_filter: str | None = None,
    sort_mode: str | None = None,
    preferred_source: str | None = None,
    reactivated_snapshot_ids: list[int] | set[int] | tuple[int, ...] | None = None,
) -> Dict:
    """Retorna historial reciente de propuestas incrementales guardadas por el usuario."""

    service = IncrementalProposalHistoryService()
    normalized_filter = _normalize_incremental_history_decision_filter(decision_status)
    normalized_priority_filter = _normalize_incremental_history_priority_filter(priority_filter)
    normalized_deferred_fit_filter = _normalize_incremental_history_deferred_fit_filter(deferred_fit_filter)
    normalized_future_purchase_source_filter = _normalize_incremental_future_purchase_source_filter(
        future_purchase_source_filter
    )
    normalized_sort_mode = _normalize_incremental_history_sort_mode(sort_mode)
    fetch_limit = max(int(limit), getattr(service, "MAX_SNAPSHOTS_PER_USER", 10))
    raw_items = service.list_recent(user=user, limit=fetch_limit, decision_status=normalized_filter)
    counts = service.get_decision_counts(user=user)
    baseline_payload = get_incremental_proposal_tracking_baseline(user=user)
    baseline_item = baseline_payload.get("item")
    normalized_reactivated_snapshot_ids = {
        int(snapshot_id)
        for snapshot_id in list(reactivated_snapshot_ids or [])
        if str(snapshot_id).strip()
    }
    items = []
    for item in raw_items:
        reapply = _build_incremental_snapshot_reapply_payload(item)
        enriched = service.normalize_serialized_snapshot(item)
        enriched["manual_decision_status_label"] = _format_incremental_manual_decision_status(
            str(item.get("manual_decision_status") or "pending")
        )
        enriched["is_backlog_front_label"] = "Al frente del backlog" if item.get("is_backlog_front") else ""
        enriched["tactical_trace"] = _build_incremental_tactical_trace(item)
        enriched["baseline_trace"] = _build_incremental_history_baseline_trace(
            baseline_item,
            item,
            tactical_trace=enriched["tactical_trace"],
        )
        enriched["history_priority"] = _build_incremental_history_priority(
            baseline_item,
            item,
            tactical_trace=enriched["tactical_trace"],
        )
        enriched["deferred_fit"] = _build_incremental_history_deferred_fit(enriched)
        enriched["future_purchase_context"] = _build_incremental_future_purchase_history_context(
            enriched,
            reactivated_snapshot_ids=normalized_reactivated_snapshot_ids,
        )
        enriched.update(reapply)
        items.append(enriched)

    priority_counts = _build_incremental_history_priority_counts(items)
    deferred_fit_counts = _build_incremental_history_deferred_fit_counts(items)
    future_purchase_source_counts = _build_incremental_future_purchase_source_counts(items)
    if normalized_priority_filter:
        items = [
            item for item in items
            if str((item.get("history_priority") or {}).get("priority") or "") == normalized_priority_filter
        ]
    if normalized_deferred_fit_filter:
        items = [
            item for item in items
            if str((item.get("deferred_fit") or {}).get("status") or "") == normalized_deferred_fit_filter
        ]
    if normalized_future_purchase_source_filter:
        items = [
            item for item in items
            if str((item.get("future_purchase_context") or {}).get("source") or "") == normalized_future_purchase_source_filter
        ]

    items = _sort_incremental_history_items(
        items,
        sort_mode=normalized_sort_mode,
        preferred_source=preferred_source,
    )
    items = items[: max(int(limit), 0)]
    future_purchase_source_summary = _build_incremental_future_purchase_source_summary(
        future_purchase_source_counts,
        active_filter=normalized_future_purchase_source_filter,
    )
    future_purchase_source_quality_summary = _build_incremental_future_purchase_source_quality_summary(items)

    return {
        "items": items,
        "count": len(items),
        "has_history": bool(items),
        "active_filter": normalized_filter or "all",
        "active_filter_label": _format_incremental_history_decision_filter_label(normalized_filter),
        "active_priority_filter": normalized_priority_filter or "all",
        "active_priority_filter_label": _format_incremental_history_priority_filter_label(normalized_priority_filter),
        "active_deferred_fit_filter": normalized_deferred_fit_filter or "all",
        "active_deferred_fit_filter_label": _format_incremental_history_deferred_fit_filter_label(
            normalized_deferred_fit_filter
        ),
        "active_future_purchase_source_filter": normalized_future_purchase_source_filter or "all",
        "active_future_purchase_source_filter_label": _format_incremental_future_purchase_source_filter_label(
            normalized_future_purchase_source_filter
        ),
        "active_sort_mode": normalized_sort_mode,
        "active_sort_mode_label": _format_incremental_history_sort_mode_label(normalized_sort_mode),
        "decision_counts": counts,
        "available_filters": _build_incremental_history_available_filters(normalized_filter, counts),
        "available_priority_filters": _build_incremental_history_priority_filter_options(
            normalized_priority_filter,
            priority_counts,
        ),
        "available_deferred_fit_filters": _build_incremental_history_deferred_fit_filter_options(
            normalized_deferred_fit_filter,
            deferred_fit_counts,
        ),
        "available_future_purchase_source_filters": _build_incremental_future_purchase_source_filter_options(
            normalized_future_purchase_source_filter,
            future_purchase_source_counts,
        ),
        "available_sort_modes": _build_incremental_history_sort_options(normalized_sort_mode),
        "priority_counts": priority_counts,
        "deferred_fit_counts": deferred_fit_counts,
        "future_purchase_source_counts": future_purchase_source_counts,
        "future_purchase_source_summary": future_purchase_source_summary,
        "future_purchase_source_quality_summary": future_purchase_source_quality_summary,
        "headline": _build_incremental_history_headline(
            normalized_filter,
            counts,
            len(items),
            priority_filter=normalized_priority_filter,
            deferred_fit_filter=normalized_deferred_fit_filter,
            future_purchase_source_filter=normalized_future_purchase_source_filter,
            sort_mode=normalized_sort_mode,
        ),
    }


def _build_incremental_tactical_trace(item: Dict | None) -> Dict:
    explanation_items = [str(bullet).strip() for bullet in list((item or {}).get("decision_explanation") or []) if str(bullet).strip()]
    badges = []

    if any("parking" in bullet.lower() for bullet in explanation_items):
        badges.append({"key": "parking", "label": "Parking", "tone": "warning"})
    if any("liquidez reciente" in bullet.lower() for bullet in explanation_items):
        badges.append({"key": "market_history", "label": "Liquidez reciente", "tone": "info"})
    if any("reemplazada por una alternativa" in bullet.lower() for bullet in explanation_items):
        badges.append({"key": "alternative_promoted", "label": "Alternativa promovida", "tone": "primary"})
    if any("repriorizada" in bullet.lower() for bullet in explanation_items):
        badges.append({"key": "reprioritized", "label": "Repriorizada", "tone": "secondary"})
    if any("condicionada" in bullet.lower() for bullet in explanation_items):
        badges.append({"key": "conditioned", "label": "Condicionada", "tone": "secondary"})

    if any(badge["key"] == "market_history" for badge in badges) and any(
        badge["key"] == "alternative_promoted" for badge in badges
    ):
        headline = "Se promovio una alternativa mas limpia por liquidez reciente."
    elif any(badge["key"] == "parking" for badge in badges) and any(
        badge["key"] == "alternative_promoted" for badge in badges
    ):
        headline = "Se promovio una alternativa mas limpia por parking visible."
    elif any(badge["key"] == "market_history" for badge in badges):
        headline = "La propuesta quedo bajo revision por liquidez reciente."
    elif any(badge["key"] == "parking" for badge in badges):
        headline = "La propuesta quedo bajo revision por parking visible."
    else:
        headline = ""

    compact_reasons = []
    for bullet in explanation_items:
        lowered = bullet.lower()
        if "parking" in lowered or "liquidez reciente" in lowered or "repriorizada" in lowered or "reemplazada por una alternativa" in lowered:
            compact_reasons.append(bullet)
    compact_reasons = compact_reasons[:3]

    return {
        "has_trace": bool(badges or compact_reasons or headline),
        "headline": headline,
        "badges": badges[:4],
        "reasons": compact_reasons,
    }


def _build_incremental_history_baseline_trace(
    baseline_item: Dict | None,
    current_item: Dict | None,
    *,
    tactical_trace: Dict | None = None,
) -> Dict:
    current_item = current_item or {}
    baseline_item = baseline_item or {}
    tactical_trace = tactical_trace or {}

    current_id = current_item.get("id")
    baseline_id = baseline_item.get("id")
    if not baseline_item or (current_id is not None and baseline_id is not None and current_id == baseline_id):
        return {
            "has_trace": False,
            "headline": "",
            "badges": [],
            "metrics": [],
        }

    comparison = _build_incremental_snapshot_comparison(baseline_item, current_item)
    winner = comparison.get("winner")
    badges = []
    metrics = []

    expected_metric = next(
        (metric for metric in comparison.get("metrics", []) if metric.get("key") == "expected_return_change"),
        None,
    )
    fragility_metric = next(
        (metric for metric in comparison.get("metrics", []) if metric.get("key") == "fragility_change"),
        None,
    )
    scenario_metric = next(
        (metric for metric in comparison.get("metrics", []) if metric.get("key") == "scenario_loss_change"),
        None,
    )

    if winner == "current":
        badges.append({"label": "Mejor que baseline", "tone": "success"})
    elif winner == "saved":
        badges.append({"label": "Peor que baseline", "tone": "danger"})
    elif winner == "tie":
        badges.append({"label": "Empata baseline", "tone": "secondary"})

    if expected_metric and expected_metric.get("direction") == "favorable":
        badges.append({"label": "Mejor retorno", "tone": "success"})
        metrics.append("Mejora retorno esperado vs baseline.")
    elif expected_metric and expected_metric.get("direction") == "unfavorable":
        badges.append({"label": "Menor retorno", "tone": "warning"})
        metrics.append("Pierde retorno esperado vs baseline.")

    if fragility_metric and fragility_metric.get("direction") == "favorable":
        badges.append({"label": "Menor fragilidad", "tone": "info"})
        metrics.append("Reduce fragilidad vs baseline.")
    elif fragility_metric and fragility_metric.get("direction") == "unfavorable":
        metrics.append("Aumenta fragilidad vs baseline.")

    if scenario_metric and scenario_metric.get("direction") == "favorable":
        metrics.append("Mejora peor escenario vs baseline.")
    elif scenario_metric and scenario_metric.get("direction") == "unfavorable":
        metrics.append("Debilita peor escenario vs baseline.")

    if tactical_trace.get("has_trace"):
        badges.append({"label": "Mas ejecutable tacticamente", "tone": "primary"})
        metrics.append("La propuesta incorpora gobierno tactico explicito frente a friccion de ejecucion.")

    if winner == "current" and expected_metric and expected_metric.get("direction") == "favorable":
        headline = "Supera al baseline en rentabilidad esperada y balance global."
    elif winner == "current":
        headline = "Supera al baseline en score comparativo."
    elif winner == "saved":
        headline = "Queda por detras del baseline actual."
    elif tactical_trace.get("has_trace"):
        headline = "No mejora claramente al baseline, pero deja una lectura tactica mas ejecutable."
    else:
        headline = ""

    return {
        "has_trace": bool(headline or badges or metrics),
        "headline": headline,
        "badges": badges[:4],
        "metrics": metrics[:4],
    }


def _build_incremental_history_priority(
    baseline_item: Dict | None,
    current_item: Dict | None,
    *,
    tactical_trace: Dict | None = None,
) -> Dict:
    current_item = current_item or {}
    if not baseline_item:
        return {
            "has_priority": False,
            "priority": "",
            "priority_label": "",
            "next_action": "",
        }

    comparison = _build_incremental_snapshot_comparison(baseline_item, current_item)
    comparison_metrics = {metric.get("key"): metric for metric in (comparison or {}).get("metrics", [])}
    candidate = {
        "snapshot": current_item,
        "score_difference": None if comparison is None else comparison.get("score_difference"),
        "beats_baseline": bool(comparison and comparison.get("winner") == "current"),
        "loses_vs_baseline": bool(comparison and comparison.get("winner") == "saved"),
        "ties_baseline": bool(comparison and comparison.get("winner") == "tie"),
        "improves_profitability": str((comparison_metrics.get("expected_return_change") or {}).get("direction") or "neutral") == "favorable",
        "protects_fragility": str((comparison_metrics.get("fragility_change") or {}).get("direction") or "neutral") != "unfavorable",
        "tactical_clean": bool(
            not (tactical_trace or {}).get("has_trace")
            or any(str(badge.get("label") or "").strip() == "Alternativa promovida" for badge in (tactical_trace or {}).get("badges", []))
        ),
    }
    priority = _classify_incremental_backlog_priority(candidate)
    return {
        "has_priority": True,
        "priority": priority,
        "priority_label": _format_incremental_backlog_priority(priority),
        "next_action": _build_incremental_backlog_next_action(priority, candidate),
    }


def _normalize_incremental_history_priority_filter(priority_filter: str | None) -> str | None:
    normalized = str(priority_filter or "").strip().lower()
    return normalized if normalized in {"high", "medium", "watch", "low"} else None


def _normalize_incremental_history_deferred_fit_filter(deferred_fit_filter: str | None) -> str | None:
    normalized = str(deferred_fit_filter or "").strip().lower()
    return normalized if normalized in {"reactivable", "archivable"} else None


def _normalize_incremental_future_purchase_source_filter(source_filter: str | None) -> str | None:
    normalized = str(source_filter or "").strip().lower()
    return normalized if normalized in {"backlog_nuevo", "reactivadas"} else None


def _normalize_incremental_history_sort_mode(sort_mode: str | None) -> str:
    normalized = str(sort_mode or "").strip().lower()
    if normalized in {"priority", "future_purchase"}:
        return normalized
    return "newest"


def _format_incremental_history_priority_filter_label(priority_filter: str | None) -> str:
    if not priority_filter:
        return "Todas las prioridades"
    return _format_incremental_backlog_priority(priority_filter)


def _format_incremental_history_deferred_fit_filter_label(deferred_fit_filter: str | None) -> str:
    if not deferred_fit_filter:
        return "Todas las diferidas"
    if deferred_fit_filter == "reactivable":
        return "Diferidas reactivables"
    return "Diferidas archivables"


def _format_incremental_future_purchase_source_filter_label(source_filter: str | None) -> str:
    if not source_filter:
        return "Todas las fuentes"
    if source_filter == "backlog_nuevo":
        return "Backlog nuevo"
    return "Reactivadas"


def _format_incremental_history_sort_mode_label(sort_mode: str | None) -> str:
    if str(sort_mode or "").strip().lower() == "future_purchase":
        return "Futuras compras"
    if str(sort_mode or "").strip().lower() == "priority":
        return "Prioridad operativa"
    return "Mas recientes"


def _build_incremental_history_priority_counts(items: list[Dict]) -> Dict[str, int]:
    return {
        "high": sum(1 for item in items if str((item.get("history_priority") or {}).get("priority") or "") == "high"),
        "medium": sum(1 for item in items if str((item.get("history_priority") or {}).get("priority") or "") == "medium"),
        "watch": sum(1 for item in items if str((item.get("history_priority") or {}).get("priority") or "") == "watch"),
        "low": sum(1 for item in items if str((item.get("history_priority") or {}).get("priority") or "") == "low"),
    }


def _build_incremental_history_deferred_fit(item: Dict) -> Dict:
    if str(item.get("manual_decision_status") or "") != "deferred":
        return {
            "status": "",
            "label": "",
            "summary": "",
            "is_deferred": False,
        }

    priority = str((item.get("history_priority") or {}).get("priority") or "")
    if priority in {"high", "medium"}:
        return {
            "status": "reactivable",
            "label": "Reactivable",
            "summary": "Sigue mostrando fit suficiente para reabrirse como futura compra.",
            "is_deferred": True,
        }
    return {
        "status": "archivable",
        "label": "Archivable",
        "summary": "Hoy ya no conserva suficiente fit economico o tactico para reactivarse primero.",
        "is_deferred": True,
    }


def _build_incremental_history_deferred_fit_counts(items: list[Dict]) -> Dict[str, int]:
    return {
        "reactivable": sum(1 for item in items if str((item.get("deferred_fit") or {}).get("status") or "") == "reactivable"),
        "archivable": sum(1 for item in items if str((item.get("deferred_fit") or {}).get("status") or "") == "archivable"),
    }


def _build_incremental_future_purchase_source_counts(items: list[Dict]) -> Dict[str, int]:
    return {
        "backlog_nuevo": sum(
            1 for item in items if str((item.get("future_purchase_context") or {}).get("source") or "") == "backlog_nuevo"
        ),
        "reactivadas": sum(
            1 for item in items if str((item.get("future_purchase_context") or {}).get("source") or "") == "reactivadas"
        ),
    }


def _build_incremental_future_purchase_source_summary(
    counts: Dict[str, int],
    *,
    active_filter: str | None = None,
) -> Dict:
    backlog_count = int(counts.get("backlog_nuevo", 0))
    reactivated_count = int(counts.get("reactivadas", 0))
    total = backlog_count + reactivated_count

    if active_filter == "backlog_nuevo":
        dominant_source = "backlog_nuevo"
    elif active_filter == "reactivadas":
        dominant_source = "reactivadas"
    elif backlog_count > reactivated_count:
        dominant_source = "backlog_nuevo"
    elif reactivated_count > backlog_count:
        dominant_source = "reactivadas"
    elif total > 0:
        dominant_source = "mixto"
    else:
        dominant_source = "none"

    if dominant_source == "backlog_nuevo":
        headline = "Hoy domina backlog nuevo dentro del historial filtrado."
        dominant_label = "Domina backlog nuevo"
    elif dominant_source == "reactivadas":
        headline = "Hoy dominan reactivadas dentro del historial filtrado."
        dominant_label = "Dominan reactivadas"
    elif dominant_source == "mixto":
        headline = "El historial filtrado hoy queda equilibrado entre backlog nuevo y reactivadas."
        dominant_label = "Lectura mixta"
    else:
        headline = "Todavía no hay futuras compras visibles para resumir por fuente."
        dominant_label = "Sin futuras compras"

    if total == 0:
        summary = "No hay snapshots visibles clasificados como backlog nuevo o reactivadas."
    else:
        summary = (
            f"{backlog_count} provienen de backlog nuevo y {reactivated_count} de reactivadas dentro del historial filtrado."
        )

    return {
        "backlog_nuevo_count": backlog_count,
        "reactivadas_count": reactivated_count,
        "total_count": total,
        "dominant_source": dominant_source,
        "dominant_label": dominant_label,
        "headline": headline,
        "summary": summary,
        "has_visible_sources": total > 0,
    }


def _is_incremental_history_tactical_clean(item: Dict) -> bool:
    tactical_trace = dict(item.get("tactical_trace") or {})
    if not tactical_trace.get("has_trace"):
        return True
    return any(
        str(badge.get("label") or "").strip() == "Alternativa promovida"
        for badge in list(tactical_trace.get("badges") or [])
    )


def _build_incremental_future_purchase_source_quality_item(source: str, items: list[Dict]) -> Dict:
    relevant_items = [
        item
        for item in items
        if str((item.get("future_purchase_context") or {}).get("source") or "") == source
    ]
    count = len(relevant_items)
    if source == "backlog_nuevo":
        label = "Backlog nuevo"
    else:
        label = "Reactivadas"

    if count == 0:
        return {
            "source": source,
            "label": label,
            "count": 0,
            "priority_fit_pct": 0.0,
            "economic_fit_pct": 0.0,
            "tactical_clean_pct": 0.0,
            "average_comparison_score": None,
            "quality_score": 0.0,
            "has_items": False,
        }

    priority_fit_count = sum(
        1
        for item in relevant_items
        if str((item.get("history_priority") or {}).get("priority") or "") in {"high", "medium"}
    )
    economic_fit_count = sum(
        1
        for item in relevant_items
        if (item.get("simulation_delta") or {}).get("expected_return_change") is not None
        and float((item.get("simulation_delta") or {}).get("expected_return_change") or 0.0) > 0
        and float((item.get("simulation_delta") or {}).get("fragility_change") or 0.0) <= 0
    )
    tactical_clean_count = sum(1 for item in relevant_items if _is_incremental_history_tactical_clean(item))
    comparable_scores = [
        float(item.get("comparison_score"))
        for item in relevant_items
        if item.get("comparison_score") is not None
    ]

    priority_fit_pct = round((priority_fit_count / count) * 100, 1)
    economic_fit_pct = round((economic_fit_count / count) * 100, 1)
    tactical_clean_pct = round((tactical_clean_count / count) * 100, 1)
    average_comparison_score = round(sum(comparable_scores) / len(comparable_scores), 2) if comparable_scores else None
    quality_score = round(priority_fit_pct + economic_fit_pct + tactical_clean_pct, 1)

    return {
        "source": source,
        "label": label,
        "count": count,
        "priority_fit_pct": priority_fit_pct,
        "economic_fit_pct": economic_fit_pct,
        "tactical_clean_pct": tactical_clean_pct,
        "average_comparison_score": average_comparison_score,
        "quality_score": quality_score,
        "has_items": True,
    }


def _build_incremental_future_purchase_source_quality_summary(items: list[Dict]) -> Dict:
    backlog_item = _build_incremental_future_purchase_source_quality_item("backlog_nuevo", items)
    reactivated_item = _build_incremental_future_purchase_source_quality_item("reactivadas", items)

    comparable = [item for item in [backlog_item, reactivated_item] if item.get("has_items")]
    if not comparable:
        dominant_source = "none"
        dominant_label = "Sin calidad comparable"
        headline = "Todavía no hay futuras compras visibles para comparar calidad promedio por fuente."
    elif len(comparable) == 1:
        dominant_source = str(comparable[0].get("source") or "none")
        dominant_label = f"Mejor calidad promedio: {comparable[0].get('label')}"
        headline = f"{comparable[0].get('label')} hoy concentra la mejor calidad promedio del historial visible."
    else:
        sorted_items = sorted(
            comparable,
            key=lambda item: (
                -float(item.get("quality_score") or 0.0),
                -float(item.get("average_comparison_score") or float("-inf")),
                str(item.get("label") or ""),
            ),
        )
        top = sorted_items[0]
        second = sorted_items[1]
        if abs(float(top.get("quality_score") or 0.0) - float(second.get("quality_score") or 0.0)) < 0.1:
            dominant_source = "mixto"
            dominant_label = "Calidad pareja"
            headline = "Backlog nuevo y reactivadas hoy muestran una calidad promedio muy similar."
        else:
            dominant_source = str(top.get("source") or "none")
            dominant_label = f"Mejor calidad promedio: {top.get('label')}"
            headline = f"{top.get('label')} hoy muestra mejor calidad promedio que la fuente alternativa."

    return {
        "backlog_nuevo": backlog_item,
        "reactivadas": reactivated_item,
        "dominant_source": dominant_source,
        "dominant_label": dominant_label,
        "headline": headline,
        "has_quality": bool(comparable),
    }


def _build_incremental_history_priority_filter_options(active_priority_filter: str | None, counts: Dict[str, int]) -> list[Dict]:
    options = [{"key": "all", "label": "Todas las prioridades", "count": sum(int(value or 0) for value in counts.values())}]
    for key, label in (
        ("high", "Alta"),
        ("medium", "Recuperable"),
        ("watch", "Observación"),
        ("low", "Baja"),
    ):
        options.append({"key": key, "label": label, "count": int(counts.get(key, 0))})
    for option in options:
        option["selected"] = (active_priority_filter or "all") == option["key"]
    return options


def _build_incremental_history_deferred_fit_filter_options(active_filter: str | None, counts: Dict[str, int]) -> list[Dict]:
    options = [
        {"key": "all", "label": "Todas las diferidas", "count": sum(int(value or 0) for value in counts.values())},
        {"key": "reactivable", "label": "Diferidas reactivables", "count": int(counts.get("reactivable", 0))},
        {"key": "archivable", "label": "Diferidas archivables", "count": int(counts.get("archivable", 0))},
    ]
    for option in options:
        option["selected"] = (active_filter or "all") == option["key"]
    return options


def _build_incremental_future_purchase_source_filter_options(active_filter: str | None, counts: Dict[str, int]) -> list[Dict]:
    options = [
        {"key": "all", "label": "Todas las fuentes", "count": sum(int(value or 0) for value in counts.values())},
        {"key": "backlog_nuevo", "label": "Backlog nuevo", "count": int(counts.get("backlog_nuevo", 0))},
        {"key": "reactivadas", "label": "Reactivadas", "count": int(counts.get("reactivadas", 0))},
    ]
    for option in options:
        option["selected"] = (active_filter or "all") == option["key"]
    return options


def _build_incremental_history_sort_options(active_sort_mode: str) -> list[Dict]:
    options = [
        {"key": "newest", "label": "Mas recientes"},
        {"key": "priority", "label": "Prioridad operativa"},
        {"key": "future_purchase", "label": "Futuras compras"},
    ]
    for option in options:
        option["selected"] = active_sort_mode == option["key"]
    return options


def _build_incremental_future_purchase_history_context(
    item: Dict,
    *,
    reactivated_snapshot_ids: set[int] | None = None,
) -> Dict:
    snapshot_id = item.get("id")
    try:
        normalized_snapshot_id = int(snapshot_id)
    except (TypeError, ValueError):
        normalized_snapshot_id = None

    is_pending = str(item.get("manual_decision_status") or "") == "pending"
    is_recently_reactivated = bool(
        normalized_snapshot_id is not None and normalized_snapshot_id in (reactivated_snapshot_ids or set())
    )
    if is_pending and is_recently_reactivated:
        return {
            "source": "reactivadas",
            "label": "Reactivada",
            "summary": "Sigue vigente tras reactivarse desde diferidas.",
            "is_relevant": True,
        }
    if is_pending:
        return {
            "source": "backlog_nuevo",
            "label": "Backlog nuevo",
            "summary": "Sigue pendiente como idea nueva dentro del backlog actual.",
            "is_relevant": True,
        }
    return {
        "source": "other",
        "label": "",
        "summary": "",
        "is_relevant": False,
    }


def _sort_incremental_history_items(
    items: list[Dict],
    *,
    sort_mode: str,
    preferred_source: str | None = None,
) -> list[Dict]:
    if sort_mode not in {"priority", "future_purchase"}:
        return items
    if sort_mode == "future_purchase":
        normalized_preferred_source = str(preferred_source or "mixto")
        if normalized_preferred_source == "reactivadas":
            source_order = {"reactivadas": 0, "backlog_nuevo": 1, "other": 2}
        elif normalized_preferred_source == "backlog_nuevo":
            source_order = {"backlog_nuevo": 0, "reactivadas": 1, "other": 2}
        else:
            source_order = {"backlog_nuevo": 0, "reactivadas": 0, "other": 1}
        return sorted(
            items,
            key=lambda item: (
                int(source_order.get(str((item.get("future_purchase_context") or {}).get("source") or "other"), 2)),
                0 if item.get("is_backlog_front") else 1,
                _incremental_backlog_priority_order(str((item.get("history_priority") or {}).get("priority") or "low")),
                -(float(item.get("comparison_score")) if item.get("comparison_score") is not None else float("-inf")),
                str(item.get("proposal_label") or ""),
            ),
        )
    return sorted(
        items,
        key=lambda item: (
            0 if item.get("is_backlog_front") else 1,
            _incremental_backlog_priority_order(str((item.get("history_priority") or {}).get("priority") or "low")),
            -(float(item.get("comparison_score")) if item.get("comparison_score") is not None else float("-inf")),
            str(item.get("proposal_label") or ""),
        ),
    )


def _build_incremental_backlog_shortlist_item(*, index: int, item: Dict) -> Dict:
    snapshot = dict(item.get("snapshot") or {})
    simulation_delta = dict(snapshot.get("simulation_delta") or {})
    economic_edge = bool(item.get("improves_profitability") and item.get("protects_fragility"))
    tactical_edge = bool(item.get("tactical_clean"))
    conviction = _build_incremental_backlog_conviction(item, economic_edge=economic_edge, tactical_edge=tactical_edge)
    followup = _build_incremental_backlog_followup(conviction_level=str(conviction.get("level") or "low"))
    return {
        "rank": index,
        "proposal_label": snapshot.get("proposal_label") or "-",
        "priority": item.get("priority") or "low",
        "priority_label": item.get("priority_label") or _format_incremental_backlog_priority("low"),
        "next_action": item.get("next_action") or "",
        "selected_context": snapshot.get("selected_context") or "",
        "score_difference": item.get("score_difference"),
        "expected_return_change": simulation_delta.get("expected_return_change"),
        "fragility_change": simulation_delta.get("fragility_change"),
        "scenario_loss_change": simulation_delta.get("scenario_loss_change"),
        "is_backlog_front": bool(snapshot.get("is_backlog_front")),
        "economic_edge": economic_edge,
        "tactical_edge": tactical_edge,
        "conviction": conviction,
        "followup": followup,
    }


def _build_incremental_backlog_focus_item(item: Dict | None, *, focus: str) -> Dict | None:
    if not item:
        return None
    shortlist_item = _build_incremental_backlog_shortlist_item(index=1, item=item)
    if focus == "economic":
        shortlist_item["focus_label"] = "L?der econ?mico"
        shortlist_item["focus_summary"] = "Mejora retorno esperado sin deterioro material de fragilidad."
    else:
        shortlist_item["focus_label"] = "L?der t?ctico"
        shortlist_item["focus_summary"] = "Conserva la ejecutabilidad m?s limpia para reconsiderar una compra."
    return shortlist_item


def _build_incremental_backlog_conviction(item: Dict, *, economic_edge: bool, tactical_edge: bool) -> Dict:
    priority = str(item.get("priority") or "low")
    if priority == "high" and economic_edge and tactical_edge:
        return {
            "level": "high",
            "label": "Convicci?n alta",
            "summary": "Mejora la ecuaci?n econ?mica y conserva una ejecutabilidad t?ctica limpia.",
        }
    if priority in {"high", "medium"} and (economic_edge or tactical_edge):
        return {
            "level": "medium",
            "label": "Convicci?n media",
            "summary": "Tiene m?rito para reabrir la compra, pero no domina ambos frentes al mismo tiempo.",
        }
    return {
        "level": "low",
        "label": "Convicci?n baja",
        "summary": "Conviene mantenerla en observaci?n hasta que mejore retorno, fragilidad o ejecutabilidad.",
    }


def _build_incremental_backlog_followup(*, conviction_level: str) -> Dict:
    if conviction_level == "high":
        return {
            "status": "review_now",
            "label": "Revisar ya",
            "summary": "Vale la pena reabrir esta propuesta como candidata inmediata de compra futura.",
        }
    if conviction_level == "medium":
        return {
            "status": "monitor",
            "label": "Monitorear",
            "summary": "Conviene seguirla de cerca y revalidarla antes de mover el proximo aporte.",
        }
    return {
        "status": "hold",
        "label": "En espera",
        "summary": "No conviene priorizarla ahora; queda como referencia secundaria del backlog.",
    }


def _normalize_incremental_backlog_followup_filter(followup_filter: str | None) -> str | None:
    normalized = str(followup_filter or "").strip().lower()
    if normalized in {"review_now", "monitor", "hold"}:
        return normalized
    return None


def _format_incremental_backlog_followup_filter_label(followup_filter: str | None) -> str:
    mapping = {
        "review_now": "Revisar ya",
        "monitor": "Monitorear",
        "hold": "En espera",
    }
    return mapping.get(str(followup_filter or "").strip().lower(), "Todas")


def _build_incremental_backlog_followup_filter_options(active_filter: str | None, counts: Dict[str, int]) -> list[Dict]:
    options = [
        {"key": "all", "label": "Todas", "count": sum(int(value or 0) for value in counts.values())},
        {"key": "review_now", "label": "Revisar ya", "count": int(counts.get("review_now", 0))},
        {"key": "monitor", "label": "Monitorear", "count": int(counts.get("monitor", 0))},
        {"key": "hold", "label": "En espera", "count": int(counts.get("hold", 0))},
    ]
    for option in options:
        option["selected"] = (active_filter or "all") == option["key"]
    return options


def _build_incremental_backlog_manual_review_summary(decision_counts: Dict[str, int]) -> Dict:
    pending_count = int(decision_counts.get("pending", 0))
    deferred_count = int(decision_counts.get("deferred", 0))
    accepted_count = int(decision_counts.get("accepted", 0))
    rejected_count = int(decision_counts.get("rejected", 0))
    closed_count = accepted_count + rejected_count
    reviewed_count = deferred_count + closed_count
    if pending_count > 0:
        headline = "Todavía hay propuestas vigentes para futuras compras dentro del backlog."
    elif reviewed_count > 0:
        headline = "El backlog vigente ya fue revisado manualmente y hoy no quedan propuestas pendientes."
    else:
        headline = "Todavía no hay decisiones manuales suficientes para leer cobertura operativa del backlog."
    return {
        "pending_count": pending_count,
        "deferred_count": deferred_count,
        "accepted_count": accepted_count,
        "rejected_count": rejected_count,
        "closed_count": closed_count,
        "reviewed_count": reviewed_count,
        "headline": headline,
        "has_manual_reviews": bool(reviewed_count),
    }


def _build_incremental_backlog_deferred_review_summary(items: List[Dict], decision_counts: Dict[str, int]) -> Dict:
    deferred_count = int(decision_counts.get("deferred", len(items)))
    reactivable_items = [
        item
        for item in items
        if str((item.get("history_priority") or {}).get("priority") or "") in {"high", "medium"}
    ]
    archivable_items = [
        item
        for item in items
        if str((item.get("history_priority") or {}).get("priority") or "") not in {"high", "medium"}
    ]
    top_reactivable = reactivable_items[0] if reactivable_items else None

    if reactivable_items:
        headline = "Parte de las diferidas todavia conserva fit suficiente para reactivarse como futura compra."
    elif deferred_count > 0:
        headline = "Las diferidas actuales ya no muestran suficiente fit economico o tactico y conviene archivarlas."
    else:
        headline = "Todavia no hay diferidas revisadas para separar entre reactivables y archivables."

    return {
        "deferred_count": deferred_count,
        "reactivable_count": len(reactivable_items),
        "archivable_count": len(archivable_items),
        "top_reactivable_label": (top_reactivable or {}).get("proposal_label") or "",
        "top_reactivable_priority_label": str(((top_reactivable or {}).get("history_priority") or {}).get("priority_label") or ""),
        "has_reactivable": bool(reactivable_items),
        "headline": headline,
    }


def get_incremental_proposal_tracking_baseline(*, user) -> Dict:
    """Retorna el snapshot incremental activo como baseline de seguimiento del usuario."""

    if user is None or not getattr(user, "is_authenticated", False) or not getattr(user, "pk", None):
        return {
            "item": None,
            "has_baseline": False,
        }
    item = IncrementalProposalHistoryService().get_tracking_baseline(user=user)
    return {
        "item": item,
        "has_baseline": item is not None,
    }


def get_incremental_manual_decision_summary(*, user) -> Dict:
    """Resume la ultima decision manual persistida sobre propuestas incrementales guardadas."""

    item = IncrementalProposalHistoryService().get_latest_manual_decision(user=user)
    status = str((item or {}).get("manual_decision_status") or "pending")
    return {
        "item": item,
        "has_decision": item is not None,
        "status": status,
        "status_label": _format_incremental_manual_decision_status(status),
        "headline": _build_incremental_manual_decision_headline(item),
    }


def get_incremental_reactivation_summary(*, user, limit: int = 3) -> Dict:
    """Resume reactivaciones recientes de snapshots diferidos dentro del backlog incremental."""

    if user is None or not getattr(user, "is_authenticated", False) or not getattr(user, "pk", None):
        return {
            "items": [],
            "count": 0,
            "active_count": 0,
            "front_count": 0,
            "acceptance_rate": 0.0,
            "redeferral_rate": 0.0,
            "rejection_rate": 0.0,
            "effectiveness_label": "Sin datos",
            "has_reactivations": False,
            "headline": "Todavia no hay reactivaciones recientes para revisar.",
        }

    audits = list(
        SensitiveActionAudit.objects.filter(
            user=user,
            action="reactivate_incremental_deferred_snapshot",
            status="success",
        ).order_by("-created_at", "-id")[: max(int(limit), 0)]
    )
    snapshot_ids = []
    for audit in audits:
        raw_snapshot_id = (audit.details or {}).get("snapshot_id")
        try:
            snapshot_ids.append(int(raw_snapshot_id))
        except (TypeError, ValueError):
            continue

    snapshots = {
        snapshot.id: snapshot
        for snapshot in IncrementalProposalSnapshot.objects.filter(user=user, id__in=snapshot_ids)
    }
    items = []
    active_count = 0
    front_count = 0
    accepted_count = 0
    deferred_count = 0
    rejected_count = 0
    for audit in audits:
        raw_snapshot_id = (audit.details or {}).get("snapshot_id")
        try:
            snapshot_id = int(raw_snapshot_id)
        except (TypeError, ValueError):
            snapshot_id = None
        snapshot = snapshots.get(snapshot_id)
        current_status = str(getattr(snapshot, "manual_decision_status", "") or "")
        is_backlog_front = bool(getattr(snapshot, "is_backlog_front", False))
        if current_status == "pending":
            active_count += 1
        if current_status == "pending" and is_backlog_front:
            front_count += 1
        if current_status == "accepted":
            accepted_count += 1
        elif current_status == "deferred":
            deferred_count += 1
        elif current_status == "rejected":
            rejected_count += 1
        items.append(
            {
                "snapshot_id": snapshot_id,
                "proposal_label": str((audit.details or {}).get("proposal_label") or getattr(snapshot, "proposal_label", "") or "-"),
                "reactivated_at": audit.created_at,
                "user_label": audit.user.username if audit.user else "system",
                "current_status": current_status or "missing",
                "current_status_label": _format_incremental_manual_decision_status(current_status) if current_status else "Sin snapshot",
                "is_backlog_front": is_backlog_front,
                "is_active": current_status == "pending",
                "is_accepted": current_status == "accepted",
                "is_deferred_again": current_status == "deferred",
                "is_rejected": current_status == "rejected",
                "current_summary": (
                    "Sigue al frente del backlog incremental."
                    if current_status == "pending" and is_backlog_front
                    else "Sigue vigente como candidata pendiente."
                    if current_status == "pending"
                    else "Termino aceptada despues de reactivarse."
                    if current_status == "accepted"
                    else "Volvio a diferirse despues de reactivarse."
                    if current_status == "deferred"
                    else "Se descarto despues de reactivarse."
                    if current_status == "rejected"
                    else "Ya no sigue pendiente en el backlog actual."
                ),
            }
        )

    if items:
        headline = (
            f"Se registraron {len(items)} reactivaciones recientes; {active_count} siguen vigentes, {accepted_count} terminaron aceptadas y {front_count} quedaron al frente del backlog."
        )
    else:
        headline = "Todavia no hay reactivaciones recientes para revisar."

    total_count = len(items)
    acceptance_rate = round((accepted_count / total_count) * 100, 1) if total_count else 0.0
    redeferral_rate = round((deferred_count / total_count) * 100, 1) if total_count else 0.0
    rejection_rate = round((rejected_count / total_count) * 100, 1) if total_count else 0.0
    if total_count == 0:
        effectiveness_label = "Sin datos"
    elif acceptance_rate >= 50 and rejection_rate == 0:
        effectiveness_label = "Alta"
    elif acceptance_rate >= 25:
        effectiveness_label = "Media"
    else:
        effectiveness_label = "Baja"

    return {
        "items": items,
        "count": len(items),
        "active_count": active_count,
        "front_count": front_count,
        "accepted_count": accepted_count,
        "deferred_count": deferred_count,
        "rejected_count": rejected_count,
        "acceptance_rate": acceptance_rate,
        "redeferral_rate": redeferral_rate,
        "rejection_rate": rejection_rate,
        "effectiveness_label": effectiveness_label,
        "has_reactivations": bool(items),
        "headline": headline,
    }


def _build_incremental_reactivation_vs_backlog_summary(
    reactivation_summary: Dict,
    backlog_prioritization: Dict,
) -> Dict:
    reactivation_count = int(reactivation_summary.get("count", 0) or 0)
    accepted_count = int(reactivation_summary.get("accepted_count", 0) or 0)
    active_count = int(reactivation_summary.get("active_count", 0) or 0)
    acceptance_rate = float(reactivation_summary.get("acceptance_rate", 0.0) or 0.0)
    backlog_high = int((backlog_prioritization.get("counts") or {}).get("high", 0) or 0)
    backlog_medium = int((backlog_prioritization.get("counts") or {}).get("medium", 0) or 0)
    backlog_top_label = str((((backlog_prioritization.get("top_item") or {}).get("snapshot") or {}).get("proposal_label")) or "")
    has_backlog = bool(backlog_prioritization.get("has_priorities"))

    if reactivation_count == 0 and has_backlog:
        return {
            "preferred_source": "backlog_nuevo",
            "label": "Priorizar backlog nuevo",
            "headline": "Hoy conviene priorizar ideas nuevas del backlog antes que rescatar diferidas.",
            "summary": "No hay evidencia reciente de reactivaciones como para desplazar el backlog pendiente actual.",
        }
    if has_backlog is False and reactivation_count > 0:
        return {
            "preferred_source": "reactivadas",
            "label": "Priorizar reactivadas",
            "headline": "Hoy conviene volver primero sobre propuestas ya reactivadas.",
            "summary": "No hay backlog nuevo priorizable por delante y las reactivaciones siguen siendo la mejor fuente de revisión.",
        }
    if acceptance_rate >= 50.0 and accepted_count >= max(backlog_high, 1):
        return {
            "preferred_source": "reactivadas",
            "label": "Priorizar reactivadas",
            "headline": "Las reactivaciones recientes están cerrando mejor que el backlog nuevo.",
            "summary": "La tasa de aceptación post-reactivación ya justifica revisar primero propuestas rescatadas.",
        }
    if backlog_high > 0 and (acceptance_rate < 25.0 or accepted_count == 0):
        return {
            "preferred_source": "backlog_nuevo",
            "label": "Priorizar backlog nuevo",
            "headline": "El backlog nuevo hoy parece más prometedor que reactivar diferidas.",
            "summary": (
                f"Hay {backlog_high} propuesta(s) de alta prioridad"
                + (f", con {backlog_top_label} al frente." if backlog_top_label else ".")
            ),
        }
    return {
        "preferred_source": "mixto",
        "label": "Priorizar mixto",
        "headline": "Conviene combinar backlog nuevo y reactivadas según el caso.",
        "summary": (
            f"Las reactivaciones muestran {accepted_count} cierre(s) positivo(s) y {active_count} siguen vigentes; "
            f"el backlog nuevo aporta {backlog_high} alta(s) y {backlog_medium} recuperable(s)."
        ),
    }


def _build_incremental_future_purchase_shortlist(
    reactivation_summary: Dict,
    backlog_prioritization: Dict,
    comparison_summary: Dict,
    quality_summary: Dict,
    *,
    limit: int = 3,
) -> Dict:
    backlog_items = []
    for item in list(backlog_prioritization.get("shortlist") or []):
        enriched = dict(item)
        enriched["source"] = "backlog_nuevo"
        enriched["source_label"] = "Backlog nuevo"
        enriched["source_priority"] = 0
        backlog_items.append(enriched)

    reactivated_items = []
    for index, item in enumerate(list(reactivation_summary.get("items") or []), start=1):
        if not item.get("is_active"):
            continue
        reactivated_items.append(
            {
                "rank": index,
                "proposal_label": item.get("proposal_label") or "-",
                "priority_label": item.get("current_status_label") or "Pendiente",
                "next_action": "Revisar reactivada vigente antes de perder contexto operativo.",
                "selected_context": "Reactivada desde diferidas",
                "expected_return_change": None,
                "fragility_change": None,
                "scenario_loss_change": None,
                "is_backlog_front": bool(item.get("is_backlog_front")),
                "economic_edge": bool(item.get("is_accepted")),
                "tactical_edge": bool(item.get("is_active")),
                "conviction": {
                    "level": "medium" if item.get("is_backlog_front") else "low",
                    "label": "Conviccion reactivada",
                    "summary": item.get("current_summary") or "",
                },
                "followup": {
                    "status": "review_now" if item.get("is_backlog_front") else "monitor",
                    "label": "Revisar ya" if item.get("is_backlog_front") else "Monitorear",
                    "summary": item.get("current_summary") or "",
                },
                "source": "reactivadas",
                "source_label": "Reactivada",
                "source_priority": 0,
            }
        )

    comparison_preferred_source = str(comparison_summary.get("preferred_source") or "mixto")
    quality_preferred_source = str(quality_summary.get("dominant_source") or "none")
    effective_preferred_source = (
        quality_preferred_source
        if quality_preferred_source in {"backlog_nuevo", "reactivadas"}
        else comparison_preferred_source
    )
    if effective_preferred_source == "reactivadas":
        for item in reactivated_items:
            item["source_priority"] = 0
        for item in backlog_items:
            item["source_priority"] = 1
    elif effective_preferred_source == "backlog_nuevo":
        for item in backlog_items:
            item["source_priority"] = 0
        for item in reactivated_items:
            item["source_priority"] = 1
    else:
        for item in backlog_items:
            item["source_priority"] = 0 if item.get("economic_edge") else 1
        for item in reactivated_items:
            item["source_priority"] = 0 if item.get("is_backlog_front") else 1

    combined_items = sorted(
        backlog_items + reactivated_items,
        key=lambda item: (
            int(item.get("source_priority", 1)),
            0 if item.get("is_backlog_front") else 1,
            0 if str((item.get("followup") or {}).get("status") or "") == "review_now" else 1,
            str(item.get("proposal_label") or ""),
        ),
    )
    shortlist = []
    for index, item in enumerate(combined_items[: max(int(limit), 0)], start=1):
        enriched = dict(item)
        enriched["rank"] = index
        shortlist.append(enriched)

    return {
        "items": shortlist,
        "count": len(shortlist),
        "has_items": bool(shortlist),
        "preferred_source": effective_preferred_source,
        "comparison_preferred_source": comparison_preferred_source,
        "quality_preferred_source": quality_preferred_source,
        "preferred_label": (
            quality_summary.get("dominant_label")
            if quality_preferred_source in {"backlog_nuevo", "reactivadas"}
            else comparison_summary.get("label") or "Priorizar mixto"
        ),
        "headline": (
            quality_summary.get("headline")
            if quality_preferred_source in {"backlog_nuevo", "reactivadas"}
            else comparison_summary.get("headline") or "Conviene revisar una shortlist mixta de futuras compras."
        ),
        "quality_label": quality_summary.get("dominant_label") or "",
        "quality_headline": quality_summary.get("headline") or "",
    }


def _build_incremental_future_purchase_source_guidance(
    quality_summary: Dict,
    shortlist: Dict,
    backlog_prioritization: Dict,
    reactivation_summary: Dict,
) -> Dict:
    source = str((shortlist or {}).get("preferred_source") or (quality_summary or {}).get("dominant_source") or "none")
    if source == "backlog_nuevo":
        top_item = dict((backlog_prioritization or {}).get("top_item") or {})
        snapshot = dict(top_item.get("snapshot") or {})
        proposal_label = str(snapshot.get("proposal_label") or "backlog nuevo prioritario")
        next_action = str(top_item.get("next_action") or f"Revisar primero {proposal_label}.")
        headline = str((quality_summary or {}).get("headline") or "Backlog nuevo hoy concentra la mejor fuente para revisar futuras compras.")
        return {
            "source": "backlog_nuevo",
            "label": "Salir desde backlog nuevo",
            "headline": headline,
            "next_action": next_action,
            "proposal_label": proposal_label,
            "has_guidance": True,
        }
    if source == "reactivadas":
        active_item = next(
            (item for item in list((reactivation_summary or {}).get("items") or []) if item.get("is_active")),
            None,
        ) or {}
        proposal_label = str(active_item.get("proposal_label") or "reactivada vigente")
        next_action = (
            "Revisar reactivada vigente antes de perder contexto operativo."
            if proposal_label == "reactivada vigente"
            else f"Revisar primero {proposal_label} entre las reactivadas vigentes."
        )
        headline = str((quality_summary or {}).get("headline") or "Reactivadas hoy concentra la mejor fuente para revisar futuras compras.")
        return {
            "source": "reactivadas",
            "label": "Salir desde reactivadas",
            "headline": headline,
            "next_action": next_action,
            "proposal_label": proposal_label,
            "has_guidance": True,
        }
    return {
        "source": "mixto",
        "label": "Lectura mixta",
        "headline": "Conviene mantener una lectura mixta entre backlog nuevo y reactivadas.",
        "next_action": "Revisar la shortlist unificada y priorizar el mejor fit visible del momento.",
        "proposal_label": "",
        "has_guidance": True,
    }


def _annotate_incremental_future_purchase_recommended_items(
    shortlist: Dict,
    history: Dict,
    guidance: Dict,
) -> tuple[Dict, Dict]:
    shortlist = dict(shortlist or {})
    history = dict(history or {})
    guidance = dict(guidance or {})

    recommended_label = str(guidance.get("proposal_label") or "").strip()
    recommended_source = str(guidance.get("source") or "").strip().lower()
    has_guidance = bool(guidance.get("has_guidance")) and bool(recommended_label) and recommended_source in {
        "backlog_nuevo",
        "reactivadas",
    }

    def _annotate_item(item: Dict, source_key: str) -> Dict:
        enriched = dict(item or {})
        is_recommended = has_guidance and str(enriched.get("proposal_label") or "").strip() == recommended_label and source_key == recommended_source
        enriched["is_future_purchase_recommended"] = is_recommended
        enriched["future_purchase_recommendation_label"] = "Recomendada ahora" if is_recommended else ""
        enriched["future_purchase_recommendation_summary"] = (
            str(guidance.get("next_action") or "").strip() if is_recommended else ""
        )
        return enriched

    shortlist["items"] = [
        _annotate_item(item, str(item.get("source") or "").strip().lower())
        for item in list(shortlist.get("items") or [])
    ]
    history["items"] = [
        _annotate_item(item, str(((item.get("future_purchase_context") or {}).get("source") or "")).strip().lower())
        for item in list(history.get("items") or [])
    ]
    shortlist["recommended_label"] = recommended_label if has_guidance else ""
    shortlist["has_recommended_item"] = any(item.get("is_future_purchase_recommended") for item in shortlist["items"])
    history["has_future_purchase_recommended_item"] = any(
        item.get("is_future_purchase_recommended") for item in history["items"]
    )
    return shortlist, history


def get_incremental_baseline_drift(
    query_params,
    *,
    user,
    capital_amount: int | float = 600000,
) -> Dict:
    """Compara el baseline incremental activo contra la propuesta preferida actual."""

    baseline_payload = get_incremental_proposal_tracking_baseline(user=user)
    preferred_payload = get_preferred_incremental_portfolio_proposal(query_params, capital_amount=capital_amount)

    baseline = baseline_payload.get("item")
    current_preferred = preferred_payload.get("preferred")
    comparison = None
    if baseline and current_preferred:
        comparison = _build_incremental_snapshot_comparison(baseline, current_preferred)

    summary = _build_incremental_baseline_drift_summary(comparison)
    alerts = _build_incremental_baseline_drift_alerts(baseline, current_preferred, summary)
    return {
        "baseline": baseline,
        "current_preferred": current_preferred,
        "comparison": comparison,
        "summary": summary,
        "alerts": alerts,
        "alerts_count": len(alerts),
        "has_alerts": bool(alerts),
        "has_drift": comparison is not None,
        "has_baseline": baseline is not None,
        "explanation": _build_incremental_baseline_drift_explanation(baseline, current_preferred, comparison, summary),
    }


def get_incremental_pending_backlog_vs_baseline(*, user, limit: int = 5) -> Dict:
    """Compara el backlog pendiente de snapshots contra el baseline incremental activo."""

    baseline_payload = get_incremental_proposal_tracking_baseline(user=user)
    pending_history = get_incremental_proposal_history(user=user, limit=limit, decision_status="pending")

    baseline = baseline_payload.get("item")
    pending_items = list(pending_history.get("items") or [])
    comparisons = []
    for item in pending_items:
        comparison = _build_incremental_snapshot_comparison(baseline, item) if baseline else None
        summary = _build_incremental_baseline_drift_summary(comparison)
        baseline_trace = dict(item.get("baseline_trace") or {})
        tactical_trace = dict(item.get("tactical_trace") or {})
        comparison_metrics = {metric.get("key"): metric for metric in (comparison or {}).get("metrics", [])}
        expected_direction = str((comparison_metrics.get("expected_return_change") or {}).get("direction") or "neutral")
        fragility_direction = str((comparison_metrics.get("fragility_change") or {}).get("direction") or "neutral")
        scenario_direction = str((comparison_metrics.get("scenario_loss_change") or {}).get("direction") or "neutral")
        tactical_clean = bool(
            not tactical_trace.get("has_trace")
            or any(str(badge.get("label") or "").strip() == "Alternativa promovida" for badge in tactical_trace.get("badges", []))
        )
        improves_profitability = expected_direction == "favorable"
        protects_fragility = fragility_direction != "unfavorable"
        comparisons.append(
            {
                "snapshot": item,
                "comparison": comparison,
                "summary": summary,
                "status_label": _format_incremental_followup_status(summary.get("status", "unavailable")),
                "score_difference": None if comparison is None else comparison.get("score_difference"),
                "beats_baseline": bool(comparison and comparison.get("winner") == "current"),
                "loses_vs_baseline": bool(comparison and comparison.get("winner") == "saved"),
                "ties_baseline": bool(comparison and comparison.get("winner") == "tie"),
                "improves_profitability": improves_profitability,
                "protects_fragility": protects_fragility,
                "tactical_clean": tactical_clean,
                "comparison_fit": {
                    "expected_direction": expected_direction,
                    "fragility_direction": fragility_direction,
                    "scenario_direction": scenario_direction,
                    "improves_profitability": improves_profitability,
                    "protects_fragility": protects_fragility,
                    "tactical_clean": tactical_clean,
                    "baseline_headline": baseline_trace.get("headline") or "",
                },
            }
        )

    better_count = sum(1 for item in comparisons if item["beats_baseline"])
    worse_count = sum(1 for item in comparisons if item["loses_vs_baseline"])
    tie_count = sum(1 for item in comparisons if item["ties_baseline"])
    comparable_items = [item for item in comparisons if item.get("comparison")]
    best_candidate = None
    if comparable_items:
        best_candidate = sorted(
            comparable_items,
            key=lambda item: (
                1 if item.get("improves_profitability") else 0,
                1 if item.get("protects_fragility") else 0,
                1 if item.get("tactical_clean") else 0,
                1 if item["beats_baseline"] else 0,
                1 if item["ties_baseline"] else 0,
                item.get("score_difference") if item.get("score_difference") is not None else float("-inf"),
            ),
            reverse=True,
        )[0]

    return {
        "baseline": baseline,
        "items": comparisons,
        "count": len(comparisons),
        "pending_count": pending_history.get("decision_counts", {}).get("pending", len(comparisons)),
        "decision_counts": dict(pending_history.get("decision_counts", {})),
        "has_baseline": baseline is not None,
        "has_pending_backlog": bool(pending_items),
        "has_comparable_items": bool(comparable_items),
        "better_count": better_count,
        "worse_count": worse_count,
        "tie_count": tie_count,
        "best_candidate": best_candidate,
        "headline": _build_incremental_pending_backlog_headline(baseline, pending_history, better_count, worse_count, tie_count),
        "explanation": _build_incremental_pending_backlog_explanation(baseline, pending_history, best_candidate, better_count, worse_count),
    }


def get_incremental_backlog_prioritization(*, user, limit: int = 5, followup_filter: str | None = None) -> Dict:
    """Ordena el backlog pendiente en prioridades operativas explicitas."""

    backlog_payload = get_incremental_pending_backlog_vs_baseline(user=user, limit=limit)
    deferred_history = get_incremental_proposal_history(user=user, limit=limit, decision_status="deferred")
    items = []
    for item in backlog_payload.get("items", []):
        priority = _classify_incremental_backlog_priority(item)
        enriched = dict(item)
        enriched["priority"] = priority
        enriched["priority_label"] = _format_incremental_backlog_priority(priority)
        enriched["next_action"] = _build_incremental_backlog_next_action(priority, item)
        items.append(enriched)

    ordered_items = sorted(
        items,
        key=lambda item: (
            0 if item["snapshot"].get("is_backlog_front") else 1,
            _incremental_backlog_priority_order(item["priority"]),
            -(item.get("score_difference") if item.get("score_difference") is not None else float("-inf")),
            item["snapshot"].get("proposal_label") or "",
        ),
    )

    counts = {
        "high": sum(1 for item in ordered_items if item["priority"] == "high"),
        "medium": sum(1 for item in ordered_items if item["priority"] == "medium"),
        "watch": sum(1 for item in ordered_items if item["priority"] == "watch"),
        "low": sum(1 for item in ordered_items if item["priority"] == "low"),
    }
    decision_counts = dict(backlog_payload.get("decision_counts", {}))
    top_item = ordered_items[0] if ordered_items else None
    economic_leader = next(
        (
            item
            for item in ordered_items
            if item.get("improves_profitability") and item.get("protects_fragility")
        ),
        None,
    )
    tactical_leader = next(
        (
            item
            for item in ordered_items
            if item.get("tactical_clean")
        ),
        None,
    )
    normalized_followup_filter = _normalize_incremental_backlog_followup_filter(followup_filter)
    shortlist_items = [
        _build_incremental_backlog_shortlist_item(index=index + 1, item=item)
        for index, item in enumerate(ordered_items)
    ]
    followup_counts = {
        "review_now": sum(1 for item in shortlist_items if item.get("followup", {}).get("status") == "review_now"),
        "monitor": sum(1 for item in shortlist_items if item.get("followup", {}).get("status") == "monitor"),
        "hold": sum(1 for item in shortlist_items if item.get("followup", {}).get("status") == "hold"),
    }
    if normalized_followup_filter:
        shortlist_items = [
            item for item in shortlist_items if str((item.get("followup") or {}).get("status") or "") == normalized_followup_filter
        ]
    shortlist = shortlist_items[:3]

    return {
        "baseline": backlog_payload.get("baseline"),
        "items": ordered_items,
        "count": len(ordered_items),
        "counts": counts,
        "manual_review_summary": _build_incremental_backlog_manual_review_summary(decision_counts),
        "deferred_review_summary": _build_incremental_backlog_deferred_review_summary(
            list(deferred_history.get("items") or []),
            decision_counts,
        ),
        "top_item": top_item,
        "economic_leader": _build_incremental_backlog_focus_item(economic_leader, focus="economic"),
        "tactical_leader": _build_incremental_backlog_focus_item(tactical_leader, focus="tactical"),
        "has_focus_split": bool(economic_leader or tactical_leader),
        "active_followup_filter": normalized_followup_filter or "all",
        "active_followup_filter_label": _format_incremental_backlog_followup_filter_label(normalized_followup_filter),
        "available_followup_filters": _build_incremental_backlog_followup_filter_options(
            normalized_followup_filter,
            followup_counts,
        ),
        "followup_counts": followup_counts,
        "shortlist": shortlist,
        "has_shortlist": bool(shortlist),
        "has_priorities": bool(ordered_items),
        "headline": _build_incremental_backlog_prioritization_headline(backlog_payload, counts, top_item),
        "explanation": _build_incremental_backlog_prioritization_explanation(backlog_payload, counts, top_item),
    }


def get_incremental_backlog_front_summary(*, user, limit: int = 5) -> Dict:
    """Resume en una sola lectura el baseline activo y el frente operativo del backlog."""

    baseline_payload = get_incremental_proposal_tracking_baseline(user=user)
    prioritization_payload = get_incremental_backlog_prioritization(user=user, limit=limit)

    baseline = baseline_payload.get("item")
    front_item = prioritization_payload.get("top_item")
    if baseline is None and front_item is None:
        status = "empty"
    elif baseline is None:
        status = "no_baseline"
    elif front_item is None:
        status = "baseline_only"
    elif front_item.get("snapshot", {}).get("is_backlog_front"):
        status = "manual_front"
    elif front_item.get("priority") == "high":
        status = "candidate_over_baseline"
    elif front_item.get("priority") == "medium":
        status = "watch"
    else:
        status = "baseline_holds"

    return {
        "status": status,
        "baseline": baseline,
        "front_item": front_item,
        "counts": prioritization_payload.get("counts", {}),
        "has_summary": bool(baseline or front_item),
        "headline": _build_incremental_backlog_front_summary_headline(status, baseline, front_item),
        "items": _build_incremental_backlog_front_summary_items(baseline, front_item, prioritization_payload),
    }


def get_incremental_backlog_operational_semaphore(
    query_params,
    *,
    user,
    capital_amount: int | float = 600000,
    limit: int = 5,
) -> Dict:
    """Clasifica el estado operativo incremental en semaforo reutilizando baseline, drift y backlog."""

    drift_payload = get_incremental_baseline_drift(query_params, user=user, capital_amount=capital_amount)
    front_summary = get_incremental_backlog_front_summary(user=user, limit=limit)
    prioritization = get_incremental_backlog_prioritization(user=user, limit=limit)

    drift_status = drift_payload.get("summary", {}).get("status", "unavailable")
    front_status = front_summary.get("status", "empty")
    high_count = int(prioritization.get("counts", {}).get("high", 0))

    if drift_status == "unfavorable":
        status = "red"
    elif front_status == "candidate_over_baseline" or high_count > 0:
        status = "yellow"
    elif front_status == "manual_front":
        status = "yellow"
    elif drift_status in {"favorable", "stable"} and front_status in {"baseline_only", "empty"}:
        status = "green"
    else:
        status = "gray"

    return {
        "status": status,
        "label": _format_incremental_operational_semaphore(status),
        "headline": _build_incremental_operational_semaphore_headline(status, front_summary, drift_payload),
        "items": _build_incremental_operational_semaphore_items(drift_payload, front_summary, prioritization),
        "has_signal": bool(drift_payload.get("has_baseline") or front_summary.get("has_summary")),
    }


def get_incremental_decision_executive_summary(
    query_params,
    *,
    user,
    capital_amount: int | float = 600000,
    limit: int = 5,
) -> Dict:
    """Consolida la lectura ejecutiva de decision incremental en una sola sintesis."""

    semaphore = get_incremental_backlog_operational_semaphore(
        query_params,
        user=user,
        capital_amount=capital_amount,
        limit=limit,
    )
    followup = get_incremental_followup_executive_summary(
        query_params,
        user=user,
        capital_amount=capital_amount,
    )
    checklist = get_incremental_adoption_checklist(
        query_params,
        user=user,
        capital_amount=capital_amount,
    )
    front_summary = get_incremental_backlog_front_summary(user=user, limit=limit)

    semaphore_status = semaphore.get("status", "gray")
    checklist_status = checklist.get("status", "pending")
    if checklist_status == "ready" and semaphore_status == "green":
        status = "adopt"
    elif semaphore_status == "red":
        status = "hold"
    elif semaphore_status == "yellow":
        status = "review_backlog"
    elif checklist_status == "review":
        status = "review_current"
    else:
        status = "pending"

    return {
        "status": status,
        "headline": _build_incremental_decision_executive_headline(status, semaphore, followup, checklist, front_summary),
        "items": _build_incremental_decision_executive_items(semaphore, followup, checklist, front_summary),
        "has_summary": bool(
            semaphore.get("has_signal")
            or followup.get("has_summary")
            or checklist.get("total_count")
            or front_summary.get("has_summary")
        ),
    }


def get_decision_engine_summary(
    user,
    *,
    query_params=None,
    capital_amount: int | float = 600000,
) -> Dict:
    """Compone una sintesis unica de decision mensual reutilizando selectors existentes."""

    query_params = query_params or {}
    query_stamp = _build_decision_engine_query_stamp(query_params)
    cache_key = f"decision_engine_summary:{getattr(user, 'pk', 'anon')}:{int(capital_amount)}:{query_stamp}"

    def build():
        portfolio_scope = _build_portfolio_scope_summary()
        macro_local = get_macro_local_context()
        analytics = get_analytics_v2_dashboard_summary()
        monthly_plan = get_monthly_allocation_plan(capital_amount=capital_amount)
        ranking = get_candidate_asset_ranking(capital_amount=capital_amount)
        preferred_payload = get_preferred_incremental_portfolio_proposal(
            query_params,
            capital_amount=capital_amount,
        )
        simulation = get_incremental_portfolio_simulation(capital_amount=capital_amount)

        macro_state = _build_decision_macro_state(macro_local)
        portfolio_state = _build_decision_portfolio_state(analytics)
        parking_feature = get_portfolio_parking_feature_context()
        market_history_feature = get_market_snapshot_history_feature_context()
        recommendation = _build_decision_recommendation(
            monthly_plan,
            parking_feature=parking_feature,
            market_history_feature=market_history_feature,
        )
        suggested_assets = _build_decision_suggested_assets(
            ranking,
            parking_feature=parking_feature,
            market_history_feature=market_history_feature,
        )
        preferred_proposal = _build_decision_preferred_proposal(
            preferred_payload,
            parking_feature=parking_feature,
            market_history_feature=market_history_feature,
        )
        expected_impact = _build_decision_expected_impact(simulation)
        recommendation_context = _build_decision_recommendation_context(portfolio_scope)
        strategy_bias = _build_decision_strategy_bias(recommendation_context)
        parking_signal = _build_decision_parking_signal(parking_feature)
        market_history_signal = _build_decision_market_history_signal(
            market_history_feature=market_history_feature,
            recommendation=recommendation,
            preferred_proposal=preferred_proposal,
        )
        execution_gate = _build_decision_execution_gate(
            parking_signal=parking_signal,
            preferred_proposal=preferred_proposal,
        )
        action_suggestions = _build_decision_action_suggestions(
            strategy_bias,
            parking_signal=parking_signal,
            market_history_signal=market_history_signal,
        )
        score = _compute_decision_score(
            macro_state=macro_state,
            portfolio_state=portfolio_state,
            recommendation=recommendation,
            suggested_assets=suggested_assets,
            preferred_proposal=preferred_proposal,
            expected_impact=expected_impact,
            parking_signal=parking_signal,
            market_history_signal=market_history_signal,
        )
        confidence = _compute_decision_confidence(
            macro_state=macro_state,
            portfolio_state=portfolio_state,
            preferred_proposal=preferred_proposal,
            expected_impact=expected_impact,
            parking_signal=parking_signal,
            market_history_signal=market_history_signal,
        )
        explanation = _build_decision_explanation(
            macro_state=macro_state,
            recommendation=recommendation,
            expected_impact=expected_impact,
            confidence=confidence,
            preferred_proposal=preferred_proposal,
            parking_signal=parking_signal,
            market_history_signal=market_history_signal,
        )
        tracking_payload = _build_decision_tracking_payload(
            preferred_proposal=preferred_proposal,
            recommendation=recommendation,
            expected_impact=expected_impact,
            score=score,
            confidence=confidence,
            macro_state=macro_state,
            portfolio_state=portfolio_state,
            parking_signal=parking_signal,
            market_history_signal=market_history_signal,
            execution_gate=execution_gate,
        )

        return {
            "portfolio_scope": portfolio_scope,
            "recommendation_context": recommendation_context,
            "strategy_bias": strategy_bias,
            "parking_signal": parking_signal,
            "market_history_signal": market_history_signal,
            "execution_gate": execution_gate,
            "action_suggestions": action_suggestions,
            "macro_state": macro_state,
            "portfolio_state": portfolio_state,
            "recommendation": recommendation,
            "suggested_assets": suggested_assets,
            "preferred_proposal": preferred_proposal,
            "expected_impact": expected_impact,
            "score": score,
            "confidence": confidence,
            "explanation": explanation,
            "tracking_payload": tracking_payload,
        }

    return _get_cached_selector_result(cache_key, build)


def get_planeacion_incremental_context(
    query_params,
    *,
    user,
    capital_amount: int | float = 600000,
    history_limit: int = 5,
) -> Dict:
    """Concentra el contrato incremental consumido por Planeacion en una sola fachada."""
    portfolio_scope_summary = _build_portfolio_scope_summary()
    monthly_allocation_plan = get_monthly_allocation_plan(capital_amount=capital_amount)
    candidate_asset_ranking = get_candidate_asset_ranking(capital_amount=capital_amount)
    incremental_portfolio_simulation = get_incremental_portfolio_simulation(capital_amount=capital_amount)
    incremental_portfolio_simulation_comparison = get_incremental_portfolio_simulation_comparison(
        capital_amount=capital_amount
    )
    candidate_incremental_portfolio_comparison = get_candidate_incremental_portfolio_comparison(
        query_params,
        capital_amount=capital_amount,
    )
    candidate_split_incremental_portfolio_comparison = get_candidate_split_incremental_portfolio_comparison(
        query_params,
        capital_amount=capital_amount,
    )
    manual_incremental_portfolio_simulation_comparison = get_manual_incremental_portfolio_simulation_comparison(
        query_params,
        default_capital_amount=capital_amount,
    )
    preferred_incremental_portfolio_proposal = get_preferred_incremental_portfolio_proposal(
        query_params,
        capital_amount=capital_amount,
    )
    decision_engine_summary = get_decision_engine_summary(
        user,
        query_params=query_params,
        capital_amount=capital_amount,
    )
    incremental_backlog_prioritization = get_incremental_backlog_prioritization(
        user=user,
        limit=history_limit,
        followup_filter=_query_param_value(query_params, "backlog_followup_filter"),
    )
    incremental_reactivation_summary = get_incremental_reactivation_summary(
        user=user,
        limit=min(history_limit, 3),
    )
    incremental_reactivation_vs_backlog_summary = _build_incremental_reactivation_vs_backlog_summary(
        incremental_reactivation_summary,
        incremental_backlog_prioritization,
    )
    incremental_proposal_history = get_incremental_proposal_history(
        user=user,
        limit=history_limit,
        decision_status=_query_param_value(query_params, "decision_status_filter"),
        priority_filter=_query_param_value(query_params, "history_priority_filter"),
        deferred_fit_filter=_query_param_value(query_params, "history_deferred_fit_filter"),
        future_purchase_source_filter=_query_param_value(query_params, "history_future_purchase_source_filter"),
        sort_mode=_query_param_value(query_params, "history_sort"),
        preferred_source=incremental_reactivation_vs_backlog_summary.get("preferred_source"),
        reactivated_snapshot_ids=[
            item.get("snapshot_id")
            for item in list(incremental_reactivation_summary.get("items") or [])
            if item.get("snapshot_id") is not None
        ],
    )
    incremental_proposal_tracking_baseline = get_incremental_proposal_tracking_baseline(user=user)
    incremental_manual_decision_summary = get_incremental_manual_decision_summary(user=user)
    incremental_future_purchase_shortlist = _build_incremental_future_purchase_shortlist(
        incremental_reactivation_summary,
        incremental_backlog_prioritization,
        incremental_reactivation_vs_backlog_summary,
        incremental_proposal_history.get("future_purchase_source_quality_summary") or {},
        limit=3,
    )
    incremental_future_purchase_source_guidance = _build_incremental_future_purchase_source_guidance(
        incremental_proposal_history.get("future_purchase_source_quality_summary") or {},
        incremental_future_purchase_shortlist,
        incremental_backlog_prioritization,
        incremental_reactivation_summary,
    )
    incremental_future_purchase_shortlist, incremental_proposal_history = _annotate_incremental_future_purchase_recommended_items(
        incremental_future_purchase_shortlist,
        incremental_proposal_history,
        incremental_future_purchase_source_guidance,
    )
    incremental_decision_executive_summary = get_incremental_decision_executive_summary(
        query_params,
        user=user,
        capital_amount=capital_amount,
        limit=history_limit,
    )

    return {
        "portfolio_scope_summary": portfolio_scope_summary,
        "monthly_allocation_plan": monthly_allocation_plan,
        "candidate_asset_ranking": candidate_asset_ranking,
        "incremental_portfolio_simulation": incremental_portfolio_simulation,
        "incremental_portfolio_simulation_comparison": incremental_portfolio_simulation_comparison,
        "candidate_incremental_portfolio_comparison": candidate_incremental_portfolio_comparison,
        "candidate_split_incremental_portfolio_comparison": candidate_split_incremental_portfolio_comparison,
        "manual_incremental_portfolio_simulation_comparison": manual_incremental_portfolio_simulation_comparison,
        "preferred_incremental_portfolio_proposal": preferred_incremental_portfolio_proposal,
        "decision_engine_summary": decision_engine_summary,
        "incremental_proposal_history": incremental_proposal_history,
        "incremental_proposal_tracking_baseline": incremental_proposal_tracking_baseline,
        "incremental_backlog_prioritization": incremental_backlog_prioritization,
        "incremental_manual_decision_summary": incremental_manual_decision_summary,
        "incremental_reactivation_summary": incremental_reactivation_summary,
        "incremental_reactivation_vs_backlog_summary": incremental_reactivation_vs_backlog_summary,
        "incremental_future_purchase_shortlist": incremental_future_purchase_shortlist,
        "incremental_future_purchase_source_guidance": incremental_future_purchase_source_guidance,
        "incremental_decision_executive_summary": incremental_decision_executive_summary,
    }


def get_incremental_followup_executive_summary(
    query_params,
    *,
    user,
    capital_amount: int | float = 600000,
) -> Dict:
    """Sintetiza una lectura ejecutiva de seguimiento incremental para Planeacion."""

    preferred_payload = get_preferred_incremental_portfolio_proposal(query_params, capital_amount=capital_amount)
    baseline_payload = get_incremental_proposal_tracking_baseline(user=user)
    drift_payload = get_incremental_baseline_drift(query_params, user=user, capital_amount=capital_amount)

    preferred = preferred_payload.get("preferred")
    baseline = baseline_payload.get("item")
    drift_status = drift_payload.get("summary", {}).get("status", "unavailable")

    if preferred is None:
        status = "pending"
    elif baseline is None:
        status = "no_baseline"
    elif drift_status == "unfavorable":
        status = "review"
    elif drift_status == "mixed":
        status = "watch"
    elif drift_status in {"favorable", "stable"}:
        status = "aligned"
    else:
        status = "watch"

    headline = _build_incremental_followup_headline(status, preferred, baseline)
    summary_items = _build_incremental_followup_summary_items(preferred, baseline, drift_payload)
    return {
        "status": status,
        "headline": headline,
        "summary_items": summary_items,
        "preferred": preferred,
        "baseline": baseline,
        "drift": drift_payload,
        "has_preferred": preferred is not None,
        "has_baseline": baseline is not None,
        "has_summary": bool(preferred or baseline),
    }


def get_incremental_adoption_checklist(
    query_params,
    *,
    user,
    capital_amount: int | float = 600000,
) -> Dict:
    """Construye un checklist operativo para decidir adopcion de la propuesta incremental actual."""

    preferred_payload = get_preferred_incremental_portfolio_proposal(query_params, capital_amount=capital_amount)
    baseline_payload = get_incremental_proposal_tracking_baseline(user=user)
    drift_payload = get_incremental_baseline_drift(query_params, user=user, capital_amount=capital_amount)
    executive_payload = get_incremental_followup_executive_summary(query_params, user=user, capital_amount=capital_amount)

    preferred = preferred_payload.get("preferred")
    baseline = baseline_payload.get("item")
    drift_status = drift_payload.get("summary", {}).get("status", "unavailable")
    drift_alerts = list(drift_payload.get("alerts") or [])

    items = [
        _build_incremental_adoption_check_item(
            key="preferred_available",
            label="Existe propuesta incremental preferida",
            passed=preferred is not None,
            detail=preferred.get("proposal_label") if preferred else "Todavia no hay propuesta incremental construible.",
        ),
        _build_incremental_adoption_check_item(
            key="purchase_plan_available",
            label="La propuesta tiene compra resumida",
            passed=bool((preferred or {}).get("purchase_plan")),
            detail=_format_incremental_purchase_plan_summary((preferred or {}).get("purchase_plan") or []),
        ),
        _build_incremental_adoption_check_item(
            key="baseline_defined",
            label="Existe baseline incremental activo",
            passed=baseline is not None,
            detail=baseline.get("proposal_label") if baseline else "Conviene fijar una referencia antes de adoptar.",
        ),
        _build_incremental_adoption_check_item(
            key="drift_not_unfavorable",
            label="El drift no es desfavorable frente al baseline",
            passed=drift_status != "unfavorable",
            detail=_format_incremental_followup_status(drift_status),
        ),
        _build_incremental_adoption_check_item(
            key="critical_drift_alerts",
            label="No hay alertas criticas de drift",
            passed=not any(alert.get("severity") == "critical" for alert in drift_alerts),
            detail=_summarize_incremental_drift_alerts(drift_alerts),
        ),
    ]

    passed_count = sum(1 for item in items if item["passed"])
    adoption_ready = all(item["passed"] for item in items[:2]) and items[3]["passed"] and items[4]["passed"]
    status = "ready" if adoption_ready else "review"
    if preferred is None:
        status = "pending"

    return {
        "status": status,
        "adoption_ready": adoption_ready,
        "items": items,
        "passed_count": passed_count,
        "total_count": len(items),
        "headline": _build_incremental_adoption_checklist_headline(status, executive_payload, preferred, baseline),
    }


def _candidate_blocks_map(candidate_ranking: Dict) -> Dict[str, Dict]:
    return {
        str(item.get("block") or ""): item
        for item in candidate_ranking.get("by_block", [])
    }


def _build_incremental_snapshot_comparison(saved_item: Dict, current_item: Dict) -> Dict:
    saved_score = _coerce_optional_float(saved_item.get("comparison_score"))
    current_score = _coerce_optional_float(current_item.get("comparison_score"))
    saved_delta = dict(saved_item.get("simulation_delta") or (saved_item.get("simulation") or {}).get("delta") or {})
    current_delta = dict(current_item.get("simulation_delta") or (current_item.get("simulation") or {}).get("delta") or {})

    metrics = []
    for key, label in (
        ("expected_return_change", "Expected return"),
        ("real_expected_return_change", "Real expected return"),
        ("fragility_change", "Fragility"),
        ("scenario_loss_change", "Worst scenario loss"),
        ("risk_concentration_change", "Top risk concentration"),
    ):
        saved_value = _coerce_optional_float(saved_delta.get(key))
        current_value = _coerce_optional_float(current_delta.get(key))
        direction = _classify_incremental_metric_direction(key, saved_value, current_value)
        metrics.append(
            {
                "key": key,
                "label": label,
                "saved_value": saved_value,
                "current_value": current_value,
                "difference": None if saved_value is None or current_value is None else round(current_value - saved_value, 4),
                "direction": direction,
            }
        )

    return {
        "score_saved": saved_score,
        "score_current": current_score,
        "score_difference": None if saved_score is None or current_score is None else round(current_score - saved_score, 4),
        "metrics": metrics,
        "winner": _resolve_incremental_snapshot_winner(saved_score, current_score),
    }


def _build_incremental_baseline_drift_summary(comparison: Dict | None) -> Dict:
    if comparison is None:
        return {
            "status": "unavailable",
            "favorable_count": 0,
            "unfavorable_count": 0,
            "changed_count": 0,
            "material_metrics": [],
        }

    material_metrics = []
    favorable_count = 0
    unfavorable_count = 0
    for metric in comparison.get("metrics", []):
        direction = metric.get("direction") or "neutral"
        if direction == "neutral":
            continue
        enriched_metric = dict(metric)
        enriched_metric["direction"] = direction
        material_metrics.append(enriched_metric)
        if direction == "favorable":
            favorable_count += 1
        elif direction == "unfavorable":
            unfavorable_count += 1

    if favorable_count and not unfavorable_count:
        status = "favorable"
    elif unfavorable_count and not favorable_count:
        status = "unfavorable"
    elif favorable_count or unfavorable_count:
        status = "mixed"
    else:
        status = "stable"

    return {
        "status": status,
        "favorable_count": favorable_count,
        "unfavorable_count": unfavorable_count,
        "changed_count": len(material_metrics),
        "material_metrics": material_metrics,
    }


def _classify_incremental_metric_direction(metric_key: str, saved_value: float | None, current_value: float | None) -> str:
    if saved_value is None or current_value is None:
        return "neutral"
    diff = round(current_value - saved_value, 4)
    if abs(diff) < 0.0001:
        return "neutral"

    higher_is_better = metric_key in {
        "expected_return_change",
        "real_expected_return_change",
        "scenario_loss_change",
    }
    if higher_is_better:
        return "favorable" if diff > 0 else "unfavorable"
    return "favorable" if diff < 0 else "unfavorable"


def _resolve_incremental_snapshot_winner(saved_score: float | None, current_score: float | None) -> str | None:
    if saved_score is None and current_score is None:
        return None
    if saved_score is None:
        return "current"
    if current_score is None:
        return "saved"
    if current_score > saved_score:
        return "current"
    if current_score < saved_score:
        return "saved"
    return "tie"


def _build_incremental_baseline_drift_explanation(
    baseline_item: Dict | None,
    current_item: Dict | None,
    comparison: Dict | None,
    summary: Dict,
) -> str:
    if not baseline_item and not current_item:
        return "Todavia no hay baseline incremental activo ni propuesta preferida actual para medir drift."
    if not baseline_item:
        return "Todavia no hay un baseline incremental activo para medir drift contra la propuesta preferida actual."
    if not current_item:
        return "Todavia no hay una propuesta preferida actual construible para medir drift contra el baseline activo."
    if comparison is None:
        return "No fue posible construir el drift entre el baseline incremental activo y la propuesta preferida actual."

    status = summary.get("status")
    if status == "favorable":
        return (
            f"La propuesta preferida actual ({current_item['proposal_label']}) mejora el baseline activo "
            f"({baseline_item['proposal_label']}) en las metricas incrementales relevantes."
        )
    if status == "unfavorable":
        return (
            f"La propuesta preferida actual ({current_item['proposal_label']}) empeora frente al baseline activo "
            f"({baseline_item['proposal_label']}) y conviene revisarla antes de reemplazar la referencia."
        )
    if status == "mixed":
        return (
            f"La propuesta preferida actual ({current_item['proposal_label']}) se desvia del baseline activo "
            f"({baseline_item['proposal_label']}) con mejoras y deterioros mezclados."
        )
    return (
        f"La propuesta preferida actual ({current_item['proposal_label']}) se mantiene alineada con el baseline activo "
        f"({baseline_item['proposal_label']}) sin drift material en los deltas principales."
    )


def _build_incremental_baseline_drift_alerts(
    baseline_item: Dict | None,
    current_item: Dict | None,
    summary: Dict,
) -> list[Dict]:
    if baseline_item is None or current_item is None:
        return []

    alerts: list[Dict] = []
    status = summary.get("status")
    if status == "unfavorable":
        alerts.append(
            {
                "severity": "critical" if summary.get("unfavorable_count", 0) >= 2 else "warning",
                "title": "La propuesta actual empeora frente al baseline",
                "message": (
                    f"{current_item['proposal_label']} queda por debajo de {baseline_item['proposal_label']} "
                    "en las metricas incrementales relevantes."
                ),
            }
        )
    elif status == "mixed":
        alerts.append(
            {
                "severity": "warning",
                "title": "Hay drift mixto respecto del baseline",
                "message": (
                    f"{current_item['proposal_label']} mejora algunas metricas pero deteriora otras frente a "
                    f"{baseline_item['proposal_label']}."
                ),
            }
        )
    elif status == "stable":
        alerts.append(
            {
                "severity": "info",
                "title": "No hay drift material",
                "message": (
                    f"{current_item['proposal_label']} se mantiene alineada con el baseline activo "
                    f"{baseline_item['proposal_label']}."
                ),
            }
        )

    for metric in summary.get("material_metrics", []):
        if metric.get("direction") != "unfavorable":
            continue
        alerts.append(
            {
                "severity": "warning",
                "title": f"Drift desfavorable en {metric['label']}",
                "message": (
                    f"El delta actual ({metric.get('current_value')}) queda peor que el baseline "
                    f"({metric.get('saved_value')}) en {metric['label']}."
                ),
            }
        )
    return alerts


def _build_incremental_followup_headline(status: str, preferred: Dict | None, baseline: Dict | None) -> str:
    if status == "pending":
        return "Todavia no hay una propuesta incremental preferida para seguimiento."
    if status == "no_baseline":
        return (
            f"La propuesta actual ({preferred['proposal_label']}) ya esta lista para seguimiento, "
            "pero todavia no definiste un baseline activo."
        )
    if status == "review":
        return (
            f"La propuesta actual ({preferred['proposal_label']}) se desvio en forma desfavorable respecto del baseline "
            f"({baseline['proposal_label']}) y conviene revisarla antes de adoptarla."
        )
    if status == "watch":
        return (
            f"La propuesta actual ({preferred['proposal_label']}) muestra drift mixto frente al baseline "
            f"({baseline['proposal_label']}) y requiere seguimiento cercano."
        )
    return (
        f"La propuesta actual ({preferred['proposal_label']}) se mantiene alineada con el baseline "
        f"({baseline['proposal_label']})."
    )


def _build_incremental_followup_summary_items(
    preferred: Dict | None,
    baseline: Dict | None,
    drift_payload: Dict,
) -> list[Dict]:
    summary = drift_payload.get("summary", {})
    preferred_score = _coerce_optional_float((preferred or {}).get("comparison_score"))
    baseline_score = _coerce_optional_float((baseline or {}).get("comparison_score"))
    score_diff = None if preferred_score is None or baseline_score is None else round(preferred_score - baseline_score, 4)
    return [
        {
            "label": "Propuesta actual",
            "value": (preferred or {}).get("proposal_label") or "-",
        },
        {
            "label": "Baseline activo",
            "value": (baseline or {}).get("proposal_label") or "-",
        },
        {
            "label": "Estado de drift",
            "value": _format_incremental_followup_status(summary.get("status", "unavailable")),
        },
        {
            "label": "Score actual - baseline",
            "value": score_diff if score_diff is not None else "-",
        },
        {
            "label": "Métricas favorables",
            "value": summary.get("favorable_count", 0),
        },
        {
            "label": "Métricas desfavorables",
            "value": summary.get("unfavorable_count", 0),
        },
    ]


def _format_incremental_followup_status(status: str) -> str:
    mapping = {
        "favorable": "Drift favorable",
        "unfavorable": "Drift desfavorable",
        "mixed": "Drift mixto",
        "stable": "Sin drift material",
        "unavailable": "Sin comparacion",
    }
    return mapping.get(status, "Sin clasificar")


def _build_incremental_adoption_check_item(*, key: str, label: str, passed: bool, detail: str) -> Dict:
    return {
        "key": key,
        "label": label,
        "passed": bool(passed),
        "detail": str(detail or "-"),
    }


def _format_incremental_manual_decision_status(status: str) -> str:
    mapping = {
        "accepted": "Aceptada",
        "deferred": "Diferida",
        "rejected": "Rechazada",
        "pending": "Pendiente",
    }
    return mapping.get(status, "Pendiente")


def _build_incremental_manual_decision_headline(item: Dict | None) -> str:
    if item is None:
        return "Todavia no registraste una decision manual sobre snapshots incrementales guardados."

    decision_label = _format_incremental_manual_decision_status(str(item.get("manual_decision_status") or "pending")).lower()
    note = str(item.get("manual_decision_note") or "").strip()
    base = f"La ultima decision manual registrada es {decision_label} sobre {item.get('proposal_label') or 'la propuesta seleccionada'}."
    if note:
        return f"{base} Nota: {note}"
    return base


def _normalize_incremental_history_decision_filter(decision_status: str | None) -> str | None:
    normalized = str(decision_status or "").strip().lower()
    if normalized in {"pending", "accepted", "deferred", "rejected"}:
        return normalized
    return None


def _format_incremental_history_decision_filter_label(decision_status: str | None) -> str:
    if decision_status is None:
        return "Todos"
    return _format_incremental_manual_decision_status(decision_status)


def _build_incremental_history_available_filters(active_filter: str | None, counts: Dict) -> list[Dict]:
    options = [None, "pending", "accepted", "deferred", "rejected"]
    items = []
    for option in options:
        key = option or "all"
        items.append(
            {
                "key": key,
                "label": _format_incremental_history_decision_filter_label(option),
                "count": int(counts.get("total", 0) if option is None else counts.get(option, 0)),
                "selected": (active_filter or "all") == key,
            }
        )
    return items


def _build_incremental_history_headline(
    decision_status: str | None,
    counts: Dict,
    visible_count: int,
    *,
    priority_filter: str | None = None,
    deferred_fit_filter: str | None = None,
    future_purchase_source_filter: str | None = None,
    sort_mode: str | None = None,
) -> str:
    total = int(counts.get("total", 0))
    if total == 0:
        return "Todavia no guardaste propuestas incrementales para seguimiento manual."
    if decision_status is None:
        base = f"Se muestran {visible_count} snapshots recientes sobre un total de {total} propuestas guardadas."
    else:
        label = _format_incremental_history_decision_filter_label(decision_status).lower()
        base = f"Se muestran {visible_count} snapshots con decision {label}."

    suffix = []
    if priority_filter:
        suffix.append(f"Prioridad: {_format_incremental_history_priority_filter_label(priority_filter)}")
    if deferred_fit_filter:
        suffix.append(f"Diferidas: {_format_incremental_history_deferred_fit_filter_label(deferred_fit_filter)}")
    if future_purchase_source_filter:
        suffix.append(f"Fuente: {_format_incremental_future_purchase_source_filter_label(future_purchase_source_filter)}")
    if str(sort_mode or "").strip().lower() == "priority":
        suffix.append("Ordenados por prioridad operativa")
    if str(sort_mode or "").strip().lower() == "future_purchase":
        suffix.append("Ordenados para futuras compras")
    if suffix:
        return f"{base} {' · '.join(suffix)}."
    return base


def _build_incremental_pending_backlog_headline(
    baseline_item: Dict | None,
    pending_history: Dict,
    better_count: int,
    worse_count: int,
    tie_count: int,
) -> str:
    pending_count = int(pending_history.get("decision_counts", {}).get("pending", pending_history.get("count", 0)))
    if baseline_item is None and pending_count == 0:
        return "No hay baseline activo ni backlog pendiente para seguimiento operativo."
    if baseline_item is None:
        return "Hay backlog incremental pendiente, pero todavia no existe baseline activo para compararlo."
    if pending_count == 0:
        return "No hay snapshots pendientes en el backlog incremental contra el baseline activo."
    return (
        f"Hay {pending_count} snapshot(s) pendientes: {better_count} superan el baseline, "
        f"{worse_count} quedan por debajo y {tie_count} empatan."
    )


def _build_incremental_pending_backlog_explanation(
    baseline_item: Dict | None,
    pending_history: Dict,
    best_candidate: Dict | None,
    better_count: int,
    worse_count: int,
) -> str:
    pending_count = int(pending_history.get("decision_counts", {}).get("pending", pending_history.get("count", 0)))
    if baseline_item is None and pending_count == 0:
        return "Todavia no hay baseline incremental activo ni snapshots pendientes para comparar."
    if baseline_item is None:
        return "Conviene fijar un baseline incremental activo antes de priorizar el backlog pendiente."
    if pending_count == 0:
        return (
            f"El baseline activo ({baseline_item.get('proposal_label') or 'sin etiqueta'}) no tiene backlog pendiente "
            "contra el cual compararse."
        )
    if best_candidate and best_candidate.get("beats_baseline"):
        snapshot = best_candidate["snapshot"]
        return (
            f"El backlog pendiente ya contiene al menos una alternativa superior al baseline activo: "
            f"{snapshot.get('proposal_label') or 'snapshot pendiente'}."
        )
    if worse_count == pending_count:
        return (
            f"Todas las propuestas pendientes quedan por debajo del baseline activo "
            f"({baseline_item.get('proposal_label') or 'sin etiqueta'})."
        )
    return (
        f"El backlog pendiente frente al baseline activo ({baseline_item.get('proposal_label') or 'sin etiqueta'}) "
        "muestra resultados mixtos y conviene revisar primero las alternativas con mejor score."
    )


def _classify_incremental_backlog_priority(item: Dict) -> str:
    if item.get("beats_baseline") and item.get("improves_profitability") and item.get("protects_fragility") and item.get("tactical_clean"):
        return "high"
    if item.get("beats_baseline"):
        return "medium"
    if item.get("ties_baseline"):
        return "watch"
    return "low"


def _format_incremental_backlog_priority(priority: str) -> str:
    mapping = {
        "high": "Alta",
        "medium": "Recuperable",
        "watch": "Observación",
        "low": "Baja",
    }
    return mapping.get(priority, "Baja")


def _incremental_backlog_priority_order(priority: str) -> int:
    mapping = {
        "high": 0,
        "medium": 1,
        "watch": 2,
        "low": 3,
    }
    return mapping.get(priority, 4)


def _build_incremental_backlog_next_action(priority: str, item: Dict) -> str:
    proposal_label = item.get("snapshot", {}).get("proposal_label") or "este snapshot"
    if item.get("snapshot", {}).get("is_backlog_front"):
        return f"{proposal_label} ya esta marcado al frente del backlog para revision prioritaria."
    if priority == "high":
        return f"Revisar primero {proposal_label}: mejora baseline, cuida fragilidad y mantiene buena ejecutabilidad tactica."
    if priority == "medium":
        return f"Revisar {proposal_label} como candidata recuperable: mejora baseline, pero todavia no es la opcion mas limpia."
    if priority == "watch":
        return f"Mantener {proposal_label} en observacion; hoy empata con el baseline o mejora parcialmente."
    return f"Dejar {proposal_label} al final del backlog operativo mientras no mejore su comparacion."


def _build_incremental_backlog_prioritization_headline(backlog_payload: Dict, counts: Dict, top_item: Dict | None) -> str:
    if not backlog_payload.get("has_baseline") and not backlog_payload.get("has_pending_backlog"):
        return "Todavia no hay backlog pendiente priorizable ni baseline activo."
    if not backlog_payload.get("has_baseline"):
        return "Hay backlog pendiente, pero falta baseline activo para priorizarlo con criterio comparativo."
    if not backlog_payload.get("has_pending_backlog"):
        return "No hay snapshots pendientes para priorizar contra el baseline activo."
    if top_item is None:
        return "No fue posible priorizar el backlog pendiente contra el baseline activo."
    if top_item.get("snapshot", {}).get("is_backlog_front"):
        return (
            f"Backlog priorizado con frente manual: {top_item.get('snapshot', {}).get('proposal_label') or 'snapshot al frente'} "
            "queda primero para revision operativa."
        )
    return (
        f"Backlog priorizado: {counts.get('high', 0)} alta, {counts.get('medium', 0)} media y "
        f"{counts.get('low', 0)} baja. Primero revisar {top_item.get('snapshot', {}).get('proposal_label') or 'el snapshot prioritario'}."
    )


def _build_incremental_backlog_prioritization_explanation(backlog_payload: Dict, counts: Dict, top_item: Dict | None) -> str:
    if not backlog_payload.get("has_baseline") and not backlog_payload.get("has_pending_backlog"):
        return "Todavia no hay insumos para una priorizacion operativa del backlog incremental."
    if not backlog_payload.get("has_baseline"):
        return "La priorizacion explicita del backlog requiere primero un baseline incremental activo."
    if not backlog_payload.get("has_pending_backlog"):
        return "No hay backlog pendiente por ordenar en este momento."
    if top_item is not None and top_item.get("snapshot", {}).get("is_backlog_front"):
        return (
            f"{top_item.get('snapshot', {}).get('proposal_label') or 'El snapshot elegido'} fue promovido manualmente "
            "al frente del backlog y queda primero en la lectura operativa."
        )
    if counts.get("high", 0) > 0 and top_item is not None:
        return (
            f"El backlog ya contiene alternativas que superan el baseline activo con mejor retorno esperado, "
            f"sin deterioro material de fragilidad y con buena ejecutabilidad tactica; "
            f"{top_item.get('snapshot', {}).get('proposal_label') or 'la primera opcion'} queda arriba por prioridad."
        )
    if counts.get("medium", 0) > 0:
        return "El backlog incluye alternativas recuperables: mejoran baseline, pero todavia no muestran el balance tactico mas limpio."
    if counts.get("watch", 0) > 0:
        return "El backlog muestra alternativas en observacion: empatan baseline o mejoran solo una parte de la ecuacion riesgo-retorno."
    return "El backlog pendiente actual queda por debajo del baseline activo y puede revisarse al final."


def _build_incremental_backlog_front_summary_headline(status: str, baseline: Dict | None, front_item: Dict | None) -> str:
    if status == "empty":
        return "Todavia no hay baseline activo ni backlog incremental priorizable."
    if status == "no_baseline":
        return (
            f"El backlog incremental ya tiene un frente operativo ({front_item.get('snapshot', {}).get('proposal_label') or 'snapshot'}) "
            "pero falta baseline activo."
        )
    if status == "baseline_only":
        return (
            f"El baseline activo ({baseline.get('proposal_label') or 'sin etiqueta'}) no tiene backlog priorizable por delante."
        )
    if status == "manual_front":
        return (
            f"{front_item.get('snapshot', {}).get('proposal_label') or 'El snapshot al frente'} lidera el backlog por "
            f"marcacion manual frente al baseline {baseline.get('proposal_label') or 'activo'}."
        )
    if status == "candidate_over_baseline":
        return (
            f"{front_item.get('snapshot', {}).get('proposal_label') or 'El frente del backlog'} ya supera al baseline "
            f"{baseline.get('proposal_label') or 'activo'}."
        )
    if status == "watch":
        return (
            f"El frente del backlog ({front_item.get('snapshot', {}).get('proposal_label') or 'snapshot'}) empata con el "
            f"baseline {baseline.get('proposal_label') or 'activo'} y conviene seguirlo de cerca."
        )
    return (
        f"El baseline activo ({baseline.get('proposal_label') or 'sin etiqueta'}) sigue por delante del backlog incremental."
    )


def _build_incremental_backlog_front_summary_items(
    baseline: Dict | None,
    front_item: Dict | None,
    prioritization_payload: Dict,
) -> list[Dict]:
    snapshot = (front_item or {}).get("snapshot", {})
    return [
        {
            "label": "Baseline activo",
            "value": (baseline or {}).get("proposal_label") or "-",
        },
        {
            "label": "Frente del backlog",
            "value": snapshot.get("proposal_label") or "-",
        },
        {
            "label": "Prioridad del frente",
            "value": (front_item or {}).get("priority_label") or "-",
        },
        {
            "label": "Score vs baseline",
            "value": (front_item or {}).get("score_difference") if front_item is not None else "-",
        },
        {
            "label": "Pendientes alta prioridad",
            "value": prioritization_payload.get("counts", {}).get("high", 0),
        },
    ]


def _format_incremental_operational_semaphore(status: str) -> str:
    mapping = {
        "green": "Verde",
        "yellow": "Amarillo",
        "red": "Rojo",
        "gray": "Sin señal",
    }
    return mapping.get(status, "Sin señal")


def _build_incremental_operational_semaphore_headline(status: str, front_summary: Dict, drift_payload: Dict) -> str:
    if status == "red":
        return "Semáforo rojo: la propuesta actual empeora frente al baseline y conviene frenar cambios."
    if status == "yellow":
        return front_summary.get("headline") or "Semáforo amarillo: hay backlog incremental que merece revisión."
    if status == "green":
        return "Semáforo verde: el baseline actual se mantiene sólido y no hay backlog urgente por delante."
    return drift_payload.get("explanation") or "Todavía no hay suficiente señal operativa incremental."


def _build_incremental_operational_semaphore_items(
    drift_payload: Dict,
    front_summary: Dict,
    prioritization: Dict,
) -> list[Dict]:
    return [
        {
            "label": "Drift vs baseline",
            "value": _format_incremental_followup_status(drift_payload.get("summary", {}).get("status", "unavailable")),
        },
        {
            "label": "Frente del backlog",
            "value": ((front_summary.get("front_item") or {}).get("snapshot") or {}).get("proposal_label") or "-",
        },
        {
            "label": "Pendientes alta prioridad",
            "value": prioritization.get("counts", {}).get("high", 0),
        },
    ]


def _build_incremental_decision_executive_headline(
    status: str,
    semaphore: Dict,
    followup: Dict,
    checklist: Dict,
    front_summary: Dict,
) -> str:
    if status == "adopt":
        return "La propuesta incremental actual queda lista para adopción y el baseline no muestra presión operativa."
    if status == "hold":
        return "Conviene sostener el baseline actual y frenar cambios hasta resolver el drift desfavorable."
    if status == "review_backlog":
        return front_summary.get("headline") or "Hay backlog incremental que merece revisión antes de adoptar."
    if status == "review_current":
        return checklist.get("headline") or "La propuesta actual todavía requiere revisión operativa."
    return followup.get("headline") or "Todavía no hay una señal ejecutiva suficiente para decidir."


def _build_incremental_decision_executive_items(
    semaphore: Dict,
    followup: Dict,
    checklist: Dict,
    front_summary: Dict,
) -> list[Dict]:
    items = [
        {
            "label": "Semáforo operativo",
            "value": semaphore.get("label") or "Sin señal",
        },
        {
            "label": "Checklist de adopción",
            "value": f"{checklist.get('passed_count', 0)}/{checklist.get('total_count', 0)}",
        },
        {
            "label": "Estado ejecutivo actual",
            "value": followup.get("status") or "-",
        },
        {
            "label": "Frente del backlog",
            "value": ((front_summary.get("front_item") or {}).get("snapshot") or {}).get("proposal_label") or "-",
        },
    ]
    return items


def _format_incremental_purchase_plan_summary(purchase_plan: list[Dict]) -> str:
    summary = build_incremental_purchase_plan_summary(purchase_plan)
    if not summary:
        return "Sin compra resumida disponible."
    return summary


def _summarize_incremental_drift_alerts(alerts: list[Dict]) -> str:
    if not alerts:
        return "Sin alertas activas."
    critical_titles = [alert.get("title") for alert in alerts if alert.get("severity") == "critical"]
    if critical_titles:
        return ", ".join(str(title) for title in critical_titles if title)
    return f"{len(alerts)} alerta(s) de drift no criticas."


def _build_incremental_adoption_checklist_headline(
    status: str,
    executive_payload: Dict,
    preferred: Dict | None,
    baseline: Dict | None,
) -> str:
    if status == "pending":
        return "Todavia no hay una propuesta incremental lista para pasar por checklist de adopcion."
    if status == "ready":
        return (
            f"La propuesta actual ({preferred['proposal_label']}) supera el checklist operativo y puede "
            "pasar a decision manual."
        )
    if baseline is None:
        return (
            f"La propuesta actual ({preferred['proposal_label']}) todavia requiere contexto adicional: "
            "conviene fijar un baseline antes de adoptarla."
        )
    return executive_payload.get("headline") or (
        f"La propuesta actual ({preferred['proposal_label']}) todavia requiere revision antes de adopcion."
    )


def _build_incremental_snapshot_reapply_payload(item: Dict) -> Dict:
    purchase_plan = list(item.get("purchase_plan") or [])
    query_items = [("manual_compare", "1")]
    capital_amount = item.get("capital_amount")
    if capital_amount:
        query_items.append(("plan_a_capital", _stringify_reapply_amount(capital_amount)))

    for index, purchase in enumerate(purchase_plan[:3], start=1):
        query_items.append((f"plan_a_symbol_{index}", str(purchase.get("symbol") or "").strip().upper()))
        query_items.append((f"plan_a_amount_{index}", _stringify_reapply_amount(purchase.get("amount") or 0)))

    return {
        "reapply_querystring": urlencode(query_items),
        "reapply_truncated": len(purchase_plan) > 3,
    }


def _stringify_reapply_amount(value) -> str:
    amount = float(value or 0)
    if amount.is_integer():
        return str(int(amount))
    return f"{amount:.2f}"


def _coerce_optional_float(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _build_decision_engine_query_stamp(query_params) -> str:
    if query_params is None:
        return "none"
    if isinstance(query_params, dict):
        items = sorted((str(key), str(value)) for key, value in query_params.items())
        return urlencode(items)
    items_method = getattr(query_params, "lists", None)
    if callable(items_method):
        normalized = []
        for key, values in query_params.lists():
            for value in values:
                normalized.append((str(key), str(value)))
        return urlencode(sorted(normalized))
    return str(query_params)


def _build_decision_macro_state(macro_local: Dict | None) -> Dict:
    macro_local = macro_local or {}
    fx_state = str(macro_local.get("fx_signal_state") or "").strip().lower()
    riesgo_pais = _coerce_optional_float(macro_local.get("riesgo_pais_arg"))
    uva_annualized = _coerce_optional_float(macro_local.get("uva_annualized_pct_30d"))

    if fx_state == "divergent" or (riesgo_pais is not None and riesgo_pais >= 900):
        return {
            "key": "crisis",
            "label": "Crisis",
            "score_component": 4,
            "summary": "El contexto local exige maxima cautela antes de sumar riesgo.",
        }
    if fx_state == "tensioned" or (riesgo_pais is not None and riesgo_pais >= 700) or (
        uva_annualized is not None and uva_annualized >= 35
    ):
        return {
            "key": "tension",
            "label": "Tension",
            "score_component": 13,
            "summary": "Hay tension local y conviene evitar decisiones agresivas.",
        }
    if fx_state or riesgo_pais is not None or uva_annualized is not None:
        return {
            "key": "normal",
            "label": "Normal",
            "score_component": 25,
            "summary": "No hay una senal macro dominante que invalide el flujo principal.",
        }
    return {
        "key": "indefinido",
        "label": "Indefinido",
        "score_component": 12,
        "summary": "Falta contexto macro suficiente para una lectura mas firme.",
    }


def _build_decision_portfolio_state(analytics: Dict | None) -> Dict:
    analytics = analytics or {}
    stress = analytics.get("stress_testing") or {}
    expected = analytics.get("expected_return") or {}
    risk = analytics.get("risk_contribution") or {}
    top_asset = risk.get("top_asset") or {}

    fragility_score = _coerce_optional_float(stress.get("fragility_score"))
    total_loss_pct = _coerce_optional_float(stress.get("total_loss_pct"))
    real_expected_return_pct = _coerce_optional_float(expected.get("real_expected_return_pct"))
    top_asset_contribution = _coerce_optional_float(top_asset.get("contribution_pct"))

    if (fragility_score is not None and fragility_score >= 70) or (
        total_loss_pct is not None and total_loss_pct < -20
    ):
        return {
            "key": "riesgo",
            "label": "Riesgo",
            "score_component": 5,
            "summary": "La cartera ya muestra fragilidad relevante y pide prudencia.",
        }
    if (real_expected_return_pct is not None and real_expected_return_pct < 0) or (
        top_asset_contribution is not None and top_asset_contribution > 0.25
    ):
        return {
            "key": "desbalance",
            "label": "Desbalance",
            "score_component": 14,
            "summary": "Hay senales de concentracion o retorno real debil a corregir.",
        }
    if (
        fragility_score is not None
        or total_loss_pct is not None
        or real_expected_return_pct is not None
        or top_asset_contribution is not None
    ):
        return {
            "key": "ok",
            "label": "OK",
            "score_component": 25,
            "summary": "La cartera admite un aporte incremental sin desviar el flujo principal.",
        }
    return {
        "key": "indefinido",
        "label": "Indefinido",
        "score_component": 12,
        "summary": "Falta contexto suficiente sobre el estado actual de la cartera.",
    }


def _normalize_decision_block_label(value: str | None) -> str:
    normalized = unicodedata.normalize("NFKD", str(value or "").strip().lower())
    ascii_only = "".join(char for char in normalized if not unicodedata.combining(char))
    return " ".join(ascii_only.replace("/", " ").split())


def _has_block_overlap(target_block: str | None, candidate_blocks: list[Dict] | list[str] | None) -> bool:
    target = _normalize_decision_block_label(target_block)
    if not target:
        return False
    for item in candidate_blocks or []:
        if isinstance(item, dict):
            candidate = _normalize_decision_block_label(item.get("label"))
        else:
            candidate = _normalize_decision_block_label(item)
        if candidate and (candidate == target or candidate in target or target in candidate):
            return True
    return False


def _is_parking_overlap_with_recommendation(recommendation_block: str | None, parking_blocks: list[Dict] | None) -> bool:
    return _has_block_overlap(recommendation_block, parking_blocks)


def _is_market_history_overlap_with_recommendation(
    recommendation_block: str | None,
    weak_blocks: list[Dict] | list[str] | None,
) -> bool:
    return _has_block_overlap(recommendation_block, weak_blocks)


def _should_promote_clean_recommendation_alternative(primary_block: dict, alternative_block: dict) -> bool:
    primary_amount = _coerce_optional_float(primary_block.get("suggested_amount")) or 0.0
    alternative_amount = _coerce_optional_float(alternative_block.get("suggested_amount")) or 0.0
    if primary_amount <= 0:
        return alternative_amount > 0
    return alternative_amount >= (primary_amount * 0.5)


def _build_decision_recommendation(
    monthly_plan: Dict | None,
    *,
    parking_feature: Dict | None = None,
    market_history_feature: Dict | None = None,
) -> Dict:
    monthly_plan = monthly_plan or {}
    recommended_blocks = list(monthly_plan.get("recommended_blocks") or [])
    primary_block = next(iter(recommended_blocks), None)
    if not primary_block:
        return {
            "block": None,
            "amount": None,
            "reason": "Todavia no hay un bloque dominante para este mes.",
            "has_recommendation": False,
            "priority_label": "Sin prioridad",
            "priority_tone": "secondary",
            "is_conditioned_by_parking": False,
        }
    block_label = primary_block.get("label")
    reason = str(primary_block.get("reason") or "").strip()
    parking_overlap = _is_parking_overlap_with_recommendation(
        block_label,
        (parking_feature or {}).get("parking_blocks") or [],
    )
    market_history_overlap = _is_market_history_overlap_with_recommendation(
        block_label,
        (market_history_feature or {}).get("weak_blocks") or [],
    )
    if market_history_overlap:
        clean_alternative = next(
            (
                block for block in recommended_blocks[1:]
                if not _is_market_history_overlap_with_recommendation(
                    str(block.get("label") or "").strip(),
                    (market_history_feature or {}).get("weak_blocks") or [],
                )
                and _should_promote_clean_recommendation_alternative(primary_block, block)
            ),
            None,
        )
        if clean_alternative is not None:
            alternative_label = str(clean_alternative.get("label") or "").strip()
            alternative_reason = str(clean_alternative.get("reason") or "").strip()
            return {
                "block": alternative_label,
                "amount": _coerce_optional_float(clean_alternative.get("suggested_amount")),
                "reason": (
                    f"Se prioriza {alternative_label} porque el bloque original {block_label} viene con liquidez reciente debil. "
                    f"{alternative_reason or 'La alternativa limpia conserva una asignacion razonable dentro del mismo plan mensual.'}"
                ).strip(),
                "has_recommendation": True,
                "priority_label": "Repriorizada por liquidez reciente",
                "priority_tone": "warning",
                "is_conditioned_by_parking": False,
                "is_conditioned_by_market_history": False,
                "was_reprioritized_by_market_history": True,
                "original_block_label": block_label,
            }
    if parking_overlap:
        reason = f"{reason} Hay parking visible dentro de este mismo bloque y conviene revisar la restriccion antes de ejecutar."
    elif market_history_overlap:
        reason = f"{reason} La liquidez reciente de este bloque viene debil y conviene revisar spread y actividad antes de tomarlo como prioridad limpia."
    return {
        "block": block_label,
        "amount": _coerce_optional_float(primary_block.get("suggested_amount")),
        "reason": reason,
        "has_recommendation": True,
        "priority_label": "Condicionada" if (parking_overlap or market_history_overlap) else "Prioritaria",
        "priority_tone": "warning" if (parking_overlap or market_history_overlap) else "success",
        "is_conditioned_by_parking": parking_overlap,
        "is_conditioned_by_market_history": market_history_overlap,
        "was_reprioritized_by_market_history": False,
        "original_block_label": block_label,
    }


def _build_decision_suggested_assets(
    ranking: Dict | None,
    *,
    parking_feature: Dict | None = None,
    market_history_feature: Dict | None = None,
) -> list[Dict]:
    ranking = ranking or {}
    assets = []
    for item in (ranking.get("candidate_assets") or []):
        block_label = item.get("block_label")
        conditioned_by_parking = _is_parking_overlap_with_recommendation(
            block_label,
            (parking_feature or {}).get("parking_blocks") or [],
        )
        conditioned_by_market_history = _is_market_history_overlap_with_recommendation(
            block_label,
            (market_history_feature or {}).get("weak_blocks") or [],
        )
        if conditioned_by_parking:
            priority_label = "Condicionado por parking"
        elif conditioned_by_market_history:
            priority_label = "Condicionado por liquidez reciente"
        else:
            priority_label = ""
        assets.append(
            {
                "symbol": item.get("asset"),
                "block": block_label,
                "score": _coerce_optional_float(item.get("score")),
                "reason": item.get("main_reason"),
                "is_conditioned_by_parking": conditioned_by_parking,
                "is_conditioned_by_market_history": conditioned_by_market_history,
                "priority_label": priority_label,
                "market_history_note": (
                    "La liquidez reciente de este bloque viene debil y conviene revisar spread y actividad antes de usarlo como candidato principal."
                    if conditioned_by_market_history
                    else ""
                ),
            }
        )
    assets.sort(
        key=lambda item: (
            1 if item["is_conditioned_by_parking"] else 0,
            1 if item["is_conditioned_by_market_history"] else 0,
            -(item["score"] or 0),
        )
    )
    return assets[:3]


def _build_purchase_plan_blocks(purchase_plan: list[Dict]) -> list[str]:
    symbols = [str(item.get("symbol") or "").strip().upper() for item in purchase_plan if item.get("symbol")]
    if not symbols:
        return []
    parametros = ParametroActivo.objects.filter(simbolo__in=symbols)
    labels: list[str] = []
    for parametro in parametros:
        label = str(getattr(parametro, "bloque_estrategico", "") or "").strip()
        if label and label not in labels:
            labels.append(label)
    return labels


def _annotate_decision_proposal_with_market_context(
    proposal: Dict,
    *,
    parking_feature: Dict | None = None,
    market_history_feature: Dict | None = None,
) -> Dict:
    annotated = dict(proposal or {})
    purchase_plan = list(annotated.get("purchase_plan") or [])
    purchase_plan_blocks = _build_purchase_plan_blocks(purchase_plan)
    parking_overlap = any(
        _is_parking_overlap_with_recommendation(block_label, (parking_feature or {}).get("parking_blocks") or [])
        for block_label in purchase_plan_blocks
    )
    market_history_overlap = any(
        _is_market_history_overlap_with_recommendation(block_label, (market_history_feature or {}).get("weak_blocks") or [])
        for block_label in purchase_plan_blocks
    )
    if parking_overlap:
        priority_label = "Condicionada por parking"
        priority_tone = "warning"
        note = "La propuesta preferida cae en un bloque con parking visible y conviene revisarla antes de tomarla como ejecucion directa."
    elif market_history_overlap:
        priority_label = "Condicionada por liquidez reciente"
        priority_tone = "warning"
        note = "La propuesta preferida cae en un bloque con liquidez reciente debil y conviene revisar spread y actividad antes de ejecutarla."
    else:
        priority_label = "Lista"
        priority_tone = "success"
        note = ""
    annotated.update(
        {
            "purchase_plan": purchase_plan,
            "purchase_plan_blocks": purchase_plan_blocks,
            "is_conditioned_by_parking": parking_overlap,
            "is_conditioned_by_market_history": market_history_overlap,
            "priority_label": priority_label,
            "priority_tone": priority_tone,
            "parking_note": note,
            "was_reprioritized_by_parking": False,
            "was_reprioritized_by_market_history": False,
        }
    )
    return annotated


def _should_promote_clean_alternative(conditioned: Dict, clean: Dict) -> bool:
    conditioned_score = _coerce_optional_float(conditioned.get("comparison_score"))
    clean_score = _coerce_optional_float(clean.get("comparison_score"))
    if clean_score is None:
        return False
    if conditioned_score is None:
        return True
    return clean_score >= (conditioned_score - 0.25)


def _build_decision_preferred_proposal(
    preferred_payload: Dict | None,
    *,
    parking_feature: Dict | None = None,
    market_history_feature: Dict | None = None,
) -> Dict | None:
    preferred_payload = preferred_payload or {}
    preferred = preferred_payload.get("preferred")
    if not preferred:
        return None
    def normalize_candidate(item: Dict) -> Dict:
        simulation = item.get("simulation") or {}
        return {
            "proposal_key": item.get("proposal_key"),
            "proposal_label": item.get("proposal_label") or item.get("label"),
            "source_label": item.get("source_label"),
            "comparison_score": _coerce_optional_float(item.get("comparison_score")),
            "purchase_plan": list(item.get("purchase_plan") or []),
            "purchase_summary": item.get("purchase_summary") or _format_incremental_purchase_plan_summary(
                list(item.get("purchase_plan") or [])
            ),
            "simulation_delta": dict(simulation.get("delta") or item.get("simulation_delta") or {}),
            "simulation_interpretation": str(simulation.get("interpretation") or item.get("simulation_interpretation") or ""),
            "priority_rank": int(item.get("priority_rank") or 0),
        }

    raw_candidates = [normalize_candidate(item) for item in (preferred_payload.get("candidates") or [])]
    if not raw_candidates:
        raw_candidates = [normalize_candidate(preferred)]

    annotated_candidates = [
        _annotate_decision_proposal_with_market_context(
            item,
            parking_feature=parking_feature,
            market_history_feature=market_history_feature,
        )
        for item in raw_candidates
    ]

    selected = next(
        (
            item for item in annotated_candidates
            if item.get("proposal_key") == preferred.get("proposal_key")
        ),
        annotated_candidates[0],
    )

    if selected.get("is_conditioned_by_parking"):
        clean_candidates = [
            item for item in annotated_candidates
            if not item.get("is_conditioned_by_parking")
            and not item.get("is_conditioned_by_market_history")
            and _should_promote_clean_alternative(selected, item)
        ]
        if clean_candidates:
            selected = sorted(
                clean_candidates,
                key=lambda item: (
                    float(item.get("comparison_score") if item.get("comparison_score") is not None else float("-inf")),
                    int(item.get("priority_rank") or 0),
                ),
                reverse=True,
            )[0]
            selected["was_reprioritized_by_parking"] = True
            selected["priority_label"] = "Repriorizada por parking"
            selected["priority_tone"] = "info"
            selected["parking_note"] = (
                "Se promovio esta alternativa porque la propuesta preferida original caia en un bloque con parking visible."
            )
    elif selected.get("is_conditioned_by_market_history"):
        clean_candidates = [
            item for item in annotated_candidates
            if not item.get("is_conditioned_by_parking")
            and not item.get("is_conditioned_by_market_history")
            and _should_promote_clean_alternative(selected, item)
        ]
        if clean_candidates:
            selected = sorted(
                clean_candidates,
                key=lambda item: (
                    float(item.get("comparison_score") if item.get("comparison_score") is not None else float("-inf")),
                    int(item.get("priority_rank") or 0),
                ),
                reverse=True,
            )[0]
            selected["was_reprioritized_by_market_history"] = True
            selected["priority_label"] = "Repriorizada por liquidez reciente"
            selected["priority_tone"] = "info"
            selected["parking_note"] = (
                "Se promovio esta alternativa porque la propuesta preferida original caia en un bloque con liquidez reciente debil."
            )

    return selected


def _build_decision_expected_impact(simulation: Dict | None) -> Dict:
    simulation = simulation or {}
    delta = dict(simulation.get("delta") or {})
    expected_return = _coerce_optional_float(delta.get("expected_return_change"))
    fragility = _coerce_optional_float(delta.get("fragility_change"))
    worst_case = _coerce_optional_float(delta.get("scenario_loss_change"))
    risk_concentration = _coerce_optional_float(delta.get("risk_concentration_change"))

    favorable = 0
    unfavorable = 0
    if expected_return is not None:
        favorable += 1 if expected_return >= 0 else 0
        unfavorable += 1 if expected_return < 0 else 0
    if fragility is not None:
        favorable += 1 if fragility <= 0 else 0
        unfavorable += 1 if fragility > 0 else 0
    if worst_case is not None:
        favorable += 1 if worst_case >= 0 else 0
        unfavorable += 1 if worst_case < 0 else 0
    if risk_concentration is not None:
        favorable += 1 if risk_concentration <= 0 else 0
        unfavorable += 1 if risk_concentration > 0 else 0

    if favorable and not unfavorable:
        status = "positive"
        score_component = 25
    elif unfavorable and not favorable:
        status = "negative"
        score_component = 5
    elif favorable or unfavorable:
        status = "mixed"
        score_component = 14
    else:
        status = "neutral"
        score_component = 12

    return {
        "return": expected_return,
        "fragility": fragility,
        "worst_case": worst_case,
        "risk_concentration": risk_concentration,
        "status": status,
        "score_component": score_component,
        "summary": str(simulation.get("interpretation") or "Impacto incremental no disponible."),
    }


def _compute_decision_score(
    *,
    macro_state: Dict,
    portfolio_state: Dict,
    recommendation: Dict,
    suggested_assets: list[Dict],
    preferred_proposal: Dict | None,
    expected_impact: Dict,
    parking_signal: Dict | None = None,
    market_history_signal: Dict | None = None,
) -> int:
    recommendation_score = 0
    if recommendation.get("has_recommendation"):
        recommendation_score += 10
    if suggested_assets:
        recommendation_score += 5
    if len(suggested_assets) >= 2:
        recommendation_score += 3
    if preferred_proposal:
        recommendation_score += 7
    recommendation_score = min(recommendation_score, 25)

    total = (
        int(macro_state.get("score_component") or 0)
        + int(portfolio_state.get("score_component") or 0)
        + recommendation_score
        + int(expected_impact.get("score_component") or 0)
    )
    if (parking_signal or {}).get("has_signal"):
        total -= 5
    if (market_history_signal or {}).get("has_signal"):
        total -= 4
    return max(0, min(100, total))


def _build_decision_recommendation_context(portfolio_scope: Dict | None) -> str | None:
    portfolio_scope = portfolio_scope or {}
    cash_ratio_total = _coerce_optional_float(portfolio_scope.get("cash_ratio_total")) or 0.0
    invested_ratio_total = _coerce_optional_float(portfolio_scope.get("invested_ratio_total")) or 0.0

    if cash_ratio_total > 0.30:
        return "high_cash"
    if invested_ratio_total > 0.90:
        return "fully_invested"
    return None


def _build_decision_strategy_bias(recommendation_context: str | None) -> str | None:
    if recommendation_context == "high_cash":
        return "deploy_cash"
    if recommendation_context == "fully_invested":
        return "rebalance"
    return None


def _build_decision_parking_signal(parking_feature: Dict | None) -> Dict:
    parking_feature = parking_feature or {}
    summary = parking_feature.get("summary") or {}
    parking_count = int(summary.get("parking_count") or 0)
    parking_value_total = summary.get("parking_value_total") or Decimal("0")

    if not parking_feature.get("has_visible_parking") or parking_count <= 0:
        return {
            "has_signal": False,
            "severity": "info",
            "title": "",
            "summary": "",
            "parking_count": 0,
            "parking_value_total": Decimal("0"),
        }

    return {
        "has_signal": True,
        "severity": "warning",
        "title": "Parking visible antes de reforzar",
        "summary": f"Hay {parking_count} posicion(es) con parking visible por {parking_value_total.quantize(Decimal('0.01'))}.",
        "parking_count": parking_count,
        "parking_value_total": parking_value_total,
    }


def _build_decision_market_history_signal(
    *,
    market_history_feature: Dict | None,
    recommendation: Dict | None,
    preferred_proposal: Dict | None,
) -> Dict:
    market_history_feature = market_history_feature or {}
    weak_blocks = {
        str(item.get("label") or "").strip()
        for item in market_history_feature.get("weak_blocks", [])
        if str(item.get("label") or "").strip()
    }
    overlap_blocks = []
    recommendation_block = str((recommendation or {}).get("block") or "").strip()
    if recommendation_block and recommendation_block in weak_blocks:
        overlap_blocks.append(recommendation_block)
    original_block_label = str((recommendation or {}).get("original_block_label") or "").strip()
    if (
        original_block_label
        and original_block_label in weak_blocks
        and original_block_label not in overlap_blocks
        and (
            (recommendation or {}).get("was_reprioritized_by_market_history")
            or (recommendation or {}).get("is_conditioned_by_market_history")
        )
    ):
        overlap_blocks.append(original_block_label)
    for block in (preferred_proposal or {}).get("purchase_plan_blocks") or []:
        block_label = str(block or "").strip()
        if block_label and block_label in weak_blocks and block_label not in overlap_blocks:
            overlap_blocks.append(block_label)

    if not overlap_blocks:
        return {
            "has_signal": False,
            "title": "",
            "summary": "",
            "overlap_blocks": [],
        }

    overlap_rows = [
        row for row in market_history_feature.get("rows", [])
        if str(row.get("bloque_estrategico") or "").strip() in set(overlap_blocks)
        and row.get("quality_status") == "weak"
    ]
    overlap_symbols = ", ".join(row["simbolo"] for row in overlap_rows[:3])
    summary = (
        f"El bloque sugerido viene con liquidez reciente debil en {', '.join(overlap_blocks)}."
    )
    if overlap_symbols:
        summary += f" Revisar spread y actividad reciente en {overlap_symbols} antes de comprar."

    return {
        "has_signal": True,
        "title": "Liquidez reciente debil en la zona sugerida",
        "summary": summary,
        "overlap_blocks": overlap_blocks,
    }


def _build_decision_action_suggestions(
    strategy_bias: str | None,
    *,
    parking_signal: Dict | None = None,
    market_history_signal: Dict | None = None,
) -> list[Dict]:
    suggestions = []
    if strategy_bias == "deploy_cash":
        suggestions.append(
            {
                "type": "allocation",
                "message": "Tenés capital disponible para invertir",
                "suggestion": "Evaluar asignar entre 20% y 40% del cash.",
            }
        )
    elif strategy_bias == "rebalance":
        suggestions.append(
            {
                "type": "rebalance",
                "message": "Cartera altamente invertida",
                "suggestion": "Evaluar reducción de concentración en top posiciones.",
            }
        )
    if (parking_signal or {}).get("has_signal"):
        suggestions.append(
            {
                "type": "parking",
                "message": "Hay posiciones con parking visible en cartera",
                "suggestion": "Conviene revisar esas restricciones antes de reforzar la misma zona de exposicion.",
            }
        )
    if (market_history_signal or {}).get("has_signal"):
        suggestions.append(
            {
                "type": "market_history",
                "message": "La liquidez reciente del bloque sugerido viene debil",
                "suggestion": "Conviene priorizar compras en zonas con mejor spread y actividad reciente o esperar un punto de entrada mas limpio.",
            }
        )
    return suggestions


def _build_decision_execution_gate(*, parking_signal: Dict | None, preferred_proposal: Dict | None) -> Dict:
    if (parking_signal or {}).get("has_signal") or (preferred_proposal or {}).get("is_conditioned_by_parking"):
        return {
            "has_blocker": True,
            "status": "review_parking",
            "title": "Revisar restricciones antes de ejecutar",
            "summary": "La propuesta puede seguir siendo valida, pero conviene revisar primero el parking visible antes de desplegar mas capital.",
            "primary_cta_label": "Revisar antes de ejecutar",
            "primary_cta_tone": "warning",
        }
    if preferred_proposal:
        return {
            "has_blocker": False,
            "status": "ready",
            "title": "",
            "summary": "",
            "primary_cta_label": "Ejecutar decisión",
            "primary_cta_tone": "success",
        }
    return {
        "has_blocker": False,
        "status": "pending",
        "title": "",
        "summary": "",
        "primary_cta_label": "Ejecutar decisión",
        "primary_cta_tone": "success",
    }


def _compute_decision_confidence(
    *,
    macro_state: Dict,
    portfolio_state: Dict,
    preferred_proposal: Dict | None,
    expected_impact: Dict,
    parking_signal: Dict | None = None,
    market_history_signal: Dict | None = None,
) -> str:
    if preferred_proposal is None:
        return "Baja"
    if expected_impact.get("status") == "negative":
        return "Baja"
    if macro_state.get("key") == "crisis":
        return "Baja"
    if (
        macro_state.get("key") == "normal"
        and portfolio_state.get("key") != "riesgo"
        and expected_impact.get("status") in {"positive", "neutral"}
    ):
        confidence = "Alta"
    else:
        confidence = "Media"

    if (
        (parking_signal or {}).get("has_signal")
        or (preferred_proposal or {}).get("was_reprioritized_by_parking")
        or (preferred_proposal or {}).get("is_conditioned_by_parking")
        or (market_history_signal or {}).get("has_signal")
        or (preferred_proposal or {}).get("is_conditioned_by_market_history")
    ):
        if confidence == "Alta":
            return "Media"
        return "Baja"
    return confidence


def _build_decision_explanation(
    *,
    macro_state: Dict,
    recommendation: Dict,
    expected_impact: Dict,
    confidence: str,
    preferred_proposal: Dict | None,
    parking_signal: Dict | None = None,
    market_history_signal: Dict | None = None,
) -> list[str]:
    recommendation_block = recommendation.get("block") or "el bloque sugerido"
    recommendation_reason = recommendation.get("reason") or "es la prioridad mas clara del mes"
    proposal_label = (preferred_proposal or {}).get("proposal_label") or "la mejor propuesta disponible"

    risk_line = "El riesgo no aumenta materialmente con la propuesta actual."
    if expected_impact.get("status") == "negative" or confidence == "Baja":
        risk_line = "El riesgo pide revision adicional antes de ejecutar la decision."
    elif expected_impact.get("status") == "mixed":
        risk_line = "El riesgo queda controlado, pero conviene revisar las senales mixtas."

    bullets = [
        f"Se refuerza {recommendation_block} porque {recommendation_reason}.",
        f"El contexto macro esta en {str(macro_state.get('label') or 'Indefinido').lower()} y {macro_state.get('summary') or 'no invalida la decision principal'}.",
        f"El impacto esperado de {proposal_label} es {expected_impact.get('status') or 'neutral'} en retorno, fragilidad y peor escenario.",
        risk_line,
    ]
    if (parking_signal or {}).get("has_signal"):
        bullets.append("Hay parking visible en cartera y conviene revisar esas restricciones antes de ejecutar la propuesta.")
    if recommendation.get("was_reprioritized_by_parking"):
        bullets.append("La recomendacion principal fue repriorizada porque el bloque original quedaba condicionado por parking visible.")
    elif recommendation.get("is_conditioned_by_parking"):
        bullets.append("La recomendacion principal quedo condicionada por parking visible en el mismo bloque estrategico.")
    if recommendation.get("was_reprioritized_by_market_history"):
        bullets.append("La recomendacion principal fue repriorizada porque el bloque original mostraba liquidez reciente debil.")
    elif recommendation.get("is_conditioned_by_market_history") or (market_history_signal or {}).get("has_signal"):
        bullets.append("La liquidez reciente del bloque sugerido pide validar mejor la ejecucion antes de comprar.")
    if (preferred_proposal or {}).get("was_reprioritized_by_parking"):
        bullets.append("La propuesta preferida guardable fue reemplazada por una alternativa mas limpia frente a parking visible.")
    elif (preferred_proposal or {}).get("was_reprioritized_by_market_history"):
        bullets.append("La propuesta preferida guardable fue reemplazada por una alternativa con liquidez reciente mas limpia.")
    return bullets[:8]


def _build_decision_tracking_payload(
    *,
    preferred_proposal: Dict | None,
    recommendation: Dict,
    expected_impact: Dict,
    score: int,
    confidence: str,
    macro_state: Dict,
    portfolio_state: Dict,
    parking_signal: Dict | None = None,
    market_history_signal: Dict | None = None,
    execution_gate: Dict | None = None,
) -> Dict:
    preferred_proposal = preferred_proposal or {}
    parking_signal = parking_signal or {}
    market_history_signal = market_history_signal or {}
    execution_gate = execution_gate or {}
    return {
        "recommended_block": recommendation.get("block"),
        "recommended_amount": recommendation.get("amount"),
        "preferred_proposal": {
            "proposal_key": preferred_proposal.get("proposal_key"),
            "proposal_label": preferred_proposal.get("proposal_label"),
            "source_label": preferred_proposal.get("source_label"),
        },
        "purchase_plan": list(preferred_proposal.get("purchase_plan") or []),
        "simulation_delta": dict(preferred_proposal.get("simulation_delta") or {}),
        "score": score,
        "confidence": confidence,
        "macro_state": macro_state.get("key"),
        "portfolio_state": portfolio_state.get("key"),
        "expected_impact_status": expected_impact.get("status"),
        "governance": {
            "execution_gate_key": execution_gate.get("key"),
            "parking_signal_active": bool(parking_signal.get("has_signal")),
            "parking_blocks": [
                str(item.get("label") or "").strip()
                for item in (parking_signal.get("parking_blocks") or [])
                if str(item.get("label") or "").strip()
            ],
            "market_history_signal_active": bool(market_history_signal.get("has_signal")),
            "market_history_blocks": [
                str(item.get("label") or "").strip()
                for item in (
                    [{"label": block} for block in (market_history_signal.get("overlap_blocks") or [])]
                )
                if str(item.get("label") or "").strip()
            ],
            "recommendation": {
                "block": recommendation.get("block"),
                "priority_label": recommendation.get("priority_label"),
                "conditioned_by_parking": bool(recommendation.get("is_conditioned_by_parking")),
                "reprioritized_by_parking": bool(recommendation.get("was_reprioritized_by_parking")),
                "conditioned_by_market_history": bool(recommendation.get("is_conditioned_by_market_history")),
                "reprioritized_by_market_history": bool(recommendation.get("was_reprioritized_by_market_history")),
                "original_block_label": recommendation.get("original_block_label"),
            },
            "preferred_proposal": {
                "proposal_label": preferred_proposal.get("proposal_label"),
                "conditioned_by_parking": bool(preferred_proposal.get("is_conditioned_by_parking")),
                "reprioritized_by_parking": bool(preferred_proposal.get("was_reprioritized_by_parking")),
                "conditioned_by_market_history": bool(preferred_proposal.get("is_conditioned_by_market_history")),
                "reprioritized_by_market_history": bool(preferred_proposal.get("was_reprioritized_by_market_history")),
            },
        },
    }


def _extract_best_incremental_proposal(payload: Dict) -> Dict | None:
    best_key = payload.get("best_proposal_key")
    if not best_key:
        return None
    for proposal in payload.get("proposals", []):
        if proposal.get("proposal_key") == best_key:
            return proposal
    return None


def _normalize_incremental_proposal_item(item: Dict | None) -> Dict:
    return normalize_incremental_proposal_payload(item)


def _preferred_source_priority_rank(source_key: str, payload: Dict) -> int:
    if source_key == "manual_plan" and payload.get("submitted") and payload.get("proposals"):
        return 4
    if source_key == "candidate_split":
        return 3
    if source_key == "candidate_block":
        return 2
    return 1


def _build_preferred_proposal_context(source_key: str, payload: Dict) -> str | None:
    if source_key == "candidate_block":
        return payload.get("selected_label")
    if source_key == "candidate_split":
        return payload.get("selected_label")
    if source_key == "manual_plan":
        return "Plan manual enviado por el usuario" if payload.get("submitted") else None
    return None


def _build_preferred_incremental_explanation(best: Dict | None, manual_payload: Dict) -> str:
    if best is None:
        return "Todavia no hay una propuesta incremental preferida construible con los comparadores actuales."
    if best["source_key"] == "manual_plan" and manual_payload.get("submitted"):
        return (
            f"La propuesta preferida actual sale del comparador manual: {best['proposal_label']}. "
            "Se prioriza porque refleja una intencion explicita del usuario y ademas lidera el score comparativo disponible."
        )
    context = f" para {best['selected_context']}" if best.get("selected_context") else ""
    return (
        f"La propuesta preferida actual surge de {best['source_label']}{context}: {best['proposal_label']}. "
        "Se selecciona por score comparativo y desempate de prioridad entre comparadores."
    )


def _build_comparable_candidate_blocks(monthly_plan: Dict, candidate_ranking: Dict) -> list[Dict]:
    by_block = _candidate_blocks_map(candidate_ranking)
    comparable_blocks = []
    for block in monthly_plan.get("recommended_blocks", []):
        bucket = str(block.get("bucket") or "")
        candidates = by_block.get(bucket, {}).get("candidates", [])
        if not candidates:
            continue
        comparable_blocks.append(
            {
                "bucket": bucket,
                "label": block.get("label", bucket),
                "suggested_amount": float(block.get("suggested_amount") or 0.0),
                "candidates": [
                    {
                        "asset": candidate.get("asset"),
                        "score": candidate.get("score"),
                        "main_reason": candidate.get("main_reason"),
                    }
                    for candidate in candidates[:3]
                ],
            }
        )
    return comparable_blocks


def _build_purchase_plan_variant(monthly_plan: Dict, candidate_ranking: Dict, *, candidate_index: int) -> Dict:
    by_block = _candidate_blocks_map(candidate_ranking)
    purchase_amounts: Dict[str, float] = {}
    selected_candidates = []
    unmapped_blocks = []

    for block in monthly_plan.get("recommended_blocks", []):
        bucket = str(block.get("bucket") or "")
        amount = float(block.get("suggested_amount") or 0.0)
        block_candidates = by_block.get(bucket, {}).get("candidates", [])
        if amount <= 0 or not block_candidates:
            unmapped_blocks.append(block.get("label", bucket))
            continue
        idx = candidate_index if len(block_candidates) > candidate_index else 0
        candidate = block_candidates[idx]
        symbol = candidate.get("asset")
        purchase_amounts[symbol] = purchase_amounts.get(symbol, 0.0) + amount
        selected_candidates.append(
            {
                "symbol": symbol,
                "block": bucket,
                "block_label": block.get("label", bucket),
                "amount": amount,
                "candidate_score": candidate.get("score"),
                "candidate_reason": candidate.get("main_reason"),
            }
        )

    purchase_plan = [
        {"symbol": symbol, "amount": round(amount, 2)}
        for symbol, amount in purchase_amounts.items()
    ]
    return {
        "purchase_plan": purchase_plan,
        "selected_candidates": selected_candidates,
        "unmapped_blocks": unmapped_blocks,
    }


def _build_top_candidate_purchase_plan(monthly_plan: Dict, candidate_ranking: Dict) -> Dict:
    return _build_purchase_plan_variant(monthly_plan, candidate_ranking, candidate_index=0)


def _build_runner_up_purchase_plan(monthly_plan: Dict, candidate_ranking: Dict) -> Dict:
    return _build_purchase_plan_variant(monthly_plan, candidate_ranking, candidate_index=1)


def _build_split_largest_block_purchase_plan(monthly_plan: Dict, candidate_ranking: Dict) -> Dict:
    by_block = _candidate_blocks_map(candidate_ranking)
    recommended_blocks = sorted(
        monthly_plan.get("recommended_blocks", []),
        key=lambda item: float(item.get("suggested_amount") or 0.0),
        reverse=True,
    )
    purchase_amounts: Dict[str, float] = {}
    selected_candidates = []
    unmapped_blocks = []

    split_bucket = None
    for block in recommended_blocks:
        bucket = str(block.get("bucket") or "")
        if len(by_block.get(bucket, {}).get("candidates", [])) >= 2:
            split_bucket = bucket
            break

    for block in monthly_plan.get("recommended_blocks", []):
        bucket = str(block.get("bucket") or "")
        amount = float(block.get("suggested_amount") or 0.0)
        candidates = by_block.get(bucket, {}).get("candidates", [])
        if amount <= 0 or not candidates:
            unmapped_blocks.append(block.get("label", bucket))
            continue

        if bucket == split_bucket:
            first = candidates[0]
            second = candidates[1]
            first_amount = round(amount / 2.0, 2)
            second_amount = round(amount - first_amount, 2)
            for candidate, candidate_amount in ((first, first_amount), (second, second_amount)):
                symbol = candidate.get("asset")
                purchase_amounts[symbol] = purchase_amounts.get(symbol, 0.0) + candidate_amount
                selected_candidates.append(
                    {
                        "symbol": symbol,
                        "block": bucket,
                        "block_label": block.get("label", bucket),
                        "amount": candidate_amount,
                        "candidate_score": candidate.get("score"),
                        "candidate_reason": candidate.get("main_reason"),
                    }
                )
            continue

        candidate = candidates[0]
        symbol = candidate.get("asset")
        purchase_amounts[symbol] = purchase_amounts.get(symbol, 0.0) + amount
        selected_candidates.append(
            {
                "symbol": symbol,
                "block": bucket,
                "block_label": block.get("label", bucket),
                "amount": amount,
                "candidate_score": candidate.get("score"),
                "candidate_reason": candidate.get("main_reason"),
            }
        )

    purchase_plan = [
        {"symbol": symbol, "amount": round(amount, 2)}
        for symbol, amount in purchase_amounts.items()
    ]
    return {
        "purchase_plan": purchase_plan,
        "selected_candidates": selected_candidates,
        "unmapped_blocks": unmapped_blocks,
    }


def _score_incremental_simulation(simulation: Dict) -> float:
    delta = simulation.get("delta", {})
    score = 0.0
    score += float(delta.get("expected_return_change") or 0.0)
    score += float(delta.get("real_expected_return_change") or 0.0) * 0.5
    score += float(delta.get("scenario_loss_change") or 0.0) * 0.75
    score -= float(delta.get("fragility_change") or 0.0)
    score -= float(delta.get("risk_concentration_change") or 0.0) * 0.5
    return round(score, 2)


def _build_manual_incremental_comparison_form_state(
    query_params,
    *,
    default_capital_amount: int | float = 600000,
) -> Dict:
    submitted = str(_query_param_value(query_params, "manual_compare", "")).strip() == "1"
    plans = []
    normalized_plans = []

    for plan_key, label in (("plan_a", "Plan manual A"), ("plan_b", "Plan manual B")):
        capital_raw = str(_query_param_value(query_params, f"{plan_key}_capital", "")).strip()
        rows = []
        for index in range(1, 4):
            rows.append(
                {
                    "symbol": str(_query_param_value(query_params, f"{plan_key}_symbol_{index}", "")).strip().upper(),
                    "amount_raw": str(_query_param_value(query_params, f"{plan_key}_amount_{index}", "")).strip(),
                }
            )

        warnings = []
        purchase_plan = []
        total_amount = 0.0
        touched_rows = 0
        for row in rows:
            symbol = row["symbol"]
            amount = _coerce_manual_amount(row["amount_raw"])
            if symbol or row["amount_raw"]:
                touched_rows += 1
            if not symbol and not row["amount_raw"]:
                continue
            if not symbol:
                warnings.append("missing_symbol")
                continue
            if amount <= 0:
                warnings.append(f"invalid_amount:{symbol}")
                continue
            amount = round(amount, 2)
            purchase_plan.append({"symbol": symbol, "amount": amount})
            total_amount += amount

        capital_amount = _coerce_manual_amount(capital_raw)
        if capital_amount <= 0:
            capital_amount = total_amount if total_amount > 0 else float(default_capital_amount)
        capital_amount = round(capital_amount, 2)

        plan_state = {
            "plan_key": plan_key,
            "label": label,
            "capital_raw": capital_raw or str(int(default_capital_amount)),
            "rows": rows,
            "warnings": warnings,
            "has_input": touched_rows > 0 or bool(capital_raw),
        }
        plans.append(plan_state)

        if purchase_plan:
            normalized_plans.append(
                {
                    "proposal_key": plan_key,
                    "label": label,
                    "capital_amount": capital_amount,
                    "purchase_plan": purchase_plan,
                    "warnings": warnings,
                }
            )

    return {
        "submitted": submitted,
        "plans": plans,
        "normalized_plans": normalized_plans,
    }


def _query_param_value(query_params, key: str, default=""):
    getter = getattr(query_params, "get", None)
    if callable(getter):
        return getter(key, default)
    if isinstance(query_params, dict):
        return query_params.get(key, default)
    return default


def _coerce_manual_amount(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def get_analytics_v2_dashboard_summary() -> Dict:
    """Resume Analytics v2 para consumo server-rendered en dashboard."""

    def build():
        resolved_risk = _get_active_risk_contribution_result()
        base_risk_service = RiskContributionService()
        covariance_risk_result = resolved_risk["covariance_result"]
        risk_result = resolved_risk["active_result"]
        scenario_service = ScenarioAnalysisService()
        factor_service = FactorExposureService()
        explanation_service = AnalyticsExplanationService()
        stress_service = StressFragilityService()
        expected_return_service = ExpectedReturnService()
        local_macro_service = LocalMacroSignalsService()

        argentina_stress = scenario_service.analyze("argentina_stress")
        tech_shock = scenario_service.analyze("tech_shock")
        fragility = stress_service.calculate("local_crisis_severe")
        factor_result = factor_service.calculate()
        expected_return_result = expected_return_service.calculate()
        local_macro_result = local_macro_service.calculate()

        combined_signals = (
            base_risk_service.build_recommendation_signals(top_n=5)
            + scenario_service.build_recommendation_signals()
            + factor_service.build_recommendation_signals()
            + stress_service.build_recommendation_signals()
            + expected_return_service.build_recommendation_signals()
            + local_macro_service.build_recommendation_signals()
        )
        combined_signals = sorted(
            combined_signals,
            key=lambda signal: {"high": 0, "medium": 1, "low": 2}.get(signal.get("severity"), 3)
        )

        top_risk_asset = risk_result["top_contributors"][0] if risk_result.get("top_contributors") else None
        top_risk_sector = risk_result["by_sector"][0] if risk_result.get("by_sector") else None
        dominant_factor_key = factor_result.get("dominant_factor")
        dominant_factor = next(
            (item for item in factor_result.get("factors", []) if item.get("factor") == dominant_factor_key),
            None,
        )
        covariance_variant = covariance_risk_result.get("model_variant", "mvp_proxy")
        covariance_observations = int(covariance_risk_result.get("covariance_observations") or 0)
        covariance_coverage_pct = float(covariance_risk_result.get("coverage_pct") or 0.0)
        covariance_warning = next(
            iter(covariance_risk_result.get("metadata", {}).get("warnings", [])),
            None,
        )
        worst_scenario = (
            {
                "label": "Argentina Stress",
                **argentina_stress,
            }
            if (argentina_stress.get("total_impact_pct") or 0) <= (tech_shock.get("total_impact_pct") or 0)
            else {
                "label": "Tech Shock",
                **tech_shock,
            }
        )

        return {
            "risk_contribution": {
                "top_asset": top_risk_asset,
                "top_sector": top_risk_sector,
                "confidence": risk_result["metadata"]["confidence"],
                "warnings_count": len(risk_result["metadata"].get("warnings", [])),
                "model_variant": covariance_variant,
                "covariance_observations": covariance_observations,
                "coverage_pct": covariance_coverage_pct,
                "covariance_warning": covariance_warning,
                "interpretation": explanation_service.build_risk_contribution_explanation(risk_result),
            },
            "scenario_analysis": {
                "argentina_stress_pct": argentina_stress.get("total_impact_pct"),
                "tech_shock_pct": tech_shock.get("total_impact_pct"),
                "confidence": min(
                    argentina_stress["metadata"]["confidence"],
                    tech_shock["metadata"]["confidence"],
                    key=lambda level: {"high": 3, "medium": 2, "low": 1}.get(level, 0),
                ),
                "worst_label": worst_scenario["label"],
                "interpretation": explanation_service.build_scenario_analysis_explanation(
                    {
                        "worst_scenario": worst_scenario,
                    }
                ),
            },
            "factor_exposure": {
                "dominant_factor": dominant_factor_key,
                "dominant_factor_exposure_pct": dominant_factor.get("exposure_pct") if dominant_factor else None,
                "unknown_assets_count": len(factor_result.get("unknown_assets", [])),
                "confidence": factor_result["metadata"]["confidence"],
                "interpretation": explanation_service.build_factor_exposure_explanation(factor_result),
            },
            "stress_testing": {
                "scenario_key": fragility.get("scenario_key"),
                "fragility_score": fragility.get("fragility_score"),
                "total_loss_pct": fragility.get("total_loss_pct"),
                "confidence": fragility["metadata"]["confidence"],
                "interpretation": explanation_service.build_stress_fragility_explanation(fragility),
            },
            "expected_return": {
                "expected_return_pct": expected_return_result.get("expected_return_pct"),
                "real_expected_return_pct": expected_return_result.get("real_expected_return_pct"),
                "confidence": expected_return_result["metadata"]["confidence"],
                "warnings_count": len(expected_return_result["metadata"].get("warnings", [])),
                "interpretation": explanation_service.build_expected_return_explanation(expected_return_result),
            },
            "local_macro": {
                "argentina_weight_pct": local_macro_result.get("summary", {}).get("argentina_weight_pct"),
                "ars_liquidity_weight_pct": local_macro_result.get("summary", {}).get("ars_liquidity_weight_pct"),
                "cer_weight_pct": local_macro_result.get("summary", {}).get("cer_weight_pct"),
                "sovereign_bond_weight_pct": local_macro_result.get("summary", {}).get("sovereign_bond_weight_pct"),
                "local_hard_dollar_bond_weight_pct": local_macro_result.get("summary", {}).get("local_hard_dollar_bond_weight_pct"),
                "local_cer_bond_weight_pct": local_macro_result.get("summary", {}).get("local_cer_bond_weight_pct"),
                "local_hard_dollar_share_pct": local_macro_result.get("summary", {}).get("local_hard_dollar_share_pct"),
                "local_cer_share_pct": local_macro_result.get("summary", {}).get("local_cer_share_pct"),
                "top_local_sovereign_symbol": local_macro_result.get("summary", {}).get("top_local_sovereign_symbol"),
                "top_local_sovereign_share_pct": local_macro_result.get("summary", {}).get("top_local_sovereign_share_pct"),
                "local_sovereign_symbols_count": local_macro_result.get("summary", {}).get("local_sovereign_symbols_count"),
                "local_sovereign_concentration_hhi": local_macro_result.get("summary", {}).get("local_sovereign_concentration_hhi"),
                "badlar_real_carry_pct": local_macro_result.get("summary", {}).get("badlar_real_carry_pct"),
                "usdars_mep": local_macro_result.get("summary", {}).get("usdars_mep"),
                "usdars_ccl": local_macro_result.get("summary", {}).get("usdars_ccl"),
                "usdars_financial": local_macro_result.get("summary", {}).get("usdars_financial"),
                "fx_gap_pct": local_macro_result.get("summary", {}).get("fx_gap_pct"),
                "fx_gap_mep_pct": local_macro_result.get("summary", {}).get("fx_gap_mep_pct"),
                "fx_gap_ccl_pct": local_macro_result.get("summary", {}).get("fx_gap_ccl_pct"),
                "fx_mep_ccl_spread_pct": local_macro_result.get("summary", {}).get("fx_mep_ccl_spread_pct"),
                "fx_signal_state": local_macro_result.get("summary", {}).get("fx_signal_state"),
                "riesgo_pais_arg": local_macro_result.get("summary", {}).get("riesgo_pais_arg"),
                "uva": local_macro_result.get("summary", {}).get("uva"),
                "uva_change_pct_30d": local_macro_result.get("summary", {}).get("uva_change_pct_30d"),
                "uva_annualized_pct_30d": local_macro_result.get("summary", {}).get("uva_annualized_pct_30d"),
                "real_rate_badlar_vs_uva_30d": local_macro_result.get("summary", {}).get("real_rate_badlar_vs_uva_30d"),
                "ipc_yoy_pct": local_macro_result.get("summary", {}).get("ipc_yoy_pct"),
                "confidence": local_macro_result.get("metadata", {}).get("confidence"),
                "warnings_count": len(local_macro_result.get("metadata", {}).get("warnings", [])),
            },
            "signals": combined_signals[:6],
        }

    return _get_cached_selector_result("analytics_v2_dashboard_summary", build)


