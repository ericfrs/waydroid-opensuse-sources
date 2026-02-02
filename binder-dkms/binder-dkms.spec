#
# spec file for package binder-dkms
#
# Copyright (c) 2026 SUSE LLC
# Copyright (c) 2026 James "Jim" Ed Randson <jimedrand@disroot.org>
#
# All modifications and additions to the file contributed by third parties
# remain the property of their copyright owners, unless otherwise agreed
# upon. The license for this file, and modifications and additions to the
# file, is the same license as for the pristine package itself (unless the
# license for the pristine package is not an Open Source License, in which
# case the license is the MIT License). An "Open Source License" is a
# license that conforms to the Open Source Definition (Version 1.9)
# published by the Open Source Initiative.

# Please submit bugfixes or comments via https://bugs.opensuse.org/
#

%define commit 1434f1ebf74135a99d17e83f25d8e23908efc4cf
%define commitshort 1434f1e
%define shortdate 250804

Name:           binder-dkms
Version:        %{shortdate}.%{commitshort}
Release:        0
Summary:        DKMS source for binder kernel module
License:        GPL-2.0-only
Group:          System/Kernel
URL:            https://github.com/choff/anbox-modules
Source0:        https://github.com/choff/anbox-modules/archive/%{commit}.tar.gz#/%{name}-%{version}.tar.gz
Patch0:         fix-leap-15_5.patch
BuildArch:      noarch
Requires:       dkms
Requires:       gcc
Requires:       make
Provides:       %{name}-kmod = %{version}
Provides:       anbox-modules-dkms = %{version}
Conflicts:      anbox-kmp
Conflicts:      anbox-modules-dkms
Obsoletes:      %{name}-kmod < %{version}
Obsoletes:      anbox-modules-dkms < %{version}
BuildRequires:  systemd-rpm-macros
%{?systemd_requires}

%description
This package provides the binder kernel module source code and DKMS configuration
for automatic building against installed kernels.

DKMS will automatically rebuild the module when new kernels are installed,
ensuring compatibility across kernel updates without requiring manual intervention.

%prep
%setup -q -n anbox-modules-%{commit}
%patch -P 0 -p1

%build

%install
mkdir -p %{buildroot}%{_usrsrc}/%{name}-%{version}
cp -r binder %{buildroot}%{_usrsrc}/%{name}-%{version}/
cp anbox.conf %{buildroot}%{_usrsrc}/%{name}-%{version}/binder.conf
cp 99-anbox.rules %{buildroot}%{_usrsrc}/%{name}-%{version}/99-binder.rules
install -D -m 0644 debian/copyright %{buildroot}%{_usrsrc}/%{name}-%{version}/copyright
install -D -m 0644 README.md %{buildroot}%{_usrsrc}/%{name}-%{version}/README.md

cat > %{buildroot}%{_usrsrc}/%{name}-%{version}/dkms.conf << 'EOF'
PACKAGE_NAME="binder-dkms"
PACKAGE_VERSION="%{version}"
MAKE[0]="make -C binder KERNEL_DIR=${kernel_source_dir} KERNELRELEASE=${kernelver}"
CLEAN="make -C binder clean"
BUILT_MODULE_NAME[0]="binder_linux"
BUILT_MODULE_LOCATION[0]="binder/"
DEST_MODULE_LOCATION[0]="/kernel/drivers/misc/"
AUTOINSTALL="yes"
REMAKE_INITRD="yes"
EOF

cat > %{buildroot}%{_usrsrc}/%{name}-%{version}/Makefile << 'EOF'
KERNEL_DIR ?= /lib/modules/$(shell uname -r)/build
KERNELRELEASE ?= $(shell uname -r)

all:
	$(MAKE) -C binder KERNEL_DIR=$(KERNEL_DIR) KERNELRELEASE=$(KERNELRELEASE)

clean:
	$(MAKE) -C binder clean

install:
	$(MAKE) -C binder KERNEL_DIR=$(KERNEL_DIR) KERNELRELEASE=$(KERNELRELEASE) modules_install

.PHONY: all clean install
EOF

mkdir -p %{buildroot}%{_libexecdir}/dkms
cat > %{buildroot}%{_libexecdir}/dkms/binder-dkms-rebuild << 'EOFSCRIPT'
#!/bin/bash

KERNEL_VERSION="$1"
MODULE_NAME="binder-dkms"
MODULE_VERSION="%{version}"

if [ -z "$KERNEL_VERSION" ]; then
    KERNEL_VERSION=$(uname -r)
fi

if ! command -v dkms >/dev/null 2>&1; then
    exit 0
fi

if ! dkms status -m "$MODULE_NAME" -v "$MODULE_VERSION" >/dev/null 2>&1; then
    exit 0
fi

dkms build -m "$MODULE_NAME" -v "$MODULE_VERSION" -k "$KERNEL_VERSION" 2>/dev/null
dkms install -m "$MODULE_NAME" -v "$MODULE_VERSION" -k "$KERNEL_VERSION" 2>/dev/null

exit 0
EOFSCRIPT
chmod 0755 %{buildroot}%{_libexecdir}/dkms/binder-dkms-rebuild

mkdir -p %{buildroot}%{_unitdir}
cat > %{buildroot}%{_unitdir}/binder-dkms-rebuild.service << 'EOFSERVICE'
[Unit]
Description=Rebuild binder-dkms DKMS module for running kernel
ConditionPathExists=%{_libexecdir}/dkms/binder-dkms-rebuild
After=local-fs.target

