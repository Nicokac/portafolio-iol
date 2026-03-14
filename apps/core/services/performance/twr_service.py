from datetime import timedelta
from decimal import Decimal
from typing import Dict

import pandas as pd
from django.db.models import Sum
from django.db.models.functions import TruncDate
from django.utils import timezone

from apps.operaciones_iol.models import OperacionIOL
from apps.portafolio_iol.models import PortfolioSnapshot


class TWRService:
    """
    Calculo de Time-Weighted Return.

    Formula diaria:
    r_t = (V_t - V_{t-1} - CF_t) / V_{t-1}
    TWR = Π(1 + r_t) - 1
    """

    TRADING_DAYS_PER_YEAR = 252

    def build_daily_return_series(self, days: int = 30) -> pd.Series:
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days)

        snapshots = PortfolioSnapshot.objects.filter(
            fecha__range=(start_date, end_date)
        ).order_by("fecha")

        if snapshots.count() < 2:
            return pd.Series(dtype=float)

        df = pd.DataFrame(list(snapshots.values("fecha", "total_iol")))
        if df.empty:
            return pd.Series(dtype=float)

        df["fecha"] = pd.to_datetime(df["fecha"])
        df["total_iol"] = pd.to_numeric(df["total_iol"], errors="coerce")
        df = df.set_index("fecha").sort_index()
        return self._build_return_series_from_frame(df, start_date, end_date)

    def calculate_twr(self, days: int = 30) -> Dict[str, float]:
        returns_series = self.build_daily_return_series(days=days)
        returns = returns_series.tolist()

        if not returns:
            return {}

        twr_factor = 1.0
        for value in returns:
            twr_factor *= (1 + value)

        total_twr = twr_factor - 1
        periods = len(returns)
        annualized_twr = (1 + total_twr) ** (self.TRADING_DAYS_PER_YEAR / periods) - 1 if periods > 0 else 0

        return {
            "twr_total_return": round(total_twr * 100, 2),
            "twr_annualized_return": round(annualized_twr * 100, 2),
            "twr_periods": periods,
        }

    def _build_return_series_from_frame(self, df: pd.DataFrame, start_date, end_date) -> pd.Series:
        daily_flows = self._get_daily_cash_flows(start_date, end_date)
        returns = []
        index = []

        for idx in range(1, len(df)):
            curr_timestamp = df.index[idx]
            curr_date = curr_timestamp.date()

            start_value = float(df["total_iol"].iloc[idx - 1])
            end_value = float(df["total_iol"].iloc[idx])
            if start_value == 0:
                continue

            # Se descuenta flujo del dia final del subperiodo.
            flow = float(daily_flows.get(curr_date, Decimal("0")))
            period_return = (end_value - start_value - flow) / start_value
            returns.append(period_return)
            index.append(curr_timestamp)

        if not returns:
            return pd.Series(dtype=float)

        return pd.Series(returns, index=pd.to_datetime(index), dtype=float).sort_index()

    def _get_daily_cash_flows(self, start_date, end_date):
        """
        Estima flujos netos diarios.
        Compra: flujo positivo (aporte)
        Venta: flujo negativo (retiro)
        """
        operations = OperacionIOL.objects.filter(
            fecha_orden__date__range=(start_date, end_date),
            estado__in=["terminada", "Terminada", "TERMINADA"],
            tipo__in=["Compra", "COMPRA", "Venta", "VENTA"],
        ).annotate(
            operation_date=TruncDate("fecha_orden")
        ).values("operation_date", "tipo").annotate(
            total=Sum("monto_operado")
        )

        flows = {}
        for item in operations:
            amount = item["total"] or Decimal("0")
            if item["tipo"].lower() == "venta":
                amount = -amount
            day = item["operation_date"]
            flows[day] = flows.get(day, Decimal("0")) + amount
        return flows
