%define selinuxtype targeted
%define upstream_name waydroid
%define upstream_version 1.4.3

Name:           waydroid14x
Version:        %{upstream_version}
Release:        1
Summary:        Container-based approach to boot a full Android system on GNU/Linux (version 1.4.x for running Android 11)
License:        GPL-3.0-only
Group:          System/Emulators/Other
URL:            https://github.com/waydroid/waydroid
Source0:        https://github.com/waydroid/waydroid/archive/refs/tags/%{upstream_version}.tar.gz#/%{upstream_name}-%{upstream_version}.tar.gz
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
Recommends:     dkms
Recommends:     kernel-devel

%if 0%{?suse_version}
Requires:       container-selinux
BuildRequires:  container-selinux
%endif

Conflicts:      waydroid
Provides:       waydroid = %{version}-%{release}

%description
Waydroid is a container-based approach to boot a full Android system on a regular GNU/Linux system. It uses Linux namespaces (user, pid, uts, net, mount, ipc) to run a full Android system in a container and provide Android applications on any GNU/Linux-based platform.

The Android inside the container has direct access to needed hardware through LXC. The Android runtime environment ships with a minimal customized Android system image based on LineageOS.

This package is specifically for Waydroid 1.4.x series, designed to run Android 11.

%prep
%autosetup -p1 -n %{upstream_name}-%{upstream_version}

mkdir -p SELinux
cp %{SOURCE1} SELinux/
cp %{SOURCE2} SELinux/

%build
sed -i -e '/"system_channel":/ s/: ".*"/: ""/' tools/config/__init__.py
sed -i -e '/"vendor_channel":/ s/: ".*"/: ""/' tools/config/__init__.py

%if 0%{?suse_version}
cd SELinux
%make_build NAME=%{selinuxtype} -f %{_datadir}/selinux/devel/Makefile
cd ..
%endif

%install
%make_install LIBDIR=%{_libdir} DESTDIR=%{buildroot} USE_SYSTEMD=1 USE_DBUS_ACTIVATION=1 USE_NFTABLES=1

%py3_compile %{buildroot}%{_prefix}/lib/waydroid

%if 0%{?suse_version}
install -d %{buildroot}%{_datadir}/selinux/%{selinuxtype}
install -p -m 0644 SELinux/waydroid.pp %{buildroot}%{_datadir}/selinux/%{selinuxtype}/%{name}.pp
%endif

install -d %{buildroot}%{_datadir}/gbinder/config
install -p -m 0644 %{SOURCE3} %{buildroot}%{_datadir}/gbinder/config/waydroid.conf

%check
desktop-file-validate %{buildroot}%{_datadir}/applications/Waydroid.desktop
desktop-file-validate %{buildroot}%{_datadir}/applications/waydroid.market.desktop
desktop-file-validate %{buildroot}%{_datadir}/applications/waydroid.app.install.desktop
appstream-util validate-relax --nonet %{buildroot}%{_datadir}/metainfo/id.waydro.waydroid.metainfo.xml

%pre
%service_add_pre waydroid-container.service

%if 0%{?suse_version}
%selinux_relabel_pre -s %{selinuxtype}
%endif

%post
%if 0%{?suse_version}
%selinux_modules_install -s %{selinuxtype} %{_datadir}/selinux/%{selinuxtype}/%{name}.pp
%selinux_relabel_post -s %{selinuxtype}
%endif

%service_add_post waydroid-container.service

if [ $1 -eq 1 ]; then
cat << 'EOF'

================================================================================
Waydroid 1.4.x (Android 11) Installation Complete
================================================================================

This is Waydroid 1.4.x specifically for running Android 11.
To initialize Waydroid, run: waydroid init

EOF
fi

if [ $1 -gt 1 ]; then
cat << 'EOF'

================================================================================
Waydroid 1.4.x (Android 11) Upgrade Complete
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

%if 0%{?suse_version}
if [ $1 -eq 0 ]; then
    %selinux_modules_uninstall -s %{selinuxtype} %{name}
    %selinux_relabel_post -s %{selinuxtype}
fi
%endif

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

%if 0%{?suse_version}
%{_datadir}/selinux/%{selinuxtype}/%{name}.pp
%endif

%changelog
* Sat Jan 17 2026 James "Jim" Ed Randson <jimedrand@example.com> - 1.4.3-1
- Initial package for waydroid14x (Waydroid 1.4.x for Android 11)
