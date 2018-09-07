#!/bin/sh

function help_msg {
  #filename="$(basename $0)"
  cat << EOF
$filename [options] TEST_FILES
  Runs the unit tests on TEST_FILES files in glidinwms/unittests/
$filename -a [other options]
  Run the unit tests on all the files in glidinwms/unittests/ named test_*
Runs unit tests and exit the results to standard output. Failed tests will cause also a line starting with ERROR:
  -q          Just print the unit test output
  -h          print this message
  -a          run on all unit tests (see above)
  -c          generate a coverage report while running unit tests
  -3          run unit tests using python3 (SL7 only)
EOF
}

filename="$(basename $0)"
VERBOSE=yes
PYTHON3=''


while getopts ":hqac3" option
do
  case "${option}"
  in
  h) help_msg; exit 0;;
  q) VERBOSE='';;
  a) LIST_FILES=yes;;
  3) PYTHON3=yes;;
  c) COVERAGE=yes;;
  :) echo "$filename: illegal option: -$OPTARG requires an argument" 1>&2; help_msg 1>&2; exit 1;;
  *) echo "$filename: illegal option: -$OPTARG" 1>&2; help_msg 1>&2; exit 1;;
  \?) echo "$filename: illegal option: -$OPTARG" 1>&2; help_msg 1>&2; exit 1;;
  esac
done

shift $((OPTIND-1))


# Script setup
WORKSPACE=`pwd`
export GLIDEINWMS_SRC=$WORKSPACE/glideinwms



if [ ! -e  $GLIDEINWMS_SRC/build/jenkins/utils.sh ]; then
    echo "ERROR: $GLIDEINWMS_SRC/build/jenkins/utils.sh not found!"
    echo "script running in `pwd`, expects a git managed glideinwms subdirectory"
    echo "exiting"
    exit 1
fi

if ! source $GLIDEINWMS_SRC/build/jenkins/utils.sh ; then
    echo "ERROR: $GLIDEINWMS_SRC/build/jenkins/utils.sh contains errors!"
    echo "exiting"
    exit 1
fi


if [ "x$VIRTUAL_ENV" = "x" ]; then
    if [ "$PYTHON3" = "yes" ]; then
        setup_python3_venv $WORKSPACE
    else
        setup_python_venv $WORKSPACE
    fi
fi
cd $GLIDEINWMS_SRC/unittests
SOURCES="${GLIDEINWMS_SRC},${GLIDEINWMS_SRC}/factory/"
SOURCES="${SOURCES},${GLIDEINWMS_SRC}/factory/tools,${GLIDEINWMS_SRC}/frontend"
SOURCES="${SOURCES},${GLIDEINWMS_SRC}/frontend/tools,${GLIDEINWMS_SRC}/install"
SOURCES="${SOURCES},${GLIDEINWMS_SRC}/install/services,${GLIDEINWMS_SRC}/lib"
SOURCES="${SOURCES},${GLIDEINWMS_SRC}/tools,${GLIDEINWMS_SRC}/tools/lib"


# Example file lists (space separated list)
files="test_frontend.py"
files="test_frontend_element.py"
files="test_frontend.py test_frontend_element.py"

if [ -n "$LIST_FILES" ]; then
    files_list="$(ls test_*py)"
else
    files_list=$@
fi

TIMEOUTCMD=''
COVERAGECMD=''

if [ "x$TIME_LIMIT" = "x" ]; then
    TIME_LIMIT=900
fi
if [ "$PYTHON3" = "yes" ]; then
    TIMEOUTCMD="timeout --preserve-status $TIME_LIMIT "
fi

if [ "$COVERAGE" = "yes" ]; then
    coverage erase
    COVERAGECMD="coverage run  --source=${SOURCES}"' --omit=test_*.py  -a '
fi

for file in $files_list ; do
    [ -n "$VERBOSE" ] && echo; echo "TESTING ==========> $file"
    $TIMEOUTCMD $COVERAGECMD ./$file
    TEST_STATUS=$?
    if [ "$TEST_STATUS" = "143" ]; then
        echo "$file reached time limit of $TIME_LIMIT seconds and was killed"
    fi
    if [ -n "$VERBOSE" ] && [ "$TEST_STATUS" != "0" ]; then
        log_nonzero_rc "$file" $TEST_STATUS
    fi
done

CURR_BRANCH=$(git rev-parse --abbrev-ref HEAD)
BR_NO_SLASH=$(echo ${CURR_BRANCH} | sed -e 's/\//_/g')

if [ "$COVERAGE" = "yes" ]; then
    PV=$(python --version 2>&1| sed  's/ /_/g')
    coverage report > ${WORKSPACE}/coverage.report.$PV.${BR_NO_SLASH}
    coverage html
    mv htmlcov ${WORKSPACE}/htmlcov.$PV.${BR_NO_SLASH}
fi

