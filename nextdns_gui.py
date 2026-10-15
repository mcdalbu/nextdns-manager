#!/usr/bin/python3
"""GTK 4 and libadwaita front end for NextDNS configuration."""
import json
import os
import re
import subprocess
import tempfile
import threading
import urllib.request
from pathlib import Path

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("WebKit", "6.0")
from gi.repository import Adw, Gio, GLib, Gtk, WebKit

HELPER = "/usr/libexec/nextdns-manager-helper"
CONFIG = "/etc/systemd/resolved.conf.d/90-nextdns-manager.conf"
APP_ID = "io.github.mca_afk.nextdns_manager"
TRAY_ID = APP_ID + ".Tray"
TRAY_COMMAND = "/usr/bin/nextdns-manager-tray"
AUTOSTART_FILE = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "autostart" / (TRAY_ID + ".desktop")
TEST_URL = "https://test.nextdns.io/"
PING_URL = "https://ping.nextdns.io/"
SETTINGS_FILE = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "nextdns-manager" / "settings.json"


def load_preferences():
    try:
        with SETTINGS_FILE.open(encoding="utf-8") as stream:
            saved = json.load(stream)
        if isinstance(saved, dict) and saved.get("remember") is True:
            return {
                "remember": True,
                "profile": saved.get("profile", "") if isinstance(saved.get("profile"), str) else "",
                "device": saved.get("device", "") if isinstance(saved.get("device"), str) else "",
            }
    except (OSError, ValueError):
        pass
    return {"remember": False, "profile": "", "device": ""}


def save_preferences(remember, profile="", device=""):
    settings = {
        "remember": bool(remember),
        "profile": profile if remember else "",
        "device": device if remember else "",
    }
    SETTINGS_FILE.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".settings-", dir=SETTINGS_FILE.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(settings, stream)
            stream.write("\n")
        os.replace(temporary, SETTINGS_FILE)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def tray_running():
    try:
        bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        result = bus.call_sync(
            "org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus",
            "NameHasOwner", GLib.Variant("(s)", (TRAY_ID,)),
            GLib.VariantType.new("(b)"), Gio.DBusCallFlags.NONE, 1000, None,
        )
        return result.unpack()[0]
    except GLib.Error:
        return False


def set_autostart(enabled):
    if not enabled:
        AUTOSTART_FILE.unlink(missing_ok=True)
        return
    AUTOSTART_FILE.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    content = (
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Name=NextDNS Manager Tray\n"
        "Comment=Show the NextDNS configuration status in the system tray\n"
        "Exec=nextdns-manager-tray\n"
        f"Icon={APP_ID}\n"
        "Terminal=false\n"
        "X-GNOME-Autostart-enabled=true\n"
    )
    fd, temporary = tempfile.mkstemp(prefix=".nextdns-tray-", dir=AUTOSTART_FILE.parent)
    try:
        os.fchmod(fd, 0o644)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(content)
        os.replace(temporary, AUTOSTART_FILE)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)

