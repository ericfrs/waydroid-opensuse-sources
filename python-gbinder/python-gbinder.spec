#
# spec file for package python-gbinder
#
# Copyright (c) 2026 SUSE LLC
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

%define pythonlib python3-gbinder
%define upstream_name gbinder-python
%{?sle15_python_module_pythons}

Name:           python-gbinder
Version:        1.3.0
Release:        2
Summary:        Python bindings for libgbinder
License:        GPL-3.0-or-later
URL:            https://github.com/waydroid/gbinder-python
Source0:        https://github.com/waydroid/%{upstream_name}/archive/%{version}/%{upstream_name}-%{version}.tar.gz
BuildRequires:  %{pythons}
BuildRequires:  python-rpm-generators
BuildRequires:  %{python_module Cython}
BuildRequires:  %{python_module setuptools}
BuildRequires:  fdupes
BuildRequires:  gcc-c++
BuildRequires:  libgbinder-devel
BuildRequires:  libglibutil-devel
BuildRequires:  python-rpm-macros
%{?python_enable_dependency_generator}
%python_subpackages

%description
Python bindings for libgbinder library, providing access to Android's
Binder IPC mechanism. This package contains two Cython files: cgbinder.pxd
describing the C++ API of the libgbinder library, and gbinder.pyx describing
classes that will be visible from Python user code. The .pyx imports .pxd
to learn about C functions available to be called.

The package can be built using Cython's cythonize() function to generate
a .c file from the .pyx one, and then compile it against the libgbinder.so
library, or if the .c is already provided, just compile it directly without
requiring Cython.

%prep
%autosetup -n %{upstream_name}-%{version}

%build
%python_build

%install
%python_install
%python_expand %fdupes %{buildroot}%{$python_sitearch}

%files %{python_files}
%license LICENSE
%doc README.md
%{python_sitearch}/gbinder.*
%{python_sitearch}/gbinder_python-%{version}*-info

%changelog
* Mon Jan 12 2026 James Ed Randson <jimedrand@disroot.org> - 1.3.0-2
- Redirect source to waydroid/gbinder-python upstream
- Update to version 1.3.0
- Fix spec file build requirements and macros

* Thu Jun 19 2025 James Ed Randson <jimedrand@disroot.org> - 1.3.0-1
- Initial package for %{pythonlib}