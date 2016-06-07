#!/bin/sh

WORKSPACE=`pwd`
export GLIDEINWMS_SRC=$WORKSPACE/glideinwms

source $GLIDEINWMS_SRC/build/jenkins/utils.sh

ERRORS=$WORKSPACE/errors
# pylint related variables
PYLINT_LOG=$WORKSPACE/pylint.log
PYLINT_RCFILE=/dev/null
#PYLINT_RCFILE=$WORKSPACE/pylint.cfg
PYLINT_OPTIONS="--errors-only --msg-template=\"{path}:{line}: [{msg_id}({symbol}), {obj}] {msg}\" --rcfile=$PYLINT_RCFILE"

# pep8 related variables
PEP8_LOG=$WORKSPACE/pep8.log
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

# Initialize logs
echo > $ERRORS
echo > $PYLINT_LOG
echo > $PEP8_LOG

setup_python_venv $WORKSPACE

# Generate pylint config file
pylint --generate-rcfile > $PYLINT_RCFILE
#cat $PYLINT_RCFILE

# get list of python scripts without .py extension
scripts=`find glideinwms -path glideinwms/.git -prune -o -exec file {} \; -a -type f | grep -i python | grep -vi '\.py' | cut -d: -f1`
echo $scripts
pylint $PYLINT_OPTIONS -e F0401 ${scripts}  >> $PYLINT_LOG || log_nonzero_rc "pylint" $?
pep8 $PEP8_OPTIONS ${scripts} >> $PEP8_LOG || log_nonzero_rc "pep8" $?

currdir=`pwd`
modules_checked=""

for dir in lib creation/lib factory frontend tools tools/lib
do
    cd ${GLIDEINWMS_SRC}/$dir

    for file in *.py
    do
      modules_checked="$modules_checked $file"
      pylint $PYLINT_OPTIONS $file >> $PYLINT_LOG || log_nonzero_rc "pylint" $?
      pep8 $PEP8_OPTIONS $file >> $PEP8_LOG || log_nonzero_rc "pep8" $?
    done
    cd $currdir
done
echo "Modules checked="$modules_checked >> $ERRORS

echo "----------------"
cat $ERRORS
echo "----------------"

