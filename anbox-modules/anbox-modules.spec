#
# spec file for package anbox-modules
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
# needssslcertforbuild


%ifarch x86_64
%if 0%{?suse_version} > 1600
%define kmp_longterm 1
%endif
%endif

Name:           anbox-modules
Version:        20250305.18f37ba
Release:        0
Summary:        Anbox binder kernel module
License:        GPL-2.0-only
Group:          System/Kernel
URL:            https://github.com/ericfrs/anbox-modules
Source0:        %{name}-%{version}.tar.gz
Source1:        %{name}-preamble
%if 0%{?suse_version} == 1550
Patch0:         fix-leap-15_5.patch
%endif
BuildRequires:  %{kernel_module_package_buildreqs}
BuildRequires:  pesign-obs-integration
%if 0%{?kmp_longterm}
BuildRequires:  kernel-syms-longterm
%endif

%kernel_module_package -n anbox -p %{SOURCE1} -x debug -x trace -c %{_sourcedir}/_projectcert.crt 

%description
Anbox binder out-of-tree kernel module for running Android containers.
This package provides the kernel module package (KMP) variant that is
built against specific kernel versions.

%package dkms
Summary:        DKMS source for anbox kernel modules
Group:          System/Kernel
Requires:       dkms
Requires:       gcc
Requires:       make
BuildArch:      noarch
Provides:       %{name}-kmod = %{version}
Conflicts:      anbox-kmp
Obsoletes:      %{name}-kmod < %{version}

%description dkms
This package provides the anbox kernel module source code and DKMS configuration
for automatic building against installed kernels. The modules include the binder
driver required for Anbox Android container runtime.

DKMS will automatically rebuild the module when new kernels are installed,
ensuring compatibility across kernel updates without requiring manual intervention.

%prep
# Source code setup
%setup -q -n %{name}-%{version}

# Apply specific patch for Leap 15.5
%if 0%{?suse_version} == 1550
%patch -P 0 -p1
%endif

set -- *
mkdir source
mv "$@" source/
mkdir obj

%build
for flavor in %{flavors_to_build} ; do
    rm -rf obj/$flavor
    cp -r source obj/$flavor
    %make_build V=1 -C %{kernel_source $flavor} %{?linux_make_arch} modules M=$PWD/obj/$flavor/binder
done

%install
export INSTALL_MOD_PATH=%{buildroot}
export INSTALL_MOD_DIR='%{kernel_module_package_moddir}'

for flavor in %{flavors_to_build} ; do
    make V=1 -C %{kernel_source $flavor} modules_install M=$PWD/obj/$flavor/binder
done

export BRP_PESIGN_FILES='*.ko'

install -D -m 0644 -t %{buildroot}%{_modulesloaddir} source/anbox.conf
install -D -m 0644 -t %{buildroot}%{_udevrulesdir} source/99-anbox.rules

# Install DKMS source
mkdir -p %{buildroot}%{_usrsrc}/%{name}-%{version}
cp -r source/binder %{buildroot}%{_usrsrc}/%{name}-%{version}/
cp source/anbox.conf %{buildroot}%{_usrsrc}/%{name}-%{version}/
cp source/99-anbox.rules %{buildroot}%{_usrsrc}/%{name}-%{version}/
install -D -m 0644 source/debian/copyright %{buildroot}%{_usrsrc}/%{name}-%{version}/copyright
install -D -m 0644 source/README.md %{buildroot}%{_usrsrc}/%{name}-%{version}/README.md

# Create DKMS configuration
cat > %{buildroot}%{_usrsrc}/%{name}-%{version}/dkms.conf << 'EOF'
PACKAGE_NAME="anbox-modules"
PACKAGE_VERSION="%{version}"
MAKE[0]="make -C binder KERNEL_DIR=${kernel_source_dir} KERNELRELEASE=${kernelver}"
CLEAN="make -C binder clean"
BUILT_MODULE_NAME[0]="binder_linux"
BUILT_MODULE_LOCATION[0]="binder/"
DEST_MODULE_LOCATION[0]="/kernel/drivers/misc/"
AUTOINSTALL="yes"
REMAKE_INITRD="yes"
EOF

# Create Makefile wrapper for DKMS
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

# Create kernel update trigger script
mkdir -p %{buildroot}%{_libexecdir}/dkms
cat > %{buildroot}%{_libexecdir}/dkms/anbox-modules-rebuild << 'EOFSCRIPT'
#!/bin/bash
# Auto-rebuild anbox-modules when kernel is updated

KERNEL_VERSION="$1"
MODULE_NAME="anbox-modules"
MODULE_VERSION="%{version}"

if [ -z "$KERNEL_VERSION" ]; then
    KERNEL_VERSION=$(uname -r)
fi

# Check if DKMS is available
if ! command -v dkms >/dev/null 2>&1; then
    exit 0
fi

# Check if module is registered with DKMS
if ! dkms status -m "$MODULE_NAME" -v "$MODULE_VERSION" >/dev/null 2>&1; then
    exit 0
fi

# Build and install for the new kernel
dkms build -m "$MODULE_NAME" -v "$MODULE_VERSION" -k "$KERNEL_VERSION" 2>/dev/null
dkms install -m "$MODULE_NAME" -v "$MODULE_VERSION" -k "$KERNEL_VERSION" 2>/dev/null

