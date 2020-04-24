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
  futurize - run futurize
  shellcheck - run shellcheck
 Options:
  -h          print this message
  -v          verbose
  -i          run in place without checking out a branch (default)
  -f          force git checkout of branch when processing multiple branches
  -b BNAMES   comma separated list of branches that needs to be inspected
              (branches from glideinwms git repository, quotes are needed if the branch name contains spaces)
  NOT-IMPLEMENTED -B BFILE    file containing a list of branches that needs to be inspected, one per line
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

#find . -name '*.sh' -o -name '*.source'
get_shell_files() {
    # Return to stdout a space separated list of Shell files with .py extension
    # All Shell files
    local src_dir="${1:-.}"
    echo $(find "$src_dir" -path .git -prune -o -name '*.sh' -o -name '*.source')
}


get_python_files() {
    # Return to stdout a space separated list of Python files with .py extension
    # All Python files
    local src_dir="${1:-.}"
    echo $(find "$src_dir" -path .git -prune -o -name '*.py')
}


get_python_scripts() {
    # Return to stdout a space separated list of Python scripts without .py extension
    # Python2 files
    # 1 - source directory
    # 2 - magic_file for find
    magic_file="$(find_aux gwms_magic)"
    local src_dir="${1:-.}"
    FILE_MAGIC=
    [[ -e  "$magic_file" ]] && FILE_MAGIC="-m $magic_file"
    scripts=$(find "${1:-.}" -path .git -prune -o -exec file ${FILE_MAGIC} {} \; -a -type f | grep -i ':.*python' | grep -vi python3 | grep -vi '\.py' | cut -d: -f1 | grep -v "\.html$")
    #if [ -e  "$magic_file" ]; then
    #    scripts=$(find "${1:-.}" -path .git -prune -o -exec file -m "$magic_file" {} \; -a -type f | grep -i python | grep -vi python3 | grep -vi '\.py' | cut -d: -f1 | grep -v "\.html$")
    #else
    #    scripts=$(find "${1:-.}" -path .git -prune -o -exec file {} \; -a -type f | grep -i python | grep -vi python3 | grep -vi '\.py' | cut -d: -f1 | grep -v "\.html$")
    #fi
    echo "$scripts"
}


parse_options() {
    # Parse and validate options to the runtest command
    # OPTS=$(getopt --options $SHORT --long $LONG --name "$0" -- "$@")
    # The man page mentions optional options' arguments for getopts but they are not handled correctly
    while getopts ":hvifso:Cc:Tt:z" option
    do
        case "${option}"
        in
        h) help_msg; exit 0;;
        v) VERBOSE=yes;;
        i) INPLACE=yes;;
        f) GITFLAG='-f';;
        b) BRANCH_LIST="$OPTARG";;
        a) BRANCHES_FILE="$OPTARG";;
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
    if [[ -n "$BRANCH_LIST" ]]; then
        IFS=',' read -r -a git_branches <<< "$BRANCH_LIST"
    fi
    # Default output dir
    [[ -z "$OUT_DIR" ]] && OUT_DIR="$DEFAULT_OUTPUT_DIR"
}


# Create a process branch function
process_branch () {
    # ?? Global Variables Used: $mail_file & $fail - and HTML Constants
    # 1 - branch name or LOCAL (for in place processing)
    local branch_no_slash=$(echo "${1}" | sed -e 's/\//_/g')
    local outfile="${OUT_DIR}"/output.${branch_no_slash}
    do_process_branch "$1" "$outfile" "${CMD_OPTIONS[@]}"
}


test_cleanup() {
    loginfo "Removing all files from temp dir '$1'."
    [[ -n "$1" ]] && rm -rf "$1"
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
#   do_parse_options
#   do_process_branch - run the test on the current branch
# All functions start with do_...

# Defaults for commands' functions and variables
do_use_python() { false; }
do_check_requirements() { true; }
# Alternative to do_git_init_command to run 'git submodule update --init --recursive' when needed:
# do_get_git_clone_options() { echo "--recurse-submodules"; } AND do_get_git_checkout_options() { ?; }
do_git_init_command() { true; }
do_parse_options() { logerror "command not implemented"; exit 1; }

case "$COMMAND" in
    unittest) command_file=do_unittest.sh;;
    bats) command_file=do_bats.sh;;
    pylint) command_file=do_pylint.sh;;
    shellcheck) command_file=do_shellcheck.sh;;
    *) logerror "invalid command ($COMMAND)"; help_msg 1>&2; exit 1;;
