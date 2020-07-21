#!/bin/sh


find_aux () {
    # $1 basename of the aux file
    [ -e "$MYDIR/$1" ] && { echo "$MYDIR/$1"; return; }
    [ -e "$GLIDEINWMS_SRC/$1" ] && { echo "$GLIDEINWMS_SRC/$1"; return; }
    false
}


process_branch() {
    local pylint_log=$1
    local pep8_log=$2
    local results=$3
    local git_branch=$4

    echo "===================================================================="
    echo "GIT BRANCH: $git_branch"
    echo "===================================================================="
    # Initialize logs
    > $pylint_log
    > ${pep8_log}
    > $results

    echo "GIT_BRANCH=\"$git_branch\"" >> $results
    if [ -n "$git_branch" ]; then
        cd $GLIDEINWMS_SRC
        git checkout $GIT_FLAG $git_branch
        checkout_rc=$?
        git pull
        cd $WORKSPACE
        if [ $checkout_rc -ne 0 ]; then
            log_nonzero_rc "git checkout" $?
            echo "GIT_CHECKOUT=\"FAILED\"" >> $results
            return
        fi
    fi
    # Consider success if no git checkout was done
    echo "GIT_CHECKOUT=\"PASSED\"" >> $results

    ################
    # pylint
    ################

    # pylint related variables
    PYLINT_RCFILE=/dev/null
    PYLINT_OPTIONS="--errors-only --rcfile=$PYLINT_RCFILE"
    # Starting pylint 1.4 external modules must be whitelisted
    PYLINT_OPTIONS="$PYLINT_OPTIONS --extension-pkg-whitelist=htcondor,classad"

    ################
    # pycodestyle
    ################

    # Formorally pep8, which the name is still used in logging

    #uncomment or add lines to taste
    #see tail of pep8.log for counts of
    #various pep8 errors

    # Note:  Uncommenting the first line  should be
    # ="$PEP8_OPTIONS""CODE"

    PEP8_OPTIONS="--ignore="


    # E1    Indentation
    # E101  indentation contains mixed spaces and tabs
    #PEP8_OPTIONS="$PEP8_OPTIONS,E101"
    # E111  indentation is not a multiple of four
    PEP8_OPTIONS="$PEP8_OPTIONS""E111"
    # E112  expected an indented block
    #PEP8_OPTIONS="$PEP8_OPTIONS,E112"
    # E113  unexpected indentation
    #PEP8_OPTIONS="$PEP8_OPTIONS,E113"
    # E114  indentation is not a multiple of four (comment)
    #PEP8_OPTIONS="$PEP8_OPTIONS,E114"
    # E115  expected an indented block (comment)
    #PEP8_OPTIONS="$PEP8_OPTIONS,E115"
    # E116  unexpected indentation (comment)
    #PEP8_OPTIONS="$PEP8_OPTIONS,E116"
    # E117  over-indented
    #PEP8_OPTIONS="$PEP8_OPTIONS,E117"
    # E121 (*^) continuation line under-indented for hanging indent
    #PEP8_OPTIONS="$PEP8_OPTIONS,E121"
    # E122 (^)  continuation line missing indentation or outdented
    #PEP8_OPTIONS="$PEP8_OPTIONS,E122"
    # E123 (*)  closing bracket does not match indentation of opening bracket’s line
    #PEP8_OPTIONS="$PEP8_OPTIONS,E123"
    # E124 (^)  closing bracket does not match visual indentation
    #PEP8_OPTIONS="$PEP8_OPTIONS,E124"
    # E125 (^)  continuation line with same indent as next logical line
    #PEP8_OPTIONS="$PEP8_OPTIONS,E125"
    # E126 (*^) continuation line over-indented for hanging indent
    #PEP8_OPTIONS="$PEP8_OPTIONS,E126"
    # E127 (^)  continuation line over-indented for visual indent
    #PEP8_OPTIONS="$PEP8_OPTIONS,E127"
    # E128 (^)  continuation line under-indented for visual indent
    #PEP8_OPTIONS="$PEP8_OPTIONS,E128"
    # E129 (^)  visually indented line with same indent as next logical line
    #PEP8_OPTIONS="$PEP8_OPTIONS,E129"
    # E131 (^)  continuation line unaligned for hanging indent
    #PEP8_OPTIONS="$PEP8_OPTIONS,E131"
    # E133 (*)  closing bracket is missing indentation
    #PEP8_OPTIONS="$PEP8_OPTIONS,E13
    # E2    Whitespace3"
    #PEP8_OPTIONS="$PEP8_OPTIONS,E2"
    # E201  whitespace after ‘(‘
    #PEP8_OPTIONS="$PEP8_OPTIONS,E201"
    # E202  whitespace before ‘)’
    #PEP8_OPTIONS="$PEP8_OPTIONS,E202"
    # E203  whitespace before ‘:’
    #PEP8_OPTIONS="$PEP8_OPTIONS,E203"
    # E211  whitespace before ‘(‘
    #PEP8_OPTIONS="$PEP8_OPTIONS,E211"
    # E221  multiple spaces before operator
    #PEP8_OPTIONS="$PEP8_OPTIONS,E221"
    # E222  multiple spaces after operator
    #PEP8_OPTIONS="$PEP8_OPTIONS,E222"
    # E223  tab before operator
    #PEP8_OPTIONS="$PEP8_OPTIONS,E223"
    # E224  tab after operator
    #PEP8_OPTIONS="$PEP8_OPTIONS,E224"
    # E225  missing whitespace around operator
    PEP8_OPTIONS="$PEP8_OPTIONS,E225"
    # E226 (*)  missing whitespace around arithmetic operator
    PEP8_OPTIONS="$PEP8_OPTIONS,E226"
    # E227  missing whitespace around bitwise or shift operator
    #PEP8_OPTIONS="$PEP8_OPTIONS,E227"
    # E228  missing whitespace around modulo operator
    PEP8_OPTIONS="$PEP8_OPTIONS,E228"
    # E231  missing whitespace after ‘,’, ‘;’, or ‘:’
    PEP8_OPTIONS="$PEP8_OPTIONS,E231"
    # E241 (*)  multiple spaces after ‘,’
    #PEP8_OPTIONS="$PEP8_OPTIONS,E241"
    # E242 (*)  tab after ‘,’
    #PEP8_OPTIONS="$PEP8_OPTIONS,E242"
    # E251  unexpected spaces around keyword / parameter equals
    #PEP8_OPTIONS="$PEP8_OPTIONS,E251"
    # E261  at least two spaces before inline comment
    PEP8_OPTIONS="$PEP8_OPTIONS,E261"
    # E262  inline comment should start with ‘# ‘
    #PEP8_OPTIONS="$PEP8_OPTIONS,E262"
    # E265  block comment should start with ‘# ‘
    PEP8_OPTIONS="$PEP8_OPTIONS,E265"
    # E266  too many leading ‘#’ for block comment
    #PEP8_OPTIONS="$PEP8_OPTIONS,E266"
    # E271  multiple spaces after keyword
    #PEP8_OPTIONS="$PEP8_OPTIONS,E271"
    # E272  multiple spaces before keyword
    #PEP8_OPTIONS="$PEP8_OPTIONS,E272"
    # E273  tab after keyword
    #PEP8_OPTIONS="$PEP8_OPTIONS,E273"
    # E274  tab before keyword
    #PEP8_OPTIONS="$PEP8_OPTIONS,E274"
    # E275  missing whitespace after keyword
    #PEP8_OPTIONS="$PEP8_OPTIONS,E275"

    # E3    Blank line
    # E301  expected 1 blank line, found 0
    #PEP8_OPTIONS="$PEP8_OPTIONS,E301"
    # E302  expected 2 blank lines, found 0
    PEP8_OPTIONS="$PEP8_OPTIONS,E302"
    # E303  too many blank lines (3)
    #PEP8_OPTIONS="$PEP8_OPTIONS,E303"
    # E304  blank lines found after function decorator
    #PEP8_OPTIONS="$PEP8_OPTIONS,E304"
    # E305  expected 2 blank lines after end of function or class
    #PEP8_OPTIONS="$PEP8_OPTIONS,E305"
    # E306  expected 1 blank line before a nested definition
    #PEP8_OPTIONS="$PEP8_OPTIONS,E306"

    # E4    Import
    # E401  multiple imports on one line
    #PEP8_OPTIONS="$PEP8_OPTIONS,E401"
    # E402  module level import not at top of file
    #PEP8_OPTIONS="$PEP8_OPTIONS,E402"

    # E5    Line length
    # E501 (^)  line too long (82 > 79 characters)
    PEP8_OPTIONS="$PEP8_OPTIONS,E501"
    # E502  the backslash is redundant between brackets
    #PEP8_OPTIONS="$PEP8_OPTIONS,E502"

    # E7    Statement
    # E701  multiple statements on one line (colon)
    #PEP8_OPTIONS="$PEP8_OPTIONS,E701"
    # E702  multiple statements on one line (semicolon)
    #PEP8_OPTIONS="$PEP8_OPTIONS,E702"
    # E703  statement ends with a semicolon
    #PEP8_OPTIONS="$PEP8_OPTIONS,E703"
    # E704 (*)  multiple statements on one line (def)
    #PEP8_OPTIONS="$PEP8_OPTIONS,E704"
    # E711 (^)  comparison to None should be ‘if cond is None:’
    #PEP8_OPTIONS="$PEP8_OPTIONS,E711"
    # E712 (^)  comparison to True should be ‘if cond is True:’ or ‘if cond:’
    #PEP8_OPTIONS="$PEP8_OPTIONS,E712"
    # E713  test for membership should be ‘not in’
    #PEP8_OPTIONS="$PEP8_OPTIONS,E713"
    # E714  test for object identity should be ‘is not’
    #PEP8_OPTIONS="$PEP8_OPTIONS,E714"
    # E721 (^)  do not compare types, use ‘isinstance()’
    #PEP8_OPTIONS="$PEP8_OPTIONS,E721"
    # E722  do not use bare except, specify exception instead
    #PEP8_OPTIONS="$PEP8_OPTIONS,E722"
    # E731  do not assign a lambda expression, use a def
    #PEP8_OPTIONS="$PEP8_OPTIONS,E731"
    # E741  do not use variables named ‘l’, ‘O’, or ‘I’
    #PEP8_OPTIONS="$PEP8_OPTIONS,E741"
    # E742  do not define classes named ‘l’, ‘O’, or ‘I’
    #PEP8_OPTIONS="$PEP8_OPTIONS,E742"
    # E743  do not define functions named ‘l’, ‘O’, or ‘I’
    #PEP8_OPTIONS="$PEP8_OPTIONS,E743"

    # E9    Runtime
    # E901  SyntaxError or IndentationError
    #PEP8_OPTIONS="$PEP8_OPTIONS,E901"
    # E902  IOError
    #PEP8_OPTIONS="$PEP8_OPTIONS,E902"

    # W1    Indentation warning
    # W191  indentation contains tabs
    #PEP8_OPTIONS="$PEP8_OPTIONS,W191"

    # W2    Whitespace warning
    # W291  trailing whitespace
    PEP8_OPTIONS="$PEP8_OPTIONS,W291"
    # W292  no newline at end of file
    #PEP8_OPTIONS="$PEP8_OPTIONS,W292"
    # W293  blank line contains whitespace
    PEP8_OPTIONS="$PEP8_OPTIONS,W293"

    # W3    Blank line warning
    # W391  blank line at end of file
    #PEP8_OPTIONS="$PEP8_OPTIONS,W391"

    # W5    Line break warning
    # W503 (*)  line break before binary operator
    #PEP8_OPTIONS="$PEP8_OPTIONS,W503"
    # W504 (*)  line break after binary operator
    #PEP8_OPTIONS="$PEP8_OPTIONS,W504"
    # W505 (*^) doc line too long (82 > 79 characters)
    #PEP8_OPTIONS="$PEP8_OPTIONS,W505"

    # W6    Deprecation warning
    # W601  .has_key() is deprecated, use ‘in’
    #PEP8_OPTIONS="$PEP8_OPTIONS,W601"
    # W602  deprecated form of raising exception
    #PEP8_OPTIONS="$PEP8_OPTIONS,W602"
    # W603  ‘<>’ is deprecated, use ‘!=’
    #PEP8_OPTIONS="$PEP8_OPTIONS,W603"
    # W604  backticks are deprecated, use ‘repr()’
    #PEP8_OPTIONS="$PEP8_OPTIONS,W604"
    # W605  invalid escape sequence ‘x’
    #PEP8_OPTIONS="$PEP8_OPTIONS,W605"
    # W606  ‘async’ and ‘await’ are reserved keywords starting with Python 3.7
    #PEP8_OPTIONS="$PEP8_OPTIONS,W606"


    # Uncomment to see all pep8 errors
    #PEP8_OPTIONS=""


    # get list of python scripts without .py extension
    magic_file="$(find_aux gwms_magic)"
    FILE_MAGIC=
    [ -e  "$magic_file" ] && FILE_MAGIC="-m $magic_file"
    #if [ -e  "$magic_file" ]; then
    #    scripts=`find glideinwms -readable -path glideinwms/.git -prune -o -exec file -m "$magic_file" {} \; -a -type f | grep -i python | grep -vi python3 | grep -vi '\.py' | cut -d: -f1 | grep -v "\.html$" | sed -e 's/glideinwms\///g'`
    #else
    #    scripts=`find glideinwms -readable -path glideinwms/.git -prune -o -exec file {} \; -a -type f | grep -i python | grep -vi python3 | grep -vi '\.py' | cut -d: -f1 | grep -v "\.html$" | sed -e 's/glideinwms\///g'`
    #fi
    #scripts=$(find glideinwms -readable -path glideinwms/.git -prune -o -exec file $FILE_MAGIC {} \; -a -type f | grep -i ':.*python' | grep -vi python3 | grep -vi '\.py' | cut -d: -f1 | grep -v "\.html$" | sed -e 's/glideinwms\///g')
    scripts=$(find glideinwms -path glideinwms/.git -prune -o -path glideinwms/.tox -prune -o -exec file $FILE_MAGIC {} \; -a -type f | grep -i ':.*python' | grep -vi python3 | grep -vi '\.py' | cut -d: -f1 | grep -v "\.html$" | sed -e 's/glideinwms\///g')
    echo "-- DBG $(echo $scripts | wc -w | tr -d " ") scripts found using magic file ($FILE_MAGIC) --"
    cd "${GLIDEINWMS_SRC}"
    for script in $scripts; do
      #can't seem to get --ignore or --ignore-modules to work, so do it this way
      PYLINT_SKIP="False"
      for ignore in $PYLINT_IGNORE_LIST; do
          if [ "$ignore" = "$script" ] ; then
             echo "pylint skipping $script" >>  "$pylint_log"
             PYLINT_SKIP="True"
          fi
      done
      if [ "$PYLINT_SKIP" != "True" ]; then
          python3 -m pylint $PYLINT_OPTIONS ${script}  >> $pylint_log || log_nonzero_rc "pylint" $?
      fi
      python3 -m pycodestyle $PEP8_OPTIONS ${script} >> ${pep8_log} || log_nonzero_rc "pep8" $?
    done

    currdir=`pwd`
    files_checked=`echo $scripts`

    #now do all the .py files
    #shopt -s globstar
    #py_files=$(find . -readable -type f -name '*\.py')
    py_files=$(find . -path ./.git -prune -o -path ./.tox -prune -o -type f -name '*\.py')
    for file in $py_files
    do
      files_checked="$files_checked $file"
      PYLINT_SKIP="False"
      for ignore in $PYLINT_IGNORE_LIST; do
          if [ "$ignore" = "$file" ] ; then
             echo "pylint skipping $file" >>  "$pylint_log"
             PYLINT_SKIP="True"
          fi
      done
      if [ "$PYLINT_SKIP" != "True" ]; then
          python3 -m pylint $PYLINT_OPTIONS $file >> "$pylint_log" || log_nonzero_rc "pylint" $?
      fi
      python3 -m pycodestyle $PEP8_OPTIONS $file >> "${pep8_log}" || log_nonzero_rc "pep8" $?
    done
    awk '{$1=""; print $0}' ${pep8_log} | sort | uniq -c | sort -n > ${pep8_log}.sorted
    echo "-------------------" >> ${pep8_log}
    echo "error count summary" >> ${pep8_log}
    echo "-------------------" >> ${pep8_log}
    cat ${pep8_log}.sorted     >> ${pep8_log}
    cd $currdir

    echo "FILES_CHECKED=\"$files_checked\"" >> $results
    echo "FILES_CHECKED_COUNT=`echo $files_checked | wc -w | tr -d " "`" >> $results
    echo "PYLINT_ERROR_FILES_COUNT=`grep '^\*\*\*\*\*\*' $pylint_log | wc -l | tr -d " "`" >> $results
    echo "PYLINT_ERROR_COUNT=`grep '^E:' $pylint_log | wc -l | tr -d " "`" >> $results
    echo "PEP8_ERROR_COUNT=`cat ${pep8_log} | wc -l | tr -d " "`" >> $results
    echo "----------------"
    cat $results
    echo "----------------"

}


