import pytest
from django.utils import timezone
from datetime import timedelta
from unittest.mock import patch
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
        assert token.access_token != 'new_token'
        assert token.get_access_token() == 'new_token'
        assert token.get_refresh_token() == 'new_refresh'
        assert manager._current_token == token
        assert IOLToken.objects.count() == 1

    def test_save_token_reuses_latest_row_atomically(self):
        IOLToken.objects.create(
            access_token='legacy_token',
            refresh_token='legacy_refresh',
            expires_at=timezone.now() + timedelta(hours=1),
        )
        latest = IOLToken.objects.create(
            access_token='older_extra',
            refresh_token='older_refresh',
            expires_at=timezone.now() + timedelta(minutes=30),
        )

        manager = IOLTokenManager()
        token = manager.save_token('replacement_token', 'replacement_refresh', expires_in=3600)

        assert token.pk == latest.pk
        assert token.get_access_token() == 'replacement_token'
        assert token.get_refresh_token() == 'replacement_refresh'
        assert IOLToken.objects.count() == 1

    def test_save_token_rolls_back_if_update_fails(self):
        existing = IOLToken.objects.create(
            access_token='stable_token',
            refresh_token='stable_refresh',
            expires_at=timezone.now() + timedelta(hours=1),
        )

        with patch.object(IOLToken, 'save', side_effect=RuntimeError('boom')):
            with pytest.raises(RuntimeError):
                IOLToken.save_token('new_token', 'new_refresh', expires_in=3600)

        existing.refresh_from_db()
        assert IOLToken.objects.count() == 1
        assert existing.get_access_token() == 'stable_token'
        assert existing.get_refresh_token() == 'stable_refresh'

    def test_get_valid_token_supports_legacy_plaintext_tokens(self):
        token = IOLToken.objects.create(
            access_token='legacy_plain_token',
            refresh_token='legacy_refresh',
            expires_at=timezone.now() + timedelta(hours=1),
        )
        manager = IOLTokenManager()
        assert manager.get_valid_token() == 'legacy_plain_token'
        assert token.get_refresh_token() == 'legacy_refresh'
        token.refresh_from_db()
        assert token.access_token != 'legacy_plain_token'
        assert token.refresh_token != 'legacy_refresh'
        assert token.access_token.startswith('enc::')
        assert token.refresh_token.startswith('enc::')

    def test_get_access_token_keeps_encrypted_tokens_unchanged(self):
        token = IOLToken.save_token(
            access_token='encrypted_token',
            refresh_token='encrypted_refresh',
            expires_in=3600,
        )
        original_access = token.access_token
        original_refresh = token.refresh_token

        assert token.get_access_token() == 'encrypted_token'
        assert token.get_refresh_token() == 'encrypted_refresh'

        token.refresh_from_db()
        assert token.access_token == original_access
        assert token.refresh_token == original_refresh

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
