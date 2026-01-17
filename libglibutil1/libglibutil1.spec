#
# spec file for package libglibutil1
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

%define libname libglibutil
Name:           %{libname}1
Version:        1.0.80
Release:        1
Summary:        Library of glib utilities 
License:        BSD-3-Clause
URL:            https://github.com/sailfishos/%{libname}
Source0:        https://github.com/sailfishos/%{libname}/archive/refs/tags/%{version}.tar.gz#/%{libname}-%{version}.tar.gz
BuildRequires:  gcc
BuildRequires:  pkgconfig
BuildRequires:  pkgconfig(glib-2.0)

%description
Provides glib utility functions and macros

%package -n     %{libname}-devel
Summary:        Development files for %{libname}
Requires:       %{name} = %{version}

%description -n %{libname}-devel
The %{libname}-devel package contains libraries and header files for
developing applications that use %{libname}.

%prep
%autosetup -n %{libname}-%{version} -p1

%build
make %{?_smp_mflags} LIBDIR=%{_libdir} KEEP_SYMBOLS=1 release pkgconfig

%install
make LIBDIR=%{_libdir} DESTDIR=%{buildroot} install-dev

%check
make -C  test test

%post -p /sbin/ldconfig
%postun -p /sbin/ldconfig

%files
%license LICENSE
%doc README
%{_libdir}/%{libname}.so.*

%files -n %{libname}-devel
%{_libdir}/pkgconfig/%{libname}.pc
%{_libdir}/%{libname}.so
%{_includedir}/gutil/

%changelog
* Sat Jan 17 2026 James Ed Randson <jimedrand@disroot.org> - 1.0.80
- Maintain an package %{libname}
