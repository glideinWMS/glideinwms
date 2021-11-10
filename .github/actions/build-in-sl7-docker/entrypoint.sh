#!/bin/bash
export PYVER=${1:-"3.6"}
GITHUB_WORKSPACE=${GITHUB_WORKSPACE:-`pwd`}
export SW_VER=${RELEASE_VERSION:-"master"}
export RPM_VER=${RPM_VERSION:-"3.7.5"}
export RPM_REL=${RPM_RELESE:-"55.post.nightly"}
export HERE="`pwd`"
mkdir rel
glideinwms/build/ReleaseManager/release.py --release-version=$SW_VER --source-dir="$HERE"/glideinwms --release-dir="$HERE"/rel --rpm-release=$RPM_REL --rpm-version=$RPM_VER 
status=$?
mkdir gwms_rpms
#mkdir rpm_logs
mv "$HERE"/rel/3_7_5/rpmbuild/RPMS/*rpm gwms_rpms/
tar cvfj $GITHUB_WORKSPACE/rpms.tar.bz2 gwms_rpms/*
#cat #some logs
exit $status
