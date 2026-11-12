Name:           linux-inventory-agent
Version:        1.0.0
Release:        1%{?dist}
Summary:        Auditable RPM and repository inventory collector
License:        MIT
BuildArch:      noarch
Requires:       python3
Source0:        linux_inventory_agent.py

%description
Collects operating-system, RPM package, and enabled-repository information and
writes a versioned JSON inventory record for controlled software operations.

%prep

%build

%install
install -D -m 0755 %{SOURCE0} %{buildroot}%{_bindir}/linux-inventory-agent
install -d -m 0755 %{buildroot}%{_localstatedir}/lib/linux-inventory-agent

%files
%{_bindir}/linux-inventory-agent
%dir %{_localstatedir}/lib/linux-inventory-agent

%changelog
* Thu Nov 12 2026 Komal Wavhal <wavhalkomal7@gmail.com> - 1.0.0-1
- Initial controlled inventory-agent package

