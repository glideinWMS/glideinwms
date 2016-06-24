#!/bin/sh

log_nonzero_rc() {
    echo "`date` ERROR: $1 failed with non zero exit code ($2)" 1>&2
}


setup_python_venv() {
    if [ $# -gt 1 ]; then
        echo "Invalid number of arguments to setup_python_venv. Will accept the location to install venv or use PWD as default"
        exit 1
    fi
    WORKSPACE=${1:-`pwd`}
    VIRTUALENV_TARBALL=virtualenv-12.0.7.tar.gz
    VIRTUALENV_URL="https://pypi.python.org/packages/source/v/virtualenv/$VIRTUALENV_TARBALL"
    VIRTUALENV_EXE=$WORKSPACE/virtualenv-12.0.7/virtualenv.py
    VENV=$WORKSPACE/venv

    # Following is useful for running the script outside jenkins
    if [ ! -d "$WORKSPACE" ]; then
        mkdir $WORKSPACE
    fi

    echo "SETTING UP VIRTUAL ENVIRONMENT ..."
    if [ -f $WORKSPACE/$VIRTUALENV_TARBALL ]; then
        rm $WORKSPACE/$VIRTUALENV_TARBALL
    fi
    # Get latest virtualenv package that works with python 2.6
    curl -o $WORKSPACE/$VIRTUALENV_TARBALL $VIRTUALENV_URL
    tar xzf $WORKSPACE/$VIRTUALENV_TARBALL
    if [ ! -d $VENV ] ; then
       #virtualenv --python=python2.6 --always-copy $VENV
       $WORKSPACE/virtualenv-12.0.7/virtualenv.py --system-site-packages $VENV
       #$WORKSPACE/virtualenv-12.0.7/virtualenv.py $VENV
    fi

    source $VENV/bin/activate

    export PYTHONPATH="$PWD:$PYTHONPATH"

    # Install dependancies first so we don't get uncompatible ones
    # Following RPMs need to be installed on the machine:
    # 1. rrdtool-devel
    # 2. openssl-devel
    # 3. swig
    pip_packages="astroid==1.2.1 pylint==1.3.1 pep8 unittest2 coverage rrdtool pyyaml mock xmlrunner"
    for package in $pip_packages; do
        echo "Installing $package ..."
        status="DONE"
        pip install --quiet $package
        if [ $? -ne 0 ]; then
            status="FAILED"
        fi
        echo "Installing $package ... $status"
    done
    #pip install M2Crypto==0.20.2

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
}


print_python_info() {
    if [ $# -ne 0 ]; then
        br="<br/>"
        bo="<b>"
        bc="</b>"
    fi
    echo "${bo}PYTHON INFO:${bc} `which python`$br"
    echo "${bo}PYLINT INFO:${bc} `pylint --version`$br"
    echo "${bo}PEP8 INFO:${bc} `pep8 --version`$br"
}


mail_results() {
    local contents=$1
    local subject=$2
    echo "From: gwms-builds@donot-reply.com;
To: parag@fnal.gov;
Subject: $subject;
Content-Type: text/html;
MIME-VERSION: 1.0;
;
`cat $contents`
" | sendmail -t
}
