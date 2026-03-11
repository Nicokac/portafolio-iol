from datetime import timedelta
from decimal import Decimal
from typing import Dict, List

from django.db.models import Max, Min, Sum
from django.utils import timezone

from apps.core.services.performance.twr_service import TWRService
from apps.operaciones_iol.models import OperacionIOL
from apps.parametros.models import ParametroActivo
from apps.portafolio_iol.models import ActivoPortafolioSnapshot, PortfolioSnapshot


class AttributionService:
    """Attribution de performance por activo, bucket y efecto de flujos."""

    def __init__(self):
        self.twr_service = TWRService()

    def calculate_attribution(self, days: int = 30) -> Dict:
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)

        date_bounds = ActivoPortafolioSnapshot.objects.filter(
            fecha_extraccion__range=(start_date, end_date)
        ).aggregate(
            first_date=Min("fecha_extraccion"),
            last_date=Max("fecha_extraccion"),
        )

        first_date = date_bounds["first_date"]
        last_date = date_bounds["last_date"]
        if not first_date or not last_date or first_date == last_date:
            return {}

        initial_positions = list(
            ActivoPortafolioSnapshot.objects.filter(fecha_extraccion=first_date).values(
                "simbolo", "valorizado"
            )
        )
        final_positions = list(
            ActivoPortafolioSnapshot.objects.filter(fecha_extraccion=last_date).values(
                "simbolo", "valorizado"
            )
        )

        initial_map = {row["simbolo"]: float(row["valorizado"]) for row in initial_positions}
        final_map = {row["simbolo"]: float(row["valorizado"]) for row in final_positions}

        total_initial = sum(initial_map.values())
        if total_initial <= 0:
            return {}

        symbols = sorted(set(initial_map.keys()) | set(final_map.keys()))
        params = {
            p.simbolo: p
            for p in ParametroActivo.objects.filter(simbolo__in=symbols)
        }

        by_asset = []
        for symbol in symbols:
            start_value = initial_map.get(symbol, 0.0)
            end_value = final_map.get(symbol, 0.0)

            weight = (start_value / total_initial) if total_initial > 0 else 0.0
            asset_return = ((end_value - start_value) / start_value) if start_value > 0 else 0.0
            contribution = weight * asset_return * 100

            param = params.get(symbol)
            by_asset.append(
                {
                    "symbol": symbol,
                    "start_value": round(start_value, 2),
                    "end_value": round(end_value, 2),
                    "weight_pct": round(weight * 100, 2),
                    "return_pct": round(asset_return * 100, 2),
                    "contribution_pct": round(contribution, 2),
                    "sector": param.sector if param else "Sin clasificar",
                    "country": param.pais_exposicion if param else "Sin clasificar",
                    "patrimonial_type": param.tipo_patrimonial if param else "Sin clasificar",
                }
            )

        top_contributors = sorted(
            by_asset, key=lambda item: item["contribution_pct"], reverse=True
        )[:5]
        bottom_contributors = sorted(
            by_asset, key=lambda item: item["contribution_pct"]
        )[:5]

        sector_attr = self._aggregate_contribution(by_asset, "sector")
        country_attr = self._aggregate_contribution(by_asset, "country")
        patrimonial_attr = self._aggregate_contribution(by_asset, "patrimonial_type")

        flow_attr = self._calculate_flow_attribution(start_date.date(), end_date.date())

        return {
            "period_days": days,
            "by_asset": by_asset,
            "top_contributors": top_contributors,
            "bottom_contributors": bottom_contributors,
            "by_sector": sector_attr,
            "by_country": country_attr,
            "by_patrimonial_type": patrimonial_attr,
            "flows": flow_attr,
        }

    @staticmethod
    def _aggregate_contribution(by_asset: List[Dict], field_name: str) -> Dict[str, float]:
        bucket = {}
        for item in by_asset:
            key = item[field_name]
            bucket[key] = bucket.get(key, 0.0) + item["contribution_pct"]
        return {key: round(value, 2) for key, value in bucket.items()}

    def _calculate_flow_attribution(self, start_date, end_date) -> Dict:
        snapshots = PortfolioSnapshot.objects.filter(
            fecha__range=(start_date, end_date)
        ).order_by("fecha")
        if snapshots.count() < 2:
            return {}

        first_snapshot = snapshots.first()
        last_snapshot = snapshots.last()
        if not first_snapshot or not last_snapshot or float(first_snapshot.total_iol) == 0:
            return {}

        total_period_return = (
            (float(last_snapshot.total_iol) - float(first_snapshot.total_iol))
            / float(first_snapshot.total_iol)
            * 100
        )

        twr_result = self.twr_service.calculate_twr(days=(end_date - start_date).days + 1)
        market_return = float(twr_result.get("twr_total_return", 0.0))
        flow_effect = total_period_return - market_return

        operations = OperacionIOL.objects.filter(
            fecha_orden__date__range=(start_date, end_date),
            estado__in=["terminada", "Terminada", "TERMINADA"],
            tipo__in=["Compra", "COMPRA", "Venta", "VENTA"],
        ).values("tipo").annotate(total=Sum("monto_operado"))

        buy_total = Decimal("0")
        sell_total = Decimal("0")
        for row in operations:
            if row["tipo"].lower() == "compra":
                buy_total += row["total"] or Decimal("0")
            elif row["tipo"].lower() == "venta":
                sell_total += row["total"] or Decimal("0")

        net_flows = buy_total - sell_total

        return {
            "total_period_return_pct": round(total_period_return, 2),
            "market_return_pct": round(market_return, 2),
            "flow_effect_pct": round(flow_effect, 2),
            "buy_flows": float(round(buy_total, 2)),
            "sell_flows": float(round(sell_total, 2)),
            "net_flows": float(round(net_flows, 2)),
        }
