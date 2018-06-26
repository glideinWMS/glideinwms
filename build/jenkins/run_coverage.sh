#!/bin/bash

show_help(){
    PROG=$(basename $0)
    echo "generate a python coverage report for `pwd`/glideinwms"
    echo "usage:"
    echo "    $PROG help: display this message"
    echo "    $PROG <branch>: check out <branch>, run a coverage report on it"
    echo "    $PROG current: run a coverage report on the current branch"
}
BRANCH=$1
if [ "$BRANCH" = "help" ] || [ "x$BRANCH" = "x" ]; then
    show_help
    exit 0
fi

WORKSPACE=`pwd`
export GLIDEINWMS_SRC=${WORKSPACE}/glideinwms
source ${GLIDEINWMS_SRC}/build/jenkins/utils.sh

if [ "x$VIRTUAL_ENV" = "x" ]; then
         setup_python_venv ${WORKSPACE}
fi

cd ${GLIDEINWMS_SRC}/unittests
CURR_BRANCH=$(git rev-parse --abbrev-ref HEAD)
if [ "$BRANCH" = "current" ]; then
    BRANCH=${CURR_BRANCH}
else
    git checkout ${BRANCH}
fi
SOURCES="${GLIDEINWMS_SRC},${GLIDEINWMS_SRC}/factory/"
SOURCES="${SOURCES},${GLIDEINWMS_SRC}/factory/tools,${GLIDEINWMS_SRC}/frontend"
SOURCES="${SOURCES},${GLIDEINWMS_SRC}/frontend/tools,${GLIDEINWMS_SRC}/install"
SOURCES="${SOURCES},${GLIDEINWMS_SRC}/install/services,${GLIDEINWMS_SRC}/lib"
SOURCES="${SOURCES},${GLIDEINWMS_SRC}/tools,${GLIDEINWMS_SRC}/tools/lib"
BR_NO_SLASH=$(echo ${BRANCH} | sed -e 's/\//-/g')
coverage erase
coverage run  --source="${SOURCES}" --omit="test_*.py"  -m unittest2 discover -s . 
coverage report > ${WORKSPACE}/coverage.report.${BR_NO_SLASH}
coverage html
mv htmlcov ${WORKSPACE}/htmlcov.${BR_NO_SLASH}
git checkout ${CURR_BRANCH}
