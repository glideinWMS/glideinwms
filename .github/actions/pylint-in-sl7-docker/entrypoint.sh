#!/bin/bash
PYVER=${1:-"3.6"}
GITHUB_WORKSPACE=${GITHUB_WORKSPACE:-`pwd`}
env PYVER=$PYVER glideinwms/build/ci/runtest.sh -vi pylint -t1 -a
tar cvfj $GITHUB_WORKSPACE/logs.tar.bz2 output/*
cat output/gwms.*.pylint
cat output/gwms.*.pylint.pylint
# The line count includes also the file names
exit `cat output/gwms.*.pylint.pylint | wc -l`
