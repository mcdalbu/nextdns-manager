#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
version=2.2.0
topdir="$(mktemp -d)"
trap 'rm -rf "$topdir"' EXIT
mkdir -p "$topdir"/{BUILD,BUILDROOT,RPMS,SOURCES,SPECS,SRPMS}
archive="$topdir/SOURCES/nextdns-manager-$version.tar.gz"
tar -czf "$archive" --transform "s,^,nextdns-manager-$version/," \
    nextdns_gui.py nextdns_helper.py io.github.mca_afk.nextdns_manager.desktop \
    io.github.mca_afk.nextdns_manager.svg nextdns-manager.policy
cp nextdns-manager.spec "$topdir/SPECS/"
rpmbuild --define "_topdir $topdir" --define "_tmppath $topdir" -bb "$topdir/SPECS/nextdns-manager.spec"
find "$topdir/RPMS" -name '*.rpm' -exec cp -v {} . \;
