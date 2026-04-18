#!/bin/bash

APP_NAME="nextdns-manager"
DESKTOP_FILE="$HOME/.local/share/applications/$APP_NAME.desktop"

echo "Uninstalling $APP_NAME..."

if [ -f "$DESKTOP_FILE" ]; then
    rm "$DESKTOP_FILE"
    echo "Removed $DESKTOP_FILE"
    update-desktop-database "$HOME/.local/share/applications"
else
    echo "Desktop file not found."
fi

echo "Uninstallation complete."
