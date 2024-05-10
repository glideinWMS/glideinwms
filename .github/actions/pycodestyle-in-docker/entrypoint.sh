#!/bin/bash

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

PYVER=${1:-"3.9"}
GITHUB_WORKSPACE=${GITHUB_WORKSPACE:-`pwd`}
env PYVER=$PYVER glideinwms/build/ci/runtest.sh -vi pylint -t2 -a
tar cvfj $GITHUB_WORKSPACE/logs.tar.bz2 output/*
cat output/gwms.*.pylint
cat output/gwms.*.pylint.pycs
## The line count includes also the file names
#pycs_warnings=$(cat output/gwms.*.pylint.pycs | wc -l)
. output/gwms.LOCAL.pylint
pycs_warnings=$PEP8_ERROR_COUNT
# Save the warnings count in a file
echo ${pycs_warnings} >  $GITHUB_WORKSPACE/result-pycodestyle-warnings.txt
# and in an output variable
echo "::set-output name=warnings::${pycs_warnings}"
# Always successful
exit 0
