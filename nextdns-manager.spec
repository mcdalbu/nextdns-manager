Name:           nextdns-manager
Version:        1.0.0
Release:        1%{?dist}
Summary:        NextDNS Manager for Systemd-Resolved

License:        MIT
URL:            https://github.com/mcda/nextdns-manager
Source0:        %{name}-%{version}.tar.gz

BuildArch:      noarch
BuildRequires:  python3
Requires:       python3
Requires:       python3-gobject
Requires:       gtk4
Requires:       polkit
Requires:       systemd
Requires:       NetworkManager

%description
A GTK4 application to manage NextDNS configuration for systemd-resolved on Fedora.

%prep
%setup -q

%install
mkdir -p %{buildroot}%{_bindir}
mkdir -p %{buildroot}%{_datadir}/applications

install -m 755 nextdns_gui.py %{buildroot}%{_bindir}/nextdns-manager
install -m 755 nextdns.sh %{buildroot}%{_bindir}/nextdns-manager-cli
install -m 644 nextdns-manager.desktop %{buildroot}%{_datadir}/applications/

%files
%{_bindir}/nextdns-manager
%{_bindir}/nextdns-manager-cli
%{_datadir}/applications/nextdns-manager.desktop

%changelog
* Sat Apr 18 2026 mcda - 1.0.0-1
- Initial release
