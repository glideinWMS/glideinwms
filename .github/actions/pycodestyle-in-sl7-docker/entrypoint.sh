#!/bin/bash
PYVER=${1:-"3.6"}
GITHUB_WORKSPACE=${GITHUB_WORKSPACE:-`pwd`}
env PYVER=$PYVER glideinwms/build/ci/runtest.sh -vi pylint -t2 -a
tar cvfj $GITHUB_WORKSPACE/logs.tar.bz2 output/*
cat output/gwms.*.pylint
cat output/gwms.*.pylint.pycs
# The line count includes also the file names
exit `cat output/gwms.*.pylint.pycs | wc -l`
