#!/usr/bin/python3
"""GTK 4 and libadwaita front end for NextDNS configuration."""
import json
import os
import re
import subprocess
import tempfile
import threading
from pathlib import Path

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk

HELPER = "/usr/libexec/nextdns-manager-helper"
CONFIG = "/etc/systemd/resolved.conf.d/90-nextdns-manager.conf"
APP_ID = "io.github.mca_afk.nextdns_manager"
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

class Window(Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title="NextDNS Manager")
        self.set_default_size(650, 560)
        self.set_icon_name(APP_ID)

        self.toasts = Adw.ToastOverlay()
        self.set_content(self.toasts)
        toolbar = Adw.ToolbarView()
        self.toasts.set_child(toolbar)
        toolbar.add_top_bar(Adw.HeaderBar())
        scroll = Gtk.ScrolledWindow()
        toolbar.set_content(scroll)
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
        self.refresh()

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
