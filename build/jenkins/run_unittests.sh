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
  -3          run unit tests using python3 (SL7 only)
EOF
}

filename="$(basename $0)"
VERBOSE=yes
PYTHON3=''

while getopts ":hqa3" option
do
  case "${option}"
  in
  h) help_msg; exit 0;;
  q) VERBOSE='';;
  a) LIST_FILES=yes;;
  3) PYTHON3=yes;;
  : ) echo "$filename: illegal option: -$OPTARG requires an argument" 1>&2; help_msg 1>&2; exit 1;;
  *) echo "$filename: illegal option: -$OPTARG" 1>&2; help_msg 1>&2; exit 1;;
  \?) echo "$filename: illegal option: -$OPTARG" 1>&2; help_msg 1>&2; exit 1;;
  esac
done

# f) BRANCHES_FILE=$OPTARG;;

shift $((OPTIND-1))

# Script setup
WORKSPACE=`pwd`
export GLIDEINWMS_SRC=$WORKSPACE/glideinwms

source $GLIDEINWMS_SRC/build/jenkins/utils.sh

if [ "$PYTHON3" = "yes" ]; then
    setup_python3_venv $WORKSPACE
else
    setup_python_venv $WORKSPACE
fi

cd $GLIDEINWMS_SRC/unittests

# Example file lists (space separated list)
files="test_frontend.py"
files="test_frontend_element.py"
files="test_frontend.py test_frontend_element.py"

if [ -n "$LIST_FILES" ]; then
    files_list="$(ls test_*py)"
else
    files_list=$@
fi

for file in $files_list ; do
    [ -n "$VERBOSE" ] && echo "TESTING ==========> $file"
    if [ -n "$VERBOSE" ]; then
        ./$file || log_nonzero_rc "$file" $?
    else
        ./$file
    fi
done
