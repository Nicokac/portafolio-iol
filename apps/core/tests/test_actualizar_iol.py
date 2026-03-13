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

    @patch.object(IOLSyncService, 'sync_estado_cuenta')
    @patch.object(IOLSyncService, 'sync_portafolio')
    @patch.object(IOLSyncService, 'sync_operaciones')
    @patch.object(IOLSyncService, 'sync_all')
    def test_command_runs_only_selected_syncs(
        self,
        mock_sync_all,
        mock_sync_operaciones,
        mock_sync_portafolio,
        mock_sync_estado_cuenta,
    ):
        mock_sync_estado_cuenta.return_value = True
        mock_sync_portafolio.return_value = True

        call_command('actualizar_iol', '--estado-cuenta', '--portafolio')

        mock_sync_all.assert_not_called()
        mock_sync_estado_cuenta.assert_called_once()
        mock_sync_portafolio.assert_called_once_with('argentina')
        mock_sync_operaciones.assert_not_called()

    @patch.object(IOLSyncService, 'sync_estado_cuenta')
    @patch.object(IOLSyncService, 'sync_portafolio')
    @patch.object(IOLSyncService, 'sync_operaciones')
    @patch.object(IOLSyncService, 'sync_all')
    def test_command_runs_operaciones_only_when_requested(
        self,
        mock_sync_all,
        mock_sync_operaciones,
        mock_sync_portafolio,
        mock_sync_estado_cuenta,
    ):
        mock_sync_operaciones.return_value = True

        call_command('actualizar_iol', '--operaciones')

        mock_sync_all.assert_not_called()
        mock_sync_estado_cuenta.assert_not_called()
        mock_sync_portafolio.assert_not_called()
        mock_sync_operaciones.assert_called_once()

    @patch.object(IOLSyncService, 'sync_all')
    def test_command_prints_failure_diagnostics(self, mock_sync):
        mock_sync.return_value = {
            'estado_cuenta': False,
            'portafolio_argentina': True,
            'operaciones': False,
        }
        mock_sync_service = mock_sync.return_value
        # no-op; we inspect patched instance via class mock below

        with patch('apps.core.management.commands.actualizar_iol.IOLSyncService') as mock_service_cls:
            service = mock_service_cls.return_value
            service.sync_all.return_value = {
                'estado_cuenta': False,
                'portafolio_argentina': True,
                'operaciones': False,
            }
            service.last_diagnostics = {
                'estado_cuenta': {
                    'operation': 'estado_cuenta',
                    'error_type': 'http_error',
                    'status_code': 401,
                    'message': 'Unauthorized',
                    'auth_context': {
                        'has_username': True,
                        'has_password': True,
                        'has_saved_token': True,
                        'token_expired': True,
                        'has_refresh_token': False,
                    },
                },
                'operaciones': {},
            }

            with patch('sys.stdout') as mock_stdout:
                call_command('actualizar_iol')

            output = ''.join(call.args[0] for call in mock_stdout.write.call_args_list)
            assert 'Diagnostico rapido de fallas:' in output
            assert 'operacion: estado_cuenta' in output
            assert 'tipo_error: http_error' in output
            assert 'status_code: 401' in output
            assert 'sin detalle tecnico disponible' in output
            assert 'Checklist sugerido:' in output

    def test_print_failure_diagnostics_returns_early_when_all_succeeded(self):
        from apps.core.management.commands.actualizar_iol import Command

        command = Command()
        service = type('Service', (), {'last_diagnostics': {}})()

        with patch.object(command.stdout, 'write') as mock_write:
            command._print_failure_diagnostics(service, {'estado_cuenta': True})

        mock_write.assert_not_called()
