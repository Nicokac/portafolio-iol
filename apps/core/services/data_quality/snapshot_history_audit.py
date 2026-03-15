from __future__ import annotations

from datetime import timedelta

import pandas as pd
from django.utils import timezone

from apps.core.services.analytics_v2.risk_contribution_service import RiskContributionService
from apps.core.services.portfolio.covariance_service import CovarianceService
from apps.portafolio_iol.models import ActivoPortafolioSnapshot


class SnapshotHistoryAuditService:
    """Audita la historia diaria util para covarianza sobre el universo invertido actual."""

    def __init__(
        self,
        risk_service: RiskContributionService | None = None,
        covariance_service: CovarianceService | None = None,
    ):
        self.risk_service = risk_service or RiskContributionService()
        self.covariance_service = covariance_service or CovarianceService()

    def audit_current_invested_history(self, lookback_days: int = 252) -> dict:
        positions = self.risk_service._load_current_invested_positions()  # noqa: SLF001
        symbols = [position.simbolo for position in positions]
        end_dt = timezone.now()
        start_dt = end_dt - timedelta(days=lookback_days)
        end_date = end_dt.date()
        start_date = start_dt.date()

        if not symbols:
            return {
                "lookback_days": lookback_days,
                "expected_symbols_count": 0,
                "expected_symbols": [],
                "available_price_dates_count": 0,
                "usable_observations_count": 0,
                "rows": [],
                "missing_calendar_dates": [],
                "warning": "empty_portfolio",
            }

        queryset = ActivoPortafolioSnapshot.objects.filter(
            simbolo__in=symbols,
            fecha_extraccion__range=(start_dt, end_dt),
        ).values("fecha_extraccion", "simbolo", "valorizado")
        df = pd.DataFrame(list(queryset))
        if df.empty:
            return {
                "lookback_days": lookback_days,
                "expected_symbols_count": len(symbols),
                "expected_symbols": symbols,
                "available_price_dates_count": 0,
                "usable_observations_count": 0,
                "rows": [],
                "missing_calendar_dates": [
                    day.date().isoformat()
                    for day in pd.date_range(start=start_date, end=end_date, freq="D")
                ],
                "warning": "insufficient_history",
            }

        df["fecha_extraccion"] = pd.to_datetime(df["fecha_extraccion"])
        df["valorizado"] = pd.to_numeric(df["valorizado"], errors="coerce")
        raw_daily = (
            df.assign(fecha=df["fecha_extraccion"].dt.date)
            .sort_values("fecha_extraccion")
            .dropna(subset=["valorizado"])
            .drop_duplicates(subset=["fecha", "simbolo"], keep="last")
        )

        direct_presence = (
            raw_daily.pivot_table(
                index="fecha",
                columns="simbolo",
                values="valorizado",
                aggfunc="last",
            )
            .sort_index()
            .reindex(columns=symbols)
        )
        price_matrix = self.covariance_service._build_daily_price_matrix(df, symbols)  # noqa: SLF001
        returns = self.covariance_service.build_returns_matrix(symbols, lookback_days=lookback_days)
        usable_dates = {pd.Timestamp(idx).date().isoformat() for idx in returns.index}

        all_dates = [day.date() for day in pd.date_range(start=start_date, end=end_date, freq="D")]
        direct_dates = {idx.isoformat() for idx in direct_presence.index}
        missing_calendar_dates = [day.isoformat() for day in all_dates if day.isoformat() not in direct_dates]

        rows = []
        for day in all_dates:
            iso_day = day.isoformat()
            if day in direct_presence.index:
                direct_row = direct_presence.loc[day]
                assets_present = int(direct_row.notna().sum())
                missing_symbols = [symbol for symbol in symbols if pd.isna(direct_row.get(symbol))]
            else:
                assets_present = 0
                missing_symbols = list(symbols)

            if day in price_matrix.index:
                filled_row = price_matrix.loc[day]
                complete_after_ffill = bool(filled_row.notna().all())
            else:
                complete_after_ffill = False

            rows.append(
                {
                    "date": iso_day,
                    "assets_present": assets_present,
                    "expected_assets": len(symbols),
                    "coverage_pct": round((assets_present / len(symbols)) * 100.0, 2) if symbols else 0.0,
                    "complete_after_ffill": complete_after_ffill,
                    "usable": iso_day in usable_dates,
                    "missing_symbols_count": len(missing_symbols),
                    "missing_symbols": missing_symbols[:10],
                }
            )

        return {
            "lookback_days": lookback_days,
            "expected_symbols_count": len(symbols),
            "expected_symbols": symbols,
            "available_price_dates_count": int(len(price_matrix.index)),
            "usable_observations_count": int(len(returns.index)),
            "rows": rows,
            "missing_calendar_dates": missing_calendar_dates,
            "warning": None if len(returns.index) else "insufficient_history",
        }
