#!/bin/sh
# Build-time only. Never installs a package or loads a kernel module.
set -eu
export SOURCE_DATE_EPOCH=1794787200
package=/usr/local/repos/nvidia-dkms-open_620.70.06-1ubuntu1_amd64.deb
source=usr/src/nvidia-620.70.06/nvidia-uvm/uvm_va_range.c
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
echo "fae10115b4938a4cc016d0cece0acab03756f216a4dc49491052e68519362e28  $package" | sha256sum -c -
test "$(dpkg-deb -f "$package" Package)" = nvidia-dkms-open
test "$(dpkg-deb -f "$package" Version)" = 620.70.06-1ubuntu1
dpkg-deb --raw-extract "$package" "$work"
cd "$work"
echo "6ed2a2ed36f39654151d9df7e60e5812bc791517d7a1045cc841287b8f7dea91  $source" | sha256sum -c -
patch --batch --forward --fuzz=0 -p1 < /policy/uvm-reject-managed-memory.patch
echo "5648dbfe43957eb257d9efb715906de0fb6caa43458752544221d90db6efdb18  $source" | sha256sum -c -
new_md5=$(md5sum "$source" | cut -d ' ' -f 1)
sed -i "s|^[0-9a-f]*  $source\$|$new_md5  $source|" DEBIAN/md5sums
md5sum -c DEBIAN/md5sums >/dev/null
# All original control fields, maintainer scripts and package version remain.
dpkg-deb --build --root-owner-group --threads-max=1 "$work" "$package"
cd /usr/local/repos
dpkg-scanpackages . /dev/null | gzip -n -9 > Packages.gz
mkdir -p /usr/share/cps-managed-memory-policy
cp /policy/provenance.json /policy/uvm-reject-managed-memory.patch /usr/share/cps-managed-memory-policy/
sha256sum "$package" > /usr/share/cps-managed-memory-policy/derived-package.sha256
