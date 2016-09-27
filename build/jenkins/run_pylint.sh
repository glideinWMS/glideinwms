#!/bin/sh

process_branch() {
    local pylint_log=$1
    local pep8_log=$2
    local results=$3
    local git_branch=$4

    echo "===================================================================="
    echo "GIT BRANCH: $git_branch"
    echo "===================================================================="
    # Initialize logs
    echo -n > $pylint_log
    echo -n > $pep8_log
    echo -n > $results

    echo "GIT_BRANCH=\"$git_branch\"" >> $results
    if [ -n "$git_branch" ]; then
        cd $GLIDEINWMS_SRC
        git checkout $git_branch
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

    # pylint related variables
    PYLINT_RCFILE=/dev/null
    #PYLINT_RCFILE=$WORKSPACE/pylint.cfg
    #PYLINT_OPTIONS="--errors-only --msg-template=\"{path}:{line}: [{msg_id}({symbol}), {obj}] {msg}\" --rcfile=$PYLINT_RCFILE"
    PYLINT_OPTIONS="--errors-only --rcfile=$PYLINT_RCFILE"

    # pep8 related variables
    # default: E121,E123,E126,E226,E24,E704
    # E501 line too long (90 > 79 characters)
    # E251 unexpected spaces around keyword / parameter equals
    # E303 too many blank lines (2)
    # E225 missing whitespace around operator
    # E231 missing whitespace after ','
    # E228 missing whitespace around modulo operator
    # E302 expected 2 blank lines, found 1
    # E221 multiple spaces before operator
    # E261 at least two spaces before inline comment
    # E111 indentation is not a multiple of four
    # W293 blank line contains whitespace
    # W291 trailing whitespace
    # E265 block comment should start with '# '

    PEP8_OPTIONS="--ignore=E121,E123,E126,E226,E24,E704,E501,E251,E303,E225,E231,E228,E302,E221,E261,E111,W293,W291,E265"

    # Generate pylint config file
    #pylint --generate-rcfile > $PYLINT_RCFILE
    #cat $PYLINT_RCFILE

    # get list of python scripts without .py extension
    scripts=`find glideinwms -path glideinwms/.git -prune -o -exec file {} \; -a -type f | grep -i python | grep -vi '\.py' | cut -d: -f1 | grep -v "\.html$"`
    pylint $PYLINT_OPTIONS -e F0401 ${scripts}  >> $pylint_log || log_nonzero_rc "pylint" $?
    pep8 $PEP8_OPTIONS ${scripts} >> $pep8_log || log_nonzero_rc "pep8" $?

    currdir=`pwd`
    files_checked=`echo $scripts`

    for dir in lib creation/lib factory frontend tools tools/lib
    do
        cd ${GLIDEINWMS_SRC}/$dir

        for file in *.py
        do
          files_checked="$files_checked $file"
          pylint $PYLINT_OPTIONS $file >> $pylint_log || log_nonzero_rc "pylint" $?
          pep8 $PEP8_OPTIONS $file >> $pep8_log || log_nonzero_rc "pep8" $?
        done
        cd $currdir
    done
    echo "FILES_CHECKED=\"$files_checked\"" >> $results
    echo "FILES_CHECKED_COUNT=`echo $files_checked | wc -w`" >> $results
    echo "PYLINT_ERROR_FILES_COUNT=`grep '^\*\*\*\*\*\*' $pylint_log | wc -l`" >> $results
    echo "PYLINT_ERROR_COUNT=`grep '^E:' $pylint_log | wc -l`" >> $results
    echo "PEP8_ERROR_COUNT=`cat $pep8_log | wc -l`" >> $results
    echo "----------------"
    cat $results
    echo "----------------"
}


init_results_mail () {
    local mail_file=$1
    echo -n > $mail_file
}

init_results_logging() {
    local mail_file=$1
    cat >> $mail_file << TABLE_START
<body>

<style>
table, th, td {
    border: 1px solid black;
    border-collapse: collapse;
}
thead, th {
    font-weight: bold;
    border: 0px solid black;
}
thead {
    background-color: #ffcc00;
}
th {
    background-color: #00ccff;
    padding: 8px;
}
tr, td {
    padding: 5px;
    text-align: center;
}
tr.failed, td.failed {
    background-color: #ff0000;
    border: 0px solid black;
}
tr.passed, td.passed {
    background-color: #00ff00;
    border: 0px solid black;
}
</style>

  <p>
`print_python_info $mail_file`
  </p>
<table>
  <thead>
    <tr>
      <th>GIT BRANCH</th>
      <th>FILES CHECKED</th>
      <th>FILES WITH ERRORS</th>
      <th>TOTAL ERRORS</th>
      <th>PEP8 ERRORS</th>
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
    source $branch_results

    class=$GIT_CHECKOUT
    if [ "$class" = "PASSED" ]; then
        [ ${PYLINT_ERROR_COUNT:-1} -gt 0 ] && class="FAILED"
    fi
    cat >> $mail_file << TABLE_ROW
<tr class='$class'>
    <th>$GIT_BRANCH</th>
    <td class='$class'>${FILES_CHECKED_COUNT:-NA}</td>
    <td class='$class'>${PYLINT_ERROR_FILES_COUNT:-NA}</td>
    <td class='$class'>${PYLINT_ERROR_COUNT:-NA}</td>
    <td class='$class'>${PEP8_ERROR_COUNT:-NA}</td>
</tr>
TABLE_ROW
}


finalize_results_logging() {
    local mail_file=$1
    cat >> $mail_file << TABLE_END
    </tbody>
</table>
</body>
TABLE_END
}

###############################################################################


git_branches="$1"
WORKSPACE=`pwd`
export GLIDEINWMS_SRC=$WORKSPACE/glideinwms

source $GLIDEINWMS_SRC/build/jenkins/utils.sh
setup_python_venv $WORKSPACE

# Jenkins will reuse the workspace on the slave node if it is available
# There is no reason for not using it, but we need to make sure we keep
# logs for same build together to make it easier to attach to the email
# notifications or for violations. $BUILD_NUMBER is only available when
# running this script from the jenkins environment
LOG_DIR=$WORKSPACE/$BUILD_NUMBER
[ -d $LOG_DIR ] || mkdir -p $LOG_DIR

PYLINT_LOG=$LOG_DIR/pylint.log
PEP8_LOG=$LOG_DIR/pep8.log
RESULTS=$LOG_DIR/results.log
RESULTS_MAIL=$LOG_DIR/mail.results


init_results_mail $RESULTS_MAIL
init_results_logging $RESULTS_MAIL

if [ $# -eq 0 ]; then
    process_branch $PYLINT_LOG $PEP8_LOG $RESULTS $gb
    log_branch_results $RESULTS_MAIL $RESULTS
fi

for gb in `echo $git_branches | sed -e 's/,/ /g'`
do
    if [ -n "$gb" ]; then
        gb_escape=`echo $gb | sed -e 's|/|_|g'`
        pylint_log="$PYLINT_LOG.$gb_escape"
        pep8_log="$PEP8_LOG.$gb_escape"
        results="$RESULTS.$gb_escape"
    fi
    process_branch $pylint_log $pep8_log $results $gb
    log_branch_results $RESULTS_MAIL $results
done

finalize_results_logging $RESULTS_MAIL

#mail_results $RESULTS_MAIL "Pylint/PEP8 Validation Results"
