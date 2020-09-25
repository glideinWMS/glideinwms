#!/bin/bash
export PYVER=${1:-"3.6"}
GITHUB_WORKSPACE=${GITHUB_WORKSPACE:-`pwd`}
glideinwms/build/jenkins/runtest.sh -vi pyunittest -a 
status=$?
tar cvfj $GITHUB_WORKSPACE/logs.tar.bz2 output/*
cat output/gwms.*.pyunittest
exit $status
