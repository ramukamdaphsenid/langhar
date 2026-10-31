"""Tests for the packaged application's server lifecycle."""
import subprocess
import unittest
from unittest.mock import Mock, call

from launcher import (
    SERVER_SHUTDOWN_TIMEOUT,
    _configure_webview,
    _stop_server_process,
)


class TestLauncherWebViewDownloads(unittest.TestCase):
    def test_configure_webview_enables_downloads(self):
        webview = Mock()
        webview.settings = {'ALLOW_DOWNLOADS': False}

        _configure_webview(webview)

        self.assertTrue(webview.settings['ALLOW_DOWNLOADS'])


class TestLauncherShutdown(unittest.TestCase):
    def _process(self):
        process = Mock()
        process.poll.return_value = None
        return process

    def test_shutdown_terminates_running_server_process(self):
        process = self._process()

        _stop_server_process(process)

        process.terminate.assert_called_once_with()
        process.wait.assert_called_once_with(timeout=SERVER_SHUTDOWN_TIMEOUT)
        process.kill.assert_not_called()

    def test_shutdown_kills_server_if_termination_times_out(self):
        process = self._process()
        process.wait.side_effect = [
            subprocess.TimeoutExpired("Langhar", SERVER_SHUTDOWN_TIMEOUT),
            None,
        ]

        _stop_server_process(process)

        process.terminate.assert_called_once_with()
        process.kill.assert_called_once_with()
        self.assertEqual(
            process.wait.call_args_list,
            [
                call(timeout=SERVER_SHUTDOWN_TIMEOUT),
                call(),
            ],
        )
