from collections import defaultdict
from datetime import timedelta
from typing import Dict, List

from django.db.models import Case, IntegerField, When
from django.utils import timezone
from dateutil.relativedelta import relativedelta

from apps.core.models import Alert
from apps.parametros.models import ParametroActivo
from apps.portafolio_iol.models import ActivoPortafolioSnapshot, PortfolioSnapshot
from apps.resumen_iol.models import ResumenCuentaSnapshot


def build_portafolio_clasificado_fecha(portafolio_fecha) -> Dict[str, List[Dict]]:
    simbolos = [activo.simbolo for activo in portafolio_fecha]
    parametros = {p.simbolo: p for p in ParametroActivo.objects.filter(simbolo__in=simbolos)}

    liquidez = []
    fci_cash_management = []
    inversion = []

    for activo in portafolio_fecha:
        parametro = parametros.get(activo.simbolo)
        tipo_traducido = "Desconocido"
        if activo.tipo == "CEDEARS":
            tipo_traducido = "CEDEAR"
        elif activo.tipo == "ACCIONES":
            tipo_traducido = "Accion"
        elif activo.tipo == "TitulosPublicos":
            tipo_traducido = "Titulo Publico"
        elif activo.tipo == "FondoComundeInversion":
            tipo_traducido = "FCI"
        elif activo.tipo == "CAUCIONESPESOS":
            tipo_traducido = "Caucion"

        item = {
            "activo": activo,
            "tipo_traducido": tipo_traducido,
            "parametro": parametro,
        }

        if parametro and parametro.bloque_estrategico == "Liquidez":
            liquidez.append(item)
        elif parametro and parametro.bloque_estrategico == "FCI Cash Management":
            fci_cash_management.append(item)
        else:
            inversion.append(item)

    return {
        "liquidez": liquidez,
        "fci_cash_management": fci_cash_management,
        "inversion": inversion,
    }


