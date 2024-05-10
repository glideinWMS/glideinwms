#!/bin/bash

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

PYVER=${1:-"3.9"}
GITHUB_WORKSPACE=${GITHUB_WORKSPACE:-`pwd`}
env PYVER=$PYVER glideinwms/build/ci/runtest.sh -vi pylint -t1 -a
tar cvfj $GITHUB_WORKSPACE/logs.tar.bz2 output/*
cat output/gwms.*.pylint
cat output/gwms.*.pylint.pylint
# The line count includes also the file names
exit `cat output/gwms.*.pylint.pylint | wc -l`
