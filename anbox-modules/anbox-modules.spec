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

%package autoload
Summary:        Autoload configuration for anbox kernel modules
Supplements:    kmod(binder_linux.ko)
BuildArch:      noarch

%description autoload
Configuration files to autoload the anbox binder kernel module
during system startup.

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

# configs for autoload package
install -D -m 0644 source/anbox.conf %{buildroot}%{_modulesloaddir}/anbox.conf
install -D -m 0644 source/99-anbox.rules %{buildroot}%{_udevrulesdir}/99-anbox.rules

%files autoload
%dir %{_modulesloaddir}
%{_modulesloaddir}/anbox.conf
%{_udevrulesdir}/99-anbox.rules

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
