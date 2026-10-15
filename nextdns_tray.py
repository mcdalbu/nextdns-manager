#!/usr/bin/python3
"""GTK 3 AppIndicator companion for the GTK 4 NextDNS Manager."""
import subprocess
import sys
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


class TrayApplication(Gtk.Application):
    def __init__(self):
        super().__init__(
            application_id=APP_ID,
            flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE,
        )
        self.indicator = None
        self.last_enabled = None

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
        refresh_item = Gtk.MenuItem.new_with_label("Refresh status")
        refresh_item.connect("activate", lambda _: self.refresh_status(force=True))
        menu.append(refresh_item)
        menu.append(Gtk.SeparatorMenuItem())
        quit_item = Gtk.MenuItem.new_with_label("Quit tray")
        quit_item.connect("activate", lambda _: self.quit())
        menu.append(quit_item)
        menu.show_all()
        self.indicator.set_menu(menu)
        self.indicator.set_status(Indicator.IndicatorStatus.ACTIVE)
        self.refresh_status(force=True)
        GLib.timeout_add_seconds(5, self.refresh_status)
        self.hold()

    def refresh_status(self, force=False):
        enabled = CONFIG.is_file()
        if force or enabled != self.last_enabled:
            self.last_enabled = enabled
            description = "NextDNS configured" if enabled else "NextDNS disabled"
            self.indicator.set_icon_full(ICON_ON if enabled else ICON_OFF, description)
            self.status_item.set_label("NextDNS: Enabled" if enabled else "NextDNS: Disabled")
        return GLib.SOURCE_CONTINUE

    def open_manager(self, _item):
        subprocess.Popen(
            ["nextdns-manager"], stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            start_new_session=True,
        )


if __name__ == "__main__":
    TrayApplication().run(sys.argv)
