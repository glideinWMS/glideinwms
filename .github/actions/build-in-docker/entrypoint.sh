#!/bin/bash

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

export PYVER=${1:-"3.9"}
GITHUB_WORKSPACE=${GITHUB_WORKSPACE:-`pwd`}
export SW_VER=${RELEASE_VERSION:-"master"}
# export RPM_VER=${RPM_VERSION:-"3.7.5"}
export RPM_REL=${RPM_RELESE:-"55"}
export RPM_FULLREL="$RPM_REL.post.$(date +"%Y%m%d%H%M")"
export HERE="`pwd`"
mkdir rel
glideinwms/build/ReleaseManager/release.py --no-mock --release-version=$SW_VER --source-dir="$HERE"/glideinwms --release-dir="$HERE"/rel --rpm-release=$RPM_FULLREL
status=$?
mkdir gwms_rpms
#mkdir rpm_logs
mv "$HERE/rel/$SW_VER"/rpmbuild/RPMS/noarch/*rpm gwms_rpms/
tar cvfj $GITHUB_WORKSPACE/rpms.tar.bz2 gwms_rpms/*
#cat #some logs
exit $status
