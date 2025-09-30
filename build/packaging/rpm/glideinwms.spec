# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

# Disable shebang mangling (see GHI#436)
%undefine __brp_mangle_shebangs

# How to build tar file

# git clone http://cdcvs.fnal.gov/projects/glideinwms
# cd glideinwms
# git archive v3_0_rc3 --prefix='glideinwms/' | gzip > ../glideinwms.tar.gz
# change v3_0_rc3 to the proper tag in the above line

# Release Candidates NVR format
#%define release 0.1.rc1
# Official Release NVR format
#%define release 2

# ------------------------------------------------------------------------------
# For Release Candidate builds, check with Software team on release string
# ------------------------------------------------------------------------------
%global version __GWMS_RPM_VERSION__
%global release __GWMS_RPM_RELEASE__

%global frontend_xml frontend.xml
%global factory_xml glideinWMS.xml
%global web_dir %{_localstatedir}/lib/gwms-frontend/web-area
%global web_base %{_localstatedir}/lib/gwms-frontend/web-base
%global frontend_dir %{_localstatedir}/lib/gwms-frontend/vofrontend
%global frontend_token_dir %{_localstatedir}/lib/gwms-frontend/tokens.d
%global frontend_passwd_dir %{_localstatedir}/lib/gwms-frontend/passwords.d
%global factory_web_dir %{_localstatedir}/lib/gwms-factory/web-area
%global factory_web_base %{_localstatedir}/lib/gwms-factory/web-base
%global factory_dir %{_localstatedir}/lib/gwms-factory/work-dir
%global factory_condor_dir %{_localstatedir}/lib/gwms-factory/condor
%global logserver_dir %{_localstatedir}/lib/gwms-logserver
%global logserver_web_dir %{_localstatedir}/lib/gwms-logserver/web-area
%global systemddir %{_prefix}/lib/systemd/system
# Minimum HTCondor and Python required versions
%global htcss_min_version 8.9.5
%global python_min_version 3.6

Name:           glideinwms
Version:        %{version}
Release:        %{release}%{?dist}
Summary:        The glidein Workload Management System (glideinWMS)
# Group: has been deprecated, removing it from all specifications, wes "System Environment/Daemons"
License:        Apache-2.0
URL:            http://glideinwms.fnal.gov
BuildRoot:      %{_tmppath}/%{name}-%{version}-%{release}-root-%(%{__id_u} -n)
BuildArch:      noarch


Source:         glideinwms.tar.gz
Source1:        creation/templates/frontend_startup
Source2:        %{frontend_xml}
Source3:        creation/templates/factory_startup
Source4:        %{factory_xml}
Source7:        chksum.sh
Source11:       creation/templates/frontend_startup_sl7
Source12:       creation/templates/factory_startup_sl7

BuildRequires:  python3
BuildRequires:  python3-devel

%description
This is a package for the glidein workload management system.
GlideinWMS provides a simple way to access the Grid, Cloud and HPC
resources through a dynamic HTCondor pool of grid-submitted resources.


%package vofrontend
Summary: The VOFrontend for GlideinWMS submission host
Provides:       GlideinWMSFrontend = %{version}-%{release}
Obsoletes:      GlideinWMSFrontend < 2.5.1-11
Requires: glideinwms-vofrontend-standalone = %{version}-%{release}
Requires: glideinwms-userschedd = %{version}-%{release}
Requires: glideinwms-usercollector = %{version}-%{release}
Obsoletes:      glideinwms-vofrontend-condor < 2.6.2-2
%description vofrontend
The purpose of the glideinWMS is to provide a simple way to
access the Grid, Cloud and HPC resources. GlideinWMS is a Glidein Based
WMS (Workload Management System) that works on top of Condor.
For those familiar with the Condor system, it is used for
scheduling and job control. This package is for a one-node
vofrontend install (userschedd, usercollector, vofrontend).


%package vofrontend-standalone
Summary: The VOFrontend for GlideinWMS submission host
Requires: glideinwms-vofrontend-core = %{version}-%{release}
Requires: glideinwms-vofrontend-httpd = %{version}-%{release}
%description vofrontend-standalone
The purpose of the glideinWMS is to provide a simple way
to access the Grid, Cloud and HPC resources. GlideinWMS is a Glidein
Based WMS (Workload Management System) that works on top of
Condor. For those familiar with the Condor system, it is used
for scheduling and job control.
This package is for a standalone vofrontend install


%package vofrontend-core
Summary: The intelligence logic for GlideinWMS Frontend.
Requires: condor >= %{htcss_min_version}
Requires: python3 >= %{python_min_version}
Requires: javascriptrrd >= 1.1.0
Requires: osg-wn-client
Requires: vo-client
Requires: voms-clients-cpp
Requires: glideinwms-minimal-condor = %{version}-%{release}
Requires: glideinwms-libs = %{version}-%{release}
Requires: glideinwms-glidecondor-tools = %{version}-%{release}
Requires: glideinwms-common-tools = %{version}-%{release}
Requires: glideinwms-vofrontend-libs
Requires: glideinwms-vofrontend-glidein
# Added rrdtool to make sure that at least the client tools are there
Requires: rrdtool
# Recommends: python3-rrdtool - this would be ideal but is supported only in Fedora>=24 and not RHEL
# Remove the line below for the OSG 3.5 build (no python3-rrdtool there)
Requires: python3-rrdtool
%if 0%{?rhel} >= 8
Requires: initscripts
Requires: python3-m2crypto
%else
Requires: python36-m2crypto
%endif
Requires(post): /sbin/service
Requires(post): /usr/sbin/useradd
Requires(post): /usr/sbin/usermod
Requires(post): /sbin/chkconfig
%description vofrontend-core
This subpackage includes all the scripts needed to run a
frontend. Created to separate out the httpd server.


%package vofrontend-libs
Summary: The Python creation library for GlideinWMS Frontend.
Requires: python3 >= %{python_min_version}
Requires: javascriptrrd >= 1.1.0
Requires: glideinwms-libs = %{version}-%{release}
Requires: glideinwms-common-tools = %{version}-%{release}
%description vofrontend-libs
This subpackage includes libraries for Frontend-like programs.


%package vofrontend-glidein
Summary: The Glidein components for GlideinWMS Frontend.
Requires: python3 >= %{python_min_version}
Requires: glideinwms-libs = %{version}-%{release}
Requires: glideinwms-common-tools = %{version}-%{release}
%description vofrontend-glidein
This subpackage includes the Glidein components for the Frontend.


%package vofrontend-httpd
Summary: The Apache http configuration for GlideinWMS Frontend.
Requires: httpd
Requires: mod_ssl
Requires: glideinwms-httpd = %{version}-%{release}
%description vofrontend-httpd
This subpackage includes the minimal configuration to start Apache to
serve the Frontend files to the pilot and the monitoring pages.


%package usercollector
Summary: The VOFrontend GlideinWMS collector host
Requires: condor >= %{htcss_min_version}
Requires: ganglia
Requires: glideinwms-minimal-condor = %{version}-%{release}
Requires: glideinwms-glidecondor-tools = %{version}-%{release}
%description usercollector
The user collector matches user jobs to glideins in the WMS pool.
It can be installed independently.


%package userschedd
Summary: The VOFrontend GlideinWMS submission host
Requires: condor >= %{htcss_min_version}
Requires: glideinwms-minimal-condor = %{version}-%{release}
Requires: glideinwms-common-tools = %{version}-%{release}
Requires: glideinwms-glidecondor-tools = %{version}-%{release}
%description userschedd
This is a package for a glideinwms submit host.


%package httpd
Summary: Common Apache http configuration for GlideinWMS.
Requires: httpd
%description httpd
This subpackage includes the Apache configuration cecommended to
harden the GlideinWMS Web servers for safer production use.

%package libs
Summary: The GlideinWMS common libraries.
Requires: python3 >= %{python_min_version}
Requires: python3-condor
# was condor-python for python2
%if 0%{?rhel} >= 8
Requires: python3-pyyaml
Requires: python3-jwt
Requires: python3-cryptography
Requires: python3-m2crypto
#Requires: python3-structlog
%else
Requires: PyYAML
Requires: python36-jwt
Requires: python36-cryptography
Requires: python36-m2crypto
Requires: python36-structlog
%endif
Requires: python3-rrdtool
%description libs
This package provides common libraries used by glideinwms.


%package glidecondor-tools
Summary: Condor tools useful with the GlideinWMS.
Requires: glideinwms-libs = %{version}-%{release}
%description glidecondor-tools
This package provides common libraries used by glideinwms.


%package minimal-condor
Summary: The VOFrontend minimal condor config
Provides: gwms-condor-config
Requires: glideinwms-condor-common-config = %{version}-%{release}
Requires: condor >= %{htcss_min_version}
%description minimal-condor
This is an alternate condor config for just the minimal amount
needed for VOFrontend.


%package condor-common-config
Summary: Shared condor config files
Requires: condor >= %{htcss_min_version}
%description condor-common-config
This contains condor config files shared between alternate
condor config setups (minimal-condor and factory-condor).


%package common-tools
Summary: Shared tools
%description common-tools
This contains tools common to both the glideinwms factory and vofrontend
standalone packages.


%package factory
Summary: The Factory for GlideinWMS
Provides:       GlideinWMSFactory = %{version}-%{release}
Requires: glideinwms-factory-httpd = %{version}-%{release}
Requires: glideinwms-factory-core = %{version}-%{release}
%description factory
The purpose of the glideinWMS is to provide a simple way
to access the Grid, Cloud and HPC resources. GlideinWMS is a Glidein
Based WMS (Workload Management System) that works on top of
HTCondor. For those familiar with the Condor system, it is used
for scheduling and job control.


%package factory-core
Summary: The scripts for the GlideinWMS Factory
Requires: glideinwms-factory-condor = %{version}-%{release}
Requires: glideinwms-libs = %{version}-%{release}
Requires: glideinwms-glidecondor-tools = %{version}-%{release}
Requires: glideinwms-common-tools = %{version}-%{release}
Requires: condor >= %{htcss_min_version}
Requires: fetch-crl
Requires: python3 >= %{python_min_version}
# This is in py3 std library - Requires: python-argparse
# Is this the same? Requires: python36-configargparse
Requires: javascriptrrd >= 1.1.0
%if 0%{?rhel} >= 8
Requires: initscripts
Requires: python3-m2crypto
Requires: python3-requests
Requires: python3-jwt
%else
Requires: python36-m2crypto
Requires: python36-requests
Requires: python36-jwt
%endif
Requires: python3-rrdtool
Requires(post): /sbin/service
Requires(post): /usr/sbin/useradd
Requires(post): /usr/sbin/usermod
Requires(post): /sbin/chkconfig
%description factory-core
This subpackage includes all the scripts needed to run a
Factory. Created to separate out the httpd server.


%package factory-httpd
Summary: The Apache httpd configuration for the GlideinWMS Factory
Requires: httpd
Requires: mod_ssl
Requires: glideinwms-httpd = %{version}-%{release}
%description factory-httpd
This subpackage includes the minimal configuration to start Apache to
serve the Factory files to the pilot and the monitoring pages.


%package factory-condor
Summary: The GlideinWMS Factory condor config
Provides:       gwms-factory-config
Requires: glideinwms-condor-common-config = %{version}-%{release}
Requires: condor >= %{htcss_min_version}
%description factory-condor
This is a package including condor_config for a full one-node
install of wmscollector + wms factory


%package logserver
Summary: The Glidein Log Server and its Apache httpd configuration.
Requires: httpd
Requires: mod_ssl
Requires: php
Requires: php-fpm
Requires: composer
Requires: glideinwms-httpd = %{version}-%{release}
%description logserver
This subpackage includes an example of the files and Apache configuration
to implement a simple server to receive Glidein logs.


%prep
%setup -q -n glideinwms
# Apply the patches here if any
#%patch -P 0 -p1


