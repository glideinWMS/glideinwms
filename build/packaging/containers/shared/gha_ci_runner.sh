#!/bin/bash

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

# receiving as argument all the options for runtest
# e.g. glideinwms/build/ci/runtest.sh -vi bats -a -k 1200 -> bats runtest -vi bats -a -k 1200
# parameters starting w/ "-" before runtest are script options
#
# Invocations
#   glideinwms/build/ci/runtest.sh -vi bats -a -k 1200
#     # 20 minutes timeout for each test
#   glideinwms/build/ci/runtest.sh -vI pyunittest -a
#   glideinwms/build/ci/runtest.sh -vi pylint -t1 -a
#   env PYVER=$PYVER glideinwms/build/ci/runtest.sh -vi pylint -t2 -a
#     # pycodestyle

TESTUSER=gwmsciuser
SWITCHUSER=
# Parse options (if any) and shift
#
# get script
mytest=$1
myscript=$2
shift 2
[[ "$myscript" == runtest ]] && myscript=glideinwms/build/ci/runtest.sh || true
# setup and run
echo "GHA runner: in $(pwd), switching from $USER to $TESTUSER"
# Avoid running the tests as root
if [[ $(id -u) == 0 ]]; then
  chown -R $TESTUSER .
  # Needed to avoid permission problems at cleanup
  chmod -R g=u .
  SWITCHUSER="sudo -u $TESTUSER"
fi
GITHUB_WORKSPACE=${GITHUB_WORKSPACE:-$(pwd)}
export PYVER=${1:-"3.9"}
# PYVER=${1:-"3.9"}
# env PYVER=$PYVER glideinwms/build/ci/runtest.sh -vi pylint -t1 -a
$SWITCHUSER "$myscript" "$@"
status=$?
# collect logs, print and exit
$SWITCHUSER tar cvjf $GITHUB_WORKSPACE/logs.tar.bz2 output/*
$SWITCHUSER rm -rf $GITHUB_WORKSPACE/glideinwms
if [[ "$mytest" == pycodestyle ]]; then
    $SWITCHUSER cat output/gwms.*.pylint
    $SWITCHUSER cat output/gwms.*.pylint.pycs
    ## The line count includes also the file names
    #pycs_warnings=$(cat output/gwms.*.pylint.pycs | wc -l)
    pycs_warnings=$($SWITCHUSER bash -c ". output/gwms.LOCAL.pylint >/dev/null; echo $PEP8_ERROR_COUNT")
    # Save the warnings count in a file
    $SWITCHUSER echo ${pycs_warnings} >  $GITHUB_WORKSPACE/result-pycodestyle-warnings.txt
    # and in an output variable
    $SWITCHUSER echo "::set-output name=warnings::${pycs_warnings}"
    # Always successful
    exit 0
fi
# If not pycodestyle
$SWITCHUSER cat output/gwms.*.$mytest
if [[ "$mytest" == pylint ]]; then
    $SWITCHUSER cat output/gwms.*.pylint.pylint
    # The line count includes also the file names
    exit `cat output/gwms.*.pylint.pylint | wc -l`
fi
exit $status
