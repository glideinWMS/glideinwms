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

    if python --version 2>&1 | grep 'Python 2.6' > /dev/null ; then
        # Get latest packages that work with python 2.6
        PY_VER="2.6"
        VIRTUALENV_VER=virtualenv-12.0.7
        PYLINT='pylint==1.3.1'
        ASTROID='astroid==1.2.1'
        HYPOTHESIS="hypothesislegacysupport"
        AUTOPEP8="autopep8==1.3"
        # htcondor is not pip for python 2.6 (will be found from the RPM)
        HTCONDOR=
    else
        # use something more up-to-date
        PY_VER="2.7"
        VIRTUALENV_VER=virtualenv-16.0.0
        PYLINT='pylint==1.8.4'
        ASTROID='astroid==1.6.0'
        HYPOTHESIS="hypothesis"
        AUTOPEP8="autopep8"
        # Installing the pip version, in case the RPM is not installed
        HTCONDOR=htcondor
    fi

    VIRTUALENV_TARBALL=${VIRTUALENV_VER}.tar.gz
    VIRTUALENV_URL="https://pypi.python.org/packages/source/v/virtualenv/$VIRTUALENV_TARBALL"
    VIRTUALENV_EXE=$WORKSPACE/${VIRTUALENV_VER}/virtualenv.py
    VENV=$WORKSPACE/venv-$PY_VER

    # Following is useful for running the script outside jenkins
    if [ ! -d "$WORKSPACE" ]; then
        mkdir $WORKSPACE
    fi

    echo "SETTING UP VIRTUAL ENVIRONMENT ..."
    if [ -f $WORKSPACE/$VIRTUALENV_TARBALL ]; then
        rm $WORKSPACE/$VIRTUALENV_TARBALL
    fi
    curl -L -o $WORKSPACE/$VIRTUALENV_TARBALL $VIRTUALENV_URL
    tar xzf $WORKSPACE/$VIRTUALENV_TARBALL

    #if we download the venv tarball everytime we should remake the venv
    #every time
    rm -rf $VENV
    $WORKSPACE/${VIRTUALENV_VER}/virtualenv.py --system-site-packages $VENV

    source $VENV/bin/activate

    export PYTHONPATH="$PWD:$PYTHONPATH"

    # Install dependancies first so we don't get uncompatible ones
    # Following RPMs need to be installed on the machine:
    # 1. rrdtool-devel
    # 2. openssl-devel
    # 3. swig
    # pep8 has been replaced by pycodestyle
    pip_packages="${ASTROID} ${PYLINT} pycodestyle unittest2 coverage" 
    pip_packages="$pip_packages rrdtool pyyaml mock xmlrunner future importlib argparse"
    pip_packages="$pip_packages ${HYPOTHESIS} ${AUTOPEP8}"
    pip_packages="$pip_packages ${HTCONDOR}"


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
    if [ -n "$PYTHONPATH" ]; then
        export PYTHONPATH=${PYTHONPATH}:${GLIDEINWMS_SRC}
    else
        export PYTHONPATH=${GLIDEINWMS_SRC}
    fi

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
    echo "${bo}HOSTNAME:${bc} `hostname -f`$br"
    echo "${bo}LINUX DISTRO:${bc} `lsb_release -d`$br"
    echo "${bo}PYTHON LOCATION:${bc} `which python`$br"
    echo "${bo}PYLINT:${bc} `pylint --version`$br"
    echo "${bo}PEP8:${bc} `pycodestyle --version`$br"
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
