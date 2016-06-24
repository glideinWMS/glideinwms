#!/bin/sh

process_branch() {
    local git_branch=$1

    echo "===================================================================="
    echo "GIT BRANCH: $git_branch"
    echo "===================================================================="
    # Initialize logs
    echo -n > $PYLINT_LOG
    echo -n > $PEP8_LOG
    echo -n > $RESULTS

    echo "GIT_BRANCH=\"$git_branch\"" >> $RESULTS
    if [ -n "$git_branch" ]; then
        cd $GLIDEINWMS_SRC
        git checkout $git_branch
        cd $WORKSPACE
        if [ $? -ne 0 ]; then
            log_nonzero_rc "pep8" $?
            echo "GIT_CHECKOUT=\"FAILED\"" >> $RESULTS
            exit 1
        fi
    fi
    # Consider success if no git checkout was done
    echo "GIT_CHECKOUT=\"PASSED\"" >> $RESULTS

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
    pylint $PYLINT_OPTIONS -e F0401 ${scripts}  >> $PYLINT_LOG || log_nonzero_rc "pylint" $?
    pep8 $PEP8_OPTIONS ${scripts} >> $PEP8_LOG || log_nonzero_rc "pep8" $?

    currdir=`pwd`
    files_checked=`echo $scripts`

    for dir in lib creation/lib factory frontend tools tools/lib
    do
        cd ${GLIDEINWMS_SRC}/$dir

        for file in *.py
        do
          files_checked="$files_checked $file"
          pylint $PYLINT_OPTIONS $file >> $PYLINT_LOG || log_nonzero_rc "pylint" $?
          pep8 $PEP8_OPTIONS $file >> $PEP8_LOG || log_nonzero_rc "pep8" $?
        done
        cd $currdir
    done
    echo "FILES_CHECKED=\"$files_checked\"" >> $RESULTS
    echo "FILES_CHECKED_COUNT=`echo $files_checked | wc -w`" >> $RESULTS
    echo "PYLINT_ERROR_FILES_COUNT=`grep '^\*\*\*\*\*\*' $PYLINT_LOG | wc -l`" >> $RESULTS
    echo "PYLINT_ERROR_COUNT=`grep '^E:' $PYLINT_LOG | wc -l`" >> $RESULTS
    echo "PEP8_ERROR_COUNT=`cat $PEP8_LOG | wc -l`" >> $RESULTS
    echo "----------------"
    cat $RESULTS
    echo "----------------"
}


init_results_mail () {
    local mail_file=$1
    echo -n > $mail_file
    cat > $mail_file << EOF
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
}
tr, td {
    padding: 5px;
}
</style>

EOF
}

init_results_logging() {
    local mail_file=$1
    cat >> $mail_file << TABLE_START
<body>

  <p>
`print_python_info $mail_file`
  </p>
<table>
  <thead>
    <tr>
      <td>GIT BRANCH</td>
      <td>FILES CHECKED</td>
      <td>FILES WITH ERRORS</td>
      <td>TOTAL ERRORS</td>
      <td>PEP8 ERRORS</td>
    </tr>
  </thead>
  <tbody>
TABLE_START

}


log_branch_results() {
    local mail_file=$1
    local branch_results=$2
    source $branch_results

    cat >> $mail_file << TABLE_ROW
<tr>
    <td>$GIT_BRANCH</td>
    <td>$FILES_CHECKED_COUNT</td>
    <td>$PYLINT_ERROR_FILES_COUNT</td>
    <td>$PYLINT_ERROR_COUNT</td>
    <td>$PEP8_ERROR_COUNT</td>
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

PYLINT_LOG=$WORKSPACE/pylint.log
PEP8_LOG=$WORKSPACE/pep8.log
RESULTS=$WORKSPACE/results.log
RESULTS_MAIL=$WORKSPACE/mail.results


init_results_mail $RESULTS_MAIL
init_results_logging $RESULTS_MAIL

if [ $# -eq 0 ]; then
    process_branch $gb
    log_branch_results $RESULTS_MAIL $RESULTS
fi

for gb in `echo $git_branches | sed -e 's/,/ /g'`
do

    if [ -n "$gb" ]; then
        PYLINT_LOG="$PYLINT_LOG.$gb"
        PEP8_LOG="$PEP8_LOG.$gb"
        RESULTS="$RESULTS.$gb"
    fi
    process_branch $gb
    log_branch_results $RESULTS_MAIL $RESULTS
done

finalize_results_logging $RESULTS_MAIL

#mail_results $RESULTS_MAIL "Pylint/PEP8 Validation Results"
