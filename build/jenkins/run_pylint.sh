#!/bin/sh


run_pylint() {
    # Get the log directory
    local log_dir=$1
    local branch_name=$2

    # Set the location of the logs
    pylint_log="${log_dir}/${branch_name}_pylint.log"
    pep8_log="${log_dir}/${branch_name}_pep8.log"
    results="${log_dir}/${branch_name}_pylint_results.log"

    # Initialize logs
    > $pylint_log
    > $pep8_log
    > $results

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
    echo "export FILES_CHECKED=\"$files_checked\"" >> $results
    echo "export FILES_CHECKED_COUNT=`echo $files_checked | wc -w | tr -d " "`" >> $results
    echo "export PYLINT_ERROR_FILES_COUNT=`grep '^\*\*\*\*\*\*' $pylint_log | wc -l | tr -d " "`" >> $results
    echo "export PYLINT_ERROR_COUNT=`grep '^E:' $pylint_log | wc -l | tr -d " "`" >> $results
    echo "export PEP8_ERROR_COUNT=`cat $pep8_log | wc -l | tr -d " "`" >> $results

    source $results
    return
}


if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    current_dir=$(pwd)

    WORKSPACE=`pwd`
    export GLIDEINWMS_SRC=$WORKSPACE/glideinwms

    source $GLIDEINWMS_SRC/build/jenkins/utils.sh
    setup_python_venv $WORKSPACE

    run_pylint $current_dir "Pylint"
fi
