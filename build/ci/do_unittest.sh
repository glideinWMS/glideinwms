#!/bin/bash

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

# Shell source file to be sourced to run Python unit tests and coverage (shebang added for linting purposes)
# To be used only inside runtest.sh (runtest.sh and util.sh functions defined, VARIABLES available)
# All function names start with do_...

UNITTEST_TIMEOUT=10m

do_help_msg() {
  cat << EOF
${COMMAND} command:
${filename} [options] ${COMMAND} [other command options] TEST_FILES
  Runs the unit tests on TEST_FILES files in glidinwms/unittests/
${filename} [options] ${COMMAND} -a [other command options]
  Run the unit tests on all the files in glidinwms/unittests/ named test_*
Runs unit tests and exit the results to standard output. Failed tests will cause also a line starting with ERROR.
Command options:
  -h        print this message
  -a        run on all unit tests (see above)
  -c        generate a coverage report while running unit tests
EOF
}

LIST_FILES=
RUN_COVERAGE=

do_parse_options () {
    while getopts ":hac" option
    do
      case "${option}"
      in
      h) help_msg; do_help_msg; exit 0;;
      a) LIST_FILES=yes;;
      c) RUN_COVERAGE=yes;;
      : ) logerror "illegal option: -$OPTARG requires an argument"; help_msg 1>&2; exit 1;;
      *) logerror "illegal option: -$OPTARG"; help_msg 1>&2; exit 1;;
      ##\?) logerror "illegal option: -$OPTARG"; help_msg 1>&2; exit 1;;
      esac
    done

    shift $((OPTIND-1))

    CMD_OPTIONS="$@"

    if [[ -n "${SHOW_FLAGS}" ]]; then
        do_show_flags
        TEST_COMPLETE=branch
    fi
}

do_use_python() { true; }

do_show_flags() {
    SOURCES="$(get_source_directories .. )"
    if [[ -n "$RUN_COVERAGE" ]]; then
        echo "Coverage will run Python unittest as (timeout ${UNITTEST_TIMEOUT}):"
        echo 'coverage run --source="'"${SOURCES}"'" --omit="test_*.py"  -a TESTFILE'
    else
        echo "Python unittest will run as (timeout ${UNITTEST_TIMEOUT}):"
        echo "./TESTFILE"
    fi
}

do_count_failures() {
    # Counts the failures using bats output (print format)
    # Uses implicit $file (test file) $tmp_out (stdout form test execution)
    # 1 - test execution exit code
    # BATS exit codes
    # 0 - no failed tests
    # 1 - failed tests
    # >1 - execution error (e.g. 126 wrong permission)
    [[ $1 -eq 0 ]] && return  # should not have been called w/ exit code 0
    fail=0
    fail_files_list="$fail_files_list $file"
    local tmp_fail=
    if [[ $1 -eq 1 ]]; then
        lline="$(echo "$tmp_out" | grep "FAILED (")"
        if [[ "$lline" == "FAILED ("* ]]; then
            tmp_fail="${lline##*=}"
            fail=${tmp_fail%)}
            #(echo "$lline" | cut -f3 -d' ')
        fi
    fi
    fail_files=$((fail_files + 1))
    fail_all=$((fail_all + fail))
    if [[ $1 -eq 124 ]]; then
        logerror "Test $file failed ($1): $fail failed tests, likely timeout"
    else
        logerror "Test $file failed ($1): $fail failed tests"
    fi
    return $1
}