init_results_mail () {
    local mail_file=$1
    echo -n > "$mail_file"
}

init_results_logging() {
    local mail_file=$1
    cat >> "$mail_file" << TABLE_START
<body>

  <p>
  $(print_python_info "$mail_file")
  </p>
<table style="$HTML_TABLE">
  <thead style="$HTML_THEAD">
    <tr style="$HTML_TR">
      <th style="$HTML_THEAD_TH">GIT BRANCH</th>
      <th style="$HTML_THEAD_TH">FILES CHECKED</th>
      <th style="$HTML_THEAD_TH">FILES WITH ERRORS</th>
      <th style="$HTML_THEAD_TH">TOTAL ERRORS</th>
      <th style="$HTML_THEAD_TH">PEP8 ERRORS</th>
    </tr>
  </thead>
  <tbody>
TABLE_START

}


log_branch_results() {
    local mail_file=$1
    local branch_results=$2
    unset GIT_BRANCH
    unset GIT_CHECKOUT
    unset FILES_CHECKED_COUNT
    unset PYLINT_ERROR_FILES_COUNT
    unset PYLINT_ERROR_COUNT
    unset PEP8_ERROR_COUNT
    . "$branch_results"

    class=$GIT_CHECKOUT
    if [ "$class" = "PASSED" ]; then
        [ ${PYLINT_ERROR_COUNT:-1} -gt 0 ] && class="FAILED"
    fi
    if [ "$class" = "PASSED" ]; then
        cat >> "$mail_file" << TABLE_ROW_PASSED
<tr style="$HTML_TR">
    <th style="$HTML_TH">$GIT_BRANCH</th>
    <td style="$HTML_TD_PASSED">${FILES_CHECKED_COUNT:-NA}</td>
    <td style="$HTML_TD_PASSED">${PYLINT_ERROR_FILES_COUNT:-NA}</td>
    <td style="$HTML_TD_PASSED">${PYLINT_ERROR_COUNT:-NA}</td>
    <td style="$HTML_TD_PASSED">${PEP8_ERROR_COUNT:-NA}</td>
</tr>
TABLE_ROW_PASSED
    else
        cat >> "$mail_file" << TABLE_ROW_FAILED
<tr style="$HTML_TR">
    <th style="$HTML_TH">$GIT_BRANCH</th>
    <td style="$HTML_TD_FAILED">${FILES_CHECKED_COUNT:-NA}</td>
    <td style="$HTML_TD_FAILED">${PYLINT_ERROR_FILES_COUNT:-NA}</td>
    <td style="$HTML_TD_FAILED">${PYLINT_ERROR_COUNT:-NA}</td>
    <td style="$HTML_TD_FAILED">${PEP8_ERROR_COUNT:-NA}</td>
</tr>
TABLE_ROW_FAILED
    fi
}


