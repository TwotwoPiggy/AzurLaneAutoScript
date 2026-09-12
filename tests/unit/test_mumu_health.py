import sys
import unittest
from unittest import mock

# Mock external hardware/network dependencies if not installed in current environment
for mod_name in ['uiautomator2', 'adbutils', 'adbutils.errors']:
    if mod_name not in sys.modules:
        try:
            __import__(mod_name)
        except ImportError:
            sys.modules[mod_name] = mock.MagicMock()

if 'uiautomator2cache' not in sys.modules:
    try:
        import uiautomator2cache
    except ImportError:
        mock_u2c = mock.MagicMock()
        mock_u2c.__file__ = 'dummy/uiautomator2cache.py'
        sys.modules['uiautomator2cache'] = mock_u2c

import pytest

from module.device.connection import Connection


def make_connection(is_mumu_family=True):
    """
    Creates a mock Connection object with real check_mumu_nemu_ipc_health method bound,
    avoiding network/device hardware calls in Connection.__init__.
    """
    conn = mock.MagicMock(spec=Connection)
    conn.is_mumu_family = is_mumu_family
    # Bind the real method from Connection class to the mock instance
    conn.check_mumu_nemu_ipc_health = Connection.check_mumu_nemu_ipc_health.__get__(conn, Connection)
    return conn


class TestMuMuHealthDiagnostics(unittest.TestCase):
    @mock.patch('module.device.connection.IS_WINDOWS', False)
    @mock.patch('module.device.connection.logger')
    def test_non_windows_skip(self, mock_logger):
        """On non-Windows OS, check_mumu_nemu_ipc_health must skip immediately."""
        conn = make_connection(is_mumu_family=True)
        conn.nemu_ipc_available = mock.Mock(return_value=False)

        conn.check_mumu_nemu_ipc_health()

        mock_logger.warning.assert_not_called()

    @mock.patch('module.device.connection.IS_WINDOWS', True)
    @mock.patch('module.device.connection.logger')
    def test_non_mumu_skip(self, mock_logger):
        """On Windows but non-MuMu emulator (e.g. LDPlayer/Nox), check must skip immediately."""
        conn = make_connection(is_mumu_family=False)
        conn.nemu_ipc_available = mock.Mock(return_value=False)

        conn.check_mumu_nemu_ipc_health()

        mock_logger.warning.assert_not_called()

    @mock.patch('module.device.connection.IS_WINDOWS', True)
    @mock.patch('module.device.connection.logger')
    def test_mumu_with_nemu_ipc_available(self, mock_logger):
        """On Windows MuMu with NemuIPC available, no warning should be logged."""
        conn = make_connection(is_mumu_family=True)
        conn.nemu_ipc_available = mock.Mock(return_value=True)

        conn.check_mumu_nemu_ipc_health()

        mock_logger.warning.assert_not_called()

    @mock.patch('module.device.connection.IS_WINDOWS', True)
    @mock.patch('module.device.connection.logger')
    def test_mumu_nemu_ipc_unavailable_triggers_warning(self, mock_logger):
        """
        On Windows MuMu when NemuIPC is unavailable, warning must be logged with
        doc link, without raising any blocking exception.
        """
        conn = make_connection(is_mumu_family=True)
        conn.nemu_ipc_available = mock.Mock(return_value=False)

        # Should execute completely without raising any exceptions
        conn.check_mumu_nemu_ipc_health()

        mock_logger.warning.assert_called_once()
        warning_message = mock_logger.warning.call_args[0][0]
        assert 'doc/low_spec_tuning_guide.md' in warning_message
        assert 'NemuIPC' in warning_message
        assert '后台挂机保活' in warning_message
