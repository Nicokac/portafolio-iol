from __future__ import annotations

from datetime import datetime

import requests


class BCRAClient:
    BASE_URL = "https://api.bcra.gob.ar/estadisticas/v4.0"

    def fetch_variable(self, variable_id: str, limit: int = 1000) -> list[dict]:
        response = requests.get(
            f"{self.BASE_URL}/monetarias/{variable_id}",
            params={"limit": limit},
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()

        if payload.get("status") != 200:
            raise ValueError(f"BCRA API error for variable {variable_id}")

        results = payload.get("results", [])
        if not results:
            return []

        rows = []
        for item in results[0].get("detalle", []):
            rows.append(
                {
                    "fecha": datetime.strptime(item["fecha"], "%Y-%m-%d").date(),
                    "value": float(item["valor"]),
                }
            )
        return sorted(rows, key=lambda item: item["fecha"])