%build
cp %{SOURCE7} .
chmod 700 chksum.sh
./chksum.sh v%{version}-%{release}.osg etc/checksum.frontend "CVS doc .git .gitattributes poolwatcher factory/check* factory/glideFactory* factory/test* factory/manage* factory/stop* factory/tools creation/create_glidein creation/reconfig_glidein creation/info_glidein creation/lib/cgW* creation/web_base/factory*html creation/web_base/collector_setup.sh creation/web_base/condor_platform_select.sh creation/web_base/condor_startup.sh creation/web_base/create_mapfile.sh creation/web_base/singularity_setup.sh creation/web_base/singularity_wrapper.sh creation/web_base/singularity_lib.sh creation/web_base/gconfig.py creation/web_base/glidein_startup.sh creation/web_base/job_submit.sh creation/web_base/local_start.sh creation/web_base/setup_x509.sh creation/web_base/update_proxy.py creation/web_base/validate_node.sh chksum.sh etc/checksum* unittests build"
./chksum.sh v%{version}-%{release}.osg etc/checksum.factory "CVS doc .git .gitattributes poolwatcher frontend/* creation/reconfig_glidein creation/clone_glidein creation/lib/cgW* creation/web_base/factory*html creation/web_base/collector_setup.sh creation/web_base/condor_platform_select.sh creation/web_base/condor_startup.sh creation/web_base/create_mapfile.sh creation/web_base/singularity_setup.sh creation/web_base/singularity_wrapper.sh creation/web_base/singularity_lib.sh creation/web_base/gconfig.py creation/web_base/glidein_startup.sh creation/web_base/job_submit.sh creation/web_base/local_start.sh creation/web_base/setup_x509.sh creation/web_base/update_proxy.py creation/web_base/validate_node.sh chksum.sh etc/checksum* unittests build creation/lib/matchPolicy*"

%install
rm -rf $RPM_BUILD_ROOT

# Set the Python version
%global __python %{__python3}

# TODO: Check if some of the following are needed
# seems never used
# %define py_ver %(python -c "import sys; v=sys.version_info[:2]; print '%d.%d'%v")

# From http://fedoraproject.org/wiki/Packaging:Python
# Assuming python3_sitelib and python3_sitearch are defined, not supporting RHEL < 7 or old FC
# Define python_sitelib

#%if ! (0%{?fedora} > 12 || 0%{?rhel} > 5)
#%{!?python_sitelib: %global python_sitelib %(%{__python} -c "from distutils.sysconfig import get_python_lib; print(get_python_lib())")}
#%{!?python_sitearch: %global python_sitearch %(%{__python} -c "from distutils.sysconfig import get_python_lib; print(get_python_lib(1))")}
#%endif

#Change src_dir in reconfig_Frontend
sed -i "s/WEB_BASE_DIR *=.*/WEB_BASE_DIR = \"\/var\/lib\/gwms-frontend\/web-base\"/" creation/reconfig_frontend
sed -i "s/STARTUP_DIR *=.*/STARTUP_DIR = \"\/var\/lib\/gwms-frontend\/web-base\"/" creation/reconfig_frontend
sed -i "s/WEB_BASE_DIR *=.*/WEB_BASE_DIR = \"\/var\/lib\/gwms-factory\/web-base\"/" creation/lib/cgWConsts.py
sed -i "s/STARTUP_DIR *=.*/STARTUP_DIR = \"\/var\/lib\/gwms-factory\/web-base\"/" creation/reconfig_glidein
sed -i "s/STARTUP_DIR *=.*/STARTUP_DIR = \"\/var\/lib\/gwms-factory\/web-base\"/" creation/clone_glidein

#Create the RPM startup files (init.d) from the templates
creation/create_rpm_startup . frontend_initd_startup_template factory_initd_startup_template %{SOURCE1} %{SOURCE3}
creation/create_rpm_startup . frontend_initd_startup_template_sl7 factory_initd_startup_template_sl7 %{SOURCE11} %{SOURCE12}

# install the executables
install -d $RPM_BUILD_ROOT%{_sbindir}
install -d $RPM_BUILD_ROOT%{_libexecdir}
# Find all the executables in the frontend directory
install -m 0500 frontend/checkFrontend.py $RPM_BUILD_ROOT%{_sbindir}/checkFrontend
install -m 0500 frontend/glideinFrontendElement.py $RPM_BUILD_ROOT%{_sbindir}/glideinFrontendElement.py
install -m 0500 frontend/manageFrontendDowntimes.py $RPM_BUILD_ROOT%{_sbindir}/
install -m 0500 frontend/stopFrontend.py $RPM_BUILD_ROOT%{_sbindir}/stopFrontend
install -m 0500 frontend/glideinFrontend.py $RPM_BUILD_ROOT%{_sbindir}/glideinFrontend
install -m 0500 creation/reconfig_frontend $RPM_BUILD_ROOT%{_sbindir}/reconfig_frontend
install -m 0500 frontend/gwms_renew_proxies.py $RPM_BUILD_ROOT%{_libexecdir}/gwms_renew_proxies

#install the factory executables
install -m 0500 factory/checkFactory.py $RPM_BUILD_ROOT%{_sbindir}/
install -m 0500 factory/glideFactoryEntry.py $RPM_BUILD_ROOT%{_sbindir}/
install -m 0500 factory/glideFactoryEntryGroup.py $RPM_BUILD_ROOT%{_sbindir}/
install -m 0500 factory/manageFactoryDowntimes.py $RPM_BUILD_ROOT%{_sbindir}/
install -m 0500 factory/stopFactory.py $RPM_BUILD_ROOT%{_sbindir}/
install -m 0500 creation/clone_glidein $RPM_BUILD_ROOT%{_sbindir}/
install -m 0500 creation/info_glidein $RPM_BUILD_ROOT%{_sbindir}/
install -m 0500 factory/glideFactory.py $RPM_BUILD_ROOT%{_sbindir}/
install -m 0500 creation/reconfig_glidein $RPM_BUILD_ROOT%{_sbindir}/

# install the library parts
install -d $RPM_BUILD_ROOT%{python3_sitelib}
cp -r ../glideinwms $RPM_BUILD_ROOT%{python3_sitelib}

# Some of the files are not needed by RPM
rm -Rf $RPM_BUILD_ROOT%{python3_sitelib}/glideinwms/bigfiles
rm -Rf $RPM_BUILD_ROOT%{python3_sitelib}/glideinwms/install
rm -Rf $RPM_BUILD_ROOT%{python3_sitelib}/glideinwms/doc
rm -Rf $RPM_BUILD_ROOT%{python3_sitelib}/glideinwms/etc
rm -Rf $RPM_BUILD_ROOT%{python3_sitelib}/glideinwms/build
rm -Rf $RPM_BUILD_ROOT%{python3_sitelib}/glideinwms/.codespell
rm -Rf $RPM_BUILD_ROOT%{python3_sitelib}/glideinwms/config
rm -f $RPM_BUILD_ROOT%{python3_sitelib}/glideinwms/creation/create_rpm_startup
rm -f $RPM_BUILD_ROOT%{python3_sitelib}/glideinwms/.editorconfig
rm -f $RPM_BUILD_ROOT%{python3_sitelib}/glideinwms/.gitattributes
rm -Rf $RPM_BUILD_ROOT%{python3_sitelib}/glideinwms/.github
rm -f $RPM_BUILD_ROOT%{python3_sitelib}/glideinwms/.gitignore
rm -f $RPM_BUILD_ROOT%{python3_sitelib}/glideinwms/.gitmodules
rm -f $RPM_BUILD_ROOT%{python3_sitelib}/glideinwms/.mailmap
rm -f $RPM_BUILD_ROOT%{python3_sitelib}/glideinwms/.pep8speaks.yml
rm -f $RPM_BUILD_ROOT%{python3_sitelib}/glideinwms/.pre-commit-config.yaml
rm -f $RPM_BUILD_ROOT%{python3_sitelib}/glideinwms/.prettierignore
rm -f $RPM_BUILD_ROOT%{python3_sitelib}/glideinwms/.travis.yml
rm -f $RPM_BUILD_ROOT%{python3_sitelib}/glideinwms/pyproject.toml
rm -Rf $RPM_BUILD_ROOT%{python3_sitelib}/glideinwms/test
rm -Rf $RPM_BUILD_ROOT%{python3_sitelib}/glideinwms/unittests
rm -f $RPM_BUILD_ROOT%{python3_sitelib}/glideinwms/chksum.sh
rm -f $RPM_BUILD_ROOT%{python3_sitelib}/glideinwms/requirements.txt
rm -Rf $RPM_BUILD_ROOT%{python3_sitelib}/glideinwms/.reuse
rm -f $RPM_BUILD_ROOT%{python3_sitelib}/glideinwms/tox.ini
rm -f $RPM_BUILD_ROOT%{python3_sitelib}/glideinwms/LICENSE
rm -Rf $RPM_BUILD_ROOT%{python3_sitelib}/glideinwms/LICENSES
rm -f $RPM_BUILD_ROOT%{python3_sitelib}/glideinwms/ACKNOWLEDGMENTS.md
rm -f $RPM_BUILD_ROOT%{python3_sitelib}/glideinwms/DEVELOPMENT.md
rm -f $RPM_BUILD_ROOT%{python3_sitelib}/glideinwms/README.md
rm -f $RPM_BUILD_ROOT%{python3_sitelib}/glideinwms/REUSE.toml
rm -f $RPM_BUILD_ROOT%{python3_sitelib}/glideinwms/CHANGELOG.md

# Following files are Put in other places. Remove them from python3_sitelib
rm -Rf $RPM_BUILD_ROOT%{python3_sitelib}/glideinwms/creation/web_base
rm -f $RPM_BUILD_ROOT%{python3_sitelib}/glideinwms/creation/add_entry
rm -f $RPM_BUILD_ROOT%{python3_sitelib}/glideinwms/creation/clone_glidein
rm -f $RPM_BUILD_ROOT%{python3_sitelib}/glideinwms/creation/create_condor_tarball
rm -f $RPM_BUILD_ROOT%{python3_sitelib}/glideinwms/creation/create_cvmfsexec_distros.sh
rm -f $RPM_BUILD_ROOT%{python3_sitelib}/glideinwms/creation/create_frontend
rm -f $RPM_BUILD_ROOT%{python3_sitelib}/glideinwms/creation/create_glidein
rm -f $RPM_BUILD_ROOT%{python3_sitelib}/glideinwms/creation/info_glidein
rm -rf $RPM_BUILD_ROOT%{python3_sitelib}/glideinwms/plugins
rm -rf $RPM_BUILD_ROOT%{python3_sitelib}/glideinwms/logserver

# For sl7 sighup to work, we need reconfig_frontend and reconfig_glidein
# under this directory
# Following 4 sl7 templates are only needed by create_rpm_startup above,
# after that, we dont package these, so deleting them here
rm -f $RPM_BUILD_ROOT%{python3_sitelib}/glideinwms/creation/templates/factory_initd_startup_template_sl7
rm -f $RPM_BUILD_ROOT%{python3_sitelib}/glideinwms/creation/templates/frontend_initd_startup_template_sl7
rm -f $RPM_BUILD_ROOT%{python3_sitelib}/glideinwms/creation/templates/gwms-renew-proxies.cron
rm -f $RPM_BUILD_ROOT%{python3_sitelib}/glideinwms/creation/templates/gwms-renew-proxies.init
rm -f $RPM_BUILD_ROOT%{python3_sitelib}/glideinwms/creation/templates/gwms-renew-proxies.service
rm -f $RPM_BUILD_ROOT%{python3_sitelib}/glideinwms/creation/templates/gwms-renew-proxies.timer
rm -f $RPM_BUILD_ROOT%{python3_sitelib}/glideinwms/creation/templates/proxies.ini

%if 0%{?rhel} >= 7
install -d $RPM_BUILD_ROOT/%{systemddir}
install -m 0644 install/config/gwms-frontend.service $RPM_BUILD_ROOT/%{systemddir}/
install -m 0644 install/config/gwms-factory.service $RPM_BUILD_ROOT/%{systemddir}/
install -m 0644 creation/templates/gwms-renew-proxies.service $RPM_BUILD_ROOT/%{systemddir}/
install -m 0644 creation/templates/gwms-renew-proxies.timer $RPM_BUILD_ROOT/%{systemddir}/
install -d $RPM_BUILD_ROOT/%{_sbindir}
install -m 0755 %{SOURCE11} $RPM_BUILD_ROOT/%{_sbindir}/gwms-frontend
install -m 0755 %{SOURCE12} $RPM_BUILD_ROOT/%{_sbindir}/gwms-factory
%else
# Install the init.d
install -d $RPM_BUILD_ROOT%{_initrddir}
install -d $RPM_BUILD_ROOT%{_sysconfdir}/cron.d
install -m 0755 %{SOURCE1} $RPM_BUILD_ROOT%{_initrddir}/gwms-frontend
install -m 0755 %{SOURCE3} $RPM_BUILD_ROOT%{_initrddir}/gwms-factory
install -m 0755 creation/templates/gwms-renew-proxies.init $RPM_BUILD_ROOT%{_initrddir}/gwms-renew-proxies
install -m 0644 creation/templates/gwms-renew-proxies.cron $RPM_BUILD_ROOT%{_sysconfdir}/cron.d/gwms-renew-proxies
%endif