finalize_results_logging() {
    local mail_file=$1
    cat >> "$mail_file" << TABLE_END
    </tbody>
</table>
</body>
TABLE_END
}

###############################################################################
# HTML inline CSS
HTML_TABLE="border: 1px solid black;border-collapse: collapse;"
HTML_THEAD="font-weight: bold;border: 0px solid black;background-color: #ffcc00;"
HTML_THEAD_TH="border: 0px solid black;border-collapse: collapse;font-weight: bold;background-color: #ffb300;padding: 8px;"

HTML_TH="border: 0px solid black;border-collapse: collapse;font-weight: bold;background-color: #00ccff;padding: 8px;"
HTML_TR="padding: 5px;text-align: center;"
HTML_TD="border: 1px solid black;border-collapse: collapse;padding: 5px;text-align: center;"

HTML_TR_PASSED="padding: 5px;text-align: center;"
HTML_TD_PASSED="border: 0px solid black;border-collapse: collapse;background-color: #00ff00;padding: 5px;text-align: center;"

HTML_TR_FAILED="padding: 5px;text-align: center;"
HTML_TD_FAILED="border: 0px solid black;border-collapse: collapse;background-color: #ff0000;padding: 5px;text-align: center;"



###############################################################################



print_help() {
    echo
    echo  "Usage:"
	echo "$1          Setup virtualenv and Run pylint and pycodestyle on the current branch in the source directory"
	echo "$1 BRANCHES  Setup virtualenv and Run pylint and pycodestyle on all BRANCHES (comma separated list of branch names)"
    echo "$1 -f BRANCHES  Setup virtualenv and Run pylint and pycodestyle on all BRANCHES, doing a git checkout -f (force) for "
    echo "          each new branch."
    echo
    echo "                    IF YOU USE -f INTERACTIVELY IT WILL ERASE UN CHECKED IN EDITS so be warned."
    echo
	echo "The source code (a clone of the GWMS git repository) is expected to be already in the ./glideinwms subdirectory of PWD (source dir)"
	echo "The script will checkout one by one and run pylint and pycodestyle on all listed BRANCHES, in the listed order"
        echo "At the end of the tests the last branch will be the one in the source directory."
	echo "The script has no cleanup. Will leave directories and result files in the working directory (virtualenv,  log files, ...)"
	echo "$1 -h        Print this message and exit"
	exit 0
}