exit 0
EOFSCRIPT
chmod 0755 %{buildroot}%{_libexecdir}/dkms/anbox-modules-rebuild

# Create systemd service for kernel update hook
mkdir -p %{buildroot}%{_unitdir}
cat > %{buildroot}%{_unitdir}/anbox-modules-dkms-rebuild.service << 'EOFSERVICE'
[Unit]
Description=Rebuild anbox-modules DKMS module for running kernel
ConditionPathExists=%{_libexecdir}/dkms/anbox-modules-rebuild
After=local-fs.target

[Service]
Type=oneshot
ExecStart=%{_libexecdir}/dkms/anbox-modules-rebuild
RemainAfterExit=no
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOFSERVICE

%pre dkms
# Clean up old versions if present
if [ -x /usr/sbin/dkms ] || [ -x /usr/bin/dkms ]; then
    INSTALLED_VERSIONS=$(dkms status -m %{name} 2>/dev/null | grep -v "%{version}" | awk -F'[, ]' '{print $2}' | sort -u)
    for old_ver in $INSTALLED_VERSIONS; do
        if [ -n "$old_ver" ]; then
            dkms remove -m %{name} -v "$old_ver" --all 2>/dev/null || true
        fi
    done
fi

%post dkms
# Check if dkms is available
if [ -x /usr/sbin/dkms ] || [ -x /usr/bin/dkms ]; then
    # Add to DKMS tree
    dkms add -m %{name} -v %{version} --rpm_safe_upgrade 2>/dev/null || true
    
    # Build and install for all installed kernels
    for kernel in /lib/modules/*; do
        kernel_version=$(basename "$kernel")
        if [ -d "$kernel/build" ] || [ -L "$kernel/build" ]; then
            dkms build -m %{name} -v %{version} -k "$kernel_version" 2>/dev/null || true
            dkms install -m %{name} -v %{version} -k "$kernel_version" 2>/dev/null || true
        fi
    done
fi

# Install configuration files
if [ ! -f %{_modulesloaddir}/anbox.conf ]; then
    install -D -m 0644 %{_usrsrc}/%{name}-%{version}/anbox.conf %{_modulesloaddir}/anbox.conf
fi
if [ ! -f %{_udevrulesdir}/99-anbox.rules ]; then
    install -D -m 0644 %{_usrsrc}/%{name}-%{version}/99-anbox.rules %{_udevrulesdir}/99-anbox.rules
    if [ -x /usr/bin/udevadm ]; then
        udevadm control --reload-rules 2>/dev/null || true
        udevadm trigger --subsystem-match=misc 2>/dev/null || true
    fi
fi

# Enable rebuild service
if [ -x /usr/bin/systemctl ]; then
    systemctl daemon-reload 2>/dev/null || true
fi

# Load module for current kernel if built successfully
if lsmod | grep -q binder_linux; then
    modprobe -r binder_linux 2>/dev/null || true
fi
modprobe binder_linux 2>/dev/null || true

%preun dkms
# Only remove on complete uninstall, not upgrade
if [ "$1" = "0" ]; then
    # Unload module if loaded
    if lsmod | grep -q binder_linux; then
        modprobe -r binder_linux 2>/dev/null || true
    fi
    
    # Check if dkms is available before removing
    if [ -x /usr/sbin/dkms ] || [ -x /usr/bin/dkms ]; then
        dkms remove -m %{name} -v %{version} --all --rpm_safe_upgrade 2>/dev/null || true
    fi
    
    # Disable and stop rebuild service
    if [ -x /usr/bin/systemctl ]; then
        systemctl disable anbox-modules-dkms-rebuild.service 2>/dev/null || true
        systemctl daemon-reload 2>/dev/null || true
    fi
fi

%postun dkms
# Clean up configuration files and DKMS source on complete uninstall
if [ "$1" = "0" ]; then
    rm -f %{_modulesloaddir}/anbox.conf
    rm -f %{_udevrulesdir}/99-anbox.rules
    
    if [ -x /usr/bin/udevadm ]; then
        udevadm control --reload-rules 2>/dev/null || true
    fi
    
    # Clean up DKMS source directory
    rm -rf %{_usrsrc}/%{name}-%{version}
    
    # Clean up any remaining DKMS state
    if [ -x /usr/sbin/dkms ] || [ -x /usr/bin/dkms ]; then
        for kernel in /lib/modules/*; do
            kernel_version=$(basename "$kernel")
            dkms remove -m %{name} -v %{version} -k "$kernel_version" 2>/dev/null || true
        done
    fi
fi

%posttrans dkms
# Rebuild for current kernel after transaction completes
if [ -x /usr/sbin/dkms ] || [ -x /usr/bin/dkms ]; then
    CURRENT_KERNEL=$(uname -r)
    dkms build -m %{name} -v %{version} -k "$CURRENT_KERNEL" 2>/dev/null || true
    dkms install -m %{name} -v %{version} -k "$CURRENT_KERNEL" 2>/dev/null || true
fi

%files
%license source/debian/copyright
%doc source/README.md
%dir %{_modulesloaddir}
%{_modulesloaddir}/anbox.conf
%{_udevrulesdir}/99-anbox.rules

%files dkms
%{_usrsrc}/%{name}-%{version}/
%dir %{_libexecdir}/dkms
%{_libexecdir}/dkms/anbox-modules-rebuild
%{_unitdir}/anbox-modules-dkms-rebuild.service

%changelog
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
