# Shell source file to be sourced to run Python unit tests and coverage
# To be used only inside runtest.sh (runtest.sh and util.sh functions defined, VARIABLES available)
# All function names start with do_...

do_help_msg() {
  cat << EOF
${COMMAND} command:
  Run shellcheck and output the results to standard output
${filename} [options] ${COMMAND} [other command options] TEST_FILES
  Run shellcheck on TEST_FILES files in glidinwms/
${filename} [options] ${COMMAND} -a [other command options]
  Run shellcheck on all the shell files in glidinwms/
Command options:
  -h        print this message
  -a        run on all shell scripts (see above)
  -l        show the list of files checked
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
    while getopts ":ha" option
    do
      case "${option}"
      in
      h) help_msg; do_help_msg; exit 0;;
      a) LIST_FILES=yes;;
      : ) logerror "illegal option: -$OPTARG requires an argument"; help_msg 1>&2; do_help_msg 1>&2; exit 1;;
      *) logerror "illegal option: -$OPTARG"; help_msg 1>&2; do_help_msg 1>&2; exit 1;;
      ##\?) logerror "illegal option: -$OPTARG"; help_msg 1>&2; exit 1;;
      esac
    done

    shift $((OPTIND-1))

    CMD_OPTIONS="$@"

    if ! do_check_requirements; then
        logexit "Essential software is missing. Aborting"
    fi

    if [[ -n "${RUN_COVERAGE}" ]] && ! command -v kcov > /dev/null; then
        # kcov not available
        logwarn "kcov is not available, disabling coverage"
        RUN_COVERAGE=
    fi

    if [[ -n "${SHOW_FLAGS}" ]]; then
        do_show_flags
        TEST_COMPLETE=branch
    fi
}

do_get_dependencies() { true; }

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
    # 3... - files to process (optional)
    #
    # TODO: add coverage test w/ kcov: https://github.com/SimonKagstrom/kcov

    local branch="$1"
    local branch_no_slash=$(echo "${1}" | sed -e 's/\//_/g')
    local outfile="$2"
    local outdir="$(dirname "$2")"
    local outfilename="$(basename "$2")"
    # test_outdir defined and created below
    shift 2

    local file_list
    if [[ -n "$LIST_FILES" ]]; then
        files_list="$(get_shell_files)"
    else
        files_list="$*"
    fi

    print_files_list "Shellcheck will inspect the following files:" "${files_list}" && return

    local test_date=$(date "+%Y-%m-%d %H:%M:%S")

    local fail=0

    declare -i total_issues=0
    declare -i total_error=0
    declare -i total_warning=0
    declare -i total_info=0
    declare -i total_style=0
    local fail_files_list=
    local test_outdir="${outfile}.d"
    mkdir -p "${test_outdir}"

    echo "#####################################################"
    echo "Start : ${branch}"
    start_time="$(date -u +%s.%N)"

    # Run shellcheck on each bash script. Any issues is logged in a
    # file-specific JSON log. The test fails if any SC issue of level
    # 'error' is found; 'warning' maps to warning, whereas 'info' and
    # 'style' are not considered problems (but are still reported).
    #while read -r filename
    for pfile in ${files_list}
    do
        echo "-----------------------------------------------------"
        echo "Scanning: ${pfile}"
        [ -z "${pfile}" ] && { echo "Empty file to process: ${pfile} (of: ${files_list})" >&2; exit 1; }
        # TODO: protect against scripts in different directories w/ same file name
        out_file="${test_outdir}/$(basename "${test_outdir}").$(basename "${pfile%.*}").json"
        [[ -e "$out_file" ]] && logwarn "duplicate file name, overwriting checks: $out_file"
        # shellcheck disable=SC2086
        sc_out=$(shellcheck ${SC_OPTIONS} "${pfile}" 2>/dev/null)
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
                fail_files_list="$fail_files_list $pfile"
            fi
            if (( n_warning > 0 )); then
                echo "Warning found!"
            fi
        else
            # Without jq, JSON cannot be prettified and counters would not work
            echo "$sc_out" > "$out_file"
        fi
    done
    #done <<< "$(get_shell_files)"

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
    echo "# Test #: ${branch} .... ${return_status}   ${elapsed} s"

    echo "# Shellcheck output" >> "${outfile}"
    echo "SHELLCHECK_FILES_CHECKED=\"${files_list}\"" >> "${outfile}"
    echo "SHELLCHECK_FILES_CHECKED_COUNT=$(echo ${files_list} | wc -w | tr -d " ")" >> "${outfile}"
    echo "SHELLCHECK_ERROR_FILES=\"${fail_files_list}\"" >> "${outfile}"
    echo "SHELLCHECK_ERROR_FILES_COUNT=$(echo ${fail_files_list} | wc -w | tr -d " ")" >> "${outfile}"
    echo "SHELLCHECK_ERROR_COUNT=${total_error}" >> "${outfile}"
    echo "SHELLCHECK_WARNING_COUNT=${total_warning}" >> "${outfile}"
    echo "SHELLCHECK_INFO_COUNT=${total_info}" >> "${outfile}"
    echo "SHELLCHECK_STYLE_COUNT=${total_style}" >> "${outfile}"
    echo "----------------"
    cat "${outfile}"
    echo "----------------"

    # Return the error count
    #[[ $total_error -gt 0 ]] && fail=1
    fail=$total_error
    return ${fail}
}

do_table_headers() {
    # Tab separated list of fields
    # example of table header 2 fields available start with ',' to keep first field from previous item 
    echo -e "ShellCheck,ErrFiles\t,ErrNum"
}

do_table_values() {
    # 1. branch summary file
    # 2. output format html,htnl4,html4f or empty for text (see util.sh/get_html_td )
    # Return a tab separated list of the values
    # $VAR1 $VAR2 $VAR3 expected in $1
    . "$1"
    if [[ "$2" == html* ]]; then
        local class=
        local res="<td $(get_html_td check0 $2 ${SHELLCHECK_ERROR_FILES_COUNT})>${SHELLCHECK_ERROR_FILES_COUNT}</td>\t"
        echo -e "${res}<td $(get_html_td check0 $2 ${SHELLCHECK_ERROR_COUNT})>${SHELLCHECK_ERROR_COUNT}</td>"
    else
        echo -e "${SHELLCHECK_ERROR_FILES_COUNT}\t${SHELLCHECK_ERROR_COUNT}"
    fi
}


do_get_status() {
    # 1. branch summary file
    # Return unknown, success, warning, error
    . "$1"
    [[ -z "${SHELLCHECK_ERROR_COUNT}" ]] && { echo unknown; return 2; }
    [[ "${SHELLCHECK_ERROR_COUNT}" -eq 0 ]] && { echo success; return; }
    echo error
    return 1
}
