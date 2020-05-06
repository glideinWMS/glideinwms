# Shell source file to be sourced to run Python unit tests and coverage
# To be used only inside runtest.sh (runtest.sh and util.sh functions defined, VARIABLES available)
# All function names start with do_...

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
}

do_use_python() { true; }

do_process_branch() {
    # 1 - branch
    # 2 - output file (output directory/output.branch)
    #

    if ! cd unittests ; then
        logexit "cannot find the test directory './unittests', exiting"
    fi
    local branch="$1"
    local outdir="$(dirname "$2")"
    local outfile="$(basename "$2")"
    local branch_noslash="${outfile#*.}"
    shift 2
    local test_date=$(date "+%Y-%m-%d %H:%M:%S")
    SOURCES="$(get_source_directories)"

    # Example file lists (space separated list)
    #files="test_frontend.py"
    #files="test_frontend_element.py"
    #files="test_frontend.py test_frontend_element.py"
    local file_list
    if [[ -n "$LIST_FILES" ]]; then
        files_list="$(find . -readable -name  'test_*.py' -print)"
    else
        files_list="$*"
    fi

    [[ -n "$RUN_COVERAGE" ]] && coverage erase

    for file in ${files_list} ; do
        loginfo "TESTING ==========> $file"
        if [[ -n "$VERBOSE" ]]; then
            if [[ -n "$RUN_COVERAGE" ]]; then
                coverage run   --source="${SOURCES}" --omit="test_*.py"  -a "$file" || log_nonzero_rc "$file" $?
            else
                ./"$file" || log_nonzero_rc "$file" $?
            fi
        else
            if [[ -n "$RUN_COVERAGE" ]]; then
                coverage run   --source="${SOURCES}" --omit="test_*.py"  -a "$file"
            else
                ./"$file"
            fi
        fi
    done

    if [[ -n "$RUN_COVERAGE" ]]; then
        TITLE="GlideinWMS Coverage Report for branch $branch on $test_date"
        coverage report > "${outdir}/coverage_report.${branch_noslash}"
        coverage html --title "$TITLE" || logwarn "coverage html report failed"
        if [[ -d htmlcov ]]; then
            mv htmlcov "${outdir}/htmlcov.${branch_noslash}"
        else
            # To help troubleshooting the coverage failure
            echo "no html coverage report generated for $branch_noslash on $(hostname)"
            which coverage || echo "coverage not installed"
            coverage --version || echo "coverage not installed"
        fi
    fi
}
