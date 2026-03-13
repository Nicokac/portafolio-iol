from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from typing import Iterable

import pandas as pd
from django.db import transaction

from apps.core.config.parametros_benchmark import ParametrosBenchmark
from apps.core.models import BenchmarkSnapshot
from apps.core.services.market_data.alpha_vantage_client import AlphaVantageClient


class BenchmarkSeriesService:
    def __init__(self, client: AlphaVantageClient | None = None):
        self.client = client or AlphaVantageClient()

    def sync_all(self, outputsize: str = "compact") -> dict:
        results = {}
        for benchmark_key in ParametrosBenchmark.HISTORICAL_SERIES:
            results[benchmark_key] = self.sync_benchmark(benchmark_key, outputsize=outputsize)
        return results

    def sync_benchmark(self, benchmark_key: str, outputsize: str = "compact") -> dict:
        config = ParametrosBenchmark.HISTORICAL_SERIES.get(benchmark_key)
        if not config:
            raise ValueError(f"Unknown historical benchmark key: {benchmark_key}")

        rows = self.client.fetch_daily_adjusted(config["symbol"], outputsize=outputsize)
        created = 0
        updated = 0

        with transaction.atomic():
            for row in rows:
                _, was_created = BenchmarkSnapshot.objects.update_or_create(
                    benchmark_key=benchmark_key,
                    source=config["provider"],
                    fecha=row["fecha"],
                    defaults={
                        "symbol": config["symbol"],
                        "close": Decimal(str(row["close"])),
                        "adjusted_close": Decimal(str(row["adjusted_close"])),
                        "volume": row["volume"],
                    },
                )
                if was_created:
                    created += 1
                else:
                    updated += 1

        return {
            "success": True,
            "benchmark_key": benchmark_key,
            "symbol": config["symbol"],
            "provider": config["provider"],
            "rows_received": len(rows),
            "created": created,
            "updated": updated,
        }

    def build_daily_returns(self, benchmark_key: str, dates: Iterable[pd.Timestamp]) -> pd.Series:
        normalized_dates = pd.to_datetime(list(dates))
        if len(normalized_dates) == 0:
            return pd.Series(dtype=float)

        config = ParametrosBenchmark.HISTORICAL_SERIES.get(benchmark_key)
        if not config:
            return pd.Series(dtype=float)

        snapshots = BenchmarkSnapshot.objects.filter(
            benchmark_key=benchmark_key,
            source=config["provider"],
            fecha__range=(
                (normalized_dates.min() - timedelta(days=1)).date(),
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
