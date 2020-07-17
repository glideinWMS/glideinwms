#!/bin/sh

loginfo() {
    [[ -n "$VERBOSE" ]] && echo "$1"
}


logwarn(){
    echo "$filename WARNING: $1" >&2
}


logerror() {
    echo "$filename ERROR: $1" >&2
}


logexit() {
    # Fail: log the error and exit
    logerror "$1"
    # logerror "exiting"
    exit ${2:-1}
}


log_nonzero_rc() {
    echo "$(date) ERROR: $1 failed with non zero exit code ($2)" 1>&2
    return $2
}


robust_realpath() {
    if ! realpath "$1" 2>/dev/null; then
        echo "$(cd "$(dirname "$1")"; pwd -P)/$(basename "$1")"
    fi
}


setup_python_venv() {
    if [ $# -gt 1 ]; then
        echo "Invalid number of arguments to setup_python_venv. Will accept the location to install venv or use PWD as default"
        exit 1
    fi
    WORKSPACE=${1:-$(pwd)}


    PY_VER="3.6"
    py_detected="$(python3 -V | cut -f2 -d ' ')"
    [[ "${py_detected}" == 3* ]] || logexit "Python 3 required, detected ${py_detected}. Aborting"
    [[ "${py_detected}" == "${PY_VER}"* ]] || logwarn "Reference version is Python 3.6. Detected ${py_detected}."
    VIRTUALENV_VER=virtualenv
    PYLINT='pylint'
    ASTROID='astroid'
    HYPOTHESIS="hypothesis"
    AUTOPEP8="autopep8"
    TESTFIXTURES="testfixtures"
    # Installing the pip version, in case the RPM is not installed
    HTCONDOR="htcondor"
    COVERAGE='coverage'
    JSONPICKLE="jsonpickle"
    PYCODESTYLE="pycodestyle"
    MOCK="mock=="
#    PYLINT='pylint==2.5.3'
#    ASTROID='astroid==2.4.2'
#    HYPOTHESIS="hypothesis"
#    AUTOPEP8="autopep8"
#    TESTFIXTURES="testfixtures"
#    # Installing the pip version, in case the RPM is not installed
#    HTCONDOR="htcondor"
#    COVERAGE='coverage==4.5.4'
#    JSONPICKLE="jsonpickle"
#    PYCODESTYLE="pycodestyle"
#    MOCK="mock==3.0.5"

    VIRTUALENV_TARBALL=${VIRTUALENV_VER}.tar.gz
    VIRTUALENV_URL="https://pypi.python.org/packages/source/v/virtualenv/$VIRTUALENV_TARBALL"
    #VIRTUALENV_EXE=$WORKSPACE/${VIRTUALENV_VER}/virtualenv.py
    VENV="${WORKSPACE}/venv-${py_detected}"

    # Following is useful for running the script outside jenkins
    if [ ! -d "$WORKSPACE" ]; then
        mkdir -p "$WORKSPACE"
    fi

    echo "SETTING UP VIRTUAL ENVIRONMENT ..."
    # Virtualenv is in the distribution, no need to download it separately
    # we still want to redo the virtualenv
    rm -rf "$VENV"
    #"$WORKSPACE/${VIRTUALENV_VER}"/virtualenv.py --system-site-packages "$VENV"
    python3 -m venv --system-site-packages "$VENV"

    . "$VENV"/bin/activate

    # TODO; is this needed or done in activate?
    export PYTHONPATH="$PWD:$PYTHONPATH"

    # Install dependencies first so we don't get incompatible ones
    # Following RPMs need to be installed on the machine:
    # pep8 has been replaced by pycodestyle
    # importlib and argparse are in std Python 3.6
    pip_packages="toml ${PYCODESTYLE} unittest2 ${COVERAGE} ${PYLINT} ${ASTROID}"
    pip_packages="$pip_packages pyyaml ${MOCK}  xmlrunner jwt"
    pip_packages="$pip_packages ${HYPOTHESIS} ${AUTOPEP8} ${TESTFIXTURES}"
    pip_packages="$pip_packages ${HTCONDOR} ${JSONPICKLE}"

    # TODO: load the list from requirements.txt

    python3 -m pip install --quiet --upgrade pip

    failed_packages=""
    for package in $pip_packages; do
        echo "Installing $package ..."
        status="DONE"
        python3 -m pip install --quiet "$package"
        if ! python3 -m pip install --quiet "$package" ; then
            status="FAILED"
            failed_packages="$failed_packages $package"
        fi
        echo "Installing $package ... $status"
    done
    #try again if anything failed to install, sometimes its order
    for package in $failed_packages; do
        echo "REINSTALLING $package"
        if ! python3 -m pip install "$package" ; then
            logerror "ERROR $package could not be installed.  Stopping venv setup."
            #return 1
        fi
    done

    #pip install M2Crypto==0.20.2

    ## Need this because some strange control sequences when using default TERM=xterm
    export TERM="linux"

    ## PYTHONPATH for glideinwms source code
    # pythonpath for pre-packaged only
    if [ -n "$PYTHONPATH" ]; then
        export PYTHONPATH="${PYTHONPATH}:${GLIDEINWMS_SRC}"
    else
        export PYTHONPATH="${GLIDEINWMS_SRC}"
    fi

    export PYTHONPATH=${PYTHONPATH}:${GLIDEINWMS_SRC}/lib
    export PYTHONPATH=${PYTHONPATH}:${GLIDEINWMS_SRC}/creation/lib
    export PYTHONPATH=${PYTHONPATH}:${GLIDEINWMS_SRC}/factory
    export PYTHONPATH=${PYTHONPATH}:${GLIDEINWMS_SRC}/frontend
    export PYTHONPATH=${PYTHONPATH}:${GLIDEINWMS_SRC}/tools
    export PYTHONPATH=${PYTHONPATH}:${GLIDEINWMS_SRC}/tools/lib
}


get_source_directories() {
    # Return to stdout a comma separated list of source directories
    # 1 - glideinwms directory, root of the source tree
    local src_dir="${1:-.}"
    sources="${src_dir},${src_dir}/factory/"
    sources="${sources},${src_dir}/factory/tools,${src_dir}/frontend"
    sources="${sources},${src_dir}/frontend/tools,${src_dir}/install"
    sources="${sources},${src_dir}/install/services,${src_dir}/lib"
    sources="${sources},${src_dir}/tools,${src_dir}/tools/lib"
    echo "$sources"
}


print_python_info() {
    if [ $# -ne 0 ]; then
        br="<br/>"
        bo="<b>"
        bc="</b>"
    fi
    echo "${bo}HOSTNAME:${bc} $(hostname -f)$br"
    echo "${bo}LINUX DISTRO:${bc} $(lsb_release -d)$br"
    echo "${bo}PYTHON LOCATION:${bc} $(which python)$br"
    echo "${bo}PYLINT:${bc} $(pylint --version)$br"
    echo "${bo}PEP8:${bc} $(pycodestyle --version)$br"
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
$(cat "$contents")
" | sendmail -t
}
