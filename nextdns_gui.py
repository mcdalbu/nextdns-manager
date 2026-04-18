#!/usr/bin/env python3
import sys
import subprocess
import os
import gi

gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, GLib


RESOLV_CONF = "/etc/systemd/resolved.conf"
CONFIG_FILE = "/etc/nextdns-manager.conf"
# Base template, machine name will be injected
NEXTDNS_TEMPLATE = """
[Resolve]
DNSOverTLS=yes
DNS=45.90.28.0#{name}-fd4e78.dns.nextdns.io
DNS=45.90.30.0#{name}-fd4e78.dns.nextdns.io
"""

class NextDNSApp(Gtk.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title="NextDNS Manager")
        self.set_default_size(600, 450)

        # Main box
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        vbox.set_margin_top(10)
        vbox.set_margin_bottom(10)
        vbox.set_margin_start(10)
        vbox.set_margin_end(10)
        self.set_child(vbox)

        # Machine Name Input
        hbox_name = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        hbox_name.set_halign(Gtk.Align.CENTER)
        vbox.append(hbox_name)

        lbl_name = Gtk.Label(label="Machine Name:")
        hbox_name.append(lbl_name)

        self.entry_name = Gtk.Entry()
        self.entry_name.set_text(self.load_last_host())
        self.entry_name.set_placeholder_text("Enter machine name")
        hbox_name.append(self.entry_name)

        # Buttons
        hbox_buttons = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        hbox_buttons.set_halign(Gtk.Align.CENTER)
        vbox.append(hbox_buttons)

        btn_enable = Gtk.Button(label="Enable NextDNS")
        btn_enable.connect("clicked", self.on_enable_clicked)
        hbox_buttons.append(btn_enable)

        btn_disable = Gtk.Button(label="Disable NextDNS")
        btn_disable.connect("clicked", self.on_disable_clicked)
        hbox_buttons.append(btn_disable)

        btn_refresh = Gtk.Button(label="Refresh Status")
        btn_refresh.connect("clicked", self.on_refresh_clicked)
        hbox_buttons.append(btn_refresh)

        # Status output
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        vbox.append(scrolled)

        self.status_view = Gtk.TextView()
        self.status_view.set_editable(False)
        self.status_view.set_monospace(True)
        self.status_buffer = self.status_view.get_buffer()
        scrolled.set_child(self.status_view)

        # Initial status refresh
        self.refresh_status()

    def run_command(self, cmd):
        try:
            result = subprocess.run(cmd, shell=True, check=True, capture_output=True, text=True)
            return result.stdout
        except subprocess.CalledProcessError as e:
            return f"Error executing command:\n{e.stderr}"

    def update_status(self, text):
        self.status_buffer.set_text(text)

    def refresh_status(self):
        output = self.run_command("resolvectl status")
        self.update_status(output)

    def load_last_host(self):
        try:
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, "r") as f:
                    return f.read().strip()
        except Exception:
            pass
        return "Aldebaran" # Default

    def save_last_host(self, name):
        try:
            with open(CONFIG_FILE, "w") as f:
                f.write(name)
        except Exception as e:
            print(f"Failed to save last host: {e}")

    def restart_services(self):
        self.update_status("Restarting systemd-resolved and NetworkManager...")
        # Since we are GUI, we should run this asynchronously or just let it block briefly as simple app
        try:
            subprocess.run(["systemctl", "restart", "systemd-resolved"], check=True)
            subprocess.run(["systemctl", "restart", "NetworkManager"], check=True)
            self.refresh_status()
        except subprocess.CalledProcessError as e:
            self.update_status(f"Error restarting services: {e}")

    def on_enable_clicked(self, widget):
        name = self.entry_name.get_text().strip()
        if not name:
            self.update_status("Error: Please enter a machine name.")
            return

        self.save_last_host(name)
        config_content = NEXTDNS_TEMPLATE.format(name=name)
        
        try:
            with open(RESOLV_CONF, "w") as f:
                f.write(config_content.strip())
            self.restart_services()
        except PermissionError:
            self.update_status("Permission denied. Application must run as root.")
        except Exception as e:
            self.update_status(f"Error writing config: {e}")

    def on_disable_clicked(self, widget):
        # We need to remove the lines we added.
        # We will remove lines starting with DNS=45.90... and DNSOverTLS=yes
        
        patterns = [
            "/^DNSOverTLS=yes/d",
            "/^DNS=45\\.90\\..*\\.dns\\.nextdns\\.io/d" # Matches any nextdns line with these IPs
        ]
        sed_expr = "; ".join(patterns)
        
        cmd = f"sed -i '{sed_expr}' {RESOLV_CONF}"
        
        try:
            # Check if file exists first
            if not os.path.exists(RESOLV_CONF):
                self.update_status(f"File {RESOLV_CONF} not found.")
                return

            subprocess.run(cmd, shell=True, check=True)
            self.restart_services()
        except subprocess.CalledProcessError as e:
            self.update_status(f"Error disabling NextDNS: {e}")

    def on_refresh_clicked(self, widget):
        self.refresh_status()

class MyApp(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="com.example.nextdnsmanager")

    def do_activate(self):
        win = NextDNSApp(self)
        win.present()

if __name__ == "__main__":
    # Self-elevation logic
    if os.geteuid() != 0:
        # Get absolute path to this script
        script_path = os.path.abspath(sys.argv[0])
        
        # Prepare environment variables to preserve
        env_vars = []
        for var in ['DISPLAY', 'XAUTHORITY', 'WAYLAND_DISPLAY']:
            if var in os.environ:
                env_vars.extend(['env', f'{var}={os.environ[var]}'])
        
        # Construct the command: pkexec env VAR=VAL ... python3 script_path
        cmd = ['pkexec'] + env_vars + [sys.executable, script_path]
        
        # Replace the current process
        os.execvp('pkexec', cmd)

    app = MyApp()
    app.run(sys.argv)
