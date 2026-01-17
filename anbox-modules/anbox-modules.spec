#
# spec file for package anbox-modules
#
# Copyright (c) 2025 SUSE LLC
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
URL:            https://github.com/llyyr/anbox-modules
Source0:        %{name}-%{version}.tar.gz
Source1:        %{name}-preamble
Patch0:         fix-leap-15_5.patch
BuildRequires:  %{kernel_module_package_buildreqs}
Requires:       anbox-kmp = %{version}
BuildRequires:  pesign-obs-integration

%if 0%{?kmp_longterm}
BuildRequires:  kernel-syms-longterm
%endif
%kernel_module_package -n anbox -p %{SOURCE1} -x debug -x trace -c %{_sourcedir}/_projectcert.crt 

%description
Anbox binder out-of-tree kernel module.

# DKMS subpackage
%package dkms
Summary:        DKMS source for anbox kernel modules
Group:          System Environment/Kernel
Requires:       dkms
Requires:       kernel-devel
Requires:       gcc
Requires:       make
BuildArch:      noarch
Provides:       %{name}-kmod = %{version}
Conflicts:      anbox-kmp

%description dkms
This package provides the anbox kernel module source code and DKMS configuration
for automatic building against installed kernels. The modules include the binder
driver required for Anbox Android container runtime.

%prep
%autosetup -p1

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

# Create DKMS configuration
cat > %{buildroot}%{_usrsrc}/%{name}-%{version}/dkms.conf << 'EOF'
PACKAGE_NAME="anbox-modules"
PACKAGE_VERSION="%{version}"
MAKE[0]="make -C binder KERNEL_DIR=${kernel_source_dir}"
CLEAN="make -C binder clean"
BUILT_MODULE_NAME[0]="binder_linux"
BUILT_MODULE_LOCATION[0]="binder/"
DEST_MODULE_LOCATION[0]="/kernel/drivers/misc/"
AUTOINSTALL="yes"
EOF

# Create Makefile wrapper for DKMS
cat > %{buildroot}%{_usrsrc}/%{name}-%{version}/Makefile << 'EOF'
# DKMS Makefile wrapper for anbox-modules
KERNEL_DIR ?= /lib/modules/$(shell uname -r)/build

all:
	$(MAKE) -C binder KERNEL_DIR=$(KERNEL_DIR)

clean:
	$(MAKE) -C binder clean

install:
	$(MAKE) -C binder KERNEL_DIR=$(KERNEL_DIR) modules_install

.PHONY: all clean install
EOF


# The BRP_PESIGN_FILES variable must be set to a space separated list of
# directories or patterns matching files that need to be signed.  E.g., packages
# that include firmware files would set BRP_PESIGN_FILES='*.ko /lib/firmware'
export BRP_PESIGN_FILES='*.ko'


%files
%license source/debian/copyright
%doc source/README.md
%dir %{_modulesloaddir}
%{_modulesloaddir}/anbox.conf
%{_udevrulesdir}/99-anbox.rules

%files dkms
%{_usrsrc}/%{name}-%{version}/

%post dkms
# Check if dkms is available
if [ -x /usr/sbin/dkms ] || [ -x /usr/bin/dkms ]; then
    # Add to DKMS tree
    dkms add -m %{name} -v %{version} --rpm_safe_upgrade 2>/dev/null || true
    # Build module
    dkms build -m %{name} -v %{version} 2>/dev/null || true
    # Install module
    dkms install -m %{name} -v %{version} 2>/dev/null || true
fi
# Install configuration files
if [ -f %{_usrsrc}/%{name}-%{version}/anbox.conf ]; then
    cp %{_usrsrc}/%{name}-%{version}/anbox.conf %{_modulesloaddir}/ 2>/dev/null || true
fi
if [ -f %{_usrsrc}/%{name}-%{version}/99-anbox.rules ]; then
    cp %{_usrsrc}/%{name}-%{version}/99-anbox.rules %{_udevrulesdir}/ 2>/dev/null || true
    if [ -x /usr/bin/udevadm ]; then
        udevadm control --reload-rules 2>/dev/null || true
    fi
fi

%preun dkms
# Check if dkms is available before removing
if [ -x /usr/sbin/dkms ] || [ -x /usr/bin/dkms ]; then
    # Only remove if this is a complete uninstall (not upgrade)
    if [ "$1" = "0" ]; then
        dkms remove -m %{name} -v %{version} --all --rpm_safe_upgrade 2>/dev/null || true
    fi
fi
# Clean up configuration files only on complete uninstall
if [ "$1" = "0" ]; then
    rm -f %{_modulesloaddir}/anbox.conf
    rm -f %{_udevrulesdir}/99-anbox.rules
    if [ -x /usr/bin/udevadm ]; then
        udevadm control --reload-rules 2>/dev/null || true
    fi
fi

%changelog
* Mon Jun 23 2025 James "Jim" Ed Randson <jimedrand@outlook.com> - 20250305.18f37ba-0
- Added DKMS subpackage support alongside existing KMP
- Added automatic module rebuild capability for kernel updates
- Added conflict resolution between DKMS and KMP packages
