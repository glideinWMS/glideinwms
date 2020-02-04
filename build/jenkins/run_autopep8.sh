#!/bin/bash

usage () {
    echo "usage: `basename $0` change|restore|usage"
    echo "     change: run autopep8 -a -i on all python files in $GLIDEINWMS_SRC"
    echo "     restore: check all python files back out from git"
    echo "     usage: this message"
    exit 0
}

find_aux () {
    # $1 basename of the aux file
    [ -e "$MYDIR/$1" ] && { echo "$MYDIR/$1"; return }
    [ -e "$GLIDEINWMS_SRC/$1" ] && { echo "$GLIDEINWMS_SRC/$1"; return }
    false
}

process_branch() {

    # get list of python scripts without .py extension
    magic_file="$(find_aux gwms_magic)"
    FILE_MAGIC=
    [ -e  "$magic_file" ] && FILE_MAGIC="-m $magic_file"
    scripts=$(find glideinwms -readable -path glideinwms/.git -prune -o -exec file $FILE_MAGIC {} \; -a -type f | grep -i ':.*python' | grep -vi python3 | grep -vi '\.py' | cut -d: -f1 | grep -v "\.html$" | sed -e 's/glideinwms\///g')
    cd "${GLIDEINWMS_SRC}"
    for script in $scripts; do
      echo autopep8 -a -i ${script} 
      autopep8 -a -i ${script} 
    done

    files_checked=`echo $scripts`

    #now do all the .py files
    shopt -s globstar
    for file in **/*.py
    do
      echo autopep8 -a -i  $file 
      autopep8 -a -i  $file 
      files_checked="$files_checked $file"
    done

    echo "FILES_CHANGED=\"$files_checked\"" 
    echo "FILES_CHANGED_COUNT=`echo $files_checked | wc -w | tr -d " "`"

}

restore_branch() {


    # get list of python scripts without .py extension
    magic_file="$(find_aux gwms_magic)"
    FILE_MAGIC=
    [ -e  "$magic_file" ] && FILE_MAGIC="-m $magic_file"
    scripts=$(find glideinwms -readable -path glideinwms/.git -prune -o -exec file $FILE_MAGIC {} \; -a -type f | grep -i ':.*python' | grep -vi python3 | grep -vi '\.py' | cut -d: -f1 | grep -v "\.html$" | sed -e 's/glideinwms\///g')
    cd "${GLIDEINWMS_SRC}"
    for script in $scripts; do
      echo git checkout ${script} 
      git checkout ${script} 
    done

    files_checked=`echo $scripts`

    #now do all the .py files
    shopt -s globstar
    for file in **/*.py
    do
      echo git checkout $file 
      git checkout  $file 
      files_checked="$files_checked $file"
    done

    echo "FILES_RESTORED=\"$files_checked\""
    echo "FILES_RESTORED_COUNT=`echo $files_checked | wc -w | tr -d " "`" 

}



WORKSPACE=`pwd`
export GLIDEINWMS_SRC=$WORKSPACE/glideinwms
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


if [ "$1" = "change"  ]; then
    process_branch
elif [ "$1" = "restore"  ]; then
    restore_branch
else
    usage
fi

