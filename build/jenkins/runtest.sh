#!/bin/bash
# Runner script for the different tests

GWMS_REPO="https://github.com/glideinWMS/glideinwms.git"
DEFAULT_OUTPUT_DIR=output
SCRIPTS_SUBDIR=build/jenkins

# logerror() and logexit() are in util.sh, repeated here to use them in find_aux
logerror() {
    echo "$filename ERROR: $1" >&2
}
logexit() {
    # replacing logreportfail in the function to avoid repeating all the other definitions
    if [ -n "$3" ]; then
        local msg="$3=\"FAILED\""
        [[ -n "${TESTLOG}" ]] && echo "${msg}" >> "${TESTLOG}"
        echo "${msg}"
    fi
    logerror "$1"
    exit ${2:-1}
}


find_aux() {
    # $1 basename of the aux file
    # $2 (optionsl) if "source" then source the file and exit in case of errors
    local aux_file=
    if [[ -e "$MYDIR/$1" ]]; then
        aux_file="$MYDIR/$1"
    else
        [[ -e "$GLIDEINWMS_SRC/$SCRIPTS_SUBDIR/$1" ]] && aux_file="$GLIDEINWMS_SRC/$SCRIPTS_SUBDIR/$1"
    fi
    if [[ "x$2" = xsource ]]; then
        if [[ ! -e  "${aux_file}" ]]; then
            [[ "x$3" = xnoexit ]] && { false; return; }
            logerror "${1} not found!"
            logexit "script running in $(pwd), expects a ${1} file there or in the glideinwms src tree"
        fi
        if ! . "${aux_file}" ; then
            logexit "${aux_file} contains errors!"
        fi
        return
    fi
    [[ -n "${aux_file}" ]] && { echo "${aux_file}"; return ; }
    false
}

help_msg() {
  cat << EOF
${filename} [options] COMMAND [command options]
  Runs the test form COMMAND on the current glideinwms subdirectory, as is or checking out a branch from the repository.
  Unless you use -c, a glidienwms subdirectory of WORKDIR with the git repository must exist.
  Tests are run on each of the branches in the list. Test results are saved in OUT_DIR
  NOTE that, when selecting branches, the script is checking out the branch and running the tests. It is not cleaning
  up or restoring to the initial content. For something less intrusive use '-i' option to run in place without
  changing any source file. Or use -t, to clone the repository in the new TEST_DIR directory.
 COMMAND:
  bats - run Shell unit tests and coverage
  unittest - run Python unit test and coverage
  pylint - run pylint and pycodestyle (pep8)
  shellcheck - run shellcheck
 Options:
  -h          print this message
  -v          verbose
  -i          run in place without checking out a branch (default)
  -f          force git checkout of branch when processing multiple branches
  -b BNAMES   comma separated list of branches that needs to be inspected
              (branches from glideinwms git repository, quotes are needed if the branch name contains spaces)
  -B BFILE    file containing a list of branches that needs to be inspected, one per line
              (branches from glideinwms git repository, quotes are needed if the branch name contains spaces)
  -s          run sequentially invoking the test separately for each file
  -o OUT_DIR  directory including log files (it will be created if not existing, default "./output")
              Relative to WORKDIR.
  -c REPO     clone the git repository REPO
  -C          like -c but the git repository is ${GWMS_REPO}
  -t TEST_DIR create TEST_DIR, clone the repository and run there the tests. Implies -C if -c is not there.
              Relative to the start directory. Becomes the new WORKDIR.
  -T          like -t but creates a temporary directory with mktemp.
  -z CLEAN    clean on completion (CLEAN: always, no, default:onsuccess)

EOF
}


get_files_ext() {
    # Return to stdout a space separated list of files with EXT ($1) extension
    # 1. extension to look for
    # 2. directories to prune (NOTE. this will not work if these directories or src_dir contain spaces)
    # 3. possible root directory (default:'.')
    # All Shell files
    local extension=$1
    local src_dir="${3:-.}"
    prune_opts=
    for i in $2; do
        prune_opts="${prune_opts} -path ${src_dir}/$i -prune -o"
    done
    # -readable not valid on Mac, needed?
    # e.g. $(find . -readable -name  '*.bats' -print)"
    echo "$(find "$src_dir" -path "${src_dir}"/.git -prune -o ${prune_opts} -name '*.'${extension} -print)"
}


#find . -name '*.sh' -o -name '*.source'
get_shell_files() {
    # Return to stdout a space separated list of Shell files with .sh/.source extension
    # All Shell files
    local src_dir="${1:-.}"
    echo $(find "$src_dir" -path "${src_dir}"/.git -prune -o -name '*.sh' -o -name '*.source' -print)
}


