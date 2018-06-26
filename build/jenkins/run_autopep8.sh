#!/bin/bash

process_branch() {


    # get list of python scripts without .py extension
    scripts=`find glideinwms -path glideinwms/.git -prune -o -exec file {} \; -a -type f | grep -i python | grep -vi '\.py' | cut -d: -f1 | grep -v "\.html$" | sed -e 's/glideinwms\///g'`
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
    scripts=`find glideinwms -path glideinwms/.git -prune -o -exec file {} \; -a -type f | grep -i python | grep -vi '\.py' | cut -d: -f1 | grep -v "\.html$" | sed -e 's/glideinwms\///g'`
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

help () {
    echo "usage: `basename $0` change|restore|help"
    echo "     change: run autopep8 -a -i on all python files in $GLIDEINWMS_SRC"
    echo "     restore: check all python files back out from git"
    echo "     help: this message"
}

WORKSPACE=`pwd`
export GLIDEINWMS_SRC=$WORKSPACE/glideinwms
source $GLIDEINWMS_SRC/build/jenkins/utils.sh

if [ "x$VIRTUAL_ENV" = "x" ]; then
     setup_python_venv $WORKSPACE
fi



if [ "$1" = "change"  ]; then
    process_branch
elif [ "$1" = "restore"  ]; then
    restore_branch
else
    help
fi


