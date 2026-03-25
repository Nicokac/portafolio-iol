import math
from datetime import timedelta

import pandas as pd
from django.db.models import Count
from django.utils import timezone

from apps.portafolio_iol.models import PortfolioSnapshot


class SnapshotIntegrityService:
    """Validaciones de integridad sobre snapshots patrimoniales."""

    def run_checks(self, days: int = 120):
        checked_at = timezone.now()
        end_date = checked_at.date()
        start_date = end_date - timedelta(days=days)

        snapshots = list(
            PortfolioSnapshot.objects.filter(fecha__range=(start_date, end_date)).order_by("fecha")
        )
        if not snapshots:
            return {
                "warning": "no_snapshots",
                "duplicate_dates": [],
                "time_gaps": [],
                "extreme_changes": [],
                "valuation_inconsistencies": [],
                "checked_at": checked_at.isoformat(),
            }

        duplicate_dates = self._check_duplicate_dates(start_date, end_date)
        time_gaps = self._check_time_gaps(snapshots)
        extreme_changes = self._check_extreme_changes(snapshots)
        valuation_inconsistencies = self._check_valuation_consistency(snapshots)

        return {
            "duplicate_dates": duplicate_dates,
            "time_gaps": time_gaps,
            "extreme_changes": extreme_changes,
            "valuation_inconsistencies": valuation_inconsistencies,
            "issues_count": (
                len(duplicate_dates)
                + len(time_gaps)
                + len(extreme_changes)
                + len(valuation_inconsistencies)
            ),
            "checked_at": checked_at.isoformat(),
        }

    @staticmethod
    def _check_duplicate_dates(start_date, end_date):
        duplicates = (
            PortfolioSnapshot.objects.filter(fecha__range=(start_date, end_date))
            .values("fecha")
            .annotate(c=Count("id"))
            .filter(c__gt=1)
        )
        return [{"fecha": item["fecha"], "count": item["c"]} for item in duplicates]

    @staticmethod
    def _check_time_gaps(snapshots):
        gaps = []
        for idx in range(1, len(snapshots)):
            prev_date = snapshots[idx - 1].fecha
            curr_date = snapshots[idx].fecha
            delta = (curr_date - prev_date).days
            if delta > 3:
                gaps.append({"from": prev_date, "to": curr_date, "gap_days": delta})
        return gaps

    @staticmethod
    def _check_extreme_changes(snapshots):
        data = pd.DataFrame(
            [{"fecha": s.fecha, "total_iol": float(s.total_iol)} for s in snapshots]
        ).sort_values("fecha")
        data["ret"] = data["total_iol"].pct_change() * 100
        extremes = data[data["ret"].abs() > 25].dropna()
        return [
            {"fecha": row["fecha"], "change_pct": round(float(row["ret"]), 2)}
            for _, row in extremes.iterrows()
            if math.isfinite(float(row["ret"]))
        ]

    @staticmethod
    def _check_valuation_consistency(snapshots):
        issues = []
        for snap in snapshots:
            if snap.cash_disponible_broker is not None or snap.caucion_colocada is not None:
                reconstructed = float(
                    snap.portafolio_invertido
                    + (snap.cash_disponible_broker or 0)
                    + (snap.caucion_colocada or 0)
                    + snap.cash_management
                )
                total = float(snap.total_patrimonio_modelado or 0)
                reference_field = "total_patrimonio_modelado"
            else:
                reconstructed = float(snap.portafolio_invertido + snap.liquidez_operativa + snap.cash_management)
                total = float(snap.total_iol)
                reference_field = "total_iol"

            if total == 0:
                continue
            diff_pct = abs(reconstructed - total) / total * 100
            if diff_pct > 5:
                issues.append(
                    {
                        "fecha": snap.fecha,
                        "reference_field": reference_field,
                        "reference_total": total,
                        "reconstructed_total": round(reconstructed, 2),
                        "difference_pct": round(diff_pct, 2),
                    }
                )
        return issues