if [ "x$1" = "x-h" -o "x$1" = "x--help" ]; then
    print_help $0
fi

GIT_FLAG=''
if [ "x$1" = "x-f" ]; then
    GIT_FLAG='-f'
    if [ "x$2" = "x-h" ]; then
        print_help $0
    elif [ "x$2" = "x" ]; then
        echo "Running on the current branch with -f not allowed."
        exit 1
    else
       git_branches="$2"
    fi
else
    git_branches="$1"
fi

WORKSPACE=$(pwd)
export GLIDEINWMS_SRC="$WORKSPACE"/glideinwms
export MYDIR=$(dirname $0)

if [ ! -d  "$GLIDEINWMS_SRC" ]; then
    echo "ERROR: $GLIDEINWMS_SRC not found!"
    echo "script running in $(pwd), expects a git managed glideinwms subdirectory"
    echo "exiting"
    exit 1
fi

ultil_file=$(find_aux utils.sh)

if [ ! -e  "$ultil_file" ]; then
    echo "ERROR: $ultil_file not found!"
    echo "script running in $(pwd), expects a util.sh file there or in the glideinwms src tree"
    echo "exiting"
    exit 1
fi

if ! . "$ultil_file" ; then
    echo "ERROR: $ultil_file contains errors!"
    echo "exiting"
    exit 1