get_python_files() {
    # Return to stdout a space separated list of Python files with .py extension
    # All Python files
    local src_dir="${1:-.}"
    echo $(find "${src_dir}" -path "${src_dir}"/.git -prune -o -path "${src_dir}"/.tox -prune -o -name '*.py' -print)
}


get_python_scripts() {
    # Return to stdout a space separated list of Python scripts without .py extension
    # Python3 files (containing python and
    # 1 - source directory
    # 2 - magic_file for find
    magic_file="$(find_aux gwms_magic)"
    local src_dir="${1:-.}"
    FILE_MAGIC=
    [[ -e  "$magic_file" ]] && FILE_MAGIC="-m $magic_file"
    scripts=$(find "${src_dir}" -path "${src_dir}"/.git -prune -o -path "${src_dir}"/.tox -prune -o -exec file ${FILE_MAGIC} {} \; -a -type f | grep -i ':.*python' | grep -vi python2 | grep -vi '\.py' | cut -d: -f1 | grep -v "\.html$")
    # scripts=$(find glideinwms -readable -path glideinwms/.git -prune -o -exec file $FILE_MAGIC {} \; -a -type f | grep -i ':.*python' | grep -vi python3 | grep -vi '\.py' | cut -d: -f1 | grep -v "\.html$" | sed -e 's/glideinwms\///g')
    #if [ -e  "$magic_file" ]; then
    #    scripts=$(find "${1:-.}" -path .git -prune -o -exec file -m "$magic_file" {} \; -a -type f | grep -i python | grep -vi python3 | grep -vi '\.py' | cut -d: -f1 | grep -v "\.html$")
    #else
    #    scripts=$(find "${1:-.}" -path .git -prune -o -exec file {} \; -a -type f | grep -i python | grep -vi python3 | grep -vi '\.py' | cut -d: -f1 | grep -v "\.html$")
    #fi
    # echo "-- DBG $(echo ${scripts} | wc -w | tr -d " ") scripts found using magic file (${FILE_MAGIC}) --" >&2
    echo "$scripts"
}


parse_options() {
    # Parse and validate options to the runtest command
    # OPTS=$(getopt --options $SHORT --long $LONG --name "$0" -- "$@")
    # The man page mentions optional options' arguments for getopts but they are not handled correctly
    while getopts ":hvifb:B:so:Cc:Tt:z" option
    do
        case "${option}"
        in
        h) help_msg; exit 0;;
        v) VERBOSE=yes;;
        i) INPLACE=yes;;
        f) GITFLAG='-f';;
        b) BRANCH_LIST="$OPTARG";;
        B) BRANCHES_FILE="$OPTARG";;
        s) SEQUENTIAL=yes;;
        o) OUT_DIR="$OPTARG";;
        c) REPO="$OPTARG";;
        C) REPO="$GWMS_REPO";;
        t) TEST_DIR="$OPTARG";;
        T) TEST_DIR=$(mktemp -t -d gwmstest.XXXXXXXX);;
        z) TEST_CLEAN="$OPTARG";;
        : ) logerror "illegal option: -$OPTARG requires an argument"; help_msg 1>&2; exit 1;;
        *) logerror "illegal option: -$OPTARG"; help_msg 1>&2; exit 1;;
        \?) logerror "illegal option: -$OPTARG"; help_msg 1>&2; exit 1;;
        esac
    done
    # Validate git and branching options
    [[ -z "${BRANCH_LIST}" && -z "${BRANCHES_FILE}" ]] && INPLACE=yes
    if [[ -n "$INPLACE" ]]; then
        [[ -n "$BRANCH_LIST" ]] && logwarn "Using -i the branch list will be ignored."
        BRANCH_LIST=
        [[ -n "$GITFLAG" ]] && logwarn "Using -i the force flag -f will be ignored."
        GITFLAG=
    fi
    # Fix the repo parameter w/ the default if running in temp directory
    [[ -z "$REPO" && -n "${TEST_DIR}" ]] && REPO="$GWMS_REPO"
    # Get the git branches in to an array
    if [[ -n "${BRANCH_LIST}" ]]; then
        IFS=',' read -r -a git_branches <<< "$BRANCH_LIST"
    fi
    if [[ -n "${BRANCHES_FILE}" ]]; then
        IFS=$'\r\n' read -d '' -r -a git_branches < "${BRANCHES_FILE}"
    fi
    # Default output dir
    [[ -z "${OUT_DIR}" ]] && OUT_DIR="${DEFAULT_OUTPUT_DIR}"
}


test_cleanup() {
    loginfo "Removing all files from temp dir '$1'."
    [[ -n "$1" ]] && rm -rf "$1"
}

