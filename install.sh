#!/bin/bash

# Define paths
APP_NAME="nextdns-manager"
SCRIPT_PATH="$(pwd)/nextdns_gui.py"
ICON_PATH="/usr/share/icons/Adwaita/scalable/devices/network-wired-symbolic.svg" # Generic icon backup
DESKTOP_FILE="$HOME/.local/share/applications/$APP_NAME.desktop"

# Ensure the script is executable
chmod +x "$SCRIPT_PATH"

echo "Installing $APP_NAME..."

# Create .desktop file
cat > "$DESKTOP_FILE" <<EOF
[Desktop Entry]
Name=NextDNS Manager
Comment=Manage Systemd-Resolved NextDNS Configuration
Exec="$SCRIPT_PATH"
Icon=network-workgroup
Terminal=false
Type=Application
Categories=System;Settings;
EOF

# Update desktop database
update-desktop-database "$HOME/.local/share/applications"

echo "Installation complete!"
echo "You can now search for 'NextDNS Manager' in your application menu."
echo "Note: It will ask for your password to run with administrative privileges."
