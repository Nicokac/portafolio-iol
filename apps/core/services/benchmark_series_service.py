from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
import time
from typing import Iterable

import pandas as pd
from django.db import transaction
from django.db.models import Count, Max

from apps.core.config.parametros_benchmark import ParametrosBenchmark
from apps.core.models import BenchmarkSnapshot
from apps.core.services.market_data.alpha_vantage_client import AlphaVantageClient


class BenchmarkSeriesService:
    INTERVAL_FETCHERS = {
        "daily": "fetch_daily_adjusted",
        "weekly_adjusted": "fetch_weekly_adjusted",
    }

    def __init__(self, client: AlphaVantageClient | None = None):
        self.client = client or AlphaVantageClient()

    def sync_all(self, outputsize: str = "compact") -> dict:
        results = {}
        for benchmark_key in ParametrosBenchmark.HISTORICAL_SERIES:
            try:
                results[benchmark_key] = self.sync_benchmark(benchmark_key, outputsize=outputsize)
            except Exception as exc:
                config = ParametrosBenchmark.HISTORICAL_SERIES[benchmark_key]
                results[benchmark_key] = {
                    "success": False,
                    "benchmark_key": benchmark_key,
                    "symbol": config["symbol"],
                    "provider": config["provider"],
                    "rows_received": 0,
                    "created": 0,
                    "updated": 0,
                    "error": str(exc),
                }
            time.sleep(1.1)
        return results

    def sync_benchmark(self, benchmark_key: str, outputsize: str = "compact") -> dict:
        config = ParametrosBenchmark.HISTORICAL_SERIES.get(benchmark_key)
        if not config:
            raise ValueError(f"Unknown historical benchmark key: {benchmark_key}")

        interval_results = {}
        created = 0
        updated = 0
        rows_received = 0
        success = True

        for interval in config.get("intervals", ["daily"]):
            try:
                rows = self._fetch_rows(config["symbol"], interval, outputsize=outputsize)
                created_for_interval = 0
                updated_for_interval = 0

                with transaction.atomic():
                    for row in rows:
                        _, was_created = BenchmarkSnapshot.objects.update_or_create(
                            benchmark_key=benchmark_key,
                            source=config["provider"],
                            interval=interval,
                            fecha=row["fecha"],
                            defaults={
                                "symbol": config["symbol"],
                                "close": Decimal(str(row["close"])),
                                "adjusted_close": Decimal(str(row["adjusted_close"])),
                                "volume": row["volume"],
                            },
                        )
                        if was_created:
                            created_for_interval += 1
                        else:
                            updated_for_interval += 1

                interval_results[interval] = {
                    "success": True,
                    "rows_received": len(rows),
                    "created": created_for_interval,
                    "updated": updated_for_interval,
                }
                created += created_for_interval
                updated += updated_for_interval
                rows_received += len(rows)
            except Exception as exc:
                success = False
                interval_results[interval] = {
                    "success": False,
                    "rows_received": 0,
                    "created": 0,
                    "updated": 0,
                    "error": str(exc),
                }

        return {
            "success": success,
            "benchmark_key": benchmark_key,
            "symbol": config["symbol"],
            "provider": config["provider"],
            "rows_received": rows_received,
            "created": created,
            "updated": updated,
            "intervals": interval_results,
            "error": "; ".join(
                f"{interval}: {payload['error']}"
                for interval, payload in interval_results.items()
                if not payload.get("success", True)
            ),
        }

    def build_returns(self, benchmark_key: str, dates: Iterable[pd.Timestamp], interval: str = "daily") -> pd.Series:
        normalized_dates = pd.to_datetime(list(dates))
        if len(normalized_dates) == 0:
            return pd.Series(dtype=float)

        config = ParametrosBenchmark.HISTORICAL_SERIES.get(benchmark_key)
        if not config:
            return pd.Series(dtype=float)

        snapshots = BenchmarkSnapshot.objects.filter(
            benchmark_key=benchmark_key,
            source=config["provider"],
            interval=interval,
            fecha__range=(
                (
                    normalized_dates.min() -
                    timedelta(days=7 if interval == "weekly_adjusted" else 1)
                ).date(),
                normalized_dates.max().date(),
            ),
        ).order_by("fecha")
        if snapshots.count() < 2:
            return pd.Series(dtype=float)

        field_name = config.get("field", "adjusted_close")
        df = pd.DataFrame(list(snapshots.values("fecha", field_name)))
        if df.empty:
            return pd.Series(dtype=float)

        df["fecha"] = pd.to_datetime(df["fecha"])
        df[field_name] = pd.to_numeric(df[field_name], errors="coerce")
        df = df.dropna(subset=[field_name]).set_index("fecha").sort_index()
        if len(df.index) < 2:
            return pd.Series(dtype=float)

        returns = df[field_name].pct_change().dropna()
        if returns.empty:
            return pd.Series(dtype=float)

        return returns.reindex(normalized_dates).ffill()

    def build_daily_returns(self, benchmark_key: str, dates: Iterable[pd.Timestamp]) -> pd.Series:
        return self.build_returns(benchmark_key, dates, interval="daily")

    def build_weekly_returns(self, benchmark_key: str, dates: Iterable[pd.Timestamp]) -> pd.Series:
        return self.build_returns(benchmark_key, dates, interval="weekly_adjusted")

    def get_status_summary(self) -> list[dict]:
        rows = []
        aggregated = {
            (row["benchmark_key"], row["interval"]): row
            for row in BenchmarkSnapshot.objects.values("benchmark_key", "interval").annotate(
                latest_date=Max("fecha"),
                rows_count=Count("id"),
            )
        }
        for benchmark_key, config in ParametrosBenchmark.HISTORICAL_SERIES.items():
            daily = aggregated.get((benchmark_key, "daily"))
            weekly = aggregated.get((benchmark_key, "weekly_adjusted"))
            rows_count = (daily["rows_count"] if daily else 0) + (weekly["rows_count"] if weekly else 0)
            latest_date = max(
                date_value
                for date_value in [daily["latest_date"] if daily else None, weekly["latest_date"] if weekly else None]
                if date_value is not None
            ) if (daily or weekly) else None
            rows.append(
                {
                    "benchmark_key": benchmark_key,
                    "symbol": config["symbol"],
                    "provider": config["provider"],
                    "latest_date": latest_date,
                    "rows_count": rows_count,
                    "daily_rows_count": daily["rows_count"] if daily else 0,
                    "daily_latest_date": daily["latest_date"] if daily else None,
                    "weekly_rows_count": weekly["rows_count"] if weekly else 0,
                    "weekly_latest_date": weekly["latest_date"] if weekly else None,
                    "is_ready": bool(
                        (daily and daily["rows_count"] >= 2) or
                        (weekly and weekly["rows_count"] >= 2)
                    ),
                }
            )
        return rows

    def _fetch_rows(self, symbol: str, interval: str, outputsize: str = "compact") -> list[dict]:
        fetcher_name = self.INTERVAL_FETCHERS.get(interval)
        if not fetcher_name:
            raise ValueError(f"Unsupported benchmark interval: {interval}")

        fetcher = getattr(self.client, fetcher_name)
        if interval == "daily":
            return fetcher(symbol, outputsize=outputsize)
        return fetcher(symbol)