SKIP_LOG=
log_init() {
    # 1. file that will store the email body (in HTML)
    local log_content
    if ! log_content="$(do_log_init)"; then
        SKIP_LOG=yes
        return
    fi
    mail_init "$1"
    if do_use_python; then
        mail_add "$(print_python_info email)"
    fi
    mail_add "${log_content}"
}

log_close() {
    [ -n "${SKIP_LOG}" ] && return
    mail_add "$(do_log_close)"
    mail_close
    # TODO: mail results if desired
    # mail_send "Subject" "TO?"
}

log_branch() {
    # 1. results file for the branch
    [ -n "${SKIP_LOG}" ] && return
    mail_add "$(do_log_branch "$1")"
}

# TODO: finish log_join
log_join() {
    # Join multiple HTML emails into a single one
    # use the cell style to grep for lines
    # 1. output file w/ joint HTML
    # 2..N HTML files to join
    [ $# -lt 2 ] && { logerror "Wrong arguments for log_join: $@"; return; }
    [ $# -eq 2 ] && { cp "$2" "$1"; return; }
    mail_init "$1"
    mail_add "$(sed ';</tr>;Q' "$2"| tail -n +2)"
    # create a temp dir
    # copy the grep result there (all regular cells)
    # results_1="$(grep "HEAD_COL" "$2")"
    shift 2
    for i in "$@"; do
        mail_add "$(grep "HEAD_COL" "$i"| tail -n +2)"
    done
    mail_add "$(cat << TABLE_START
    </tr>
  </thead>
  <tbody>
    <tr style="$HTML_TR">
TABLE_START
    )"
    # save grep results in temp dir. loop through the lines N at the time, saving the remainder
    # there could be multiple rows (N cells)
    mail_add "$(cat << TABLE_MIDDLE
    </tr>
    <tr style="$HTML_TR">
TABLE_MIDDLE
    )"
    echo "    </tr>"
    mail_add "$(do_log_close)"
}


# Create a process branch function
process_branch () {
    # ?? Global Variables Used: $mail_file & $fail - and HTML Constants
    # 1 - branch name or LOCAL (for in place processing)
    local branch_no_slash=$(echo "${1}" | sed -e 's/\//_/g')
    local outfile="${OUT_DIR}"/output.${branch_no_slash}
    do_process_branch "$1" "${outfile}" "${CMD_OPTIONS[@]}"
    log_branch "${outfile}"
}



#################
# Main

# Setup the build environment
filename="$(basename $0)"
full_command_line="$*"
export MYDIR=$(dirname $0)


OUT_DIR=
TEST_CLEAN=onsuccess
parse_options "$@"
# This needs to be outside to shift the general arglist
shift $((OPTIND-1))
# Needs to be reset for the next parsing
OPTIND=1

# Parse the (sub)command
COMMAND=$1; shift  # Remove the command from the argument list
# Commands provide functions to perform the actions
# Mandatory functions:
#   do_parse_options - parse the command specific command line options
#   do_process_branch - run the test on the current branch
# All functions start with do_...

# Defaults for commands' functions and variables
do_use_python() { false; }
do_check_requirements() { true; }
# Alternative to do_git_init_command to run 'git submodule update --init --recursive' when needed:
# do_get_git_clone_options() { echo "--recurse-submodules"; } AND do_get_git_checkout_options() { ?; }
do_git_init_command() { true; }
# Empty logging commands
do_log_init() { true; }
do_log_branch() { true; }
do_log_close() { true; }

do_parse_options() { logexit "command not implemented"; }
#do_process_branch "$1" "$outfile" "${CMD_OPTIONS[@]}"
# 1 - branch name
# 2 - outfile
# 3... - options/arguments passed to the command (e.g. files/test list)
do_process_branch() { logexit "command not implemented"; }


case "$COMMAND" in
    unittest) command_file=do_unittest.sh;;
    bats) command_file=do_bats.sh;;
    pylint) command_file=do_pylint.sh;;
    shellcheck) command_file=do_shellcheck.sh;;
    *) logerror "invalid command ($COMMAND)"; help_msg 1>&2; exit 1;;
esac

UTILS_OK=
COMMAND_OK=
# comman help message can be processed also w/o utils
if find_aux utils.sh source noexit; then
    UTILS_OK=yes
    if find_aux $command_file source noexit; then
        COMMAND_OK=yes
    fi
fi

# Parse options to the command, output in CMD_OPTIONS array
# Postpone options parsing if the command file was not found
[[ -n "${COMMAND_OK}" ]] && do_parse_options "$@"

# If there are no utils or no command, operations cannot proceed
[[ -z "${UTILS_OK}" || -z "${COMMAND_OK}" ]] && logexit "cannot continue without utils and command files" 1 SETUP

# Start creating files

