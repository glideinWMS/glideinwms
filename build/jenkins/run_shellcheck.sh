#!/bin/bash
# ShellCheck: linter for bash scripts

usage() {
    echo "usage: $(basename "$0") check|usage"
    echo "     check: run shellcheck on all bash scripts in ${GLIDEINWMS_SRC}"
    echo "     flags: show the list of flags passed to shellcheck"
    echo "     usage: this message"
    exit 0
}

show_flags() {
    echo "Shellcheck will run with options:"
    echo "$SC_OPTIONS"
}

process_branch() {

    show_flags

    declare -i total_issues=0
    if ! cd "${GLIDEINWMS_SRC}"; then
        echo "Cannot cd into GlideinWMS source directory" >&2
        return
    fi
    CURR_BRANCH="$(git rev-parse --abbrev-ref HEAD)"
    mkdir -p "${WORKSPACE}/${LOGDIR}/${CURR_BRANCH}"

    while read -r filename
    do
        echo "Scanning: $filename"
        out_file="${WORKSPACE}/${LOGDIR}/${CURR_BRANCH}/$(basename "${filename%.*}").json"
        # shellcheck disable=SC2086
        sc_out=$(shellcheck ${SC_OPTIONS} "${filename}" 2>/dev/null)
        if command -v jq >/dev/null 2>&1; then
            echo "$sc_out" | jq . > "$out_file"
            n_issues=$(jq '. | length' "$out_file")
            echo "Found issues: $n_issues"
            total_issues=$((total_issues + n_issues))
        else
            echo "$sc_out" > "$out_file"
        fi
    done <<< "$(find . -name '*.sh' -o -name '*.source')"
    echo "Total: $total_issues"
}

###################################
# CONFIGURABLE SHELLCHECK OPTIONS #
###################################

SC_SHELL="-s bash"

#SC_FORMAT="-f checkstyle"
SC_FORMAT="-f json"

SC_IGNORE=
SC_IGNORE="$SC_IGNORE -e SC1090"
SC_IGNORE="$SC_IGNORE -e SC1091"
SC_IGNORE="$SC_IGNORE -e SC2154"

SC_OPTIONS="$SC_OPTIONS $SC_SHELL $SC_FORMAT $SC_IGNORE"

####################################
#         CI PARAMETERS            #
####################################

WORKSPACE="$(pwd)"
export GLIDEINWMS_SRC="${WORKSPACE}"/glideinwms
LOGDIR="SC_logs"

####################################

if [ ! -e  "${GLIDEINWMS_SRC}/build/jenkins/utils.sh" ]; then
    echo "ERROR: ${GLIDEINWMS_SRC}/build/jenkins/utils.sh not found!"
    echo "script running in $(pwd), expects a git managed glideinwms subdirectory"
    echo "exiting"
    exit 1
fi

if ! . "${GLIDEINWMS_SRC}"/build/jenkins/utils.sh ; then
    echo "ERROR: ${GLIDEINWMS_SRC}/build/jenkins/utils.sh contains errors!"
    echo "exiting"
    exit 1
fi

if ! command -v shellcheck >/dev/null 2>&1; then
    echo "ERROR: shellcheck command not found!"
    echo "exiting"
    exit 1
fi

if ! command -v jq >/dev/null 2>&1; then
    echo "WARNING: jq command not found"
    echo "shellcheck tests will run anyway, but without computing the total number of errors"
fi

case "$1" in
    check) process_branch;;
    flags) show_flags;;    
    *) usage;;
esac
