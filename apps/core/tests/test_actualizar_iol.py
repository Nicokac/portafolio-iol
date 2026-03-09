import pytest
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase

from apps.core.services.iol_sync_service import IOLSyncService


class TestActualizarIOLCommand(TestCase):
    @patch.object(IOLSyncService, 'sync_all')
    def test_command_success(self, mock_sync):
        mock_sync.return_value = {
            'estado_cuenta': True,
            'portafolio_argentina': True,
            'operaciones': True,
        }

        call_command('actualizar_iol')

        mock_sync.assert_called_once()

    @patch.object(IOLSyncService, 'sync_all')
    def test_command_partial_failure(self, mock_sync):
        mock_sync.return_value = {
            'estado_cuenta': True,
            'portafolio_argentina': False,
            'operaciones': True,
        }

        call_command('actualizar_iol')

        mock_sync.assert_called_once()