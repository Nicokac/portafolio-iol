import logging
from typing import Optional

from django.utils import timezone

from apps.core.models import IOLToken

logger = logging.getLogger(__name__)


class IOLTokenManager:
    """Gestor de tokens para la API de IOL con persistencia en base de datos."""

    def __init__(self):
        self._current_token: Optional[IOLToken] = None

    def get_valid_token(self) -> Optional[str]:
        """Obtiene un token válido, renovándolo si es necesario."""
        # Buscar token válido en BD
        token_obj = IOLToken.get_latest_valid_token()

        if token_obj:
            self._current_token = token_obj
            return token_obj.get_access_token()

        # No hay token válido
        return None

    def save_token(self, access_token: str, refresh_token: str = None, expires_in: int = 3600) -> IOLToken:
        """Guarda un nuevo token en la base de datos."""
        token_obj = IOLToken.save_token(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=expires_in
        )
        self._current_token = token_obj
        logger.info("Saved new IOL token to database")
        return token_obj

    def refresh_token(self, refresh_token: str) -> Optional[str]:
        """Renueva un token usando el refresh token."""
        # Aquí iría la lógica para hacer refresh con la API
        # Por ahora, devolver None para forzar nuevo login
        logger.warning("Token refresh not implemented yet")
        return None

    def invalidate_current_token(self):
        """Invalida el token actual."""
        if self._current_token:
            # Marcar como expirado inmediatamente
            self._current_token.expires_at = timezone.now()
            self._current_token.save()
            logger.info("Invalidated current IOL token")

    def clear_all_tokens(self):
        """Elimina todos los tokens almacenados."""
        IOLToken.objects.all().delete()
        self._current_token = None
        logger.info("Cleared all IOL tokens from database")
