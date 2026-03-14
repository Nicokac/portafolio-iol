from __future__ import annotations

from datetime import datetime

import requests


class DatosGobSeriesClient:
    BASE_URL = "https://apis.datos.gob.ar/series/api/series"

    def fetch_series(self, series_id: str, limit: int = 5000) -> list[dict]:
        response = requests.get(
            self.BASE_URL,
            params={"ids": series_id, "limit": limit},
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()

        rows = []
        for raw_date, value in payload.get("data", []):
            rows.append(
                {
                    "fecha": datetime.strptime(raw_date, "%Y-%m-%d").date(),
                    "value": float(value),
                }
            )
        return sorted(rows, key=lambda item: item["fecha"])
