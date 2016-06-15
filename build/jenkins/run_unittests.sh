#!/bin/sh

WORKSPACE=`pwd`
export GLIDEINWMS_SRC=$WORKSPACE/glideinwms

source $GLIDEINWMS_SRC/build/jenkins/utils.sh

setup_python_venv $WORKSPACE

cd $GLIDEINWMS_SRC/unittests
files="test_frontend.py"
files="test_frontend_element.py"
files="test_frontend.py test_frontend_element.py"

for file in $@ ; do
    echo "TESTING ==========> $file"
    ./$file || log_nonzero_rc "$file" $?
done
