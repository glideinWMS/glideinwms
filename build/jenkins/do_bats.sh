# Shell source file to be sourced to run Python unit tests and coverage
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
EOF
}

LIST_FILES=
RUN_COVERAGE=
BATSOPT=

do_parse_options() {
    while getopts ":hatc" option
    do
      case "${option}"
      in
      h) help_msg; do_help_msg; exit 0;;
      a) LIST_FILES=yes;;
      t) BATSOPT="-t";;
      c) RUN_COVERAGE=yes;;
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
    if ! command -v bats > /dev/null 2>&1; then
        logerror "bats not available"
        false
        return
    fi
    for i in do_get_dependencies; do
        [[ -e "$i" ]] || logwarn "unable to find BATS test dependency '$i'"
    done
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
    SOURCES="$GLIDEINWMS_SRC"/creation/web_base

    local file_list
    if [[ -n "$LIST_FILES" ]]; then
        files_list="$(find . -readable -name  '*.bats' -print)"
    else
        files_list="$*"
    fi

    local fail
    local fail_all=0
    for file in ${files_list} ; do
        loginfo "TESTING ==========> $file"
        if [[ -n "$VERBOSE" ]]; then
            if [[ -n "$RUN_COVERAGE" ]]; then
                kcov --include-path="${SOURCES}" "$outdir"/coverage  ./"$file" ${BATSOPT} || log_nonzero_rc "$file" $?
            else
                ./"$file" ${BATSOPT} || log_nonzero_rc "$file" $?
            fi
        else
            if [[ -n "$RUN_COVERAGE" ]]; then
                kcov --include-path="${SOURCES}" "$outdir"/coverage  ./"$file" ${BATSOPT}
            else
                ./"$file" ${BATSOPT}
            fi
        fi
        fail=$?
        [[ ${fail} -gt ${fail_all} ]] && fail_all=${fail}
    done
    return ${fail_all}
}
