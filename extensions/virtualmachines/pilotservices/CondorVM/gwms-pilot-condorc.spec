# Define custom macros
%define is_fedora %(test -e /etc/fedora-release && echo 1 || echo 0)

Name:               gwms-pilot-condorc
Version:            0.0.1
Release:            1

Summary:            The glideinWMS service that contextualizes an VM run by the Condor VM Universe
Group:              System Environment/Daemons
License:            Fermitools Software Legal Information (Modified BSD License)
URL:                http://www.uscms.org/SoftwareComputing/Grid/WMS/glideinWMS/doc.v2/manual/
BuildRoot:          %{_builddir}
BuildArchitectures: noarch

#Requires:
#BuildRequires:

Source0:        GlideinPilot
Source1:        PilotLauncher

Requires(post): /sbin/service
Requires(post): /usr/sbin/useradd
Requires(post): /sbin/chkconfig
Requires(post): /usr/sbin/groupadd
Requires(post): /usr/sbin/useradd

%description
Glidein Pilot Service

Sets up a service definition in init.d (GlideinPilot) that executes
PilotLauncher.py.  This script contextualizes a VM launched by Condor (VM
Universe) to become a glideinWMS worker node.  It is responsible for
bootstrapping the pilot Condor StartD and shutting down the VM once the pilot
exits.

%prep
#%setup -q

%build
#make %{?_smp_mflags}

%pre
# Make user glidein_pilot
/sbin/groupadd -g 91234 glidein_pilot
/sbin/useradd -M -g 91234 -u 91234 -d /mnt/glidein_pilot -s /bin/bash glidein_pilot

%install
rm -rf $RPM_BUILD_ROOT

# Install the init.d
install -d  $RPM_BUILD_ROOT/%{_initrddir}
install -m 0755 %{SOURCE0} $RPM_BUILD_ROOT/%{_initrddir}/GlideinPilot

# install the executables
install -d $RPM_BUILD_ROOT%{_sbindir}
install -m 0500 %{SOURCE1} $RPM_BUILD_ROOT%{_sbindir}/PilotLauncher

%post
# $1 = 1 - Installation
# $1 = 2 - Upgrade
# Source: http://www.ibm.com/developerworks/library/l-rpm2/

/sbin/chkconfig --add GlideinPilot
/sbin/chkconfig GlideinPilot on

sed -i "s/SERVICE_VERSION = 0/SERVICE_VERSION = %{version}/" %{_sbindir}/PilotLauncher
sed -i "s/SERVICE_RELEASE = 0/SERVICE_RELEASE = %{release}/" %{_sbindir}/PilotLauncher

%preun
# $1 = 0 - Action is uninstall
# $1 = 1 - Action is upgrade

if [ "$1" = "0" ] ; then
    /sbin/chkconfig --del GlideinPilot
    /sbin/userdel -f glidein_pilot
    rm -rf %{_sbindir}/PilotLauncher
    rm -rf %{_initrddir}/GlideinPilot
fi

%clean
rm -rf $RPM_BUILD_ROOT

%files
%defattr(-,root,root,-)
%attr(755,root,root) %{_sbindir}/PilotLauncher
%attr(755,root,root) %{_initrddir}/GlideinPilot


%changelog
* Wed Jun 1 2011 Anthony Tiradani  0.0.1-1
- Initial Version