[Service]
Type=oneshot
ExecStart=%{_libexecdir}/dkms/binder-dkms-rebuild
RemainAfterExit=no
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOFSERVICE

install -D -m 0644 anbox.conf %{buildroot}%{_modulesloaddir}/binder.conf
install -D -m 0644 99-anbox.rules %{buildroot}%{_udevrulesdir}/99-binder.rules

%pre
if [ -x /usr/sbin/dkms ] || [ -x /usr/bin/dkms ]; then
    INSTALLED_VERSIONS=$(dkms status -m %{name} 2>/dev/null | grep -v "%{version}" | awk -F'[, ]' '{print $2}' | sort -u)
    for old_ver in $INSTALLED_VERSIONS; do
        if [ -n "$old_ver" ]; then
            dkms remove -m %{name} -v "$old_ver" --all 2>/dev/null || true
        fi
    done
fi
%service_add_pre binder-dkms-rebuild.service

%post
if [ -x /usr/sbin/dkms ] || [ -x /usr/bin/dkms ]; then
    dkms add -m %{name} -v %{version} --rpm_safe_upgrade 2>/dev/null || true
    
    for kernel in /lib/modules/*; do
        kernel_version=$(basename "$kernel")
        if [ -d "$kernel/build" ] || [ -L "$kernel/build" ]; then
            dkms build -m %{name} -v %{version} -k "$kernel_version" 2>/dev/null || true
            dkms install -m %{name} -v %{version} -k "$kernel_version" 2>/dev/null || true
        fi
    done
fi

if [ ! -f %{_modulesloaddir}/binder.conf ]; then
    install -D -m 0644 %{_usrsrc}/%{name}-%{version}/binder.conf %{_modulesloaddir}/binder.conf
fi
if [ ! -f %{_udevrulesdir}/99-binder.rules ]; then
    install -D -m 0644 %{_usrsrc}/%{name}-%{version}/99-binder.rules %{_udevrulesdir}/99-binder.rules
    if [ -x /usr/bin/udevadm ]; then
        udevadm control --reload-rules 2>/dev/null || true
        udevadm trigger --subsystem-match=misc 2>/dev/null || true
    fi
fi

%service_add_post binder-dkms-rebuild.service

if lsmod | grep -q binder_linux; then
    modprobe -r binder_linux 2>/dev/null || true
fi
modprobe binder_linux 2>/dev/null || true

%preun
if [ "$1" = "0" ]; then
    if lsmod | grep -q binder_linux; then
        modprobe -r binder_linux 2>/dev/null || true
    fi
    
    if [ -x /usr/sbin/dkms ] || [ -x /usr/bin/dkms ]; then
        dkms remove -m %{name} -v %{version} --all --rpm_safe_upgrade 2>/dev/null || true
    fi
    
    %service_del_preun binder-dkms-rebuild.service
fi

%postun
if [ "$1" = "0" ]; then
    rm -f %{_modulesloaddir}/binder.conf
    rm -f %{_udevrulesdir}/99-binder.rules
    
    if [ -x /usr/bin/udevadm ]; then
        udevadm control --reload-rules 2>/dev/null || true
    fi
    
    rm -rf %{_usrsrc}/%{name}-%{version}
    
    if [ -x /usr/sbin/dkms ] || [ -x /usr/bin/dkms ]; then
        for kernel in /lib/modules/*; do
            kernel_version=$(basename "$kernel")
            dkms remove -m %{name} -v %{version} -k "$kernel_version" 2>/dev/null || true
        done
    fi
fi
%service_del_postun binder-dkms-rebuild.service

%posttrans
if [ -x /usr/sbin/dkms ] || [ -x /usr/bin/dkms ]; then
    CURRENT_KERNEL=$(uname -r)
    dkms build -m %{name} -v %{version} -k "$CURRENT_KERNEL" 2>/dev/null || true
    dkms install -m %{name} -v %{version} -k "$CURRENT_KERNEL" 2>/dev/null || true
fi

%files
%license debian/copyright
%doc README.md
%{_usrsrc}/%{name}-%{version}/
%dir %{_libexecdir}/dkms
%{_libexecdir}/dkms/binder-dkms-rebuild
%{_unitdir}/binder-dkms-rebuild.service
%dir %{_modulesloaddir}
%{_modulesloaddir}/binder.conf
%{_udevrulesdir}/99-binder.rules

%changelog
* Mon Feb 02 2026 James "Jim" Ed Randson <jimedrand@disroot.org> - 20250305.18f37ba-0
- Renamed package to binder-dkms
- Updated all internal references to binder-dkms
- Added conflict with older anbox-modules-dkms for safety
- Applied fix-leap-15_5.patch for Leap 15.5/15.6/16.0 compatibility
- Fixed patch syntax to comply with modern RPM version requirements
- Converted to DKMS-only package (removed KMP variant)
- Package is now noarch (architecture-independent)
- Simplified build process without kernel compilation at build time

* Sat Jan 18 2026 James "Jim" Ed Randson <jimedrand@disroot.org> - 20250305.18f37ba-0
- Revised for openSUSE Factory compliance
- Added automatic DKMS rebuild on kernel updates via systemd service
- Improved DKMS cleanup on package removal
- Added posttrans scriptlet for post-upgrade rebuild
- Added kernel update trigger script
- Enhanced conflict resolution between KMP and DKMS variants
- Fixed file installation to avoid conflicts
- Added module reload capability in post scripts
- Improved error handling in all scriptlets
