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
    declare -i total_error=0
    declare -i total_warning=0
    declare -i total_info=0
    declare -i total_style=0
    if ! cd "${GLIDEINWMS_SRC}"; then
        echo "Cannot cd into GlideinWMS source directory" >&2
        return
    fi
    CURR_BRANCH="$(git rev-parse --abbrev-ref HEAD)"
    mkdir -p "${WORKSPACE}/${LOGDIR}/${CURR_BRANCH}"

    echo "#####################################################"
    echo "Start : ${CURR_BRANCH}"
    start_time="$(date -u +%s.%N)"

    # Run shellcheck on each bash script. Any issues is logged in a
    # file-specific JSON log. The test fails if any SC issue of level
    # 'error' is found; 'warning' maps to warning, whereas 'info' and
    # 'style' are not considered problems (but are still reported).
    while read -r filename
    do
        echo "-----------------------------------------------------"
        echo "Scanning: $filename"
        # TODO: protect against scripts in different directories w/ same file name
        out_file="${WORKSPACE}/${LOGDIR}/${CURR_BRANCH}/$(basename "${filename%.*}").json"
        [[ -e "$out_file" ]] && echo "WARNING: duplicate file name, overwriting checks: $out_file"
        # shellcheck disable=SC2086
        sc_out=$(shellcheck ${SC_OPTIONS} "${filename}" 2>/dev/null)
        if command -v jq >/dev/null 2>&1; then
            echo "$sc_out" | jq . > "$out_file"

            # Issues per category in this file
            n_issues=$(jq '. | length' "$out_file")
            n_style=$(cat ${out_file} | grep -c '"level": "style"')
            n_info=$(cat ${out_file} | grep -c '"level": "info"')
            n_warning=$(cat ${out_file} | grep -c '"level": "warning"')
            n_error=$(cat ${out_file} | grep -c '"level": "error"')

            # Update issues global counters
            total_issues=$((total_issues + n_issues))
            total_error=$((total_error + n_error))
            total_warning=$((total_warning + n_warning))
            total_info=$((total_info + n_info))
            total_style=$((total_style + n_style))

            # Show issues statistics
            echo "Total Issues: $n_issues"
            echo " -Error:      $n_error"
            echo " -Warning:    $n_warning"
            echo " -Info:       $n_info"
            echo " -Style:      $n_style"

            # Highlight the presence of error/warnings (makes search easier)
            if (( n_error > 0 )); then
                echo "Error found!"
            fi
            if (( n_warning > 0 )); then
                echo "Warning found!"
            fi
        else
            # Without jq, JSON cannot be prettified and counters would not work
            echo "$sc_out" > "$out_file"
        fi
    done <<< "$(find . -name '*.sh' -o -name '*.source')"

    if (( total_error > 0 )); then
        return_status="Failed"
    elif (( total_warning > 0 )); then
        return_status="Warning"
    else
        return_status="Passed"
    fi

    end_time="$(date -u +%s.%N)"
    elapsed="$(bc <<< "scale=2; (${end_time}-${start_time})/1")"
    echo
    echo "-----------------------------------------------------"
    echo "All the files have been analyzed"
    echo "Total issues: $total_issues"
    echo " -Error:      $total_error"
    echo " -Warning:    $total_warning"
    echo " -Info:       $total_info"
    echo " -Style:      $total_style"
    echo "# Test #: ${CURR_BRANCH} .... ${return_status}   ${elapsed} s"
}

###################################
# CONFIGURABLE SHELLCHECK OPTIONS #
###################################

SC_SHELL="-s bash"

#SC_FORMAT="-f checkstyle"
SC_FORMAT="-f json"

SC_IGNORE=
# 'Can't follow non-constant source. Use a directive to specify location.'
SC_IGNORE="$SC_IGNORE -e SC1090"
# 'Not following: (error message here)'
SC_IGNORE="$SC_IGNORE -e SC1091"
# 'var is referenced but not assigned.'
SC_IGNORE="$SC_IGNORE -e SC2154"

SC_OPTIONS="$SC_OPTIONS $SC_SHELL $SC_FORMAT $SC_IGNORE"

####################################
#         CI PARAMETERS            #
####################################

WORKSPACE="$(pwd)"
export GLIDEINWMS_SRC="${WORKSPACE}"/glideinwms
LOGDIR="SC_logs"

####################################

if [ ! -e  "${GLIDEINWMS_SRC}" ]; then
    echo "ERROR: ${GLIDEINWMS_SRC} not found!"
    echo "script running in $(pwd), expects a git managed glideinwms subdirectory"
    echo "exiting"
    exit 1
fi

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