fi


if [ "x$VIRTUAL_ENV" = "x" ]; then
     setup_python_venv "$WORKSPACE"
fi

# Jenkins will reuse the workspace on the slave node if it is available
# There is no reason for not using it, but we need to make sure we keep
# logs for same build together to make it easier to attach to the email
# notifications or for violations. $BUILD_NUMBER is only available when
# running this script from the jenkins environment
LOG_DIR="$WORKSPACE/$BUILD_NUMBER"
[ -d "$LOG_DIR" ] || mkdir -p "$LOG_DIR"

PYLINT_LOG="$LOG_DIR"/pylint.log
PEP8_LOG="$LOG_DIR"/pep8.log
RESULTS="$LOG_DIR"/results.log
RESULTS_MAIL="$LOG_DIR"/mail.results


init_results_mail "$RESULTS_MAIL"
init_results_logging "$RESULTS_MAIL"

if [ $# -eq 0 ]; then
    process_branch "$PYLINT_LOG" "$PEP8_LOG" "$RESULTS" "$gb"
    log_branch_results "$RESULTS_MAIL" "$RESULTS"
fi

for gb in $(echo "$git_branches" | sed -e 's/,/ /g')
do
    if [ -n "$gb" ]; then
        gb_escape=$(echo "$gb" | sed -e 's|/|_|g')
        pylint_log="$PYLINT_LOG.$gb_escape"
        pep8_log="$PEP8_LOG.$gb_escape"
        results="$RESULTS.$gb_escape"
    fi
    process_branch "$pylint_log" "$pep8_log" "$results" "$gb"
    log_branch_results "$RESULTS_MAIL" "$results"
done

finalize_results_logging "$RESULTS_MAIL"

#mail_results $RESULTS_MAIL "Pylint/PEP8 Validation Results"
