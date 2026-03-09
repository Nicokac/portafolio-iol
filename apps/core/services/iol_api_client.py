import logging
from typing import Dict, List, Optional

import requests
from django.conf import settings
from django.utils import timezone

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

    def _get_headers(self) -> Dict[str, str]:
        """Obtiene headers con token de acceso."""
        token = self.token_manager.get_valid_token()
        if not token:
            raise ValueError("No access token available. Please login first.")
        return {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json',
        }

    def login(self) -> bool:
        """Autentica con IOL y obtiene tokens."""
        url = f"{self.base_url}/token"
        data = {
            'username': self.username,
            'password': self.password,
            'grant_type': 'password',
        }
        try:
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

            logger.info("Successfully logged in to IOL API")
            return True
        except Exception as e:
            logger.error(f"Failed to login to IOL API: {e}")
            return False

    def refresh_access_token(self) -> bool:
        """Renueva el access token usando refresh token."""
        current_token = self.token_manager._current_token
        if not current_token or not current_token.refresh_token:
            logger.warning("No refresh token available")
            return False

        url = f"{self.base_url}/token"
        data = {
            'refresh_token': current_token.refresh_token,
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

            logger.info("Successfully refreshed IOL API token")
            return True
        except Exception as e:
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
        self._ensure_valid_token()
        url = f"{self.base_url}/api/v2/estadocuenta"
        try:
            response = requests.get(url, headers=self._get_headers(), timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"Failed to get estado cuenta: {e}")
            return None

    def get_portafolio(self, pais: str = 'argentina') -> Optional[Dict]:
        """Obtiene el portafolio para un país."""
        self._ensure_valid_token()
        url = f"{self.base_url}/api/v2/portafolio/{pais}"
        try:
            response = requests.get(url, headers=self._get_headers(), timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"Failed to get portafolio for {pais}: {e}")
            return None

    def get_operaciones(self, params: Optional[Dict] = None) -> Optional[List[Dict]]:
        """Obtiene las operaciones."""
        self._ensure_valid_token()
        url = f"{self.base_url}/api/v2/operaciones"
        try:
            response = requests.get(url, headers=self._get_headers(), params=params, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"Failed to get operaciones: {e}")
            return None