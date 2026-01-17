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

%define libname libgbinder
%define libglibutil_version 1.0.80

Name:           %{libname}1
Version:        1.1.43
Release:        2
Summary:        GLib-style interface to binder (Android IPC mechanism)
License:        BSD-3-Clause
URL:            https://github.com/mer-hybris/%{libname}
Source0:        https://github.com/mer-hybris/%{libname}/archive/refs/tags/%{version}.tar.gz#/%{libname}-%{version}.tar.gz

BuildRequires:  gcc
BuildRequires:  pkgconfig
BuildRequires:  pkgconfig(glib-2.0)
BuildRequires:  pkgconfig(libglibutil) >= %{libglibutil_version}
BuildRequires:  bison
BuildRequires:  flex

%description
C interfaces for Android binder

%package -n     %{libname}-devel
Summary:        Development files for %{libname}
Requires:       %{name} = %{version}

%description -n %{libname}-devel
The %{libname}-devel package contains libraries and header files for
developing applications that use %{libname}.

%package -n     %{libname}-tools
Summary: Binder tools
Requires: %{name} >= %{version}

%description -n %{libname}-tools
Binder command line utilities

%prep
%autosetup -n %{libname}-%{version} -p1

%build
export CFLAGS="%{optflags} -Wno-incompatible-pointer-types"
export CXXFLAGS="%{optflags} -Wno-incompatible-pointer-types"
make %{?_smp_mflags} LIBDIR=%{_libdir} KEEP_SYMBOLS=1 release pkgconfig
make -C test/binder-bridge KEEP_SYMBOLS=1 release
make -C test/binder-list KEEP_SYMBOLS=1 release
make -C test/binder-ping KEEP_SYMBOLS=1 release
make -C test/binder-call KEEP_SYMBOLS=1 release

%install
make LIBDIR=%{_libdir} DESTDIR=%{buildroot} install-dev
make -C test/binder-bridge DESTDIR=%{buildroot} install
make -C test/binder-list DESTDIR=%{buildroot} install
make -C test/binder-ping DESTDIR=%{buildroot} install
make -C test/binder-call DESTDIR=%{buildroot} install

%check
export CFLAGS="%{optflags} -Wno-incompatible-pointer-types"
export CXXFLAGS="%{optflags} -Wno-incompatible-pointer-types"

make -C unit test

%post -p /sbin/ldconfig
%postun -p /sbin/ldconfig

%files
%license LICENSE
%doc README
%{_libdir}/%{libname}.so.*

%files -n %{libname}-devel
%{_libdir}/pkgconfig/%{libname}.pc
%{_libdir}/%{libname}.so
%{_includedir}/gbinder/

%files -n %{libname}-tools
%{_bindir}/binder-bridge
%{_bindir}/binder-list
%{_bindir}/binder-ping
%{_bindir}/binder-call

%changelog
* Thu Jun 19 2025 James Ed Randson <jimedrand@disroot.org> - 1.1.42
- Maintain an package %{libname}

* Mon Jan 12 2026 James Ed Randson <jimedrand@disroot.org> - 1.1.43
- Updated to 1.1.43
