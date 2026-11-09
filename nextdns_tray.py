#!/usr/bin/python3
"""GTK 3 AppIndicator companion for the GTK 4 NextDNS Manager."""
import json
import os
import re
import subprocess
import sys
import threading
from pathlib import Path

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("AyatanaAppIndicator3", "0.1")
from gi.repository import AyatanaAppIndicator3 as Indicator, Gio, GLib, Gtk

APP_ID = "io.github.mca_afk.nextdns_manager.Tray"
CONFIG = Path("/etc/systemd/resolved.conf.d/90-nextdns-manager.conf")
ICON_ON = "io.github.mca_afk.nextdns_manager-tray-on"
ICON_OFF = "io.github.mca_afk.nextdns_manager-tray-off"
ICON_DIR = "/usr/share/icons/hicolor/scalable/apps"
HELPER = "/usr/libexec/nextdns-manager-helper"
SETTINGS_FILE = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "nextdns-manager" / "settings.json"


def valid_configuration(profile, device):
    return (
        isinstance(profile, str) and isinstance(device, str)
        and re.fullmatch(r"[0-9a-f]{6}", profile)
        and re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?", device)
    )


def load_configuration():
    try:
        content = CONFIG.read_text(encoding="utf-8")
        match = re.search(r"^DNS=.*?#([A-Za-z0-9-]+)-([0-9a-f]{6})\.dns\.nextdns\.io", content, re.MULTILINE)
        if match and valid_configuration(match[2], match[1]):
            return match[2], match[1]
    except (OSError, ValueError):
        pass
    try:
        saved = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        if isinstance(saved, dict) and saved.get("remember") is True:
            profile, device = saved.get("profile"), saved.get("device")
            if valid_configuration(profile, device):
                return profile, device
    except (OSError, ValueError):
        pass
    return None


class TrayApplication(Gtk.Application):
    def __init__(self):
        super().__init__(
            application_id=APP_ID,
            flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE,
        )
        self.indicator = None
        self.last_enabled = None
        self.configuration = None
        self.busy = False

    def do_command_line(self, command_line):
        if "--quit" in command_line.get_arguments()[1:]:
            self.quit()
        else:
            self.activate()
        return 0

    def do_activate(self):
        if self.indicator is not None:
            return
        self.indicator = Indicator.Indicator.new(
            "nextdns-manager", ICON_OFF, Indicator.IndicatorCategory.APPLICATION_STATUS,
        )
        self.indicator.set_icon_theme_path(ICON_DIR)
        menu = Gtk.Menu()
        open_item = Gtk.MenuItem.new_with_label("Open NextDNS Manager")
        open_item.connect("activate", self.open_manager)
        menu.append(open_item)
        self.status_item = Gtk.MenuItem.new_with_label("NextDNS: Checking…")
        self.status_item.set_sensitive(False)
        menu.append(self.status_item)
        self.toggle_item = Gtk.MenuItem.new_with_label("Connect")
        self.toggle_item.connect("activate", self.toggle_connection)
        menu.append(self.toggle_item)
        refresh_item = Gtk.MenuItem.new_with_label("Refresh status")
        refresh_item.connect("activate", lambda _: self.refresh_status(force=True))
        menu.append(refresh_item)
        menu.append(Gtk.SeparatorMenuItem())
        self.quit_item = Gtk.MenuItem.new_with_label("Quit tray")
        self.quit_item.connect("activate", lambda _: self.quit())
        menu.append(self.quit_item)
        menu.show_all()
        self.indicator.set_menu(menu)
        self.indicator.set_status(Indicator.IndicatorStatus.ACTIVE)
        self.refresh_status(force=True)
        GLib.timeout_add_seconds(5, self.refresh_status)
        self.hold()

    def refresh_status(self, force=False):
        enabled = CONFIG.is_file()
        self.configuration = load_configuration() or self.configuration
        self.toggle_item.set_sensitive(not self.busy)
        self.toggle_item.set_label(
            "Applying configuration…" if self.busy else "Disconnect" if enabled else "Connect"
        )
        if force or enabled != self.last_enabled:
            self.last_enabled = enabled
            description = "NextDNS configured" if enabled else "NextDNS disabled"
            self.indicator.set_icon_full(ICON_ON if enabled else ICON_OFF, description)
            self.status_item.set_label("NextDNS: Enabled" if enabled else "NextDNS: Disabled")
        return GLib.SOURCE_CONTINUE

    def toggle_connection(self, _item):
        if self.busy:
            return
        self.refresh_status(force=True)
        action = "disable" if self.last_enabled else "enable"
        if action == "enable" and self.configuration is None:
            self.show_message(
                "Configure NextDNS first",
                "Enter your profile ID and device name in NextDNS Manager. "
                "Enable Remember last configuration to connect from the tray after restarting it.",
            )
            self.open_manager(None)
            return
        command = ["pkexec", HELPER, action]
        if action == "enable":
            command.extend(self.configuration)
        self.busy = True
        self.quit_item.set_sensitive(False)
        self.refresh_status(force=True)

        def work():
            try:
                result = subprocess.run(command, capture_output=True, text=True, timeout=60)
                success = result.returncode == 0
                detail = result.stderr.strip() or result.stdout.strip()
            except (OSError, subprocess.TimeoutExpired) as exc:
                success, detail = False, str(exc)
            GLib.idle_add(self.finish_connection, success, detail)

        threading.Thread(target=work, daemon=True).start()

    def finish_connection(self, success, detail):
        self.busy = False
        self.quit_item.set_sensitive(True)
        self.refresh_status(force=True)
        if not success:
            self.show_message("Could not update configuration", detail or "Authorization was cancelled or the operation failed.")
        return GLib.SOURCE_REMOVE

    def show_message(self, title, detail):
        dialog = Gtk.MessageDialog(
            modal=True, message_type=Gtk.MessageType.INFO,
            buttons=Gtk.ButtonsType.CLOSE, text=title,
        )
        dialog.format_secondary_text(detail)
        dialog.connect("response", lambda dialog, _response: dialog.destroy())
        dialog.show_all()

    def open_manager(self, _item):
        subprocess.Popen(
            ["nextdns-manager"], stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            start_new_session=True,
        )


if __name__ == "__main__":
    TrayApplication().run(sys.argv)