def build_evolucion_historica(*, days: int = 30, max_points: int = 14) -> Dict[str, list]:
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

        portafolio_clasificado = build_portafolio_clasificado_fecha(portafolio_fecha)

        caucion_valor = sum(
            item["activo"].valorizado
            for item in portafolio_clasificado.get("liquidez", [])
            if item["tipo_traducido"] == "Caucion"
        )
        cash_ars = sum(cuenta.disponible for cuenta in resumen_fecha if cuenta.moneda == "ARS")
        cash_usd = sum(cuenta.disponible for cuenta in resumen_fecha if cuenta.moneda == "USD")
        liquidez_operativa = caucion_valor + cash_ars + cash_usd
        portafolio_invertido = sum(
            item["activo"].valorizado for item in portafolio_clasificado.get("inversion", [])
        )
        cash_management = sum(
            item["activo"].valorizado for item in portafolio_clasificado.get("fci_cash_management", [])
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
    return {
        "patrimonial": {
            "Liquidez": 25.0,
            "Cash Management": 7.5,
            "Invertido": 67.5,
        },
        "sectorial": {
            "Tecnologia": 17.5,
            "ETF core": 22.5,
            "Argentina": 12.5,
            "Bonos": 12.5,
            "Defensivos": 12.5,
        },
    }


def mapear_sector_a_categoria(sector: str) -> str:
    mapeo = {
        "Indice": "ETF core",
        "ETF": "ETF core",
        "Soberano": "Bonos",
        "Corporativo": "Bonos",
        "Titulo Publico": "Bonos",
        "Consumo defensivo": "Defensivos",
        "Utilities": "Defensivos",
        "Finanzas": "Defensivos",
        "Argentina": "Argentina",
        "Tecnologia": "Tecnologia",
        "Tecnologia / E-commerce": "Tecnologia",
        "Tecnologia / Semiconductores": "Tecnologia",
    }
    return mapeo.get(sector, sector)


def build_senales_rebalanceo(
    *,
    concentracion_patrimonial: Dict[str, float],
    concentracion_sectorial: Dict[str, float],
    latest_portafolio_data,
) -> Dict[str, list]:
    objetivos = get_objetivos_rebalanceo()
    tolerancia_sobre = 5.0
    tolerancia_sub = 3.0
    umbral_minimo = 2.0
    umbral_posicion_alta = 10.0

    patrimonial_sobreponderado = []
    patrimonial_subponderado = []
    for categoria, actual in concentracion_patrimonial.items():
        objetivo = objetivos["patrimonial"].get(categoria, actual)
        if actual > objetivo + tolerancia_sobre:
            patrimonial_sobreponderado.append(
                {
                    "categoria": categoria,
                    "porcentaje": float(actual),
                    "objetivo": float(objetivo),
                    "diferencia": float(actual) - float(objetivo),
                }
            )
        elif actual < objetivo - tolerancia_sub:
            patrimonial_subponderado.append(
                {
                    "categoria": categoria,
                    "porcentaje": float(actual),
                    "objetivo": float(objetivo),
                    "diferencia": float(objetivo) - float(actual),
                }
            )

    concentracion_agrupada = {}
    for sector, actual in concentracion_sectorial.items():
        categoria = mapear_sector_a_categoria(sector)
        concentracion_agrupada[categoria] = concentracion_agrupada.get(categoria, 0) + actual

    sectorial_sobreponderado = []
    sectorial_subponderado = []
    for categoria, actual in concentracion_agrupada.items():
        objetivo = objetivos["sectorial"].get(categoria)
        if objetivo is not None:
            if actual > objetivo + tolerancia_sobre:
                sectorial_sobreponderado.append(
                    {
                        "sector": categoria,
                        "porcentaje": float(actual),
                        "objetivo": float(objetivo),
                        "diferencia": float(actual) - float(objetivo),
                    }
                )
            elif actual < objetivo - tolerancia_sub:
                sectorial_subponderado.append(
                    {
                        "sector": categoria,
                        "porcentaje": float(actual),
                        "objetivo": float(objetivo),
                        "diferencia": float(objetivo) - float(actual),
                    }
                )
        elif actual < umbral_minimo:
            sectorial_subponderado.append(
                {
                    "sector": categoria,
                    "porcentaje": actual,
                    "objetivo": None,
                    "diferencia": umbral_minimo - actual,
                }
            )

    portafolio = latest_portafolio_data
    simbolos = [activo.simbolo for activo in portafolio]
    parametros = {p.simbolo: p for p in ParametroActivo.objects.filter(simbolo__in=simbolos)}
    activos_sin_metadata = []
    for activo in portafolio:
        parametro = parametros.get(activo.simbolo)
        if not parametro or not all(
            [
                parametro.sector != "N/A",
                parametro.bloque_estrategico != "N/A",
                parametro.pais_exposicion != "N/A",
                parametro.tipo_patrimonial != "N/A",
            ]
        ):
            activos_sin_metadata.append({"simbolo": activo.simbolo, "valorizado": float(activo.valorizado)})

    total_portafolio = sum(activo.valorizado for activo in portafolio)
    posiciones_altas = [
        {
            "simbolo": activo.simbolo,
            "peso": (activo.valorizado / total_portafolio * 100) if total_portafolio > 0 else 0,
            "valorizado": float(activo.valorizado),
        }
        for activo in portafolio
        if (activo.valorizado / total_portafolio * 100) > umbral_posicion_alta
    ]
    posiciones_altas.sort(key=lambda x: x["peso"], reverse=True)

    return {
        "patrimonial_sobreponderado": patrimonial_sobreponderado,
        "patrimonial_subponderado": patrimonial_subponderado,
        "sectorial_sobreponderado": sectorial_sobreponderado,
        "sectorial_subponderado": sectorial_subponderado,
        "activos_sin_metadata": activos_sin_metadata,
        "posiciones_mayor_peso": posiciones_altas,
    }


def build_snapshot_coverage_summary(*, days: int = 90) -> Dict[str, float | int | str | bool | None]:
    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=days)
    snapshots = list(PortfolioSnapshot.objects.filter(fecha__range=(start_date, end_date)).order_by("fecha"))

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


def build_active_alerts() -> list:
    severity_order = Case(
        When(severidad="critical", then=3),
        When(severidad="warning", then=2),
        When(severidad="info", then=1),
        default=0,
        output_field=IntegerField(),
    )
    alerts = Alert.objects.filter(is_active=True).order_by(-severity_order, "-created_at")
    return list(
        alerts.values(
            "id",
            "tipo",
            "mensaje",
            "severidad",
            "valor",
            "simbolo",
            "sector",
            "pais",
            "created_at",
            "is_acknowledged",
        )
    )