esac

UTILS_OK=
COMMAND_OK=
if find_aux utils.sh source noexit; then
    UTILS_OK=yes
    if find_aux $command_file source noexit; then
        COMMAND_OK=yes
    fi
fi

# Parse options to the command, output in CMD_OPTIONS array
# Postpone options parsing if the command file was not found
[[ -n "${COMMAND_OK}" ]] && do_parse_options "$@"


# Start creating files

# Setup temporary directory (if selected) and clone repo
if [[ -n "$REPO" ]]; then
    # Checkout and run in temp directory (default mktemp)
    if [[ -n "${TEST_DIR}" ]]; then
        mkdir -p "${TEST_DIR}"
        if ! cd "${TEST_DIR}"; then
            logexit "failed to setup the test directory $TEST_DIR"
        fi
    fi

    if [[ -d glideinwms && -z "$GITFLAG" ]]; then
        logexit "cannot clone the repository, a glideinwms directory exist already: `pwd`/glideinwms "
    fi
    # --recurse-submodules
    if ! git clone "$REPO" ; then
        logexit "failed to clone $REPO"
    fi
    # Adding do_git_init_command also here in case -i is used
    [[ -n "$INPLACE" ]] && ( cd glideinwms && do_git_init_command )
fi

# After this line the script is in the working directory and the source tree is in ./glideinwms
WORKSPACE=$(pwd)
export GLIDEINWMS_SRC="$WORKSPACE"/glideinwms
STATFILE="$WORKSPACE"/gwmstest.$(date +"%s").txt
OUT_DIR="$(robust_realpath "$OUT_DIR")"

# This time, fail if they are not found
[[ -z "${UTILS_OK}" ]] && find_aux utils.sh source
if [[ -z "${COMMAND_OK}" ]]; then
    find_aux $command_file source
    do_parse_options "$@"
fi

if [[ ! -d "${OUT_DIR}" ]]; then
    if ! mkdir -p "${OUT_DIR}"; then
        logexit "failed to create output directory ${OUT_DIR}"
    fi
    loginfo "created output directory ${OUT_DIR}"
fi

echo "command=$full_command_line" >> "$OUT_DIR/$STATFILE"
echo "workdir=$WORKSPACE" >> "$OUT_DIR/$STATFILE"
echo "srcdir=$GLIDEINWMS_SRC" >> "$OUT_DIR/$STATFILE"
echo "outdir=$OUT_DIR" >> "$OUT_DIR/$STATFILE"

# Iterate throughout the git_branches array
fail_global=0
if do_use_python; then
    [[ "x${VIRTUAL_ENV}" = "x" ]] && setup_python_venv "$WORKSPACE"
fi

cd "${GLIDEINWMS_SRC}"
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
        if ! git checkout "$GITFLAG" "$git_branch"; then
            logwarn "Could not checkout branch $git_branch, continuing with the next"

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
            curr_branch=$(git rev-parse --abbrev-ref HEAD)
            [[ ! "$git_branch" = "$curr_branch" ]] && logwarn "Current branch ${curr_branch} different from expected ${git_branch}, continuing anyway" >&2
        fi
        # Starting the test
        process_branch "$git_branch"
        fail=$?
        loginfo "Complete with branch ${git_branch} (ec:${fail})"
	    [[ ${fail} -gt ${fail_global} ]] && fail_global=${fail}

    done
fi

# Finish off the end of the email
mail_file="$mail_file
    </tbody>
</table>
</body>"

# Save the email to a file
echo "$mail_file" > "$OUT_DIR/email.txt"

echo "exit_code=$fail_global" >> "$OUT_DIR/$STATFILE"

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
