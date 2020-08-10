#!/bin/sh
# Utility functions for the GlideinWMS CI tests

robust_realpath() {
    if ! realpath "$1" 2>/dev/null; then
        echo "$(cd "$(dirname "$1")"; pwd -P)/$(basename "$1")"
    fi
}


######################################
# logging and output functions
######################################

# Using TESTLOG if defined
logreportok() {
    loglog "$1=\"PASSED\""
}

logreportfail() {
    loglog "$1=\"FAILED\""
}

logreportstr() {
    loglog "$1=\"$2\""
}

logreport() {
    loglog "$1=$2"
}

loglog() {
    [[ -n "${TESTLOG}" ]] && echo "$1" >> "${TESTLOG}"
    echo "$1"
}

loginfoout() {
    [[ -n "$VERBOSE" ]] && echo "$1"
}

loginfo() {
    # return 0 if not verbose (needed for bats test), print to stderr if verbose
    [[ -z "$VERBOSE" ]] && return
    echo "$filename INFO: $1" >&2
}

logwarn(){
    echo "$filename WARNING: $1" >&2
}

logerror() {
    echo "$filename ERROR: $1" >&2
}

logexit() {
    # Fail: log the error and exit
    # 1. message 2. exit code 3. attribute for logreportfail
    [ -n "$3" ] && logreportfail $3
    logerror "$1"
    # logerror "exiting"
    exit ${2:-1}
}

log_verbose_nonzero_rc() {
    [[ -z "$VERBOSE" ]] && echo "$(date) ERROR: $1 failed with non zero exit code ($2)" 1>&2
    return $2
}

log_nonzero_rc() {
    echo "$(date) ERROR: $1 failed with non zero exit code ($2)" 1>&2
    return $2
}


############################
# Python functions
############################