class Window(Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title="NextDNS Manager")
        self.set_default_size(650, 560)
        self.set_icon_name(APP_ID)

        self.toasts = Adw.ToastOverlay()
        self.set_content(self.toasts)
        toolbar = Adw.ToolbarView()
        self.toasts.set_child(toolbar)
        header = Adw.HeaderBar()
        toolbar.add_top_bar(header)
        stack = Adw.ViewStack()
        toolbar.set_content(stack)
        switcher = Adw.ViewSwitcher()
        switcher.set_stack(stack)
        header.set_title_widget(switcher)
        scroll = Gtk.ScrolledWindow()
        stack.add_titled(scroll, "configuration", "Configuration").set_icon_name("preferences-system-symbolic")
        clamp = Adw.Clamp(maximum_size=620, tightening_threshold=500)
        scroll.set_child(clamp)
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=24)
        for side in ("top", "bottom", "start", "end"):
            getattr(root, "set_margin_" + side)(24)
        clamp.set_child(root)

        heading = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        heading.set_halign(Gtk.Align.CENTER)
        icon = Gtk.Image.new_from_icon_name(APP_ID)
        icon.set_pixel_size(64)
        heading.append(icon)
        title = Gtk.Label(label="NextDNS Manager")
        title.add_css_class("title-1")
        heading.append(title)
        subtitle = Gtk.Label(label="Encrypted DNS for this device")
        subtitle.add_css_class("dim-label")
        heading.append(subtitle)
        root.append(heading)

        config = Adw.PreferencesGroup(
            title="Configuration",
            description="Enter the profile ID from your NextDNS setup page and a name for this device.",
        )
        root.append(config)
        self.profile = Adw.EntryRow(title="Profile ID")
        self.profile.set_max_length(6)
        config.add(self.profile)
        self.device = Adw.EntryRow(title="Device name")
        config.add(self.device)
        self.remember = Adw.SwitchRow(
            title="Remember last configuration",
            subtitle="Keep the profile ID and device name after NextDNS is disabled.",
        )
        config.add(self.remember)
        saved = load_preferences()
        self.profile.set_text(saved["profile"])
        self.device.set_text(saved["device"])
        self.remember.set_active(saved["remember"])
        self.remember.connect("notify::active", self.on_remember_changed)

        tray_group = Adw.PreferencesGroup(title="Background")
        root.append(tray_group)
        self.tray_switch = Adw.SwitchRow(
            title="Run in system tray",
            subtitle="Keep a status icon available after closing this window.",
        )
        tray_group.add(self.tray_switch)
        self.startup_switch = Adw.SwitchRow(
            title="Start tray at login",
            subtitle="Launch the status icon when you sign in.",
        )
        tray_group.add(self.startup_switch)
        self.tray_switch.set_active(tray_running())
        self.startup_switch.set_active(AUTOSTART_FILE.exists())
        self.tray_switch.connect("notify::active", self.on_tray_changed)
        self.startup_switch.connect("notify::active", self.on_startup_changed)

        buttons = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        buttons.set_halign(Gtk.Align.END)
        root.append(buttons)
        self.enable = Gtk.Button(label="Enable NextDNS")
        self.enable.add_css_class("suggested-action")
        self.enable.connect("clicked", lambda _: self.apply("enable"))
        self.disable = Gtk.Button(label="Disable")
        self.disable.connect("clicked", lambda _: self.apply("disable"))
        buttons.append(self.disable)
        buttons.append(self.enable)
        self.hide_to_tray = Gtk.Button(label="Hide to tray")
        self.hide_to_tray.set_sensitive(self.tray_switch.get_active())
        self.hide_to_tray.connect("clicked", lambda _: self.close())
        buttons.append(self.hide_to_tray)

        status_group = Adw.PreferencesGroup(title="Connection")
        root.append(status_group)
        status_row = Adw.ActionRow(title="NextDNS", subtitle="Checking…")
        status_group.add(status_row)
        self.status = status_row
        refresh = Gtk.Button(icon_name="view-refresh-symbolic")
        refresh.set_tooltip_text("Refresh status")
        refresh.set_valign(Gtk.Align.CENTER)
        refresh.connect("clicked", lambda _: self.refresh())
        status_row.add_suffix(refresh)
        self.detail = Adw.ActionRow(title="DNS servers", subtitle="Checking…")
        self.detail.set_subtitle_lines(0)
        self.detail.set_subtitle_selectable(True)
        status_group.add(self.detail)

        self.build_test_tab(stack)
        self.build_ping_tab(stack)
        self.stack = stack
        stack.connect("notify::visible-child-name", self.on_tab_changed)
        GLib.timeout_add_seconds(5, self.sync_tray)
        self.refresh()

    def on_tab_changed(self, stack, _property):
        name = stack.get_visible_child_name()
        if name == "test" and not self.test_has_run:
            self.run_test(self.test_button)
        elif name == "ping" and not self.ping_loaded:
            self.ping_loaded = True
            self.ping_view.load_uri(PING_URL)

    def sync_tray(self):
        running = tray_running()
        if self.tray_switch.get_active() != running:
            self._syncing_tray = True
            self.tray_switch.set_active(running)
            self._syncing_tray = False
        self.hide_to_tray.set_sensitive(running)
        return GLib.SOURCE_CONTINUE

    def on_tray_changed(self, _row, _property):
        if getattr(self, "_syncing_tray", False):
            return
        enabled = self.tray_switch.get_active()
        try:
            subprocess.Popen(
                [TRAY_COMMAND] + ([] if enabled else ["--quit"]),
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL, start_new_session=True,
            )
            self.hide_to_tray.set_sensitive(enabled)
            if not enabled and self.startup_switch.get_active():
                self.startup_switch.set_active(False)
        except OSError as exc:
            self._syncing_tray = True
            self.tray_switch.set_active(not enabled)
            self._syncing_tray = False
            self.show_toast(f"Could not start the tray: {exc}")

    def on_startup_changed(self, _row, _property):
        if getattr(self, "_syncing_startup", False):
            return
        enabled = self.startup_switch.get_active()
        try:
            set_autostart(enabled)
        except OSError as exc:
            self._syncing_startup = True
            self.startup_switch.set_active(not enabled)
            self._syncing_startup = False
            self.show_toast(f"Could not update autostart: {exc}")
            return
        if enabled and not self.tray_switch.get_active():
            self.tray_switch.set_active(True)

    def build_test_tab(self, stack):
        scroll = Gtk.ScrolledWindow()
        stack.add_titled(scroll, "test", "Test").set_icon_name("network-transmit-receive-symbolic")
        clamp = Adw.Clamp(maximum_size=620, tightening_threshold=500)
        scroll.set_child(clamp)
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        for side in ("top", "bottom", "start", "end"):
            getattr(content, "set_margin_" + side)(24)
        clamp.set_child(content)
        group = Adw.PreferencesGroup(
            title="NextDNS connection test",
            description="Query test.nextdns.io through this computer's DNS settings.",
        )
        content.append(group)
        self.test_status = Adw.ActionRow(title="Status", subtitle="Not tested yet")
        group.add(self.test_status)
        self.test_protocol = Adw.ActionRow(title="Protocol", subtitle="—")
        group.add(self.test_protocol)
        self.test_profile = Adw.ActionRow(title="Profile", subtitle="—")
        group.add(self.test_profile)
        self.test_button = Gtk.Button(label="Run test")
        self.test_button.add_css_class("suggested-action")
        self.test_button.set_halign(Gtk.Align.START)
        self.test_button.connect("clicked", self.run_test)
        content.append(self.test_button)
        self.test_has_run = False
        raw_group = Adw.PreferencesGroup(title="Full response")
        content.append(raw_group)
        self.test_response = Gtk.TextView()
        self.test_response.set_editable(False)
        self.test_response.set_cursor_visible(False)
        self.test_response.set_monospace(True)
        self.test_response.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        response_scroll = Gtk.ScrolledWindow()
        response_scroll.set_min_content_height(180)
        response_scroll.set_child(self.test_response)
        raw_group.add(response_scroll)

    def build_ping_tab(self, stack):
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        stack.add_titled(content, "ping", "Ping").set_icon_name("network-server-symbolic")
        controls = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        for side in ("top", "start", "end"):
            getattr(controls, "set_margin_" + side)(12)
        content.append(controls)
        description = Gtk.Label(label="NextDNS latency test · ping.nextdns.io", xalign=0)
        description.set_hexpand(True)
        controls.append(description)
        reload_button = Gtk.Button(icon_name="view-refresh-symbolic")
        reload_button.set_tooltip_text("Reload latency test")
        reload_button.connect("clicked", lambda _: self.ping_view.reload())
        controls.append(reload_button)
        self.ping_view = WebKit.WebView()
        self.ping_view.set_vexpand(True)
        content.append(self.ping_view)
        self.ping_loaded = False

    def run_test(self, button):
        self.test_has_run = True
        button.set_sensitive(False)
        self.test_status.set_subtitle("Testing…")
        def work():
            try:
                request = urllib.request.Request(
                    TEST_URL, headers={"Accept": "application/json", "Cache-Control": "no-cache"},
                )
                opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
                with opener.open(request, timeout=12) as response:
                    data = json.loads(response.read(65536).decode("utf-8"))
                if not isinstance(data, dict):
                    raise ValueError("Unexpected response from NextDNS")
                GLib.idle_add(self.show_test, button, data, None)
            except (OSError, ValueError) as exc:
                GLib.idle_add(self.show_test, button, None, str(exc))
        threading.Thread(target=work, daemon=True).start()

    def show_test(self, button, data, error):
        button.set_sensitive(True)
        if error:
            self.test_status.set_subtitle("Test failed")
            self.test_response.get_buffer().set_text(error)
            return GLib.SOURCE_REMOVE
        status = str(data.get("status", "unknown"))
        self.test_status.set_subtitle("Connected" if status == "ok" else status)
        self.test_protocol.set_subtitle(str(data.get("protocol", "—")))
        self.test_profile.set_subtitle(str(data.get("profile", "—")))
        self.test_response.get_buffer().set_text(json.dumps(data, indent=2, ensure_ascii=False))
        return GLib.SOURCE_REMOVE

    def refresh(self):
        self.status.set_subtitle("Checking…")
        def work():
            try:
                with open(CONFIG, encoding="utf-8") as stream:
                    lines = stream.read().splitlines()
                profile = next((part.rsplit("-", 1)[-1] for line in lines if line.startswith("DNS=")
                                for part in [line.split("#", 1)[1].split(".dns.nextdns.io")[0]]), "")
                device = next((line[10:] for line in lines if line.startswith("# Device: ")), "")
                result = subprocess.run(["resolvectl", "dns"], capture_output=True, text=True, timeout=8)
                detail = result.stdout.strip() if result.returncode == 0 else "Could not read active DNS servers."
                GLib.idle_add(self.show_status, True, profile, device, detail)
            except FileNotFoundError:
                GLib.idle_add(self.show_status, False, "", "", "No NextDNS configuration installed.")
            except (OSError, subprocess.TimeoutExpired) as exc:
                GLib.idle_add(self.show_status, None, "", "", str(exc))
        threading.Thread(target=work, daemon=True).start()

    def show_status(self, enabled, profile, device, detail):
        self.status.set_subtitle("Configured" if enabled else "Disabled" if enabled is False else "Status unavailable")
        self.detail.set_subtitle(detail)
        if enabled:
            if not self.profile.get_text():
                self.profile.set_text(profile)
            if not self.device.get_text():
                self.device.set_text(device)
        return GLib.SOURCE_REMOVE

    def apply(self, action):
        profile = self.profile.get_text().strip().lower()
        device = self.device.get_text().strip()
        if action == "enable":
            if not re.fullmatch(r"[0-9a-f]{6}", profile):
                self.show_toast("Enter a six-character hexadecimal profile ID.")
                return
            if not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?", device):
                self.show_toast("Use up to 63 letters, numbers, or internal hyphens for the device name.")
                return
        self.enable.set_sensitive(False)
        self.disable.set_sensitive(False)
        self.show_toast("Applying configuration…")
        def work():
            try:
                command = ["pkexec", HELPER, action] + ([profile, device] if action == "enable" else [])
                result = subprocess.run(command, capture_output=True, text=True, timeout=60)
                GLib.idle_add(
                    self.finish, action, profile, device,
                    result.returncode == 0, result.stderr.strip() or result.stdout.strip(),
                )
            except (OSError, subprocess.TimeoutExpired) as exc:
                GLib.idle_add(self.finish, action, profile, device, False, str(exc))
        threading.Thread(target=work, daemon=True).start()

    def finish(self, action, profile, device, success, detail):
        self.enable.set_sensitive(True)
        self.disable.set_sensitive(True)
        if success and action == "enable" and self.remember.get_active():
            try:
                save_preferences(True, profile, device)
            except OSError as exc:
                self.show_toast(f"Configuration applied, but could not save preferences: {exc}")
        self.show_toast(("Configuration updated. " if success else "Could not update configuration. ") + detail)
        self.refresh()
        return GLib.SOURCE_REMOVE

    def on_remember_changed(self, _row, _property):
        try:
            save_preferences(
                self.remember.get_active(),
                self.profile.get_text().strip().lower(),
                self.device.get_text().strip(),
            )
        except OSError as exc:
            self.show_toast(f"Could not save preferences: {exc}")

    def show_toast(self, message):
        self.toasts.add_toast(Adw.Toast.new(message))


class Application(Adw.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID)

    def do_activate(self):
        window = self.get_active_window() or Window(self)
        window.present()


if __name__ == "__main__":
    Application().run(None)