do_process_branch() {
    # 1 - branch
    # 2 - output file (output directory/output.branch)
    # 3... - files to process (optional)
    #

    if ! cd unittests ; then
        logexit "cannot find the test directory './unittests', exiting"
    fi

    local branch="$1"
    local branch_no_slash=$(echo "${1}" | sed -e 's/\//_/g')
    local outfile="$2"
    local out_coverage="${outfile}.coverage_report"
    local out_cov_html="${outfile}.coverage_html.d"
    local outdir="$(dirname "$2")"
    local outfilename="$(basename "$2")"
    # test_outdir defined and created below
    shift 2

    # Example file lists (space separated list)
    #files="test_frontend.py"
    #files="test_frontend_element.py"
    #files="test_frontend.py test_frontend_element.py"
    local files_list
    if [[ -n "$LIST_FILES" ]]; then
        #files_list="$(find . -readable -name  'test_*.py' -print)"
        files_list="$(get_files_pattern "test_*.py")"
    else
        #files_list="$*"
        files_list=""
        for file in "$@"; do
            if [[ ! -e "$file" && "$(dirname "$file")" == */unittests ]]; then
                files_list="$files_list $(basename "$file")"
            else
                files_list="$files_list $file"
            fi
        done
    fi

    print_files_list "Python will use the following unit test files:" "${files_list}" && return

    local test_date=$(date "+%Y-%m-%d %H:%M:%S")
    SOURCES="$(get_source_directories .. )"
    local test_outdir="${outfile}.d"
    mkdir -p "${test_outdir}"

    [[ -n "$RUN_COVERAGE" ]] && coverage erase

    local -i fail=0
    local -i fail_files=0
    local -i fail_all=0
    local fail_files_list=
    local tmp_out=
    local tmp_out_file=
    local -i tmp_exit_code
    local -i exit_code
    for file in ${files_list} ; do
        loginfo "Testing: $file"
#        if [[ -n "$RUN_COVERAGE" ]]; then
#            tmp_out="$(coverage run   --source="${SOURCES}" --omit="test_*.py"  -a "$file")" || log_verbose_nonzero_rc "$file" $?
#        else
#            tmp_out="$(./"$file")" || log_verbose_nonzero_rc "$file" $?
#        fi
        if [[ -n "$RUN_COVERAGE" ]]; then
            tmp_out="$($COMPCMD_TIMEOUT $UNITTEST_TIMEOUT coverage run --source="${SOURCES}" --omit="test_*.py"  -a "$file" 2>&1)" || do_count_failures $?
        else
            tmp_out="$($COMPCMD_TIMEOUT $UNITTEST_TIMEOUT ./"$file" 2>&1)" || do_count_failures $?
        fi
        tmp_exit_code=$?
        [[ ${tmp_exit_code} -gt ${exit_code} ]] && exit_code=${tmp_exit_code}

        # tmp_out_file="${test_outdir}/$(basename "${file%.*}").txt"
	    # To accommodate the flat list of files in CI the dir name is in the file name
	    tmp_out_file="${test_outdir}/$(basename ${test_outdir}).$(basename "${file%.*}").txt"
        [[ -e "$tmp_out_file" ]] && logwarn "duplicate file name, overwriting tests results: $tmp_out_file"
        echo "$tmp_out" > "${tmp_out_file}"

    done

    if [[ -n "$RUN_COVERAGE" ]]; then
        TITLE="GlideinWMS Coverage Report for branch $branch on $test_date"
        coverage report > "${out_coverage}"
        coverage html --title "$TITLE" || logwarn "coverage html report failed"
        if [[ -d htmlcov ]]; then
            mv htmlcov "${out_cov_html}"
        else
            # To help troubleshooting the coverage failure
            logwarn "no html coverage report generated for $branch_no_slash on $(hostname)"
            command -v coverage || logwarn "no path - coverage not installed"
            coverage --version || logwarn "no version - coverage not installed"
        fi
    fi

    echo "# Python unittest output" > "${outfile}"
    echo "PYUNITTEST_FILES_CHECKED=\"${files_list}\"" >> "${outfile}"
    echo "PYUNITTEST_FILES_CHECKED_COUNT=`echo ${files_list} | wc -w | tr -d " "`" >> "${outfile}"
    echo "PYUNITTEST_ERROR_FILES=\"${fail_files_list# }\"" >> "${outfile}"
    echo "PYUNITTEST_ERROR_FILES_COUNT=${fail_files}" >> "${outfile}"
    PYUNITTEST_ERROR_COUNT=${fail_all}
    echo "PYUNITTEST_ERROR_COUNT=${PYUNITTEST_ERROR_COUNT}" >> "${outfile}"
    echo "$(get_commom_info "$branch")" >> "${outfile}"
    echo "PYUNITTEST=$(do_get_status)" >> "${outfile}"
    echo "----------------"
    cat "${outfile}"
    echo "----------------"

    return ${exit_code}

}

do_table_headers() {
    # Tab separated list of fields
    # example of table header 2 fields available start with ',' to keep first field from previous item
    echo -e "UnitTest,Files\t,ErrFiles\t,ErrNum"
}

do_table_values() {
    # 1. branch summary file
    # 2. output format: if not empty triggers annotation
    # Return a tab separated list of the values
    # $VAR1 $VAR2 $VAR3 expected in $1
    # If the summary file is missing return tab separated "na" strings
    [[ -n "$1" ]] && . "$1" || { echo -e "na\tna\tna"; return; }
    if [[ "$2" = NOTAG ]]; then
        echo -e "${PYUNITTEST_FILES_CHECKED_COUNT}\t${PYUNITTEST_ERROR_FILES_COUNT}\t${PYUNITTEST_ERROR_COUNT}"
    else
        local res="${PYUNITTEST_FILES_CHECKED_COUNT}\t"
        res="${res}$(get_annotated_value check0 ${PYUNITTEST_ERROR_FILES_COUNT})\t"
        echo -e "${res}$(get_annotated_value check0 ${PYUNITTEST_ERROR_COUNT})"
    fi
}

do_get_status() {
    # 1. branch summary file (optional if the necessary variables are provided)
    # Return unknown, success, warning, error
    [[ -n "$1" ]] && . "$1"
    [[ -z "${PYUNITTEST_ERROR_COUNT}" ]] && { echo unknown; return 2; }
    [[ "${PYUNITTEST_ERROR_COUNT}" -eq 0 ]] && { echo success; return; }
    echo error
    return 1
}
