#!/bin/bash

show_help(){
    PROG=$(basename $0)
    echo "generate a python coverage report for `pwd`/glideinwms"
    echo "usage:"
    echo "    $PROG -h: display this message"
    echo "    $PROG -b <branch>: check out <branch>, run a coverage report on it"
    echo "    $PROG -c: run a coverage report on the current branch"
    exit 0
}
[ "x$1" = "x" ]  && show_help


find_aux () {
    # $1 basename of the aux file
    [ -e "$MYDIR/$1" ] && { echo "$MYDIR/$1"; return; }
    [ -e "$GLIDEINWMS_SRC/$1" ] && { echo "$GLIDEINWMS_SRC/$1"; return; }
    false
}


while getopts ":hcb" option
do
    case "${option}"
    in
    h) show_help;;
    b) shift; BRANCH=$1;;
    c) BRANCH='current';;
    *) echo "illegal option: -$OPTARG"; show_help;;    
    esac
    shift $((OPTIND-1))
done


WORKSPACE=`pwd`
export GLIDEINWMS_SRC=${WORKSPACE}/glideinwms
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
     setup_python_venv $WORKSPACE
fi

cd ${GLIDEINWMS_SRC}/unittests
CURR_BRANCH=$(git rev-parse --abbrev-ref HEAD)
if [ "x$BRANCH" = "xcurrent" ]; then
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
for TST in $(ls test*.py); do
    echo '========>' $TST
    coverage run  --source="${SOURCES}" --omit="test_*.py"  -a $TST
done
coverage report > ${WORKSPACE}/coverage.report.${BR_NO_SLASH}
coverage html
mv htmlcov ${WORKSPACE}/htmlcov.${BR_NO_SLASH}
git checkout ${CURR_BRANCH}
