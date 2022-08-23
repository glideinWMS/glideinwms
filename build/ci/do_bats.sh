#!/bin/bash

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

# Shell source file to be sourced to run Python unit tests and coverage (shebang added for linting purposes)
# To be used only inside runtest.sh (runtest.sh and util.sh functions defined, VARIABLES available)
# All function names start with do_...

do_help_msg() {
  cat << EOF
${COMMAND} command:
  Run unit tests and exit the results to standard output. Failed tests will cause also a line starting with ERROR.
${filename} [options] ${COMMAND} [other command options] TEST_FILES
  Runs the BATS unit tests on TEST_FILES files in glidinwms/test/bats/
${filename} [options] ${COMMAND} -a [other command options]
  Run the unit tests on all the files in glidinwms/test/bats/ named *.bats
Command options:
  -h        print this message
  -a        run on all unit tests (see above)
  -t        Test Anything Protocol (TAP) output format (the default is human readable)
  -c        generate a coverage report while running unit tests (requires kcov)
  -k TOUT   set a timeout of TOUT seconds for the execution of each test (BATS file).
            A TERM signal is sent if the test is still running after TOUT seconds and a
            hard kill (KILL signal) is sent 20 seconds after that if the test did not end
EOF
}

do_show_flags() {
    echo "BATS will run with options:"
    echo "$BATSOPT"
}

LIST_FILES=
RUN_COVERAGE=
BATSOPT=
TIMEOUT=
# delay after which the hard timeout will be triggered
HARD_TIMEOUT_DELAY=20

do_parse_options() {
    while getopts ":hatck:" option
    do
      case "${option}"
      in
      h) help_msg; do_help_msg; exit 0;;
      a) LIST_FILES=yes;;
      t) BATSOPT="-t";;
      c) RUN_COVERAGE=yes;;
      k) TIMEOUT=${OPTARG};;
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
    if ! command -v bats > /dev/null 2>&1; then
        logerror "bats not available"
        false
        return
    fi
    for i in $(do_get_dependencies); do
        [[ -e "$i" ]] || logwarn "unable to find BATS test dependency '$i'"
    done
}

do_count_failures_tap() {
    # Counts the failures using bats output (TAP format)
    #    1..N - start line
    #    ok N - test passed
    #    not ok N - test failed
    # Uses implicit $file (test file) $tmp_out (stdout form test execution)
    # 1 - test execution exit code
    # BATS exit codes
    # 0 - no failed tests
    # 1 - failed tests
    # >1 - execution error (e.g. 126 wrong permission)
    [[ $1 -eq 0 ]] && return  # should not have been called w/ exit code 0
    local fail=0
    fail_files_list="$fail_files_list $file"
    if [[ $1 -eq 1 ]]; then
        fail="$(echo "$tmp_out" | grep -c "^not ok")"
    elif [[ $1 -gt 123 ]]; then
            # timed out tests
         fail=1
         echo "-> Timeout of ${TIMEOUT}s triggered while executing test.."
         if [[ $1 -eq 137 ]]; then
             # hardly timed out tests
             echo "-> Timeout signal wasn't able to stop the test.."
             echo "-> Hard timeout triggered after ${HARD_TIMEOUT_DELAY}s.."
         fi
         timed_out_files=$((timed_out_files + 1))
     fi
    fail_files=$((fail_files + 1))
    fail_all=$((fail_all + fail))
    logerror "Test $file failed ($1): $fail failed tests, $timed_out_files timed out tests."
    return $1
}

do_count_failures() {
    # Counts the failures using bats output (print and TAP format). TAP:
    #    1..N - start line
    #    ok N - test passed
    #    not ok N - test failed
    # Uses implicit $file (test file) $tmp_out (stdout form test execution)
    # 1 - test execution exit code
    # BATS exit codes
    # 0 - no failed tests
    # 1 - failed tests
    # >1 - execution error (e.g. 126 wrong permission)
    # return
    #  test execution exit code (1.)
    #  side effect on fail_files, fail_all
    [[ $1 -eq 0 ]] && return  # should not have been called w/ exit code 0
    local fail=0
    local lline
    fail_files_list="$fail_files_list $file"
    if [[ $1 -eq 1 ]]; then
        if [[ "$tmp_out" = "1.."* ]]; then
            # TAP format
            fail="$(echo "$tmp_out" | grep -c "^not ok")"
        else
            # Summary line like: 24 tests, 1 failure, 1 skipped (failure or failures depending on number)
            lline="$(echo "$tmp_out" | tail -n2 | grep failure)"
            if [[ -n "$lline" ]]; then
                fail=$(echo "$lline" | cut -f3 -d' ')
            fi
        fi
    elif [[ $1 -gt 123 ]]; then
        # timed out tests
        fail=1
        echo "-> Timeout of ${TIMEOUT}s triggered while executing test.."
        if [[ $1 -eq 137 ]]; then
            # hardly timed out tests
            echo "-> Timeout signal wasn't able to stop the test.."
            echo "-> Hard timeout triggered after ${HARD_TIMEOUT_DELAY}s.."
        fi
        timed_out_files=$((timed_out_files + 1))
    fi
    fail_files=$((fail_files + 1))
    fail_all=$((fail_all + fail))
    logerror "Test $file failed ($1): $fail failed tests, $timed_out_files timed out tests."
    return $1
}

