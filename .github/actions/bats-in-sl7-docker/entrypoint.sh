#!/bin/bash
export PYVER=${1:-"3.6"}
GITHUB_WORKSPACE=${GITHUB_WORKSPACE:-`pwd`}
glideinwms/build/ci/runtest.sh -vi bats -a 
status=$?
tar cvfj $GITHUB_WORKSPACE/logs.tar.bz2 output/*
cat output/gwms.*.bats
exit $status