SETUP_VENV3=
setup_python3_venv() {
    if [ $# -gt 1 ]; then
        logexit "Invalid number of arguments to setup_python_venv. Will accept the location to install venv or use PWD as default"
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
    MOCK="mock"
    M2CRYPTO="M2Crypto" # M2CRYPTO="M2Crypto==0.20.2"
    
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

    VENV="${WORKSPACE}/venv-${py_detected}"
    # Clearing PYTHONPATH to avoid interferences
    PYTHONPATH=

    # Following is useful for running the script outside jenkins
    if [ ! -d "$WORKSPACE" ]; then
        mkdir -p "$WORKSPACE"
        SETUP_VENV3=
    fi

    if [ "${SETUP_VENV3}" = "${VENV}" ]; then
        loginfo "Python Virtual Environment already installed. Reusing it"
        if ! . "$VENV"/bin/activate; then
            echo "ERROR existing virtualenv ($VENV) could not be activated.  Exiting"
            return 1
        fi
        export PATH="$VENV/bin:$PATH"
        export PYTHONPATH="${WORKSPACE}:$PYTHONPATH"
   else
        loginfo "Setting up the Python Virtual Environment ..."
        # Virtualenv is in the distribution, no need to download it separately
        # we still want to redo the virtualenv
        rm -rf "$VENV"
        #"$WORKSPACE/${VIRTUALENV_VER}"/virtualenv.py --system-site-packages "$VENV"
        python3 -m venv --system-site-packages "$VENV"
        if ! . "$VENV"/bin/activate; then
            echo "ERROR virtualenv ($VENV) could not be activated.  Exiting"
            return 1
        fi

        # TODO; is this needed or done in activate?
        export PATH="$VENV/bin:$PATH"
        export PYTHONPATH="${WORKSPACE}:$PYTHONPATH"

        # Install dependencies first so we don't get incompatible ones
        # Following RPMs need to be installed on the machine:
        # pep8 has been replaced by pycodestyle
        # importlib and argparse are in std Python 3.6 (>=3.1)
        # leaving mock, anyway mock is std in Python 3.6 (>=3.3), as unittest.mock
        pip_packages="toml ${PYCODESTYLE} unittest2 ${COVERAGE} ${PYLINT} ${ASTROID}"
        pip_packages="$pip_packages pyyaml ${MOCK} xmlrunner jwt"
        pip_packages="$pip_packages ${HYPOTHESIS} ${AUTOPEP8} ${TESTFIXTURES}"
        pip_packages="$pip_packages ${HTCONDOR} ${JSONPICKLE} ${M2CRYPTO}"

        # TODO: load the list from requirements.txt

        # To avoid: Cache entry deserialization failed, entry ignored
        # curl https://bootstrap.pypa.io/get-pip.py | python3
        python3 -m pip install --quiet --upgrade pip

        failed_packages=""
        for package in $pip_packages; do
            loginfo "Installing $package ..."
            status="DONE"
            if ! python3 -m pip install --quiet "$package" ; then
                status="FAILED"
                failed_packages="$failed_packages $package"
            fi
            loginfo "Installing $package ... $status"
        done
        #try again if anything failed to install, sometimes its order
        NOT_FATAL="htcondor ${M2CRYPTO}"
        for package in $failed_packages; do
            loginfo "REINSTALLING $package"
            if ! python3 -m pip install "$package" ; then
                if [[ " ${NOT_FATAL} " == *" ${package} "* ]]; then
                    logerror "ERROR $package could not be installed.  Continuing."
                else
                    logerror "ERROR $package could not be installed.  Stopping venv setup."
                    return 1
                fi
            fi
        done
        #pip install M2Crypto==0.20.2

        SETUP_VENV3="${VENV}"
    fi

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
    export PYTHONPATH=${PYTHONPATH}:${GLIDEINWMS_SRC}/..

}

# TODO: to remove once there is no version with python2

SETUP_VENV2=
setup_python2_venv() {
    if [ $# -gt 1 ]; then
        echo "Invalid number of arguments to setup_python_venv. Will accept the location to install venv or use PWD as default"
        exit 1
    fi
    WORKSPACE=${1:-$(pwd)}

    if python --version 2>&1 | grep 'Python 2.6' > /dev/null ; then
        # Get latest packages that work with python 2.6
        PY_VER="2.6"
        VIRTUALENV_VER=virtualenv-12.0.7
        PYLINT='pylint==1.3.1'
        ASTROID='astroid==1.2.1'
        HYPOTHESIS="hypothesislegacysupport"
        AUTOPEP8="autopep8==1.3"
        TESTFIXTURES="testfixtures==5.4.0"
        # htcondor is not pip for python 2.6 (will be found from the RPM)
        HTCONDOR=
        COVERAGE="coverage==4.5.4"
        JSONPICKLE="jsonpickle==0.9"
        PYCODESTYLE="pycodestyle==2.4.0"
        MOCK="mock==2.0.0"
        M2CRYPTO="M2Crypto"
    else
        # use something more up-to-date
        PY_VER="2.7"
        VIRTUALENV_VER=virtualenv-16.0.0
        PYLINT='pylint==1.8.4'
        ASTROID='astroid==1.6.0'
        HYPOTHESIS="hypothesis"
        AUTOPEP8="autopep8"
        TESTFIXTURES="testfixtures"
        # Installing the pip version, in case the RPM is not installed
        HTCONDOR="htcondor"
        COVERAGE='coverage==4.5.4'
        JSONPICKLE="jsonpickle"
        PYCODESTYLE="pycodestyle"
        MOCK="mock==3.0.3"
        M2CRYPTO="M2Crypto==0.20.2"
    fi

    VIRTUALENV_TARBALL=${VIRTUALENV_VER}.tar.gz
    VIRTUALENV_URL="https://pypi.python.org/packages/source/v/virtualenv/$VIRTUALENV_TARBALL"
    #VIRTUALENV_EXE=$WORKSPACE/${VIRTUALENV_VER}/virtualenv.py
    VENV="$WORKSPACE/venv-$PY_VER"
    # Clearing PYTHONPATH to avoid interferences
    PYTHONPATH=

    # Following is useful for running the script outside jenkins
    if [ ! -d "$WORKSPACE" ]; then
        mkdir "$WORKSPACE"

    fi

    if [ "${SETUP_VENV2}" = "${VENV}" ]; then
        loginfo "Python Virtual Environment already installed. Reusing it"
        if ! . "$VENV"/bin/activate; then
            echo "ERROR existing virtualenv ($VENV) could not be activated.  Exiting"
            return 1
        fi
        export PYTHONPATH="${WORKSPACE}:$PYTHONPATH"
    else
        loginfo "Setting up Python Virtual Environment ..."
        if [ -f "$WORKSPACE/$VIRTUALENV_TARBALL" ]; then
            rm "$WORKSPACE/$VIRTUALENV_TARBALL"
        fi
        curl -L -o "$WORKSPACE/$VIRTUALENV_TARBALL" "$VIRTUALENV_URL"
        tar xzf "$WORKSPACE/$VIRTUALENV_TARBALL" -C "$WORKSPACE/"

        #if we download the venv tarball everytime we should remake the venv
        #every time
        rm -rf "$VENV"
        "$WORKSPACE/${VIRTUALENV_VER}"/virtualenv.py --system-site-packages "$VENV"
        if ! . "$VENV"/bin/activate; then
            echo "ERROR virtualenv ($VENV) could not be activated.  Exiting"
            return 1
        fi

	export PYTHONPATH="${WORKSPACE}:$PYTHONPATH"

        # Install dependancies first so we don't get uncompatible ones
        # Following RPMs need to be installed on the machine:
        # pep8 has been replaced by pycodestyle
        pip_packages="${PYCODESTYLE} unittest2 ${COVERAGE} ${PYLINT} ${ASTROID}"
        pip_packages="$pip_packages pyyaml ${MOCK}  xmlrunner future importlib argparse"
        pip_packages="$pip_packages ${HYPOTHESIS} ${AUTOPEP8} ${TESTFIXTURES}"
        pip_packages="$pip_packages ${HTCONDOR} ${JSONPICKLE} ${M2CRYPTO}"

        failed_packages=""
        for package in $pip_packages; do
            loginfo "Installing $package ..."
            status="DONE"
            if ! python -m pip install --quiet "$package"; then
                status="FAILED"
                failed_packages="$failed_packages $package"
            fi
            loginfo "Installing $package ... $status"
        done
        #try again if anything failed to install, sometimes its order
        NOT_FATAL="htcondor ${M2CRYPTO}"
        for package in $failed_packages; do
            loginfo "REINSTALLING $package"
            if ! python -m pip install "$package" ; then
                if [[ " ${NOT_FATAL} " == *" ${package} "* ]]; then
                    logerror "ERROR $package could not be installed.  Continuing."
                else
                    logerror "ERROR $package could not be installed.  Stopping venv setup."
                    return 1
                fi
            fi
        done


        SETUP_VENV2="$VENV"
    fi

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
    # Log Python info. Add HTML formatting if parameters are passed
    if [ $# -ne 0 ]; then
        br="<br/>"
        bo="<b>"
        bc="</b>"
        echo "<p>"
    fi
    echo "${bo}HOSTNAME:${bc} $(hostname -f)$br"
    if command -v lsb_release 2>/dev/null ; then
        echo "${bo}LINUX DISTRO:${bc} $(lsb_release -d)$br"
    else
        echo "${bo}LINUX DISTRO:${bc} no linux$br"
    fi
    echo "${bo}PYTHON LOCATION:${bc} $(which python)$br"
    echo "${bo}PYLINT:${bc} $(pylint --version)$br"
    echo "${bo}PEP8:${bc} $(pycodestyle --version)$br"
    [ $# -ne 0 ] && echo "</p>"
}


###############################################################################
# HTML inline CSS
HTML_TABLE="border: 1px solid black;border-collapse: collapse;"
HTML_THEAD="font-weight: bold;border: 0px solid black;background-color: #ffcc00;"
HTML_THEAD_TH="border: 0px solid black;border-collapse: collapse;font-weight: bold;background-color: #ffb300;padding: 8px;"

HTML_TH="border: 0px solid black;border-collapse: collapse;font-weight: bold;background-color: #00ccff;padding: 8px;"
HTML_TR="padding: 5px;text-align: center;"
HTML_TD="border: 1px solid black;border-collapse: collapse;padding: 5px;text-align: center;"

HTML_TR_PASSED="padding: 5px;text-align: center;"
HTML_TD_PASSED="border: 0px solid black;border-collapse: collapse;background-color: #00ff00;padding: 5px;text-align: center;"

HTML_TR_FAILED="padding: 5px;text-align: center;"
HTML_TD_FAILED="border: 0px solid black;border-collapse: collapse;background-color: #ff0000;padding: 5px;text-align: center;"


###########################
# Email functions
###########################

EMAIL_FILE=
mail_init() {
    [ -z "$1" ] && { logwarn "Email file not provided. Skipping it"; return; }
    EMAIL_FILE="$1"
    # Reset and initialize the file
    echo "<body>" > "${EMAIL_FILE}"
}

mail_add() {
    [ -z "${EMAIL_FILE}" ] && return
    echo "$1" >> "${EMAIL_FILE}"
}

mail_close() {
    mail_add "</body>"
}

mail_send() {
    [ -z "${EMAIL_FILE}" ] && { logwarn "Empty email file. Not sending it"; return; }
    local subject="${1:-"GlideinWMS CI results"}"
    echo "From: gwms-builds@donot-reply.com;
To: marcom@fnal.gov;
Subject: $subject;
Content-Type: text/html;
MIME-VERSION: 1.0;
;
$(cat "${EMAIL_FILE}")
" | sendmail -t
}


# TODO: used only by python2 tests, to remove once no more needed
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