do_process_branch() {
    # 1 - branch
    # 2 - output file (output directory/output.branch)
    # 3... - files to process (optional)
    #
    # TODO: add coverage test w/ kcov: https://github.com/SimonKagstrom/kcov

    local start_dir="$(pwd)"
    if ! cd test/bats ; then
        logexit "cannot find the test directory './test/bats', in $(pwd), exiting"
    fi
    local branch="$1"
    local branch_no_slash=$(echo "${1}" | sed -e 's/\//_/g')
    local outfile="$2"
    local out_coverage="${outfile}.coverage"
    local outdir="$(dirname "$2")"
    local outfilename="$(basename "$2")"
    shift 2
    local test_date=$(date "+%Y-%m-%d %H:%M:%S")
    # TODO: For now sources are only in creation/web_base, include other ones
    SOURCES="$GLIDEINWMS_SRC"/creation/web_base

    local file_list
    if [[ -n "$LIST_FILES" ]]; then
        files_list="$(get_files_pattern "*.bats" "lib")"
    else
        files_list="$*"
    fi

    if print_files_list "Bats will use the following test files:" "${files_list}"; then
        cd "${start_dir}"
        return
    fi

    local -i fail=0
    local -i fail_files=0
    local -i fail_all=0
    local -i timed_out_files=0
    local fail_files_list=
    local tmp_out=
    local -i tmp_exit_code
    local -i exit_code
    local test_outdir="${outfile}.d"
    mkdir -p "${test_outdir}"
    local timeout_cmd=
    # define the prefix to the command if the timout is set (prefix: 'timeout [--kill-after=HARD_DELAY] DELAY command')
    if [[ -n ${TIMEOUT} ]]; then
        timeout_cmd="timeout --kill-after=${HARD_TIMEOUT_DELAY} ${TIMEOUT}  "
    fi
    for file in ${files_list} ; do
        loginfo "Testing: $file"
        out_file="${test_outdir}/$(basename "${test_outdir}").$(basename "${file%.*}").txt"
        [[ -e "$out_file" ]] && logwarn "duplicate file name, overwriting test results: $out_file"
#            if [[ -n "$RUN_COVERAGE" ]]; then
#                kcov --include-path="${SOURCES}" "$out_coverage"  ./"$file" ${BATSOPT} || log_nonzero_rc "$file" $?
#            else
#                ./"$file" ${BATSOPT} || log_nonzero_rc "$file" $?
#            fi
        # The prefix will not be considered if the timeout was not set
        if [[ -n "$RUN_COVERAGE" ]]; then
            tmp_out="$(${timeout_cmd} kcov --include-path="${SOURCES}" "$out_coverage" "$file" -p ${BATSOPT})" || do_count_failures $?
        else
            tmp_out="$(${timeout_cmd} ./"$file" -p ${BATSOPT})" || do_count_failures $?
        fi
        tmp_exit_code=$?
        [[ ${tmp_exit_code} -gt ${exit_code} ]] && exit_code=${tmp_exit_code}
        echo "$tmp_out" > "$out_file"
    done

    echo "# BATS output" > "${outfile}"
    echo "BATS_FILES_CHECKED=\"${files_list}\"" >> "${outfile}"
    echo "BATS_FILES_CHECKED_COUNT=`echo ${files_list} | wc -w | tr -d " "`" >> "${outfile}"
    echo "BATS_ERROR_FILES=\"${fail_files_list# }\"" >> "${outfile}"
    echo "BATS_ERROR_FILES_COUNT=${fail_files}" >> "${outfile}"
    BATS_ERROR_COUNT=${fail_all}
    echo "BATS_ERROR_COUNT=${BATS_ERROR_COUNT}" >> "${outfile}"
    echo "BATS_ERROR_FILES_TIMED_OUT=${timed_out_files}" >> "${outfile}"
    echo "BATS_TIMEOUT=${TIMEOUT}" >> "${outfile}"
    echo "$(get_commom_info "$branch")" >> "${outfile}"
    echo "BATS=$(do_get_status)" >> "${outfile}"
    echo "----------------"
    cat "${outfile}"
    echo "----------------"

    # Back to the initial starting directory
    cd "${start_dir}"
    return ${exit_code}
}

do_table_headers() {
    # Tab separated list of fields
    # example of table header 2 fields available start with ',' to keep first field from previous item
    echo -e "BATS,ErrFiles\t,ErrNum"
}

do_table_values() {
    # 1. branch summary file
    # 2. output format: if not empty triggers annotation
    # Return a tab separated list of the values
    # $VAR1 $VAR2 $VAR3 expected in $1
    # If the summary file is missing return tab separated "na" strings
    [[ -n "$1" ]] && . "$1" || { echo -e "na\tna"; return; }
    if [[ "$2" = NOTAG ]]; then
        echo -e "${BATS_ERROR_FILES_COUNT}\t${BATS_ERROR_COUNT}"
    else
        local res="$(get_annotated_value check0 ${BATS_ERROR_FILES_COUNT})\t"
        echo -e "${res}$(get_annotated_value check0 ${BATS_ERROR_COUNT})"
    fi
}

do_get_status() {
    # 1. branch summary file (optional if the necessary variables are provided)
    # Return unknown, success, warning, error
    [[ -n "$1" ]] && . "$1"
    [[ -z "${BATS_ERROR_COUNT}" ]] && { echo unknown; return 2; }
    [[ "${BATS_ERROR_COUNT}" -eq 0 ]] && { echo success; return; }
    echo error
    return 1
}
