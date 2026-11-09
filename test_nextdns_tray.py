"""Headless checks for tray configuration and privileged command dispatch."""
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import nextdns_tray as tray


class TrayTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.config = Path(temporary.name) / "resolved.conf"
        self.settings = Path(temporary.name) / "settings.json"
        for name, path in (("CONFIG", self.config), ("SETTINGS_FILE", self.settings)):
            patcher = patch.object(tray, name, path)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_active_configuration_takes_priority(self):
        self.config.write_text("[Resolve]\nDNS=45.90.28.0#My-PC-abc123.dns.nextdns.io\n")
        self.settings.write_text(json.dumps(dict(remember=True, profile="123abc", device="Other")))
        self.assertEqual(tray.load_configuration(), ("abc123", "My-PC"))

    def test_saved_configuration_requires_opt_in_and_valid_values(self):
        for remember, profile, device, expected in (
            (True, "abc123", "My-PC", ("abc123", "My-PC")),
            (False, "abc123", "My-PC", None),
            (True, "invalid", "My-PC", None),
            (True, "abc123", "-bad", None),
            (True, None, [], None),
        ):
            with self.subTest(remember=remember, profile=profile, device=device):
                self.settings.write_text(json.dumps(dict(remember=remember, profile=profile, device=device)))
                self.assertEqual(tray.load_configuration(), expected)

    def test_missing_and_corrupt_configuration(self):
        self.assertIsNone(tray.load_configuration())
        self.settings.write_text("{")
        self.assertIsNone(tray.load_configuration())

    def application(self, enabled=False, configuration=("abc123", "My-PC")):
        return SimpleNamespace(
            busy=False, last_enabled=enabled, configuration=configuration,
            refresh_status=Mock(), quit_item=Mock(), show_message=Mock(),
            open_manager=Mock(), finish_connection=Mock(),
        )

    def dispatch(self, app, result=None, error=None):
        with patch.object(tray.threading, "Thread") as thread, \
                patch.object(tray.subprocess, "run", return_value=result, side_effect=error) as run, \
                patch.object(tray.GLib, "idle_add") as idle:
            thread.side_effect = lambda **kwargs: SimpleNamespace(start=kwargs["target"])
            tray.TrayApplication.toggle_connection(app, None)
            return run, idle

    def test_connect_and_disconnect_commands(self):
        for enabled, arguments in ((False, ["enable", "abc123", "My-PC"]), (True, ["disable"])):
            with self.subTest(enabled=enabled):
                app = self.application(enabled)
                run, idle = self.dispatch(app, SimpleNamespace(returncode=0, stderr="", stdout=""))
                run.assert_called_once_with(
                    ["pkexec", tray.HELPER] + arguments,
                    capture_output=True, text=True, timeout=60,
                )
                self.assertTrue(app.busy)
                idle.assert_called_once_with(app.finish_connection, True, "")

    def test_connect_without_configuration_opens_manager(self):
        app = self.application(configuration=None)
        run, _ = self.dispatch(app)
        run.assert_not_called()
        app.open_manager.assert_called_once_with(None)
        app.show_message.assert_called_once()

    def test_busy_action_is_ignored(self):
        app = self.application()
        app.busy = True
        run, _ = self.dispatch(app)
        run.assert_not_called()

    def test_errors_are_dispatched_to_main_loop(self):
        for error in (OSError("pkexec unavailable"), subprocess.TimeoutExpired("pkexec", 60)):
            with self.subTest(error=error):
                app = self.application()
                _, idle = self.dispatch(app, error=error)
                idle.assert_called_once_with(app.finish_connection, False, str(error))

    def test_failure_restores_menu_and_reports_error(self):
        app = self.application()
        app.busy = True
        tray.TrayApplication.finish_connection(app, False, "Denied")
        self.assertFalse(app.busy)
        app.quit_item.set_sensitive.assert_called_once_with(True)
        app.refresh_status.assert_called_once_with(force=True)
        app.show_message.assert_called_once_with("Could not update configuration", "Denied")

    def test_refresh_retains_session_configuration_after_disconnect(self):
        app = self.application(configuration=("abc123", "My-PC"))
        app.toggle_item, app.indicator, app.status_item = Mock(), Mock(), Mock()
        tray.TrayApplication.refresh_status(app, force=True)
        self.assertEqual(app.configuration, ("abc123", "My-PC"))
        app.toggle_item.set_label.assert_called_once_with("Connect")


if __name__ == "__main__":
    unittest.main()