# Install the web directory
install -d $RPM_BUILD_ROOT%{frontend_dir}
install -d $RPM_BUILD_ROOT%{frontend_token_dir}
install -d $RPM_BUILD_ROOT%{frontend_passwd_dir}
install -d $RPM_BUILD_ROOT%{web_base}
install -d $RPM_BUILD_ROOT%{web_dir}
install -d $RPM_BUILD_ROOT%{web_dir}/monitor/
install -d $RPM_BUILD_ROOT%{web_dir}/stage/
install -d $RPM_BUILD_ROOT%{web_dir}/stage/group_main
install -d $RPM_BUILD_ROOT%{factory_dir}
install -d $RPM_BUILD_ROOT%{factory_web_base}
install -d $RPM_BUILD_ROOT%{factory_web_dir}
install -d $RPM_BUILD_ROOT%{factory_web_dir}/monitor/
install -d $RPM_BUILD_ROOT%{factory_web_dir}/stage/
install -d $RPM_BUILD_ROOT%{factory_dir}/lock
install -d $RPM_BUILD_ROOT%{factory_condor_dir}
install -d $RPM_BUILD_ROOT%{web_dir}/monitor/lock
install -d $RPM_BUILD_ROOT%{web_dir}/monitor/jslibs
install -d $RPM_BUILD_ROOT%{web_dir}/monitor/total
install -d $RPM_BUILD_ROOT%{web_dir}/monitor/group_main
install -d $RPM_BUILD_ROOT%{web_dir}/monitor/group_main/lock
install -d $RPM_BUILD_ROOT%{web_dir}/monitor/group_main/total
install -d $RPM_BUILD_ROOT%{factory_web_dir}/monitor/lock
install -d $RPM_BUILD_ROOT%{factory_web_dir}/monitor/jslibs
install -d $RPM_BUILD_ROOT%{factory_web_dir}/monitor/total
install -d $RPM_BUILD_ROOT%{factory_web_dir}/monitor/group_main
install -d $RPM_BUILD_ROOT%{factory_web_dir}/monitor/group_main/lock
install -d $RPM_BUILD_ROOT%{factory_web_dir}/monitor/group_main/total
install -m 644 creation/web_base/nodes.blacklist $RPM_BUILD_ROOT%{web_dir}/stage/nodes.blacklist
install -m 644 creation/web_base/nodes.blacklist $RPM_BUILD_ROOT%{web_dir}/stage/group_main/nodes.blacklist

# Install the logs
install -d $RPM_BUILD_ROOT%{_localstatedir}/log/gwms-frontend/frontend
install -d $RPM_BUILD_ROOT%{_localstatedir}/log/gwms-frontend/group_main
install -d $RPM_BUILD_ROOT%{_localstatedir}/log/gwms-factory
install -d $RPM_BUILD_ROOT%{_localstatedir}/log/gwms-factory/server
install -d $RPM_BUILD_ROOT%{_localstatedir}/log/gwms-factory/server/factory
install -d $RPM_BUILD_ROOT%{_localstatedir}/log/gwms-factory/client

# Create some credential directories
install -d $RPM_BUILD_ROOT%{_localstatedir}/lib/gwms-factory/client-proxies
install -d $RPM_BUILD_ROOT%{_localstatedir}/lib/gwms-factory/server-credentials
touch $RPM_BUILD_ROOT%{_localstatedir}/lib/gwms-factory/server-credentials/jwt_secret.key

# Install frontend temp dir, for all the frontend.xml.<checksum>
install -d $RPM_BUILD_ROOT%{frontend_dir}/lock
install -d $RPM_BUILD_ROOT%{frontend_dir}/group_main
install -d $RPM_BUILD_ROOT%{frontend_dir}/group_main/lock

install -m 644 creation/web_base/frontendRRDBrowse.html $RPM_BUILD_ROOT%{web_dir}/monitor/frontendRRDBrowse.html
install -m 644 creation/web_base/frontendRRDGroupMatrix.html $RPM_BUILD_ROOT%{web_dir}/monitor/frontendRRDGroupMatrix.html
install -m 644 creation/web_base/frontendStatus.html $RPM_BUILD_ROOT%{web_dir}/monitor/frontendStatus.html
install -m 644 creation/web_base/frontend/index.html $RPM_BUILD_ROOT%{web_dir}/monitor/
install -m 644 creation/web_base/factory/index.html $RPM_BUILD_ROOT%{factory_web_dir}/monitor/
install -m 644 creation/web_base/factoryFrontendMonitorLink.html $RPM_BUILD_ROOT%{factory_web_dir}/monitor/
cp -arp creation/web_base/factory/images $RPM_BUILD_ROOT%{factory_web_dir}/monitor/
cp -arp creation/web_base/frontend/images $RPM_BUILD_ROOT%{web_dir}/monitor/

