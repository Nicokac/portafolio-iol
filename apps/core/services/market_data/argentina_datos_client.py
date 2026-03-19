from __future__ import annotations

import requests


class ArgentinaDatosClient:
    BASE_URL = "https://api.argentinadatos.com/v1"

    def fetch_status(self) -> dict:
        response = requests.get(f"{self.BASE_URL}/estado", timeout=10)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("ArgentinaDatos status payload must be a JSON object")
        return payload
