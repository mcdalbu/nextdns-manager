# NextDNS Manager

A GTK 4 and libadwaita desktop app for configuring NextDNS through systemd-resolved on Fedora.

## Install

Build the RPM with `./build-rpm.sh`, then install the resulting package:

```sh
sudo dnf install ./nextdns-manager-2.2.0-1.*.noarch.rpm
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
