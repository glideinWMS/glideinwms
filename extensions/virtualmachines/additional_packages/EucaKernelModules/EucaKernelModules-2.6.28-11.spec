Name:               euca-kernel-modules
Version:            2.6.28
Release:            11

Summary:            Eucalyptus Kernel Modules for kernel 2.6.28-11-generic (NERSC Magellan)
Group:              System Environment/Kernel
License:            GPLv2
URL:                http://www.opensciencegrid.org
Packager:           Anthony Tiradani <tiradani@fnal.gov>.

BuildRoot:          %{_tmppath}/%{name}-%{version}-%{release}-root-%(%{__id_u} -n)

BuildArch:          x86_64

Source0:            %{name}-%{version}-%{release}-generic.tar.gz

%description
This RPM was created simply because appliance-creator won't setup networking
correctly, so the post section of the kickstart cannot contain any wget or
curl commands.  The host names in the urls cannot be resolved.  You *could*
put in an IP address, however that only works if the web server doesn't use
vhosts or other tricks to have multiple websites hosted on one IP address.

The other problem is that the kernel installed on the NERSC Eucalytpus
instance is much newer than what is available in any repo that we have access
to.  So we cannot install that kernel and get the kernel modules for free.

The tarball in this rpm contains all the kernel modules that were installed on
a working VM on NERSC's Eucalyptus (Magellan) installation.  The only thing
that this RPM does is to untar the contents into /lib/modules

%prep
mkdir -p ${RPM_BUILD_ROOT}
tar -zxf %{SOURCE0} -C ${RPM_BUILD_ROOT}

%install

%clean
rm -rf ${RPM_BUILD_ROOT}

%files
%defattr(-,root,root,-)
%attr(755,root,root) /lib/modules/2.6.28-11-generic/
%attr(755,root,root) /lib/modules/2.6.27.21-0.1-xen/

%changelog
* Thu Mar 18 2010 <tiradani@fnal.gov> 2.6.28-11
- initial version
    o downloaded tarball with all the NERSC Eucalyptus kernel modules for the
      established generic centos kernel
    o all this rpm does is untar the tarball in /
    o the reason for this rpm is that appliance-creator won't setup networking
      correctly, so the post section of the kickstart cannot contain any wget
      or curl commands.
