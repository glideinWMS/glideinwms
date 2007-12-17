#!/bin/bash

config_file=$1
tmp_fname=${config_file}.$$.tmp

entry_dir=$2

function warn {
 echo `date` $@ 1>&2
}

###################################
# Add a line to the config file
function add_config_line {
    id=$1

    rm -f $tmp_fname #just in case one was there
    mv $config_file $tmp_fname
    if [ $? -ne 0 ]; then
	warn "Error renaming $config_file into $tmp_fname"
	exit 1
    fi
    grep -v "^$id " $tmp_fname > $config_file
    echo "$@" >> $config_file
    rm -f $tmp_fname
}

if [ "$entry_dir" == "main" ]; then 
    ###################################
    # Find file names
    consts_file=`grep "^CONSTS_FILE " $config_file | awk '{print $2}'`
    if [ -z "$consts_file" ]; then
	warn "Cannot find CONSTS_FILE in $config_file!"
	exit 1
    fi
else
    ###################################
    # Find file names
    consts_file=`grep "^CONSTS_ENTRY_FILE " $config_file | awk '{print $2}'`
    if [ -z "$consts_file" ]; then
	warn "Cannot find CONSTS_ENTRY_FILE in $config_file!"
	exit 1
    fi
fi

##################################
# Merge constants with config file
if [ -n "$consts_file" ]; then
    echo "# --- Provided $entry_dir constants  ---" >> $config_file
    # merge constants
    while read line
    do
	add_config_line $line
    done < "$consts_file"
    echo "# --- End $entry_dir constants       ---" >> $config_file
fi