# Install the frontend config dir
install -d $RPM_BUILD_ROOT/%{_sysconfdir}/sysconfig
install -d $RPM_BUILD_ROOT/%{_sysconfdir}/gwms-frontend
install -d $RPM_BUILD_ROOT/%{_sysconfdir}/gwms-frontend/plugin.d
install -d $RPM_BUILD_ROOT/%{_sysconfdir}/gwms-frontend/hooks.reconfig.pre
install -d $RPM_BUILD_ROOT/%{_sysconfdir}/gwms-frontend/hooks.reconfig.post
install -m 0664 %{SOURCE2} $RPM_BUILD_ROOT/%{_sysconfdir}/gwms-frontend/frontend.xml
install -m 0664 creation/templates/proxies.ini $RPM_BUILD_ROOT/%{_sysconfdir}/gwms-frontend/proxies.ini
install -m 0644 install/config/gwms-frontend.sysconfig $RPM_BUILD_ROOT/%{_sysconfdir}/sysconfig/gwms-frontend
cp -arp plugins/* $RPM_BUILD_ROOT/%{_sysconfdir}/gwms-frontend/plugin.d

# Install the factory config dir
install -d $RPM_BUILD_ROOT/%{_sysconfdir}/gwms-factory
install -d $RPM_BUILD_ROOT/%{_sysconfdir}/gwms-factory/plugin.d
install -d $RPM_BUILD_ROOT/%{_sysconfdir}/gwms-factory/hooks.reconfig.pre
install -d $RPM_BUILD_ROOT/%{_sysconfdir}/gwms-factory/hooks.reconfig.post
install -m 0644 %{SOURCE4} $RPM_BUILD_ROOT/%{_sysconfdir}/gwms-factory/glideinWMS.xml
install -m 0644 install/config/gwms-factory.sysconfig $RPM_BUILD_ROOT/%{_sysconfdir}/sysconfig/gwms-factory
# remove the file from python_sitelib as it is put elsewhere; similar to clone_glidein and info_glidein files

# Install the web base
cp -r creation/web_base/* $RPM_BUILD_ROOT%{web_base}/
cp -r creation/web_base/* $RPM_BUILD_ROOT%{factory_web_base}/
rm -rf $RPM_BUILD_ROOT%{web_base}/CVS

# Install condor stuff
install -d $RPM_BUILD_ROOT%{_sysconfdir}/condor/config.d
install -d $RPM_BUILD_ROOT%{_sysconfdir}/condor/ganglia.d
install -d $RPM_BUILD_ROOT%{_sysconfdir}/condor/certs
install -d $RPM_BUILD_ROOT%{_sysconfdir}/condor/scripts
touch install/templates/90_gwms_dns.config
install -m 0644 install/templates/00_gwms_factory_general.config $RPM_BUILD_ROOT%{_sysconfdir}/condor/config.d/
install -m 0644 install/templates/00_gwms_general.config $RPM_BUILD_ROOT%{_sysconfdir}/condor/config.d/
install -m 0644 install/templates/01_gwms_factory_collectors.config $RPM_BUILD_ROOT%{_sysconfdir}/condor/config.d/
install -m 0644 install/templates/01_gwms_collectors.config $RPM_BUILD_ROOT%{_sysconfdir}/condor/config.d/
install -m 0644 install/templates/01_gwms_ganglia.config $RPM_BUILD_ROOT%{_sysconfdir}/condor/config.d/
install -m 0644 install/templates/02_gwms_factory_schedds.config $RPM_BUILD_ROOT%{_sysconfdir}/condor/config.d/
install -m 0644 install/templates/02_gwms_schedds.config $RPM_BUILD_ROOT%{_sysconfdir}/condor/config.d/
install -m 0644 install/templates/03_gwms_local.config $RPM_BUILD_ROOT%{_sysconfdir}/condor/config.d/
install -m 0644 install/templates/11_gwms_secondary_collectors.config $RPM_BUILD_ROOT%{_sysconfdir}/condor/config.d/
install -m 0644 install/templates/90_gwms_dns.config $RPM_BUILD_ROOT%{_sysconfdir}/condor/config.d/
install -m 0644 install/templates/01_gwms_metrics.config $RPM_BUILD_ROOT%{_sysconfdir}/condor/ganglia.d/
install -m 0644 install/templates/condor_mapfile $RPM_BUILD_ROOT%{_sysconfdir}/condor/certs/
install -m 0644 install/templates/gwms_q_format.cpf $RPM_BUILD_ROOT%{_sysconfdir}/condor/gwms_q_format.cpf

# Install condor schedd dirs
# This should be consistent with 02_gwms_factory_schedds.config and 02_gwms_schedds.config
for schedd in "schedd_glideins2" "schedd_glideins3" "schedd_glideins4" "schedd_glideins5" "schedd_jobs2"; do
    install -d $RPM_BUILD_ROOT/var/lib/condor/$schedd
    install -d $RPM_BUILD_ROOT/var/lib/condor/$schedd/execute
    install -d $RPM_BUILD_ROOT/var/lib/condor/$schedd/lock
    install -d $RPM_BUILD_ROOT/var/lib/condor/$schedd/procd_pipe
    install -d $RPM_BUILD_ROOT/var/lib/condor/$schedd/spool
    chmod 'g+w' $RPM_BUILD_ROOT/var/lib/condor/$schedd
done



# Install tools
install -d $RPM_BUILD_ROOT%{_bindir}
# Install the tools as the non-*.py filenames
for file in tools/[^_]*.py; do
    newname=`echo $file | sed -e 's/.*\/\(.*\)\.py/\1/'`
    cp $file $RPM_BUILD_ROOT%{_bindir}/$newname
done
for file in factory/tools/[^_]*; do
    if [ -f "$file" ]; then
        newname=`echo $file | sed -e 's/\(.*\)\.py/\1/'`
        newname=`echo $newname | sed -e 's/.*\/\(.*\)/\1/'`
        cp $file $RPM_BUILD_ROOT%{_bindir}/$newname
    fi
done
cp creation/create_condor_tarball $RPM_BUILD_ROOT%{_bindir}
cp creation/create_cvmfsexec_distros.sh $RPM_BUILD_ROOT%{_bindir}

# Install only few frontend tools
cp frontend/tools/enter_frontend_env $RPM_BUILD_ROOT%{_bindir}/enter_frontend_env
cp frontend/tools/fetch_glidein_log $RPM_BUILD_ROOT%{_bindir}/fetch_glidein_log
cp frontend/tools/glidein_off $RPM_BUILD_ROOT%{_bindir}/glidein_off
cp frontend/tools/remove_requested_glideins $RPM_BUILD_ROOT%{_bindir}/remove_requested_glideins
#cp install/templates/frontend_condortoken $RPM_BUILD_ROOT%{_sysconfdir}/condor/scripts/
cp install/templates/04_gwms_frontend_idtokens.config $RPM_BUILD_ROOT%{_sysconfdir}/condor/config.d

# Install glidecondor
install -m 0755 install/glidecondor_addDN $RPM_BUILD_ROOT%{_sbindir}/glidecondor_addDN
install -m 0755 install/glidecondor_createSecSched $RPM_BUILD_ROOT%{_sbindir}/glidecondor_createSecSched
install -m 0755 install/glidecondor_createSecCol $RPM_BUILD_ROOT%{_sbindir}/glidecondor_createSecCol

# Install checksum file
install -m 0644 etc/checksum.frontend $RPM_BUILD_ROOT%{frontend_dir}/checksum.frontend
install -m 0644 etc/checksum.factory $RPM_BUILD_ROOT%{factory_dir}/checksum.factory

# Install web area conf
install -d $RPM_BUILD_ROOT/%{_sysconfdir}/httpd/conf.d
install -m 0644 install/config/gwms-hardening.conf.httpd $RPM_BUILD_ROOT/%{_sysconfdir}/httpd/conf.d/gwms-hardening.conf
install -m 0644 install/config/gwms-frontend.conf.httpd $RPM_BUILD_ROOT/%{_sysconfdir}/httpd/conf.d/gwms-frontend.conf
install -m 0644 install/config/gwms-factory.conf.httpd $RPM_BUILD_ROOT/%{_sysconfdir}/httpd/conf.d/gwms-factory.conf
install -m 0644 install/config/gwms-logserver.conf.httpd $RPM_BUILD_ROOT/%{_sysconfdir}/httpd/conf.d/gwms-logserver.conf

install -d $RPM_BUILD_ROOT%{web_base}/../creation
install -d $RPM_BUILD_ROOT%{web_base}/../creation/templates
install -d $RPM_BUILD_ROOT%{factory_web_base}/../creation
install -d $RPM_BUILD_ROOT%{factory_web_base}/../creation/templates

# we don't need sl7 versions in the following directory, they are only needed in RPM.
install -m 0644 creation/templates/factory_initd_startup_template $RPM_BUILD_ROOT%{factory_web_base}/../creation/templates/
install -m 0644 creation/templates/frontend_initd_startup_template $RPM_BUILD_ROOT%{web_base}/../creation/templates/

# Install the logserver
install -d $RPM_BUILD_ROOT%{logserver_dir}
install -d $RPM_BUILD_ROOT%{logserver_web_dir}
install -d $RPM_BUILD_ROOT%{logserver_web_dir}/uploads
install -d $RPM_BUILD_ROOT%{logserver_web_dir}/uploads_unauthorized
install -m 0644 logserver/web-area/put.php $RPM_BUILD_ROOT%{logserver_web_dir}/put.php
install -m 0644 logserver/logging_config.json $RPM_BUILD_ROOT%{logserver_dir}/logging_config.json
install -m 0644 logserver/composer.json $RPM_BUILD_ROOT%{logserver_dir}/composer.json
install -m 0644 logserver/jwt.php $RPM_BUILD_ROOT%{logserver_dir}/jwt.php
install -m 0644 logserver/getjwt.py $RPM_BUILD_ROOT%{logserver_dir}/getjwt.py
install -m 0644 logserver/README.md $RPM_BUILD_ROOT%{logserver_dir}/README.md

%post usercollector
/sbin/service condor condrestart > /dev/null 2>&1 || true


%post userschedd
/sbin/service condor condrestart > /dev/null 2>&1 || true


%post vofrontend-core
# $1 = 1 - Installation
# $1 = 2 - Upgrade
# Source: http://www.ibm.com/developerworks/library/l-rpm2/

fqdn_hostname=`hostname -f`
frontend_name=`echo $fqdn_hostname | sed 's/\./-/g'`_OSG_gWMSFrontend

sed -i "s/FRONTEND_NAME_CHANGEME/$frontend_name/g" %{_sysconfdir}/gwms-frontend/frontend.xml
sed -i "s/FRONTEND_HOSTNAME/$fqdn_hostname/g" %{_sysconfdir}/gwms-frontend/frontend.xml

# If the startup log exists, change the ownership to frontend user
# Ownership was fixed in v3.2.4 with the init script templates rewrite
if [ -f %{_localstatedir}/log/gwms-frontend/frontend/startup.log ]; then
    chown frontend.frontend %{_localstatedir}/log/gwms-frontend/frontend/startup.log
fi

%if 0%{?rhel} >= 7
systemctl daemon-reload
%else
/sbin/chkconfig --add gwms-frontend
%endif

if [ ! -e %{frontend_dir}/monitor ]; then
    ln -s %{web_dir}/monitor %{frontend_dir}/monitor
fi

if [ ! -e %{frontend_passwd_dir} ]; then
    mkdir -p %{frontend_passwd_dir}
    chown frontend.frontend %{frontend_passwd_dir}
fi
# The IDTOKEN password creation is now in the startup script
# For manual creation you can use:
#  openssl rand -base64 64 | /usr/sbin/condor_store_cred -u "frontend@${fqdn_hostname}" -f "/etc/condor/passwords.d/FRONTEND" add > /dev/null 2>&1
#  /bin/cp /etc/condor/passwords.d/FRONTEND /var/lib/gwms-frontend/passwords.d/FRONTEND
#  chown frontend.frontend /var/lib/gwms-frontend/passwords.d/FRONTEND

%post httpd
# Protecting from failure in case it is not running/installed
/sbin/service httpd reload > /dev/null 2>&1 || true

%post vofrontend-httpd
# Protecting from failure in case it is not running/installed
/sbin/service httpd reload > /dev/null 2>&1 || true


%post factory-core

fqdn_hostname=`hostname -f`
sed -i "s/FACTORY_HOSTNAME/$fqdn_hostname/g" %{_sysconfdir}/gwms-factory/glideinWMS.xml
if [ "$1" = "1" ] ; then
    if [ ! -e %{factory_dir}/monitor ]; then
        ln -s %{factory_web_dir}/monitor %{factory_dir}/monitor
    fi
    if [ ! -e %{factory_dir}/log ]; then
        ln -s %{_localstatedir}/log/gwms-factory %{factory_dir}/log
    fi
fi

%if 0%{?rhel} == 7
systemctl daemon-reload
%else
/sbin/chkconfig --add gwms-factory
%endif

# Protecting from failure in case it is not running/installed
/sbin/service condor condrestart > /dev/null 2>&1 || true

%post factory-httpd
# Protecting from failure in case it is not running/installed
/sbin/service httpd reload > /dev/null 2>&1 || true

%post logserver
# Protecting from failure in case it is not running/installed
/sbin/service httpd reload > /dev/null 2>&1 || true
# Could also load the dependencies with composer install

%pre vofrontend-core
# Add the "frontend" user and group if they do not exist
getent group frontend >/dev/null || groupadd -r frontend
getent passwd frontend >/dev/null || \
       useradd -r -g frontend -d /var/lib/gwms-frontend \
	-c "VO Frontend user" -s /sbin/nologin frontend
# If the frontend user already exists make sure it is part of frontend and glidein group
usermod --append --groups frontend,glidein frontend >/dev/null

%pre vofrontend-glidein
getent group glidein >/dev/null || groupadd -r glidein

%pre factory-core
# Add the "gfactory" user and group if they do not exist
getent group gfactory >/dev/null || groupadd -r gfactory
getent passwd gfactory >/dev/null || \
       useradd -r -g gfactory -d /var/lib/gwms-factory \
	-c "GlideinWMS Factory user" -s /sbin/nologin gfactory
# If the gfactory user already exists make sure it is part of gfactory group
usermod --append --groups gfactory gfactory >/dev/null

# Add the "frontend" user and group if they do not exist
getent group frontend >/dev/null || groupadd -r frontend
getent passwd frontend >/dev/null || \
       useradd -r -g frontend -d /var/lib/gwms-frontend \
	-c "VO Frontend user" -s /sbin/nologin frontend
# If the frontend user already exists make sure it is part of frontend group
usermod --append --groups frontend frontend >/dev/null

%preun vofrontend-core
# $1 = 0 - Action is uninstall
# $1 = 1 - Action is upgrade

if [ "$1" = "0" ] ; then
    %if 0%{?rhel} >= 7
    systemctl daemon-reload
    %else
    /sbin/chkconfig --del gwms-frontend
    %endif
fi

if [ "$1" = "0" ]; then
    # Remove the symlinks
    rm -f %{frontend_dir}/frontend.xml
    rm -f %{frontend_dir}/monitor
    rm -f %{frontend_dir}/group_main/monitor

    # A lot of files are generated, but rpm won't delete those
#    rm -rf %{_datadir}/gwms-frontend
#    rm -rf %{_localstatedir}/log/gwms-frontend/*
fi

%preun factory-core
if [ "$1" = "0" ] ; then
    %if 0%{?rhel} >= 7
    systemctl daemon-reload
    %else
    /sbin/chkconfig --del gwms-factory
    %endif
fi
if [ "$1" = "0" ]; then
    rm -f %{factory_dir}/log
    rm -f %{factory_dir}/monitor
fi


%postun httpd
# Protecting from failure in case it is not running/installed
/sbin/service httpd reload > /dev/null 2>&1 || true

%postun vofrontend-httpd
# Protecting from failure in case it is not running/installed
/sbin/service httpd reload > /dev/null 2>&1 || true

%postun factory-httpd
# Protecting from failure in case it is not running/installed
/sbin/service httpd reload > /dev/null 2>&1 || true

%postun logserver
# Protecting from failure in case it is not running/installed
/sbin/service httpd reload > /dev/null 2>&1 || true

%postun factory-core
# Protecting from failure in case it is not running/installed
/sbin/service condor condrestart > /dev/null 2>&1 || true


%clean
rm -rf $RPM_BUILD_ROOT

%files factory

%files vofrontend
#%attr(755,root,root) %{_sysconfdir}/condor/scripts/frontend_condortoken

%files vofrontend-standalone

%files common-tools
%defattr(-,root,root,-)
%attr(755,root,root) %{_bindir}/glidein_cat
%attr(755,root,root) %{_bindir}/glidein_gdb
%attr(755,root,root) %{_bindir}/glidein_interactive
%attr(755,root,root) %{_bindir}/glidein_ls
%attr(755,root,root) %{_bindir}/glidein_ps
%attr(755,root,root) %{_bindir}/glidein_status
%attr(755,root,root) %{_bindir}/glidein_top
%attr(755,root,root) %{_bindir}/gwms-logparser
%attr(755,root,root) %{_bindir}/wmsTxtView
%attr(755,root,root) %{_bindir}/wmsXMLView
%{python3_sitelib}/glideinwms/tools
%dir %{python3_sitelib}/glideinwms/creation/
%{python3_sitelib}/glideinwms/creation/__init__.py
%{python3_sitelib}/glideinwms/creation/__pycache__
%{python3_sitelib}/glideinwms/creation/lib/cWConsts.py
%{python3_sitelib}/glideinwms/creation/lib/cWDictFile.py
%{python3_sitelib}/glideinwms/creation/lib/cWExpand.py
%{python3_sitelib}/glideinwms/creation/lib/cWParams.py
%{python3_sitelib}/glideinwms/creation/lib/cWParamDict.py
%{python3_sitelib}/glideinwms/creation/lib/xslt.py
%{python3_sitelib}/glideinwms/creation/lib/__init__.py
# without %dir it includes all files and sub-directories. Some modules are in different packages
%dir %{python3_sitelib}/glideinwms/creation/lib/__pycache__
%{python3_sitelib}/glideinwms/creation/lib/__pycache__/cWConsts.*
%{python3_sitelib}/glideinwms/creation/lib/__pycache__/cWDictFile.*
%{python3_sitelib}/glideinwms/creation/lib/__pycache__/cWExpand.*
%{python3_sitelib}/glideinwms/creation/lib/__pycache__/cWParams.*
%{python3_sitelib}/glideinwms/creation/lib/__pycache__/cWParamDict.*
%{python3_sitelib}/glideinwms/creation/lib/__pycache__/xslt.*
%{python3_sitelib}/glideinwms/creation/lib/__pycache__/__init__.*

%files factory-core
%defattr(-,gfactory,gfactory,-)
%doc LICENSE
%doc ACKNOWLEDGMENTS.md
%doc doc
%attr(755,root,root) %{_bindir}/analyze_entries
%attr(755,root,root) %{_bindir}/analyze_frontends
%attr(755,root,root) %{_bindir}/analyze_queues
%attr(755,root,root) %{_bindir}/cat_MasterLog
%attr(755,root,root) %{_bindir}/cat_StartdHistoryLog
%attr(755,root,root) %{_bindir}/cat_StartdLog
%attr(755,root,root) %{_bindir}/cat_StarterLog
%attr(755,root,root) %{_bindir}/cat_XMLResult
%attr(755,root,root) %{_bindir}/cat_logs
%attr(755,root,root) %{_bindir}/cat_named_log
%attr(755,root,root) %{_bindir}/create_condor_tarball
%attr(755,root,root) %{_bindir}/create_cvmfsexec_distros.sh
%attr(755,root,root) %{_bindir}/entry_ls
%attr(755,root,root) %{_bindir}/entry_q
%attr(755,root,root) %{_bindir}/entry_rm
%attr(755,root,root) %{_bindir}/extract_EC2_Address
%attr(755,root,root) %{_bindir}/find_StartdLogs
%attr(755,root,root) %{_bindir}/find_logs
%attr(755,root,root) %{_bindir}/fact_chown
%attr(755,root,root) %{_bindir}/fact_chown_check
%attr(755,root,root) %{_bindir}/gwms-logcat.sh
%attr(755,root,root) %{_bindir}/manual_glidein_submit
%attr(755,root,root) %{_bindir}/OSG_autoconf
%attr(755,root,root) %{_bindir}/get_tarballs
%attr(755,root,root) %{_bindir}/gfdiff
%attr(755,root,root) %{_sbindir}/checkFactory.py
%attr(755,root,root) %{_sbindir}/stopFactory.py
%attr(755,root,root) %{_sbindir}/glideFactory.py
%attr(755,root,root) %{_sbindir}/glideFactoryEntry.py
%attr(755,root,root) %{_sbindir}/glideFactoryEntryGroup.py

%if %{?rhel}%{!?rhel:0} == 5
%attr(755,root,root) %{_sbindir}/checkFactory.pyc
%attr(755,root,root) %{_sbindir}/checkFactory.pyo
%attr(755,root,root) %{_sbindir}/glideFactory.pyc
%attr(755,root,root) %{_sbindir}/glideFactory.pyo
%attr(755,root,root) %{_sbindir}/glideFactoryEntry.pyc
%attr(755,root,root) %{_sbindir}/glideFactoryEntry.pyo
%attr(755,root,root) %{_sbindir}/glideFactoryEntryGroup.pyc
%attr(755,root,root) %{_sbindir}/glideFactoryEntryGroup.pyo
%attr(755,root,root) %{_sbindir}/manageFactoryDowntimes.pyc
%attr(755,root,root) %{_sbindir}/manageFactoryDowntimes.pyo
%attr(755,root,root) %{_sbindir}/stopFactory.pyc
%attr(755,root,root) %{_sbindir}/stopFactory.pyo
%endif
%attr(755,root,root) %{_sbindir}/info_glidein
%attr(755,root,root) %{_sbindir}/manageFactoryDowntimes.py
%attr(755,root,root) %{_sbindir}/reconfig_glidein
%attr(755,root,root) %{_sbindir}/clone_glidein
%attr(-, root, root) %dir %{_localstatedir}/lib/gwms-factory
%attr(-, gfactory, gfactory) %dir %{_localstatedir}/lib/gwms-factory/client-proxies
%attr(-, gfactory, gfactory) %dir %{_localstatedir}/lib/gwms-factory/server-credentials
%attr(0600, gfactory, gfactory) %{_localstatedir}/lib/gwms-factory/server-credentials/jwt_secret.key
%attr(-, gfactory, gfactory) %{factory_web_dir}
%attr(-, gfactory, gfactory) %{factory_web_base}
%attr(-, gfactory, gfactory) %{factory_web_base}/../creation
%attr(-, gfactory, gfactory) %{factory_dir}
%attr(-, gfactory, gfactory) %dir %{factory_condor_dir}
%attr(-, gfactory, gfactory) %dir %{_localstatedir}/log/gwms-factory
%attr(-, gfactory, gfactory) %dir %{_localstatedir}/log/gwms-factory/client
%attr(-, gfactory, gfactory) %{_localstatedir}/log/gwms-factory/server
%{python3_sitelib}/glideinwms/creation/lib/cgWConsts.py
%{python3_sitelib}/glideinwms/creation/lib/cgWCreate.py
%{python3_sitelib}/glideinwms/creation/lib/cgWDictFile.py
%{python3_sitelib}/glideinwms/creation/lib/cgWParamDict.py
%{python3_sitelib}/glideinwms/creation/lib/cgWParams.py
%{python3_sitelib}/glideinwms/creation/lib/factoryXmlConfig.py
%{python3_sitelib}/glideinwms/creation/lib/factory_defaults.xml
%{python3_sitelib}/glideinwms/creation/lib/xmlConfig.py
%{python3_sitelib}/glideinwms/creation/lib/__pycache__/cgWConsts.*
%{python3_sitelib}/glideinwms/creation/lib/__pycache__/cgWCreate.*
%{python3_sitelib}/glideinwms/creation/lib/__pycache__/cgWDictFile.*
%{python3_sitelib}/glideinwms/creation/lib/__pycache__/cgWParamDict.*
%{python3_sitelib}/glideinwms/creation/lib/__pycache__/cgWParams.*
%{python3_sitelib}/glideinwms/creation/lib/__pycache__/factoryXmlConfig.*
%{python3_sitelib}/glideinwms/creation/lib/__pycache__/xmlConfig.*
%{python3_sitelib}/glideinwms/creation/templates/factory_initd_startup_template
%{python3_sitelib}/glideinwms/creation/reconfig_glidein
%{python3_sitelib}/glideinwms/factory
%if 0%{?rhel} >= 7
%{_sbindir}/gwms-factory
%{systemddir}/gwms-factory.service
%else
%{_initrddir}/gwms-factory
%endif
%attr(-, gfactory, gfactory) %dir %{_sysconfdir}/gwms-factory
%attr(-, gfactory, gfactory) %dir %{_sysconfdir}/gwms-factory/plugin.d
%attr(-, gfactory, gfactory) %dir %{_sysconfdir}/gwms-factory/hooks.reconfig.pre
%attr(-, gfactory, gfactory) %dir %{_sysconfdir}/gwms-factory/hooks.reconfig.post
%attr(-, gfactory, gfactory) %config(noreplace) %verify(not md5 mtime size) %{_sysconfdir}/gwms-factory/glideinWMS.xml
%config(noreplace) %{_sysconfdir}/sysconfig/gwms-factory

%files vofrontend-core
%defattr(-,frontend,frontend,-)
%doc LICENSE
%doc ACKNOWLEDGMENTS.md
%doc doc
#%attr(755,root,root) %{_sysconfdir}/condor/scripts/frontend_condortoken
%attr(644,root,root) %{_sysconfdir}/condor/config.d/04_gwms_frontend_idtokens.config
%attr(755,root,root) %{_bindir}/glidein_off
%attr(755,root,root) %{_bindir}/remove_requested_glideins
%attr(755,root,root) %{_bindir}/fetch_glidein_log
%attr(755,root,root) %{_bindir}/enter_frontend_env
%attr(755,root,root) %{_sbindir}/checkFrontend
%attr(755,root,root) %{_sbindir}/glideinFrontend
%attr(755,root,root) %{_sbindir}/glideinFrontendElement.py*
%attr(755,root,root) %{_sbindir}/reconfig_frontend
%attr(755,root,root) %{_sbindir}/manageFrontendDowntimes.py
%attr(755,root,root) %{_sbindir}/stopFrontend
%attr(755,root,root) %{_libexecdir}/gwms_renew_proxies
%attr(-, frontend, frontend) %dir %{_localstatedir}/lib/gwms-frontend
%attr(700, frontend, frontend) %{frontend_token_dir}
%attr(700, frontend, frontend) %{frontend_passwd_dir}
%attr(-, frontend, frontend) %{_localstatedir}/log/gwms-frontend
%defattr(-,root,root,-)
%{python3_sitelib}/glideinwms/frontend/glideinFrontendDowntimeLib.py
%{python3_sitelib}/glideinwms/frontend/glideinFrontendMonitorAggregator.py
%{python3_sitelib}/glideinwms/frontend/glideinFrontendMonitoring.py
%{python3_sitelib}/glideinwms/frontend/glideinFrontendPidLib.py
%{python3_sitelib}/glideinwms/frontend/glideinFrontend.py
%{python3_sitelib}/glideinwms/frontend/glideinFrontendElement.py
%{python3_sitelib}/glideinwms/frontend/checkFrontend.py
%{python3_sitelib}/glideinwms/frontend/stopFrontend.py
%{python3_sitelib}/glideinwms/frontend/manageFrontendDowntimes.py
%{python3_sitelib}/glideinwms/frontend/gwms_renew_proxies.py
%{python3_sitelib}/glideinwms/frontend/__pycache__/glideinFrontendDowntimeLib.*
%{python3_sitelib}/glideinwms/frontend/__pycache__/glideinFrontendMonitorAggregator.*
%{python3_sitelib}/glideinwms/frontend/__pycache__/glideinFrontendMonitoring.*
%{python3_sitelib}/glideinwms/frontend/__pycache__/glideinFrontendPidLib.*
%{python3_sitelib}/glideinwms/frontend/__pycache__/glideinFrontend.*
%{python3_sitelib}/glideinwms/frontend/__pycache__/glideinFrontendElement.*
%{python3_sitelib}/glideinwms/frontend/__pycache__/checkFrontend.*
%{python3_sitelib}/glideinwms/frontend/__pycache__/stopFrontend.*
%{python3_sitelib}/glideinwms/frontend/__pycache__/manageFrontendDowntimes.*
%{python3_sitelib}/glideinwms/frontend/__pycache__/gwms_renew_proxies.*
%{python3_sitelib}/glideinwms/frontend/tools
%{python3_sitelib}/glideinwms/creation/lib/check_config_frontend.py
%{python3_sitelib}/glideinwms/creation/lib/check_python3_expr.py
%{python3_sitelib}/glideinwms/creation/lib/__pycache__/check_config_frontend.*
%{python3_sitelib}/glideinwms/creation/lib/__pycache__/check_python3_expr.*
%{python3_sitelib}/glideinwms/creation/templates/frontend_initd_startup_template
%{python3_sitelib}/glideinwms/creation/reconfig_frontend
%defattr(-,frontend,frontend,-)
%if 0%{?rhel} >= 7
%{_sbindir}/gwms-frontend
%attr(0644, root, root) %{systemddir}/gwms-frontend.service
%attr(0644, root, root) %{systemddir}/gwms-renew-proxies.service
%attr(0644, root, root) %{systemddir}/gwms-renew-proxies.timer
%else
%{_initrddir}/gwms-frontend
%{_initrddir}/gwms-renew-proxies
%attr(0644, root, root) %{_sysconfdir}/cron.d/gwms-renew-proxies
%endif
%attr(-, frontend, glidein) %dir %{_sysconfdir}/gwms-frontend
%attr(-, frontend, glidein) %dir %{_sysconfdir}/gwms-frontend/hooks.reconfig.pre
%attr(-, frontend, glidein) %dir %{_sysconfdir}/gwms-frontend/hooks.reconfig.post
%attr(-, frontend, glidein) %dir %{_sysconfdir}/gwms-frontend/plugin.d
%attr(-, frontend, glidein) %config(noreplace) %{_sysconfdir}/gwms-frontend/plugin.d/
%attr(0664, frontend, glidein) %config(noreplace) %verify(not md5 mtime size) %{_sysconfdir}/gwms-frontend/frontend.xml
# TODO: should these files be moved in the glidein package?
%attr(-, frontend, glidein) %config(noreplace) %{_sysconfdir}/gwms-frontend/proxies.ini
%config(noreplace) %{_sysconfdir}/sysconfig/gwms-frontend
%attr(-, frontend, frontend) %{web_base}/../creation

%files vofrontend-libs
%defattr(-,root,root,-)
%dir %{python3_sitelib}/glideinwms/frontend/
%{python3_sitelib}/glideinwms/frontend/__init__.py
%{python3_sitelib}/glideinwms/frontend/glideinFrontendConfig.py
%{python3_sitelib}/glideinwms/frontend/glideinFrontendInterface.py
%{python3_sitelib}/glideinwms/frontend/glideinFrontendPlugins.py
%{python3_sitelib}/glideinwms/frontend/glideinFrontendLib.py
%{python3_sitelib}/glideinwms/frontend/__pycache__/__init__.*
%{python3_sitelib}/glideinwms/frontend/__pycache__/glideinFrontendConfig.*
%{python3_sitelib}/glideinwms/frontend/__pycache__/glideinFrontendInterface.*
%{python3_sitelib}/glideinwms/frontend/__pycache__/glideinFrontendPlugins.*
%{python3_sitelib}/glideinwms/frontend/__pycache__/glideinFrontendLib.*

%files vofrontend-glidein
%defattr(-,root,root,-)
%{python3_sitelib}/glideinwms/creation/lib/cvWConsts.py
%{python3_sitelib}/glideinwms/creation/lib/cvWCreate.py
%{python3_sitelib}/glideinwms/creation/lib/cvWDictFile.py
%{python3_sitelib}/glideinwms/creation/lib/cvWParamDict.py
%{python3_sitelib}/glideinwms/creation/lib/cvWParams.py
%{python3_sitelib}/glideinwms/creation/lib/matchPolicy.py
%{python3_sitelib}/glideinwms/creation/lib/__pycache__/cvWConsts.*
%{python3_sitelib}/glideinwms/creation/lib/__pycache__/cvWCreate.*
%{python3_sitelib}/glideinwms/creation/lib/__pycache__/cvWDictFile.*
%{python3_sitelib}/glideinwms/creation/lib/__pycache__/cvWParamDict.*
%{python3_sitelib}/glideinwms/creation/lib/__pycache__/cvWParams.*
%{python3_sitelib}/glideinwms/creation/lib/__pycache__/matchPolicy.*
%defattr(-,root,glidein,775)
%{web_dir}
%{web_base}
%{frontend_dir}
%defattr(664,root,glidein,775)
%{web_dir}/monitor
%{web_dir}/stage
%{web_base}/factoryRRDBrowse.html

%files httpd
%config(noreplace) %{_sysconfdir}/httpd/conf.d/gwms-hardening.conf

%files factory-httpd
%config(noreplace) %{_sysconfdir}/httpd/conf.d/gwms-factory.conf

%files vofrontend-httpd
%config(noreplace) %{_sysconfdir}/httpd/conf.d/gwms-frontend.conf

%files factory-condor
%config(noreplace) %{_sysconfdir}/condor/config.d/00_gwms_factory_general.config
%config(noreplace) %{_sysconfdir}/condor/config.d/01_gwms_factory_collectors.config
%config(noreplace) %{_sysconfdir}/condor/config.d/02_gwms_factory_schedds.config
%config(noreplace) %{_sysconfdir}/condor/gwms_q_format.cpf
%attr(-, condor, condor) %{_localstatedir}/lib/condor/schedd_glideins2
%attr(-, condor, condor) %{_localstatedir}/lib/condor/schedd_glideins3
%attr(-, condor, condor) %{_localstatedir}/lib/condor/schedd_glideins4
%attr(-, condor, condor) %{_localstatedir}/lib/condor/schedd_glideins5

%files usercollector
%config(noreplace) %{_sysconfdir}/condor/config.d/01_gwms_collectors.config
%config(noreplace) %{_sysconfdir}/condor/config.d/01_gwms_ganglia.config
%config(noreplace) %{_sysconfdir}/condor/config.d/11_gwms_secondary_collectors.config
%config(noreplace) %{_sysconfdir}/condor/ganglia.d/01_gwms_metrics.config

%files userschedd
%config(noreplace) %{_sysconfdir}/condor/config.d/02_gwms_schedds.config
%attr(-, condor, condor) %{_localstatedir}/lib/condor/schedd_jobs2

%files libs
%{python3_sitelib}/glideinwms/__init__.py
%dir %{python3_sitelib}/glideinwms/__pycache__
%{python3_sitelib}/glideinwms/__pycache__/__init__.*
%{python3_sitelib}/glideinwms/lib

%files glidecondor-tools
%attr(755,root,root) %{_sbindir}/glidecondor_addDN
%attr(755,root,root) %{_sbindir}/glidecondor_createSecSched
%attr(755,root,root) %{_sbindir}/glidecondor_createSecCol

%files minimal-condor
%config(noreplace) %{_sysconfdir}/condor/config.d/00_gwms_general.config
%config(noreplace) %{_sysconfdir}/condor/config.d/90_gwms_dns.config

%files condor-common-config
%config(noreplace) %{_sysconfdir}/condor/config.d/03_gwms_local.config
%config(noreplace) %{_sysconfdir}/condor/certs/condor_mapfile
#%config(noreplace) %{_sysconfdir}/condor/scripts/frontend_condortoken

%files logserver
%defattr(-,root,root,-)
%config(noreplace) %{_sysconfdir}/httpd/conf.d/gwms-logserver.conf
%attr(-, root, root) %{logserver_dir}
%attr(-, root, apache) %{logserver_web_dir}
%attr(-, apache, apache) %{logserver_web_dir}/uploads
%attr(-, apache, apache) %{logserver_web_dir}/uploads_unauthorized
%attr(-, apache, apache) %{logserver_web_dir}/put.php
%attr(-, root, root) %{logserver_dir}/logging_config.json
%attr(-, root, root) %{logserver_dir}/composer.json
%attr(-, root, root) %{logserver_dir}/jwt.php
%attr(-, root, root) %{logserver_dir}/getjwt.py
%attr(-, root, root) %{logserver_dir}/README.md


%changelog
* Mon Sep 29 2025 Marco Mambelli <marcom@fnal.gov> - 3.10.16
- Glideinwms v3.10.16
- Release Notes: http://glideinwms.fnal.gov/doc.v3_10_16/history.html
- Release candidates 3.10.16-01.rc1 to 3.10.16-02.rc2

* Fri Jul 18 2025 Marco Mambelli <marcom@fnal.gov> - 3.10.15
- Glideinwms v3.10.15
- Release Notes: http://glideinwms.fnal.gov/doc.v3_10_15/history.html
- Release candidates 3.10.15-01.rc1 to 3.10.15-02.rc2

* Fri Jun 20 2025 Marco Mambelli <marcom@fnal.gov> - 3.10.14
- Glideinwms v3.10.14
- Release Notes: http://glideinwms.fnal.gov/doc.v3_10_14/history.html
- Release candidates 3.10.14-01.rc1 to 3.10.14-02.rc2

* Wed May 7 2025 Marco Mambelli <marcom@fnal.gov> - 3.10.13
- Glideinwms v3.10.13
- Release Notes: http://glideinwms.fnal.gov/doc.v3_10_13/history.html
- Release candidates 3.10.13-01.rc1

* Mon May 5 2025 Marco Mambelli <marcom@fnal.gov> - 3.10.12
- Glideinwms v3.10.12
- Release Notes: http://glideinwms.fnal.gov/doc.v3_10_12/history.html
- Release candidates 3.10.12-01.rc1

* Mon Mar 24 2025 Marco Mambelli <marcom@fnal.gov> - 3.10.11
- Glideinwms v3.10.11
- Release Notes: http://glideinwms.fnal.gov/doc.v3_10_11/history.html
- Release candidates 3.10.11-01.rc1 to 3.10.11-02.rc2

* Fri Jan 24 2025 Marco Mambelli <marcom@fnal.gov> - 3.10.10
- Glideinwms v3.10.10
- Release Notes: http://glideinwms.fnal.gov/doc.v3_10_10/history.html
- Release candidates 3.10.10-01.rc1

* Thu Jan 16 2025 Marco Mambelli <marcom@fnal.gov> - 3.10.9
- Glideinwms v3.10.9
- Release Notes: http://glideinwms.fnal.gov/doc.v3_10_9/history.html
- Release candidates 3.10.9-01.rc1 to 3.10.9-03.rc3

* Mon Nov 25 2024 Marco Mambelli <marcom@fnal.gov> - 3.10.8
- Glideinwms v3.10.8
- Release Notes: http://glideinwms.fnal.gov/doc.v3_10_8/history.html
- Release candidates 3.10.8-01.rc1

* Tue Oct 22 2024 Marco Mambelli <marcom@fnal.gov> - 3.10.7-3
- Glideinwms v3.10.7
- 3.10.7-1 was on Fri Jun 21 2024
- Removed bash mangling in 3.10.7-3
- Release Notes: http://glideinwms.fnal.gov/doc.v3_10_7/history.html
- Release candidates 3.10.7-01.rc1 to 3.10.7-03.rc3

* Thu Jan 25 2024 Marco Mambelli <marcom@fnal.gov> - 3.10.6
- Glideinwms v3.10.6
- Release Notes: http://glideinwms.fnal.gov/doc.v3_10_6/history.html
- Release candidates 3.10.6-01.rc1 to 3.10.6-02.rc2

* Wed Sep 27 2023 Marco Mambelli <marcom@fnal.gov> - 3.10.5
- Glideinwms v3.10.5
- Release Notes: http://glideinwms.fnal.gov/doc.v3_10_5/history.html

* Thu Sep 14 2023 Marco Mambelli <marcom@fnal.gov> - 3.10.4
- Glideinwms v3.10.4
- Release Notes: http://glideinwms.fnal.gov/doc.v3_10_4/history.html

* Mon Sep 11 2023 Marco Mambelli <marcom@fnal.gov> - 3.10.3
- Glideinwms v3.10.3
- Release Notes: http://glideinwms.fnal.gov/doc.v3_10_3/history.html
- Release candidates 3.10.3-01.rc1 to 3.10.3-02.rc2

* Wed May 10 2023 Marco Mambelli <marcom@fnal.gov> - 3.10.2
- Glideinwms v3.10.2
- Release Notes: http://glideinwms.fnal.gov/doc.v3_10_2/history.html
- Release candidates 3.10.2-01.rc1 to 3.10.2-02.rc2

* Tue Dec 13 2022 Marco Mambelli <marcom@fnal.gov> - 3.10.1
- Glideinwms v3.10.1
- Release Notes: http://glideinwms.fnal.gov/doc.v3_10_1/history.html
- Release candidates 3.10.1-01.rc1

* Wed Dec 7 2022 Marco Mambelli <marcom@fnal.gov> - 3.10.0
- Glideinwms v3.10.0
- Release Notes: http://glideinwms.fnal.gov/doc.v3_10_0/history.html
- Release candidates 3.10.0-01.rc1

* Thu Oct 27 2022 Marco Mambelli <marcom@fnal.gov> - 3.9.6
- Glideinwms v3.9.6
- Release Notes: http://glideinwms.fnal.gov/doc.v3_9_6/history.html
- Release candidates 3.9.6-01.rc1 to 3.9.6-06.rc6

* Tue May 17 2022 Bruno Coimbra <coimbra@fnal.gov> - 3.9.5
- Glideinwms v3.9.5
- Release Notes: http://glideinwms.fnal.gov/doc.v3_9_5/history.html
- Release candidates 3.9.5-01.rc1 to 3.9.5-03.rc3

* Wed Apr 20 2022 Carl Edquist <edquist@cs.wisc.edu> - 3.9.4-2
- Fix python3-rrdtool dependencies (SOFTWARE-5134)

* Tue Jan 25 2022 Bruno Coimbra <coimbra@fnal.gov> - 3.9.4
- Glideinwms v3.9.4
- Release Notes: http://glideinwms.fnal.gov/doc.v3_9_4/history.html
- Release candidates 3.9.4-01.rc1 to 3.9.4-01.rc5

* Mon Jan 24 2022  Dennis Box <dbox@fnal.gov> - 3.7.6
- Glideinwms v3.7.5
- Release Notes: http://glideinwms.fnal.gov/doc.v3_7_6/history.html
- Release candidates 3.7.5-01.rc1 to  3.7.5-01.rc2

* Tue Sep 21 2021 Bruno Coimbra <coimbra@fnal.gov> - 3.9.3
- Glideinwms v3.9.3
- Release Notes: http://glideinwms.fnal.gov/doc.v3_9_3/history.html
- Release candidates 3.9.3-01.rc1

* Thu Sep  2 2021 Dennis Box <dbox@fnal.gov> - 3.7.5
- Glideinwms v3.7.5
- Release Notes: http://glideinwms.fnal.gov/doc.v3_7_5/history.html
- Release candidates 3.7.5-01.rc1 to  3.7.5-06.rc6

* Tue Jun 1 2021 Bruno Coimbra <coimbra@fnal.gov> - 3.9.2-1
- GlideinWMS v3.9.2
- Release Notes: http://glideinwms.fnal.gov/doc.v3_9_2/history.html
- Release candidates: 3.9.2-0.1.rc1 to 3.9.2-0.5.rc5

* Fri Mar 26 2021 Dennis Box <dbox@fnal.gov> - 3.7.3-1
- GlideinWMS v3.7.3
- Release Notes: http://glideinwms.fnal.gov/doc.v3_7_3/history.html
- Release candidates: 3.7.3-01.rc1 .rc1 to

* Thu Feb 11 2021 Bruno Coimbra <coimbra@fnal.gov> - 3.9.1-1
- GlideinWMS v3.9.1
- Release Notes: http://glideinwms.fnal.gov/doc.v3_9_1/history.html
- Release candidates: 3.9-0.1.rc1 to 3.9.1-0.5.rc6

* Mon Dec 21 2020 Dennis Box <dbox@fnal.gov> - 3.7.2-1
- GlideinWMS v3.7.2
- Release Notes: http://glideinwms.fnal.gov/doc.v3_7_2/history.html
- Release candidates: 3.7.0.1.rc1 to 3.7.2-0.3.rc3

* Tue Nov 3 2020 Dennis Box <dbox@fnal.gov> - 3.7.1-1
- GlideinWMS v3.7.1
- Release Notes: http://glideinwms.fnal.gov/doc.v3_7_1/history.html
- Release candidates: 3.7.1-0.1.rc1 to 3.7.1-0.7.rc9

* Mon Oct 5 2020 Marco Mambelli <marcom@fnal.gov> - 3.6.5-1
- GlideinWMS v3.6.5
- Release Notes: http://glideinwms.fnal.gov/doc.v3_6_5/history.html
- Release candidates: 3.6.5-0.1.rc1

* Fri Sep 18 2020 Bruno Coimbra <coimbra@fnal.gov> - 3.9-1
- GlideinWMS v3.9
- Release Notes: http://glideinwms.fnal.gov/doc.v3_9/history.html
- Release candidates: 3.9-0.1.rc1 to 3.9-0.1.rc4

* Thu Sep 17 2020 Marco Mambelli <marcom@fnal.gov> - 3.6.4-1
- GlideinWMS v3.6.4
- Release Notes: http://glideinwms.fnal.gov/doc.v3_6_4/history.html
- Release candidates: 3.6.4-0.1.rc1

* Mon Aug 17 2020 Marco Mambelli <marcom@fnal.gov> - 3.6.3-1
- GlideinWMS v3.6.3
- Release Notes: http://glideinwms.fnal.gov/doc.v3_6_3/history.html
- Release candidates: 3.6.3-0.1.rc1 to 3.6.3-0.3.rc3

* Fri Apr 3 2020 Marco Mambelli <marcom@fnal.gov> - 3.7-1
- GlideinWMS v3.7
- Release Notes: http://glideinwms.fnal.gov/doc.v3_7/history.html
- Release candidates: 3.7-0.1.rc1 to 3.7-0.3.rc3

* Thu Mar 26 2020 Marco Mambelli <marcom@fnal.gov> - 3.6.2-1
- GlideinWMS v3.6.2
- Release Notes: http://glideinwms.fnal.gov/doc.v3_6_2/history.html
- Release candidates: 3.6.2-0.0.rc0 to 3.6.2-0.3.rc3

* Mon Nov 25 2019 Marco Mambelli <marcom@fnal.gov> - 3.6.1-1
- GlideinWMS v3.6.1
- Release Notes: http://glideinwms.fnal.gov/doc.v3_6_1/history.html
- Release candidates: 3.6.1-0.1.rc1

* Wed Sep 25 2019 Marco Mambelli <marcom@fnal.gov> - 3.6-1
- GlideinWMS v3.6
- Release Notes: http://glideinwms.fnal.gov/doc.v3_6/history.html
- This is a rename of 3.5.1, to respect the odd-even numbering

* Wed Sep 18 2019 Marco Mambelli <marcom@fnal.gov> - 3.5.1-1
- GlideinWMS v3.5.1
- Release Notes: http://glideinwms.fnal.gov/doc.v3_5_1/history.html
- Release candidates: 3.5.1-0.1.rc1

* Wed Aug 14 2019 Marco Mambelli <marcom@fnal.gov> - 3.4.6-1
- GlideinWMS v3.4.6
- Release Notes: http://glideinwms.fnal.gov/doc.v3_4_6/history.html
- Release candidates: 3.4.6-0.1.rc1

* Fri Jun 7 2019 Marco Mambelli <marcom@fnal.gov> - 3.5
- GlideinWMS v3.5
- Release Notes: http://glideinwms.fnal.gov/doc.v3_5/history.html
- Release candidates: 3.5-0.1.rc1 to 3.5-0.1.rc2

* Tue Jun 4 2019 Diego Davila <didavila@ucsd.edu> - 3.4.5-2
- patch (sw3689.proxy-renewal-bugfix.patch) to fix bug on proxy renewal

* Fri Apr 19 2019  Marco Mambelli <marcom@fnal.gov> - 3.4.5-1
- GlideinWMS v3.4.5
- Release Notes: http://glideinwms.fnal.gov/doc.v3_4_5/history.html
- Release candidates: 3.4.5-0.1.rc1

* Thu Apr 4 2019  Marco Mambelli <marcom@fnal.gov> - 3.4.4-1
- GlideinWMS v3.4.4
- Release Notes: http://glideinwms.fnal.gov/doc.v3_4_4/history.html
- Release candidates: 3.4.4-0.1.rc1 to 3.4.4-0.4.rc4

* Fri Jan 25 2019  Marco Mambelli <marcom@fnal.gov> - 3.4.3-1
- GlideinWMS v3.4.3
- Release Notes: http://glideinwms.fnal.gov/doc.v3_4_3/history.html
- Release candidates: 3.4.3-0.1.rc1 to 3.4.3-0.2.rc2

* Fri Oct 26 2018  Marco Mambelli <marcom@fnal.gov> - 3.4.2-1
- Controlling that Frontend is not using options incompatible w/ linked Factories
- Release Notes: http://glideinwms.fnal.gov/doc.v3_4_2/history.html

* Wed Oct 24 2018 Brian Lin <blin@cs.wisc.edu> - 3.4.1-2
- Use systemctl for loading/unloading on EL7

* Thu Oct 18 2018 Marco Mambelli <marcom@fnal.gov> - 3.4.1-1
- Glideinwms v3.4.1
- Release Notes: http://glideinwms.fnal.gov/doc.v3_4_1/history.html
- Release candidates: 3.4.1-0.1.rc1 to 3.4.1-0.3.rc3

* Tue Aug 21 2018 Mátyás Selmeci <matyas@cs.wisc.edu> - 3.4-1.1
- Bump to rebuild

* Tue Jun 5 2018 Marco Mambelli <marcom@fnal.gov> - 3.4-1
- Glideinwms v3.4
- Release Notes: http://glideinwms.fnal.gov/doc.v3_4/history.html
- Release candidates: 3.4-0.1.rc1

* Mon Apr 30 2018 Brian Lin <blin@cs.wisc.edu> - 3.2.22.2-4
- Fix proxy renewal cron format

* Thu Apr 26 2018 Brian Lin <blin@cs.wisc.edu> - 3.2.22.2-3
- Fix bug in proxy ownership code

* Wed Apr 25 2018 Brian Lin <blin@cs.wisc.edu> - 3.2.22.2-2
- Fix automatically renewed proxy ownership
- Set the proper permissions and owners for service, timer, and cron files

* Wed Apr 25 2018 Marco Mambelli <marcom@fnal.gov> - 3.3.3-1
- Glideinwms v3.3.3
- Release Notes: http://glideinwms.fnal.gov/doc.v3_3_3/history.html
- Release candidates: 3.3.3-0.1.rc1

* Tue Apr 17 2018 Marco Mambelli <marcom@fnal.gov> - 3.2.22.2-1
- Glideinwms v3.2.22.2
- Release Notes: http://glideinwms.fnal.gov/doc.v3_2_22_2/history.html

* Wed Apr 11 2018 Marco Mambelli <marcom@fnal.gov> - 3.2.22.1-1
- Glideinwms v3.2.22.1
- Release Notes: http://glideinwms.fnal.gov/doc.v3_2_22_1/history.html

* Tue Apr 10 2018 Marco Mambelli <marcom@fnal.gov> - 3.2.22-1
- Glideinwms v3.2.22
- Release Notes: http://glideinwms.fnal.gov/doc.v3_2_22/history.html
- Release candidates: 3.2.22-0.1.rc1 to 3.2.22-0.2.rc2

* Tue Feb 27 2018 Marco Mambelli <marcom@fnal.gov> - 3.2.21-2
- Fixed a problem with proxy outo-renewal, see [19147]

* Wed Feb 7 2018 Marco Mambelli <marcom@fnal.gov> - 3.2.21-1
- Glideinwms v3.2.21
- Release Notes: http://glideinwms.fnal.gov/doc.v3_2_21/history.html
- Release candidates: 3.2.21-0.1.rc1 to 3.2.21-0.3.rc3

* Wed Jan 31 2018 Brian Lin <blin@cs.wisc.edu> - 3.2.20-2
- Fix uncaught exceptions and fd backlog on gwms frontends (SOFTWARE-3120)

* Wed Nov 15 2017 Marco Mambelli <marcom@fnal.gov> - 3.2.20-1
- Glideinwms v3.2.20
- Release Notes: http://glideinwms.fnal.gov/doc.v3_2_20/history.html
- Release candidates: 3.2.20-0.1.rc1 to 3.2.20-0.4.rc4

* Thu Jun 01 2017 Marco Mambelli <marcom@fnal.gov> - 3.2.19-2
- Removed obsolete osg-cert-scripts dependency

* Tue May 30 2017 Marco Mambelli <marcom@fnal.gov> - 3.2.19-1
- Glideinwms v3.2.19
- Release Notes: http://glideinwms.fnal.gov/doc.v3_2_19/history.html
- Release candidates: 3.2.19-0.1.rc1

* Fri Mar 24 2017 Marco Mambelli <marcom@fnal.gov> - 3.3.2-1
- Glideinwms v3.3.2
- Release Notes: http://glideinwms.fnal.gov/doc.v3_3_2/history.html
- Release candidates: 3.3.2-0.1.rc1 to 3.3.2-0.3.rc3

* Tue Feb 28 2017 Marco Mambelli <marcom@fnal.gov> - 3.2.18-1
- Glideinwms v3.2.18
- Release Notes: http://glideinwms.fnal.gov/doc.v3_2_18/history.html
- Release candidates: 3.2.18-0.1.rc1

* Wed Jan 25 2017 Marco Mambelli <marcom@fnal.gov> - 3.2.17-1
- Glideinwms v3.2.17
- Release Notes: http://glideinwms.fnal.gov/doc.v3_2_17/history.html
- Release candidates: 3.2.17-0.1.rc1 to 3.2.17-0.3.rc3

* Tue Oct 25 2016 Parag Mhashilkar <parag@fnal.gov> - 3.3.1-1
- Glideinwms v3.3.1
- Release Notes: http://glideinwms.fnal.gov/doc.dev/history.html

* Fri Oct 21 2016 Parag Mhashilkar <parag@fnal.gov> - 3.2.16-1
- Glideinwms v3.2.16
- Release Notes: http://glideinwms.fnal.gov/doc.v3_2_16/history.html
- Release candidates: 3.2.16-0.1.rc1 to 3.2.16-0.2.rc2

* Tue Aug 30 2016 Parag Mhashilkar <parag@fnal.gov> - 3.3-1
- Glideinwms v3.3 release candidates (rc1-rc11)
- Release Notes: http://glideinwms.fnal.gov/doc.dev/history.html

* Wed Aug 17 2016 Parag Mhashilkar <parag@fnal.gov> - 3.2.15-1
- Glideinwms v3.2.15
- Release Notes: http://glideinwms.fnal.gov/doc.v3_2_15/history.html
- Release candidates: 3.2.15-0.1.rc1 to 3.2.15-0.4.rc4

* Fri Jun 17 2016 Parag Mhashilkar <parag@fnal.gov> - 3.2.14.1-1
- Glideinwms v3.2.14.1
- Release Notes: http://glideinwms.fnal.gov/doc.v3_2_14_1/history.html
- Release candidates: 3.2.14.1-0.1.rc1

* Fri Jun 03 2016 Parag Mhashilkar <parag@fnal.gov> - 3.2.14-1
- Glideinwms v3.2.14
- Release Notes: http://glideinwms.fnal.gov/doc.v3_2_14/history.html
- Release candidates: 3.2.14-0.1.rc1 to 3.2.14-0.2.rc2

* Wed Mar 09 2016 Parag Mhashilkar <parag@fnal.gov> - 3.2.13-1
- Glideinwms v3.2.13 (see release notes for details)
- Release Notes: http://glideinwms.fnal.gov/doc.v3_2_13/history.html
- Release candidates: 3.2.13-0.1.rc1 to 3.2.13-0.2.rc2

* Thu Jan 21 2016 Marco Mambelli <marcom@fnal.gov> - 3.2.12.1-1
- Glideinwms v3.2.12.1 release (see notes for featires and bug fixes)
- Release Notes: http://glideinwms.fnal.gov/doc.v3_2_12_1/history.html
- Release candidates: 3.2.12-0.1.rc1 to 3.2.12-0.5.rc5

* Thu Jan 14 2016 Marco Mambelli <marcom@fnal.gov> - 3.2.12-1
- Glideinwms v3.2.12 release (see notes for featires and bug fixes)
- Fixed python 2.4 compatibility
- Added glideinwms-common-tools as a dependency to glideinwms-userschedd
- Tools from glideinwms-vofrontend-standalone are now in path (bindir)
- Release Notes: http://glideinwms.fnal.gov/doc.v3_2_12/history.html
- Release candidates: 3.2.12-0.1.rc1 to 3.2.12-0.5.rc5

* Thu Oct 08 2015 Mátyás Selmeci <matyas@cs.wisc.edu> - 3.2.11.2-4
- Don't put collectors behind shared port (needed for HTCondor 8.4.0) (SOFTWARE-2015)

* Mon Oct 05 2015 Carl Edquist <edquist@cs.wisc.edu> - 3.2.11.2-2
- Repartition subpackages to avoid overlapping files (SOFTWARE-2015)

* Fri Sep 18 2015 Parag Mhashilkar <parag@fnal.gov> - 3.2.11.2-1
- Glideinwms v3.2.11.2 release
- Release Notes: http://glideinwms.fnal.gov/doc.v3_2_11_2/history.html

* Wed Sep 02 2015 Parag Mhashilkar <parag@fnal.gov> - 3.2.11.1-1
- Glideinwms v3.2.11.1 release
- Release Notes: http://glideinwms.fnal.gov/doc.v3_2_11_1/history.html

* Thu Aug 20 2015 Parag Mhashilkar <parag@fnal.gov> - 3.2.11-1
- Glideinwms v3.2.11 release
- Release Notes: http://glideinwms.fnal.gov/doc.v3_2_11/history.html

* Thu Jul 16 2015 Mátyás Selmeci <matyas@cs.wisc.edu> - 3.2.10-1.1.osg
- vofrontend-standalone: Replace osg-client dep with most of osg-client's
  contents (except the networking stuff), since osg-client has been dropped in
  OSG 3.3

* Mon Jun 01 2015 Parag Mhashilkar <parag@fnal.gov> - 3.2.10-1
- Glideinwms v3.2.10 release
- Release Notes: http://glideinwms.fnal.gov/doc.prd/history.html

* Fri May 08 2015 Parag Mhashilkar <parag@fnal.gov> - 3.2.9-1
- Glideinwms v3.2.9 release
- Release Notes: http://glideinwms.fnal.gov/doc.prd/history.html
- Release candidates: 3.2.9-0.1.rc1 to 3.2.9-0.2.rc2

* Tue Dec 30 2014 Parag Mhashilkar <parag@fnal.gov> - 3.2.8-1
- Glideinwms v3.2.8 release
- Release candidates: 3.2.8-0.1.rc1 to 3.2.8-0.2.rc2

* Thu Nov 6 2014 Parag Mhashilkar <parag@fnal.gov> - 3.2.7.2-1
- Glideinwms v3.2.7.2 release
- Sets MASTER.USE_SHARED_PORT in schedd's config to support HTCondor v8.2.3

* Wed Nov 5 2014 Parag Mhashilkar <parag@fnal.gov> - 3.2.7.1-1
- Glideinwms v3.2.7.1 release

* Tue Oct 14 2014 Parag Mhashilkar <parag@fnal.gov> - 3.2.7-1
- Glideinwms v3.2.7 release
- Disabled secondary schedd in the frontend configuration
- Added python-ldap as dependency to glideinwms-libs and glideinwms-factory
- Release candidates: 3.2.7-0.1.rc1 to 3.2.7-0.2.rc2

* Fri Jul 25 2014 Parag Mhashilkar <parag@fnal.gov> - 3.2.6-1
- Glideinwms v3.2.6 release
- Reverted group name in default dir ownership but we now explicitly make gfactory and frontend users part of the gfactory and frontend group respectively
- Removed the group name in the default dir ownership for factory and frontend
- Release candidates: 3.2.6-0.1.rc1 to 3.2.6-0.2.rc3

* Wed Jun 25 2014 Parag Mhashilkar <parag@fnal.gov> - 3.2.5.1-2
- Added GOC factory info in the factory config template

* Mon Jun 23 2014 Parag Mhashilkar <parag@fnal.gov> - 3.2.5.1-1
- Glideinwms v3.2.5.1 release

* Mon May 19 2014 Parag Mhashilkar <parag@fnal.gov> - 3.2.5-1
- Glideinwms v3.2.5 release
- Change the default trust_domain in frontend.xml from OSG to grid
- Release candidates: 3.2.5-0.1.rc1 to 3.2.5-0.2.rc3

* Mon Apr 28 2014 Parag Mhashilkar <parag@fnal.gov> - 3.2.4-3
- Fix the ownership of startup.log file for frontend in post script
- Changed the javascriptrrd dependency to be 1.1.0+ for frontend as well

* Wed Apr 16 2014 Parag Mhashilkar <parag@fnal.gov> - 3.2.4-2
- Changed the javascriptrrd dependency to be 1.1.0+

* Mon Apr 14 2014 Parag Mhashilkar <parag@fnal.gov> - 3.2.4-1
- Glideinwms v3.2.4 release
- Unified the factory and frontend startup scripts in rpm and tarball versions from common templates

* Mon Feb 03 2014 Parag Mhashilkar <parag@fnal.gov> - 3.2.3-1
- Glideinwms v3.2.3 release
- Final release does not include support for HTCondor CE rsl
- Support for HTCondor CE rsl and improvements to Frontend
- Bug fixes to factory log cleanup
- New features and bug fixes
- Added clone_glidein tool
- Release candidates: 3.2.3-0.1.rc1 to 3.2.5-0.2.rc3

* Mon Oct 28 2013 Parag Mhashilkar <parag@fnal.gov> - 3.2.1-0.1.rc2
- Added gwms-frontend and gwms-factory files in /etc/sysconfig in the respective rpms
- Added new files, xslt.* to the list for respective rpms

* Thu Oct 10 2013 Parag Mhashilkar <parag@fnal.gov> - 3.2.0-3
- Changed Requires (dependencies) to insure that the entire set of glideinwms rpms is updated as a set.

* Thu Oct 10 2013 Parag Mhashilkar <parag@fnal.gov> - 3.2.0-2
- Fixed the NVR int the rpm version as per the convention

* Mon Sep 09 2013 John Weigand <weigand@fnal.gov> - 2.7.2-0.1.rc3
- No code changes from rc2. Just a change to Requires (dependencies) to insure that the entire set of glideinwms rpms is updated as a set.
- Updated the frontend.xml and added update_proxy.py while generating the checksum for the version
- Add update_proxy.py while generating the checksum for the version

* Wed Jun 5 2013 Parag Mhashilkar <parag@fnal.gov> - 2.7.1-1.1
- Check existence of link before creating it to avoid scriptlet error.
- Removed libs directory from the vofrontend-standalone and added glideinwms-libs as its dependency.
- Added 11_gwms_secondary_collectors to respective condor rpms and glidecondor_addSecCol to the tools rpm

* Mon Apr 29 2013 Parag Mhashilkar <parag@fnal.gov> - 2.7.0-0.4
- Added missing glideinwms/__init__ to the glideinwms-libs.

* Fri Apr 26 2013 Parag Mhashilkar <parag@fnal.gov> - 2.7.0-0.3
- Further refactoring of packages.
- Added new packages glideinwms-glidecondor-tools and its dependency glideinwms-libs
- Removed files provided by glideinwms-minimal-condor from file list of glideinwms-usercollector and glideinwms-userschedd and make usercollector and userschedd depend on the minimal-condor

* Fri Apr 26 2013 Parag Mhashilkar <parag@fnal.gov> - 2.7.0-0.2
- Added glidecondor_addDN to factory, vofrontend-standalone, minimal-condor, userschedd, usercollector packages

* Tue Apr 2 2013 Parag Mhashilkar <parag@fnal.gov> - 2.7.0-0.0
- Added missing library files creation/lib/__init__ to the frontend rpm
- Updated the checksum creation to sort the info
- Changes to file list based on the python libraries

* Fri Jan 4 2013 Doug Strain <dstrain@fnal.gov> - 2.6.3-0.rc2.6
- Update to 2.6.3 rc2 release candidate
- Adding factory tools scripts and their python libraries
- Adding condor_create_tarball
- Adding frontend/factory index page.

* Thu Nov 8 2012 Doug Strain <dstrain@fnal.gov> - 2.6.2-2
- Improvements recommended by Igor to modularize glideinwms

* Fri Nov 2 2012 Doug Strain <dstrain@fnal.gov> - 2.6.2-1
- Glideinwms 2.6.2 Release

* Thu Sep 20 2012 Doug Strain <dstrain@fnal.gov> - 2.6.1-2
- Added GRIDMANAGER_PROXY_REFRESH_TIME to condor config
- Added JOB_QUEUE_LOG to the schedd condor configs

* Fri Aug 3 2012 Doug Strain <dstrain@fnal.gov> - 2.6.0-3
- Updating to new release
- Changing the schedd configs to work with both wisc and osg condor rpms

* Fri Apr 27 2012 Doug Strain <dstrain@fnal.gov> - 2.5.7-4
- Changed ownership of frontend.xml to frontend user
- Changed ownership of glideinwms.xml to gfactory user
- This allows writeback during upgrade reconfigs

* Fri Apr 27 2012 Doug Strain <dstrain@fnal.gov> - 2.5.7-3
- Changed frontend init.d script to reconfig as frontend user

* Mon Apr 9 2012 Doug Strain <dstrain@fnal.gov> - 2.5.7-2
- Updating sources for v2.5.7
- Splitting DAEMON LIST to appropriate config files

* Fri Mar 16 2012 Doug Strain <dstrain@fnal.gov> - 2.5.6-1
- Updating sources for v2.5.6

* Tue Feb 21 2012 Doug Strain <dstrain@fnal.gov> - 2.5.5-7alpha
- Adding factory RPM and v3 support
- Updating to also work on sl7
- Also added support for v3.0.0rc3 with optional define

* Thu Feb 16 2012 Doug Strain <dstrain@fnal.gov> - 2.5.5-1
- Updating for v2.5.5

* Tue Jan 10 2012 Doug Strain <dstrain@fnal.gov> - 2.5.4-7
- Adding condor_mapfile to minimal

* Mon Jan 9 2012 Doug Strain <dstrain@fnal.gov> - 2.5.4-6
- Changing directories per Igors request
-- changing directories to /var/lib
- Splitting condor config into separate package
- Fixing web-area httpd

* Thu Jan 5 2012 Doug Strain <dstrain@fnal.gov> - 2.5.4-2
- Updating for 2.5.4 release source and fixing eatures for BUG2310
-- Split directories so that the web area is in /var/www

* Thu Dec 29 2011 Doug Strain <dstrain@fnal.gov> - 2.5.4-1
- Using release source and fixing requested features for BUG2310
-- Adding user/group correctly
-- Substituting hostname name automatically

* Fri Dec 09 2011 Doug Strain <dstrain@fnal.gov> - 2.5.4-0.pre2
- Added glidecondor_addDN to vofrontend package

* Thu Nov 10 2011 Doug Strain <dstrain@fnal.gov> - 2.5.4-0.pre1
- Update to use patched 2.5.3
- Pushed patches upstream
- Made the package glideinwms with subpackage vofrontend

* Thu Nov 10 2011 Doug Strain <dstrain@fnal.gov> - 2.5.3-3
- Update to 2.5.3
- Updated condor configs to match ini installer
- Updated frontend.xml to not check index.html
- Updated init script to use "-xml" flag

* Mon Oct 17 2011 Burt Holzman <burt@fnal.gov> - 2.5.2.1-1
- Update to 2.5.2.1

* Tue Sep 06 2011 Burt Holzman <burt@fnal.gov> - 2.5.2-5
- Fix reference to upstream tarball

* Tue Sep 06 2011 Burt Holzman <burt@fnal.gov> - 2.5.2-4
- Add RPM to version number in ClassAd

* Tue Sep 06 2011 Burt Holzman <burt@fnal.gov> - 2.5.2-3
- Fixed glideinWMS versioning advertisement

* Wed Aug 31 2011 Burt Holzman <burt@fnal.gov> - 2.5.2-2
- Fixed file location for frontend_support.js

* Sat Aug 13 2011 Burt Holzman <burt@fnal.gov> - 2.5.2-1
- Update to glideinWMS 2.5.2

* Tue Aug 02 2011 Derek Weitzel <dweitzel@cse.unl.edu> - 2.5.1-13
- Made vdt-repo compatible

* Tue Apr 05 2011 Burt Holzman 2.5.1-10
- Update frontend_startup script to better determine frontend name
- Move user-editable configuration items into 02_frontend-local.config

* Tue Mar 22 2011 Derek Weitzel 2.5.1-8
- Change condor config file name to 00_frontend.config
- Separated definition of collectors into 01_collectors.config

* Fri Mar 11 2011 Burt Holzman  2.5.1-1
- Include glideinWMS 2.5.1
- Made all the directories independent of the frontend name

* Thu Mar 10 2011 Derek Weitzel  2.5.0-11
- Changed the frontend.xml to correct the web stage directory

* Thu Mar 10 2011 Derek Weitzel  2.5.0-9
- Made the work, stage, monitor, and log directory independent of the frontend name.
- Frontend name is now generated at install time

* Sun Feb 13 2011 Derek Weitzel  2.5.0-6
- Made rpm noarch
- Replaced python site-packages more auto-detectable

* Wed Feb 09 2011 Derek Weitzel  2.5.0-5
- Added the tools to bin directory

* Mon Jan 24 2011 Derek Weitzel  2.5.0-4
- Added the tools directory to the release

* Mon Jan 24 2011 Derek Weitzel  2.5.0-3
- Rebased to official 2.5.0 release.

* Thu Dec 16 2010 Derek Weitzel  2.5.0-2
- Changed GlideinWMS version to branch_v2_4plus_igor_ucsd1

* Fri Aug 13 2010 Derek Weitzel  2.4.2-2
- Removed port from primary collector in frontend.xml
- Changed GSI_DAEMON_TRUSTED_CA_DIR to point to /etc/grid-security/certificates
  where CA's are installed.
- Changed GSI_DAEMON_DIRECTORY to point to /etc/grid-security.  This is
  only used to build default directories for other GSI_*
  configuration variables.
- Removed the rm's to delete the frontend-temp and log directories at uninstall,
  they removed files when updating, not wanted.  Let RPM handle those.
