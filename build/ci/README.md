# Testing utilities
The new tests comprise
* util.sh - utility functions for all files
* runtest.sh - runner script with common actions facilitating the invocation of all tests
* do_STH.sh - files containing functions to perform a specific (STH) test

## Test files

They must implement the following functions
```bash
do_parse_options() { pass; }
#do_process_branch "$1" "$outfile" "${CMD_OPTIONS[@]}"
# 1 - branch name
# 2 - outfile
# 3... - options/arguments passed to the command (e.g. files/test list)
do_process_branch() { pass; }
# Run the test/linting on the current branch 
# 1 - branch
# 2 - output file (output directory/output.branch)
# 3... - files to process (optional)
```
They can implement the following functions (here the defaults from runtest.sh)
```bash
do_show_flags() {
    echo "Dry run: $COMMAND not providing the invocation options."
}
do_use_python() { false; }
do_check_requirements() { true; }
# Alternative to do_git_init_command to run 'git submodule update --init --recursive' when needed:
# do_get_git_clone_options() { echo "--recurse-submodules"; } AND do_get_git_checkout_options() { ?; }
do_git_init_command() { true; }
# Empty logging commands
do_log_init() { false; }
do_log_branch() { true; }
do_log_close() { true; }

do_table_headers() {
    # Tab separated list of fields
    # example of table header 2 fields available start with ',' to keep first field from previous item 
    # echo -e "TestName,var1\t,var2\t,var3"
    false
}

do_table_values() {
    # 1. branch summary file
    # 2. format html,html4,html4f ir nothing for plain text
    # Return a tab separated list of the values
    # $VAR1 $VAR2 $VAR3 expected in $1
    . "$1"
    # echo -e "${VAR1}\t${VAR2}\t${VAR3}"
}

do_get_status() {
    # 1. branch summary file
    # Return unknown, success, warning, error
    echo unknown
    return 2
}
```

## Running it and Examples
Use `-h` to see the syntax and some examples.
Normally the scripts are invoked outside the `glideinwms` source directory.
It can be invoked to run in place on the current files or checking out branches.
It can be invoked to run on a new clone of the repository in a random directory or a provided one.
```bash
$ ./glideinwms/build/ci/runtest.sh unittest -h
runtest.sh [options] COMMAND [command options]
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
  -n          show the flags passed to the COMMAND (without running it)
  -l          show the list of files with tests or checked by COMMAND (without running tests or checks)
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
  -C          like -c but the git repository is https://github.com/glideinWMS/glideinwms.git
  -t TEST_DIR create TEST_DIR, clone the repository and run there the tests. Implies -C if -c is not there and if
              there is not already a repository.
              Relative to the start directory (if path is not absolute). Becomes the new WORKDIR.
  -T          like -t but creates a temporary directory with mktemp.
  -z CLEAN    clean on completion (CLEAN: always, no, default:onsuccess)

unittest command:
runtest.sh [options] unittest [other command options] TEST_FILES
  Runs the unit tests on TEST_FILES files in glidinwms/unittests/
runtest.sh [options] unittest -a [other command options]
  Run the unit tests on all the files in glidinwms/unittests/ named test_*
Runs unit tests and exit the results to standard output. Failed tests will cause also a line starting with ERROR.
Command options:
  -h        print this message
  -a        run on all unit tests (see above)
  -c        generate a coverage report while running unit tests
```

The invocation directory or the new temporary directory become the working directory. In it there are the source tree, 
the Python virtual environment (if needed) and the output directory where the outputs from the tests are saved.
Once the test completes all these directories can be removed if so desired.

## `output` folder and files format

Each test will receive an output namespace: `output/gwms.BRANCH.TESTNAME`
This will be the name of the file with the summary of the branch results.
Different tests can have additional files or folders for detailed results, etc.
Normally other names are defined adding '.' (dot) and the additional name. 
'.d' is used for directories containing many additional files of the test 
(e.g. one file per source or test file).

Here files in the output directory:
```text
gwms.master
gwms.master.pylint
gwms.master.ptlint.pycs
gwms.master.pylint.pylint
gwms.master.pylint.sorted
gwms.master.shellcheck
gwms.master.shellcheck.d (folder)
gwms.master.bats
gwms.master.unittest


``` 

The main files, `gwms.BRANCH.TESTNAME`, contain a series of (shell) variables with the results.
```bash
# -------------------
# error count summary
# -------------------
FILES_CHECKED="./tools/manual_glidein_startup ... "
FILES_CHECKED_COUNT=218
PYLINT_ERROR_FILES_COUNT=0
PYLINT_ERROR_COUNT=0
PEP8_ERROR_COUNT=7
``` 
