# Testing utilities
The new tests comprise
* util.sh - utility functions for all files
* runtest.sh - runner script with common actions facilitating the invocation of all tests
* do_STH.sh - files containing functions to perform a specific (STH) test

## Test files

They must implement the following functions
```bash

```
They can implement the following functions
```bash

```

## Running it and Examples
Use `-h` to see the syntax and some examples.
Normally the scripts are invoked outside the `glideinwms` source directory.
It can be invoked to run in place on the current files or checking out branches.
It can be invoked to run on a new clone of the repository in a random directory or a provided one.

The invocation directory or the new temporary directory become the working directory. In it there are the source tree, 
the Python virtual environment (if needed) and the output directory where the outputs from the tests are saved.
Once the test completes all these directories can be removed if so desired.

## `output` folder and files format

Each test will receive an output namespace: `output/gwms.BRANCH.TESTNAME`
This will be the name of the file with the summary of the branch results.
Different tests can have additional files or folders for detailed results, etc.

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
