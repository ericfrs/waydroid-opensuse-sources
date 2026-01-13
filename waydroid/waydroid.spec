%define selinuxtype targeted

Name:           waydroid
Version:        1.6.1
Release:        0
Summary:        Container-based approach to boot a full Android system on GNU/Linux
License:        GPL-3.0-only
Group:          System/Emulators/Other
URL:            https://github.com/waydroid/waydroid
Source0:        https://github.com/waydroid/waydroid/archive/refs/tags/%{version}.tar.gz#/%{name}-%{version}.tar.gz
Source1:        waydroid.te
Source2:        waydroid.fc
Source3:        waydroid-help.sh
Source4:        waydroid.conf
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

%description
Waydroid is a container-based approach to boot a full Android system on a regular GNU/Linux system. It uses Linux namespaces (user, pid, uts, net, mount, ipc) to run a full Android system in a container and provide Android applications on any GNU/Linux-based platform.

The Android inside the container has direct access to needed hardware through LXC. The Android runtime environment ships with a minimal customized Android system image based on LineageOS.

%prep
%autosetup -p1

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

install -d %{buildroot}%{_sbindir}
install -p -m 0755 %{SOURCE3} %{buildroot}%{_sbindir}/waydroid-help

%if 0%{?suse_version}
install -d %{buildroot}%{_datadir}/selinux/%{selinuxtype}
install -p -m 0644 SELinux/%{name}.pp %{buildroot}%{_datadir}/selinux/%{selinuxtype}/
%endif

install -d %{buildroot}%{_datadir}/gbinder/config
install -p -m 0644 %{SOURCE4} %{buildroot}%{_datadir}/gbinder/config/waydroid.conf

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
Waydroid Installation Complete
================================================================================

Setup binder module (required):
    sudo waydroid-help install
    sudo waydroid-help load

Initialize Waydroid:
    sudo waydroid init
    sudo systemctl start waydroid-container.service

Check status:
    waydroid-help status

For more commands: waydroid-help help

To uninstall in the future:
    Remove all data and binder module: sudo waydroid-help cleanup
    Remove only binder module: sudo waydroid-help uninstall
================================================================================

EOF
fi

if [ $1 -gt 1 ]; then
cat << 'EOF'

================================================================================
Waydroid Upgrade Complete
================================================================================

Check module compatibility:
    waydroid-help status

Rebuild if needed:
    sudo waydroid-help rebuild-all

Restart Waydroid:
    sudo systemctl restart waydroid-container.service
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
%{_sbindir}/waydroid-help
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
* Tue Jan 13 2026 James Ed Randson <jimedrand@disroot.org> - 1.6.1-0
- Update to version 1.6.1
- Added waydroid-help management tool for binder module setup
- Removed automatic post-install/upgrade actions
- User must manually run waydroid-help commands
- Removed dev-binderfs.mount handling
- Removed manual DKMS dependencies from package
- Removed binder module files (handled by waydroid-help)
- Removed ashmem module dependency (mainline kernel)
- Enhanced systemd service configuration
- Added gbinder configuration file
- Simplified package to core Waydroid components only
