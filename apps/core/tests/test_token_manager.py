import pytest
from django.utils import timezone
from datetime import timedelta
from apps.core.services.token_manager import IOLTokenManager
from apps.core.models import IOLToken


@pytest.mark.django_db
class TestIOLTokenManager:

    def test_get_valid_token_no_tokens(self):
        manager = IOLTokenManager()
        result = manager.get_valid_token()
        assert result is None

    def test_get_valid_token_with_valid_token(self):
        IOLToken.objects.create(
            access_token='valid_token',
            refresh_token='refresh',
            expires_at=timezone.now() + timedelta(hours=1),
        )
        manager = IOLTokenManager()
        result = manager.get_valid_token()
        assert result == 'valid_token'
        assert manager._current_token is not None

    def test_get_valid_token_expired(self):
        IOLToken.objects.create(
            access_token='expired_token',
            refresh_token='refresh',
            expires_at=timezone.now() - timedelta(hours=1),
        )
        manager = IOLTokenManager()
        result = manager.get_valid_token()
        assert result is None

    def test_save_token(self):
        manager = IOLTokenManager()
        token = manager.save_token(
            access_token='new_token',
            refresh_token='new_refresh',
            expires_in=3600,
        )
        assert token.access_token == 'new_token'
        assert manager._current_token == token
        assert IOLToken.objects.count() == 1

    def test_refresh_token_returns_none(self):
        manager = IOLTokenManager()
        result = manager.refresh_token('some_refresh_token')
        assert result is None

    def test_invalidate_current_token(self):
        manager = IOLTokenManager()
        manager.save_token('token_to_invalidate', expires_in=3600)
        manager.invalidate_current_token()
        assert manager._current_token.expires_at <= timezone.now()

    def test_clear_all_tokens(self):
        manager = IOLTokenManager()
        manager.save_token('token1', expires_in=3600)
        manager.save_token('token2', expires_in=3600)
        manager.clear_all_tokens()
        assert IOLToken.objects.count() == 0
        assert manager._current_token is None