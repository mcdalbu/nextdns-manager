# NextDNS Manager

A GTK 4 and libadwaita desktop app for configuring NextDNS through systemd-resolved on Fedora.

## Install

Build the RPM with `./build-rpm.sh`, then install the resulting package:

```sh
sudo dnf install ./nextdns-manager-2.4.0-1.*.noarch.rpm
```

Launch **NextDNS Manager** from the application menu. Enter the six-character
profile ID from your NextDNS setup page and a device name, then select
**Enable NextDNS**. PolicyKit prompts for administrator authentication.

Enable **Remember last configuration** to keep the profile ID and device name
after disabling NextDNS or closing the app. These preferences are stored in
`~/.config/nextdns-manager/settings.json` for the current user. Turning the
option off removes the saved profile and device name from that file.

The app writes only
`/etc/systemd/resolved.conf.d/90-nextdns-manager.conf`. **Disable** removes
that drop-in. It does not rewrite the main resolved.conf or restart
NetworkManager. If an older version of this app changed
`/etc/systemd/resolved.conf`, review that file manually because its prior
contents cannot be reconstructed automatically.

The status panel shows the installed drop-in and the DNS servers reported by
`resolvectl`. It does not verify the account-side NextDNS connection.

## Tray and diagnostics

Enable **Run in system tray** to keep a status icon after closing the window.
The glowing green dot means the NextDNS drop-in is installed; the glowing red
dot means it is absent. The icon reports local configuration state, while the
**Test** tab checks the actual connection. Enable **Start tray at login** to
create a per-user XDG autostart entry. On GNOME, an AppIndicator-compatible
extension must be enabled for the tray icon to appear.

Use **Connect** or **Disconnect** in the tray menu to change the configuration
without opening the main window. PolicyKit prompts for administrator authentication.
The tray keeps the last active profile and device name in memory for reconnection.
Enable **Remember last configuration** to reconnect after restarting the tray;
if no configuration is available, **Connect** opens the manager to configure it.

The **Test** tab queries the official `https://test.nextdns.io/` endpoint
without using a proxy and shows its response. The **Ping** tab embeds
`https://ping.nextdns.io/` for NextDNS's latency test. These are the working
`.io` endpoints; the `.com` names are not used.
