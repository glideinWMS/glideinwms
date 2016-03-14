#!/bin/sh

function log_nonzero_rc {
    echo "`date` ERROR: $1 failed with non zero exit code ($2)" 1>&2
}

WORKSPACE=`pwd`
VIRTUALENV_TARBALL=virtualenv-12.0.7.tar.gz
VIRTUALENV_URL=https://pypi.python.org/packages/source/v/virtualenv/$VIRTUALENV_TARBALL
VIRTUALENV_EXE=$WORKSPACE/virtualenv-12.0.7/virtualenv.py
VENV=$WORKSPACE/venv

export GLIDEINWMS_SRC=$WORKSPACE/glideinwms
export ERRORS=$WORKSPACE/errors

# Following is useful for running the script outside jenkins
if [ ! -d "$WORKSPACE" ]; then
    mkdir $WORKSPACE
fi

echo > $ERRORS

echo "SETTING UP VIRTUAL ENVIRONMENT ..."
# Get latest virtualenv package that works with python 2.6
wget $VIRTUALENV_TARBALL
tar xzf $VIRTUALENV_TARBALL
if [ ! -d venv ] ; then
   #virtualenv --python=python2.6 --always-copy $VENV
   $WORKSPACE/virtualenv-12.0.7/virtualenv.py $VENV
fi

source $VENV/bin/activate

export PYTHONPATH="$PWD:$PYTHONPATH"

# Install dependancies first so we don't get uncompatible ones
# Following RPMs need to be installed on the machine:
# 1. rrdtool-devel
# 2. openssl-devel
# 3. swig
pip_packages="astroid==1.2.1 pylint==1.3.1 pep8 unittest2 coverage rrdtool pyyaml mock"
for package in $pip_packages; do
    echo "Installing $package ..."
    status="DONE"
    pip install --quiet $package
    if [ $? -ne 0 ]; then
        status="FAILED"
    fi
    echo "Installing $package ... $status"
done

## Need this because some strange control sequences when using default TERM=xterm
export TERM="linux"

## PYTHONPATH for glideinwms source code
# pythonpath for pre-packaged only
export PYTHONPATH=${PYTHONPATH}:${GLIDEINWMS_SRC}/lib
export PYTHONPATH=${PYTHONPATH}:${GLIDEINWMS_SRC}/creation/lib
export PYTHONPATH=${PYTHONPATH}:${GLIDEINWMS_SRC}/factory
export PYTHONPATH=${PYTHONPATH}:${GLIDEINWMS_SRC}/frontend
export PYTHONPATH=${PYTHONPATH}:${GLIDEINWMS_SRC}/tools
export PYTHONPATH=${PYTHONPATH}:${GLIDEINWMS_SRC}/tools/lib

cd $GLIDEINWMS_SRC/unittests
files="test_frontend.py test_frontend_element.py"
files="test_frontend.py"

for file in $files ; do
    ./$file || log_nonzero_rc "$file" $?
done