# Setup temporary directory (if selected) and clone repo
if [[ -n "$REPO" ]]; then
    # Checkout and run in temp directory (default mktemp)
    if [[ -n "${TEST_DIR}" ]]; then
        mkdir -p "${TEST_DIR}"
        if ! cd "${TEST_DIR}"; then
            logexit "failed to setup the test directory $TEST_DIR" 1 SETUP
        fi
    fi

    if [[ -d glideinwms && -z "$GITFLAG" ]]; then
        logexit "cannot clone the repository, a glideinwms directory exist already: `pwd`/glideinwms " 1 SETUP
    fi
    # --recurse-submodules
    if ! git clone "$REPO" ; then
        logexit "failed to clone $REPO" 1 SETUP
    fi
    # Adding do_git_init_command also here in case -i is used
    [[ -n "$INPLACE" ]] && ( cd glideinwms && do_git_init_command )
fi

# After this line the script is in the working directory and the source tree is in ./glideinwms
WORKSPACE=$(pwd)
export GLIDEINWMS_SRC="$WORKSPACE"/glideinwms
# Verify that this is correct also for in-place executions, -i
if [[ ! -d "${GLIDEINWMS_SRC}" ]]; then
    logexit "repository not found in .glideinwms (${GLIDEINWMS_SRC})" 1 SETUP
fi
STATFILE="$WORKSPACE"/gwmstest.$(date +"%s").txt
OUT_DIR="$(robust_realpath "$OUT_DIR")"

# This time, fail if they are not found
[[ -z "${UTILS_OK}" ]] && find_aux utils.sh source
if [[ -z "${COMMAND_OK}" ]]; then
    find_aux "$command_file" source
    do_parse_options "$@"
fi

if [[ ! -d "${OUT_DIR}" ]]; then
    if ! mkdir -p "${OUT_DIR}"; then
        logexit "failed to create output directory ${OUT_DIR}" 1 SETUP
    fi
    loginfo "created output directory ${OUT_DIR}"
fi

echo "command=$full_command_line" >> "$STATFILE"
echo "workdir=$WORKSPACE" >> "$STATFILE"
echo "srcdir=$GLIDEINWMS_SRC" >> "$STATFILE"
echo "outdir=$OUT_DIR" >> "$STATFILE"

# Iterate throughout the git_branches array
fail_global=0
if do_use_python; then
    [[ "x${VIRTUAL_ENV}" = "x" ]] && setup_python_venv "$WORKSPACE"
fi

cd "${GLIDEINWMS_SRC}"

# Initialize and save the email to a file
log_init "$OUT_DIR/email.txt"

if [[ -n "$INPLACE" ]]; then
    loginfo "Running on local files in glideinwms subdirectory"
    process_branch LOCAL
    fail_global=$?
    loginfo "Complete with local files (ec:${fail_global})"
else
    do_git_init_command
    for git_branch in "${git_branches[@]}"
    do
        loginfo "Now checking out branch $git_branch"
        loglog "GIT_BRANCH=\"$git_branch\""
        if ! git checkout ${GITFLAG} "$git_branch"; then
            log_nonzero_rc "git checkout" $?
            logwarn "Could not checkout branch ${git_branch}, continuing with the next"
            logreportfail "GIT_CHECKOUT"
            # Add a failed entry to the email
            mail_file="$mail_file
        <tr style=\"$HTML_TR\">
            <th style=\"$HTML_TH\">$git_branch</th>
            <td style=\"$HTML_TD_CRASHED\">ERROR: Could not checkout branch</td>
        </tr>"
            [[ ${fail} -gt ${fail_global} ]] && fail_global=${fail}
            fail=301
            continue
        else
            # Do a pull in case the repo was not a new clone
            if ! git pull; then
                logwarn "Could not update (pull) branch ${git_branch}, continuing anyway"
            fi
            curr_branch=$(git rev-parse --abbrev-ref HEAD)
            [[ ! "$git_branch" = "$curr_branch" ]] && logwarn "Current branch ${curr_branch} different from expected ${git_branch}, continuing anyway"
            logreportok "GIT_CHECKOUT"
        fi
        # Starting the test
        process_branch "$git_branch"
        fail=$?
        loginfo "Complete with branch ${git_branch} (ec:${fail})"
	    [[ ${fail} -gt ${fail_global} ]] && fail_global=${fail}

    done
fi

# Finish off the end of the email
log_close


echo "exit_code=$fail_global" >> "${STATFILE}"

# All done
loginfo "Logs are in $OUT_DIR"
if [[ "$fail_global" -ne 0 ]]; then
    loginfo "Tests Complete - Failed"
    exit ${fail_global}
fi
loginfo "Tests Complete - Success"

if [[ "${TEST_CLEAN}" = always ]] || [[ "${TEST_CLEAN}" = always && "$fail_global" -eq 0 ]]; then
    test_cleanup "${TEST_DIR}"
fi
