# Define custom macros
%define is_fedora %(test -e /etc/fedora-release && echo 1 || echo 0)

Name:               GlideinWMSAMIPilot
Version:            0.0.1
Release:            1%{?dist}

Summary:            The glideinWMS service that contextualizes an Amazon EC2 AMI 
Group:              System Environment/Daemons
License:            Fermitools Software Legal Information (Modified BSD License)
URL:                http://www.uscms.org/SoftwareComputing/Grid/WMS/glideinWMS/doc.v2/manual/
BuildRoot:          %{_builddir}
BuildArchitectures: noarch

#Requires:       
#BuildRequires:  

Source0:        rc.local
Source1:        get-credentials.sh
Source2:        update-modules.sh
Source3:        update-tools.sh

%description

%prep
%setup -q

%build
#make %{?_smp_mflags}

%install
rm -rf $RPM_BUILD_ROOT

# Install the init.d
install -d  $RPM_BUILD_ROOT/etc/rc.d
install -m 0755 %{SOURCE0} $RPM_BUILD_ROOT/etc/rc.d/rc.local

# install the executables
install -d $RPM_BUILD_ROOT%{_sbindir}
install -m 0500 %{SOURCE1} $RPM_BUILD_ROOT%{_sbindir}/get-credentials.sh
install -m 0500 %{SOURCE2} $RPM_BUILD_ROOT%{_sbindir}/update-modules.sh
install -m 0500 %{SOURCE3} $RPM_BUILD_ROOT%{_sbindir}/update-tools.sh

%post
# $1 = 1 - Installation
# $1 = 2 - Upgrade
# Source: http://www.ibm.com/developerworks/library/l-rpm2/

%preun
# $1 = 0 - Action is uninstall
# $1 = 1 - Action is upgrade

if [ "$1" = "0" ] ; then
    rm -rf /etc/rc.d/rc.local
    rm -rf %{_sbindir}/get-credentials.sh
    rm -rf %{_sbindir}/update-modules.sh
    rm -rf %{_sbindir}/update-tools.sh
fi

%clean
rm -rf $RPM_BUILD_ROOT

%files
%defattr(-,root,root,-)
%attr(755,root,root) /etc/rc.d/rc.local
%attr(755,root,root) %{_sbindir}/get-credentials.sh
%attr(755,root,root) %{_sbindir}/update-modules.sh
%attr(755,root,root) %{_sbindir}/update-tools.sh

%changelog
* Mon Nov 17 2010 Anthony Tiradani  0.0.1-1
- Initial Version

