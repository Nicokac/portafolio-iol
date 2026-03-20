import logging
from datetime import date, datetime, time, timedelta
from typing import Dict, List, Optional
from urllib.parse import quote

import requests
from django.conf import settings
from django.utils import timezone

from apps.core.models import IOLToken
from apps.core.services.token_manager import IOLTokenManager


logger = logging.getLogger(__name__)


class IOLAPIClient:
    """Cliente para interactuar con la API de InvertirOnline."""

    def __init__(self):
        self.base_url = settings.IOL_BASE_URL
        self.username = getattr(settings, 'IOL_USERNAME', None)
        self.password = getattr(settings, 'IOL_PASSWORD', None)
        self.token_manager = IOLTokenManager()

        # Para compatibilidad con código existente
        self.access_token: Optional[str] = None
        self.refresh_token: Optional[str] = None
        self.token_expires_at: Optional[timezone.datetime] = None
        self.last_error: Dict[str, object] = {}

    def _get_headers(self) -> Dict[str, str]:
        """Obtiene headers con token de acceso."""
        token = self.token_manager.get_valid_token()
        if not token:
            raise ValueError("No access token available. Please login first.")
        return {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json',
        }

    def _build_auth_context(self) -> Dict[str, object]:
        latest_token = IOLToken.objects.order_by("-created_at").first()
        now = timezone.now()
        token_expired = None
        seconds_to_expiry = None
        has_refresh_token = False
        if latest_token:
            token_expired = latest_token.expires_at <= now
            seconds_to_expiry = int((latest_token.expires_at - now).total_seconds())
            has_refresh_token = bool(latest_token.refresh_token)

        return {
            "has_username": bool(self.username),
            "has_password": bool(self.password),
            "has_saved_token": latest_token is not None,
            "token_expired": token_expired,
            "seconds_to_expiry": seconds_to_expiry,
            "has_refresh_token": has_refresh_token,
        }

    def _set_last_error(
        self,
        *,
        operation: str,
        url: str,
        error_type: str,
        status_code: Optional[int] = None,
        message: str = "",
    ) -> None:
        self.last_error = {
            "operation": operation,
            "url": url,
            "error_type": error_type,
            "status_code": status_code,
            "message": message,
            "auth_context": self._build_auth_context(),
            "occurred_at": timezone.now().isoformat(),
        }

    def _request_json(
        self,
        *,
        operation: str,
        url: str,
        params: Optional[Dict] = None,
    ) -> Optional[object]:
        self._ensure_valid_token()
        try:
            response = requests.get(url, headers=self._get_headers(), params=params, timeout=30)
            response.raise_for_status()
            self.last_error = {}
            return response.json()
        except requests.HTTPError as exc:
            status_code = exc.response.status_code if exc.response is not None else None
            if status_code == 401:
                logger.warning(
                    "IOL API returned 401 for %s. Trying token refresh/login and retrying once.",
                    operation,
                )
                self.token_manager.invalidate_current_token()
                self._ensure_valid_token()
                try:
                    retry_response = requests.get(url, headers=self._get_headers(), params=params, timeout=30)
                    retry_response.raise_for_status()
                    self.last_error = {}
                    return retry_response.json()
                except requests.RequestException as retry_exc:
                    retry_status = (
                        retry_exc.response.status_code
                        if isinstance(retry_exc, requests.HTTPError) and retry_exc.response is not None
                        else None
                    )
                    self._set_last_error(
                        operation=operation,
                        url=url,
                        error_type="http_error_after_retry",
                        status_code=retry_status,
                        message=str(retry_exc),
                    )
                    logger.error("Failed %s after retry: %s", operation, retry_exc)
                    return None

            self._set_last_error(
                operation=operation,
                url=url,
                error_type="http_error",
                status_code=status_code,
                message=str(exc),
            )
            logger.error("Failed %s: %s", operation, exc)
            return None
        except requests.RequestException as exc:
            self._set_last_error(
                operation=operation,
                url=url,
                error_type="request_error",
                message=str(exc),
            )
            logger.error("Failed %s: %s", operation, exc)
            return None
        except Exception as exc:
            self._set_last_error(
                operation=operation,
                url=url,
                error_type="unexpected_error",
                message=str(exc),
            )
            logger.error("Failed %s with unexpected error: %s", operation, exc)
            return None

    def login(self) -> bool:
        """Autentica con IOL y obtiene tokens."""
        url = f"{self.base_url}/token"
        data = {
            'username': self.username,
            'password': self.password,
            'grant_type': 'password',
        }
        try:
            if not self.username or not self.password:
                self._set_last_error(
                    operation="login",
                    url=url,
                    error_type="missing_credentials",
                    message="IOL_USERNAME/IOL_PASSWORD are empty",
                )
                logger.error("Cannot login to IOL API: missing credentials in environment")
                return False
            response = requests.post(url, data=data, timeout=30)
            response.raise_for_status()
            token_data = response.json()

            # Guardar token usando el manager
            self.token_manager.save_token(
                access_token=token_data['access_token'],
                refresh_token=token_data.get('refresh_token'),
                expires_in=3600  # Asumir 1 hora
            )

            # Para compatibilidad
            self.access_token = token_data['access_token']
            self.refresh_token = token_data.get('refresh_token')
            self.token_expires_at = timezone.now() + timezone.timedelta(hours=1)
            self.last_error = {}

            logger.info("Successfully logged in to IOL API")
            return True
        except Exception as e:
            status_code = e.response.status_code if isinstance(e, requests.HTTPError) and e.response is not None else None
            self._set_last_error(
                operation="login",
                url=url,
                error_type="login_error",
                status_code=status_code,
                message=str(e),
            )
            logger.error(f"Failed to login to IOL API: {e}")
            return False

    def refresh_access_token(self) -> bool:
        """Renueva el access token usando refresh token."""
        current_token = self.token_manager._current_token
        refresh_token = current_token.get_refresh_token() if current_token else None
        if not current_token or not refresh_token:
            logger.warning("No refresh token available")
            return False

        url = f"{self.base_url}/token"
        data = {
            'refresh_token': refresh_token,
            'grant_type': 'refresh_token',
        }
        try:
            response = requests.post(url, data=data, timeout=30)
            response.raise_for_status()
            token_data = response.json()

            # Guardar nuevo token
            self.token_manager.save_token(
                access_token=token_data['access_token'],
                refresh_token=token_data.get('refresh_token'),
                expires_in=3600
            )

            # Para compatibilidad
            self.access_token = token_data['access_token']
            self.refresh_token = token_data.get('refresh_token')
            self.token_expires_at = timezone.now() + timezone.timedelta(hours=1)
            self.last_error = {}

            logger.info("Successfully refreshed IOL API token")
            return True
        except Exception as e:
            status_code = e.response.status_code if isinstance(e, requests.HTTPError) and e.response is not None else None
            self._set_last_error(
                operation="refresh_token",
                url=url,
                error_type="refresh_error",
                status_code=status_code,
                message=str(e),
            )
            logger.error(f"Failed to refresh IOL API token: {e}")
            return False

    def _ensure_valid_token(self) -> None:
        """Asegura que el token sea válido, renovándolo si es necesario."""
        token = self.token_manager.get_valid_token()
        if not token:
            # Intentar refresh si tenemos refresh token
            current_token = self.token_manager._current_token
            if current_token and current_token.refresh_token:
                if not self.refresh_access_token():
                    self.login()
            else:
                self.login()

    def get_estado_cuenta(self) -> Optional[Dict]:
        """Obtiene el estado de cuenta."""
        url = f"{self.base_url}/api/v2/estadocuenta"
        data = self._request_json(operation="get_estado_cuenta", url=url)
        return data if isinstance(data, dict) else None

    def get_portafolio(self, pais: str = 'argentina') -> Optional[Dict]:
        """Obtiene el portafolio para un país."""
        url = f"{self.base_url}/api/v2/portafolio/{pais}"
        data = self._request_json(operation=f"get_portafolio:{pais}", url=url)
        return data if isinstance(data, dict) else None

    def get_operaciones(self, params: Optional[Dict] = None) -> Optional[List[Dict]]:
        """Obtiene las operaciones."""
        url = f"{self.base_url}/api/v2/operaciones"
        data = self._request_json(operation="get_operaciones", url=url, params=params)
        return data if isinstance(data, list) else None

    def get_titulo(self, mercado: str, simbolo: str) -> Optional[Dict]:
        """Obtiene metadata minima de un titulo en un mercado dado."""
        mercado_path = quote(str(mercado or "").strip(), safe="")
        simbolo_path = quote(str(simbolo or "").strip(), safe="")
        url = f"{self.base_url}/api/v2/{mercado_path}/Titulos/{simbolo_path}"
        data = self._request_json(
            operation=f"get_titulo:{mercado}:{simbolo}",
            url=url,
        )
        return data if isinstance(data, dict) else None

    def get_fci(self, simbolo: str) -> Optional[Dict]:
        """Obtiene metadata de un FCI por simbolo."""
        simbolo_path = quote(str(simbolo or "").strip(), safe="")
        url = f"{self.base_url}/api/v2/Titulos/FCI/{simbolo_path}"
        data = self._request_json(
            operation=f"get_fci:{simbolo}",
            url=url,
        )
        return data if isinstance(data, dict) else None

    def get_titulo_historicos(
        self,
        mercado: str,
        simbolo: str,
        params: Optional[Dict] = None,
    ) -> Optional[List[Dict]]:
        """Obtiene serie historica de cotizacion para un titulo."""
        fecha_desde, fecha_hasta, ajustada = self._resolve_historical_series_params(params)
        mercado_path = quote(str(mercado or "").strip(), safe="")
        simbolo_path = quote(str(simbolo or "").strip(), safe="")
        fecha_desde_path = quote(fecha_desde, safe="")
        fecha_hasta_path = quote(fecha_hasta, safe="")
        ajustada_path = quote(ajustada, safe="")
        url = (
            f"{self.base_url}/api/v2/{mercado_path}/Titulos/{simbolo_path}/Cotizacion/seriehistorica/"
            f"{fecha_desde_path}/{fecha_hasta_path}/{ajustada_path}"
        )
        data = self._request_json(
            operation=f"get_titulo_historicos:{mercado}:{simbolo}",
            url=url,
        )
        return data if isinstance(data, list) else None

    @staticmethod
    def _resolve_historical_series_params(params: Optional[Dict]) -> tuple[str, str, str]:
        params = params or {}
        today = date.today()
        fecha_desde = IOLAPIClient._coerce_datetime_path(
            params.get("fecha_desde") or params.get("fechaDesde") or params.get("desde") or (today - timedelta(days=365))
        )
        fecha_hasta = IOLAPIClient._coerce_datetime_path(
            params.get("fecha_hasta") or params.get("fechaHasta") or params.get("hasta") or today,
            end_of_day=True,
        )
        ajustada = str(params.get("ajustada") or "ajustada").strip() or "ajustada"
        return fecha_desde, fecha_hasta, ajustada

    @staticmethod
    def _coerce_datetime_path(value, *, end_of_day: bool = False) -> str:
        if isinstance(value, datetime):
            dt_value = value
        elif isinstance(value, date):
            dt_value = datetime.combine(value, time.max if end_of_day else time.min)
        else:
            text = str(value).strip()
            try:
                dt_value = datetime.fromisoformat(text.replace("Z", "+00:00"))
            except ValueError:
                dt_date = date.fromisoformat(text.split("T")[0])
                dt_value = datetime.combine(dt_date, time.max if end_of_day else time.min)
        if end_of_day and dt_value.time() == time.min:
            dt_value = datetime.combine(dt_value.date(), time.max)
        if not end_of_day and dt_value.time() == time.max:
            dt_value = datetime.combine(dt_value.date(), time.min)
        return dt_value.isoformat(timespec="seconds")
