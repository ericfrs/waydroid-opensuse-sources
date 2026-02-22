#
# spec file for package waydroid
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

%define selinuxtype targeted

Name:           waydroid
Version:        1.6.2
Release:        1
Summary:        Container-based approach to boot a full Android system on GNU/Linux
License:        GPL-3.0-only
Group:          System/Emulators/Other
URL:            https://github.com/waydroid/waydroid
Source0:        https://github.com/waydroid/waydroid/archive/refs/tags/%{version}.tar.gz#/%{name}-%{version}.tar.gz
Source1:        waydroid.te
Source2:        waydroid.fc
Source3:        waydroid.conf
Patch0:         setup-firewalld.patch
Patch1:         mount-secontext.patch

BuildArch:      noarch

BuildRequires:  dbus-1-devel
BuildRequires:  make
BuildRequires:  polkit-devel
BuildRequires:  python3-devel
BuildRequires:  python3-gbinder
BuildRequires:  python3-dbus-python
BuildRequires:  python3-gobject
BuildRequires:  selinux-policy-devel
BuildRequires:  systemd-rpm-macros
BuildRequires:  desktop-file-utils
BuildRequires:  appstream-glib
BuildRequires:  hicolor-icon-theme

Requires:       android-tools
Requires:       dbus-1
Requires:       dnsmasq
Requires:       iproute2
Requires:       iptables
Requires:       libgbinder1
Requires:       libglibutil1
Requires:       lxc
Requires:       nftables
Requires:       polkit
Requires:       python3-dbus-python
Requires:       python3-gbinder
Requires:       python3-gobject
Requires:       hicolor-icon-theme
Requires:       desktop-file-utils
Requires:       (%{name}-selinux = %{version}-%{release} if selinux-policy-%{selinuxtype})

# Provide choice between DKMS and KMP for kernel modules
# anbox-modules is a meta package that will pull appropriate KMP
Requires:       (anbox-modules-dkms or anbox-modules)
Recommends:     anbox-modules-dkms

%description
Waydroid is a container-based approach to boot a full Android system on a regular GNU/Linux system. It uses Linux namespaces (user, pid, uts, net, mount, ipc) to run a full Android system in a container and provide Android applications on any GNU/Linux-based platform.

The Android inside the container has direct access to needed hardware through LXC. The Android runtime environment ships with a minimal customized Android system image based on LineageOS.

%package selinux
Summary:        SELinux policy module for waydroid
Requires:       %{name} = %{version}-%{release}
Requires:       container-selinux

%description selinux
This package contains the SELinux policy module necessary to run waydroid.

%prep
%autosetup -p1

mkdir -p SELinux
cp %{SOURCE1} SELinux/
cp %{SOURCE2} SELinux/

%build
sed -i -e '/"system_channel":/ s/: ".*"/: ""/' tools/config/__init__.py
sed -i -e '/"vendor_channel":/ s/: ".*"/: ""/' tools/config/__init__.py

cd SELinux
%make_build NAME=%{selinuxtype} -f %{_datadir}/selinux/devel/Makefile
cd ..

%install
%make_install LIBDIR=%{_libdir} DESTDIR=%{buildroot} USE_SYSTEMD=1 USE_DBUS_ACTIVATION=1 USE_NFTABLES=1

%py3_compile %{buildroot}%{_prefix}/lib/waydroid

install -d %{buildroot}%{_datadir}/selinux/%{selinuxtype}
install -p -m 0644 SELinux/%{name}.pp %{buildroot}%{_datadir}/selinux/%{selinuxtype}/

install -d %{buildroot}%{_datadir}/gbinder/config
install -p -m 0644 %{SOURCE3} %{buildroot}%{_datadir}/gbinder/config/waydroid.conf

%check
desktop-file-validate %{buildroot}%{_datadir}/applications/Waydroid.desktop
desktop-file-validate %{buildroot}%{_datadir}/applications/waydroid.market.desktop
desktop-file-validate %{buildroot}%{_datadir}/applications/waydroid.app.install.desktop
appstream-util validate-relax --nonet %{buildroot}%{_datadir}/metainfo/id.waydro.waydroid.metainfo.xml

%pre
%service_add_pre waydroid-container.service

%post
%service_add_post waydroid-container.service

if [ $1 -eq 1 ]; then
cat << 'EOF'

================================================================================
Waydroid Installation Complete
================================================================================

Kernel modules required. Choose one:

1. anbox-modules-dkms (recommended)
   - Rebuilds automatically for every kernel update
   - Works with all kernel flavors (default, longterm, etc.)
   Install: zypper install anbox-modules-dkms

2. anbox-modules (KMP - Kernel Module Package)
   - Pre-compiled for specific kernel version
   - Faster installation, no compilation needed
   - Auto-selects correct variant for your kernel
   Install: zypper install anbox-modules

After installing, load module: sudo modprobe binder_linux

EOF
fi

if [ $1 -gt 1 ]; then
cat << 'EOF'

================================================================================
Waydroid Upgrade Complete
================================================================================

EOF
fi

if [ -x %{_bindir}/waydroid ]; then
    %{_bindir}/waydroid upgrade -o >/dev/null 2>&1 || :
fi

%preun
%service_del_preun waydroid-container.service

%postun
%service_del_postun waydroid-container.service

%pre selinux
%selinux_relabel_pre -s %{selinuxtype}

%post selinux
%selinux_modules_install -s %{selinuxtype} %{_datadir}/selinux/%{selinuxtype}/%{name}.pp
%selinux_relabel_post -s %{selinuxtype}
if [ "$1" -le "1" ]; then
    # On first install, restart the daemon for the custom label to be applied
    %service_del_postun_with_restart waydroid-container.service
fi

%postun selinux
if [ $1 -eq 0 ]; then
    %selinux_modules_uninstall -s %{selinuxtype} %{name}
    %selinux_relabel_post -s %{selinuxtype}
fi

%files
%license LICENSE
%doc README.md
%{_prefix}/lib/waydroid
%{_bindir}/waydroid
%{_unitdir}/waydroid-container.service
%{_datadir}/applications/Waydroid.desktop
%{_datadir}/applications/waydroid.market.desktop
%{_datadir}/applications/waydroid.app.install.desktop
%{_datadir}/metainfo/id.waydro.waydroid.metainfo.xml
%{_datadir}/icons/hicolor/512x512/apps/waydroid.png
%{_datadir}/dbus-1/system-services/id.waydro.Container.service
%{_datadir}/dbus-1/system.d/id.waydro.Container.conf
%{_datadir}/polkit-1/actions/id.waydro.Container.policy
%dir %{_datadir}/desktop-directories
%{_datadir}/desktop-directories/waydroid.directory
%dir %{_sysconfdir}/xdg/menus
%dir %{_sysconfdir}/xdg/menus/applications-merged
%{_sysconfdir}/xdg/menus/applications-merged/waydroid.menu
%dir %{_datadir}/gbinder
%dir %{_datadir}/gbinder/config
%{_datadir}/gbinder/config/waydroid.conf

%files selinux
%doc SELinux/%{name}.te
%dir %{_datadir}/selinux
%dir %{_datadir}/selinux/%{selinuxtype}
%{_datadir}/selinux/%{selinuxtype}/%{name}.pp

%changelog
* Sun Jan 18 2026 James "Jim" Ed Randson <jimedrand@disroot.org>
- Add flexible kernel module dependency support
- Allow choice between anbox-modules-dkms or anbox-modules (KMP)
- Recommend DKMS for better compatibility across kernel updates
- Simplify post-install message
