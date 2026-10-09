Name:           nextdns-manager
Version:        2.1.1
Release:        1%{?dist}
Summary:        GTK 4 and libadwaita NextDNS manager for systemd-resolved
License:        MIT
URL:            https://github.com/mca-afk/nextdns-manager
Source0:        %{name}-%{version}.tar.gz
BuildArch:      noarch
Requires:       /usr/bin/python3
Requires:       python3-gobject
Requires:       gtk4
Requires:       libadwaita
Requires:       polkit
Requires:       systemd

%description
Configure encrypted NextDNS through a GTK 4/libadwaita interface and a narrowly scoped
PolicyKit helper. The package uses a dedicated systemd-resolved drop-in.

%prep
%setup -q

%install
install -Dpm 755 nextdns_gui.py %{buildroot}%{_bindir}/nextdns-manager
install -Dpm 755 nextdns_helper.py %{buildroot}%{_libexecdir}/nextdns-manager-helper
install -Dpm 644 io.github.mca_afk.nextdns_manager.desktop %{buildroot}%{_datadir}/applications/io.github.mca_afk.nextdns_manager.desktop
install -Dpm 644 io.github.mca_afk.nextdns_manager.svg %{buildroot}%{_datadir}/icons/hicolor/scalable/apps/io.github.mca_afk.nextdns_manager.svg
install -Dpm 644 nextdns-manager.policy %{buildroot}%{_datadir}/polkit-1/actions/io.github.mca_afk.nextdns_manager.policy

%files
%{_bindir}/nextdns-manager
%{_libexecdir}/nextdns-manager-helper
%{_datadir}/applications/io.github.mca_afk.nextdns_manager.desktop
%{_datadir}/icons/hicolor/scalable/apps/io.github.mca_afk.nextdns_manager.svg
%{_datadir}/polkit-1/actions/io.github.mca_afk.nextdns_manager.policy

%changelog
* Fri Oct 09 2026 mcda - 2.1.1-1
- Match the desktop file and icon names to the GTK application ID

* Fri Oct 09 2026 mcda - 2.1.0-1
- Use libadwaita interface and system theme

* Fri Oct 09 2026 mcda - 2.0.1-1
- Preserve device name capitalization

* Fri Oct 09 2026 mcda - 2.0.0-1
- Add profile configuration, scoped authorization, and a custom icon
