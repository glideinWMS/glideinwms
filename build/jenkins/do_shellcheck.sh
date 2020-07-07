# Shell source file to be sourced to run Python unit tests and coverage
# To be used only inside runtest.sh (runtest.sh and util.sh functions defined, VARIABLES available)
# All function names start with do_...

do_help_msg() {
  cat << EOF
${COMMAND} command:
  Run shellcheck and exit the results to standard output
${filename} [options] ${COMMAND} [other command options] TEST_FILES
  Runs shellcheck on TEST_FILES files in glidinwms/
${filename} [options] ${COMMAND} -a [other command options]
  Run shellcheck on all the shell files in glidinwms/
Command options:
  -h        print this message
  -a        run on all shell scripts (see above)
  -n        show the list of flags passed to shellcheck
EOF
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

LIST_FILES=

do_show_flags() {
    echo "Shellcheck will run with options:"
    echo "$SC_OPTIONS"
}

do_parse_options() {
    while getopts ":han" option
    do
      case "${option}"
      in
      h) help_msg; do_help_msg; exit 0;;
      a) LIST_FILES=yes;;
      n) do_show_flags; exit 0;;
      : ) logerror "illegal option: -$OPTARG requires an argument"; help_msg 1>&2; do_help_msg 1>&2; exit 1;;
      *) logerror "illegal option: -$OPTARG"; help_msg 1>&2; do_help_msg 1>&2; exit 1;;
      ##\?) logerror "illegal option: -$OPTARG"; help_msg 1>&2; exit 1;;
      esac
    done

    shift $((OPTIND-1))

    CMD_OPTIONS="$@"

    if ! command -v kcov > /dev/null; then
        # kcov not available
        logwarn "kcov is not available, disabling coverage"
        RUN_COVERAGE=
    fi
}

do_get_dependencies() { pass; }

do_git_init_command() { git submodule update --init --recursive; }

do_check_requirements() {
    if ! command -v shellcheck > /dev/null 2>&1; then
        logerror "shellcheck not available"
        false
        return
    fi
    if ! command -v jq >/dev/null 2>&1; then
        logwarn "jq command not found"
        logwarn "shellcheck tests will run anyway, but without computing the total number of errors"
    fi
}

do_process_branch() {
    # 1 - branch
    # 2 - output file (output directory/output.branch)
    #
    # TODO: add coverage test w/ kcov: https://github.com/SimonKagstrom/kcov

    if ! cd test/bats ; then
        logexit "cannot find the test directory './test/bats', in $(pwd), exiting"
    fi
    local branch="$1"
    local outdir="$(dirname "$2")"
    local outfile="$(basename "$2")"
    local branch_noslash="${outfile#*.}"
    shift 2
    local test_date=$(date "+%Y-%m-%d %H:%M:%S")
    #SOURCES="$(get_source_directories)"

    local file_list
    if [[ -n "$LIST_FILES" ]]; then
        files_list="$(find . -readable -name  '*.bats' -print)"
    else
        files_list="$*"
    fi

    local fail
    local fail_all=0

    declare -i total_issues=0
    declare -i total_error=0
    declare -i total_warning=0
    declare -i total_info=0
    declare -i total_style=0
    local branch_outdir="${outdir}/${branch_noslash}"
    mkdir -p "${branch_outdir}

    echo "#####################################################"
    echo "Start : ${branch}"
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
        out_file="${branch_outdir}/$(basename "${filename%.*}").json"
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
    done <<< "$(get_shell_files)"

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

    fail_all=0
    [[ $total_error -gt 0 ]] && fail_all=1
    return ${fail_all}
}
