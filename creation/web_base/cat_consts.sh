#!/bin/bash

glidein_config=$1
tmp_fname=${glidein_config}.$$.tmp

entry_dir=$2

function warn {
 echo `date` $@ 1>&2
}

# import add_config_line function
add_config_line_source=`grep '^ADD_CONFIG_LINE_SOURCE ' $glidein_config | awk '{print $2}'`
source $add_config_line_source

if [ "$entry_dir" == "main" ]; then 
    ###################################
    # Find file names
    consts_file=`grep "^CONSTS_FILE " $glidein_config | awk '{print $2}'`
    if [ -z "$consts_file" ]; then
	warn "Cannot find CONSTS_FILE in $glidein_config!"
	exit 1
    fi
else
    ###################################
    # Find file names
    consts_file=`grep "^CONSTS_ENTRY_FILE " $glidein_config | awk '{print $2}'`
    if [ -z "$consts_file" ]; then
	warn "Cannot find CONSTS_ENTRY_FILE in $glidein_config!"
	exit 1
    fi
fi

##################################
# Merge constants with config file
if [ -n "$consts_file" ]; then
    echo "# --- Provided $entry_dir constants  ---" >> $glidein_config
    # merge constants
    while read line
    do
	add_config_line $line
    done < "$consts_file"
    echo "# --- End $entry_dir constants       ---" >> $glidein_config
fi
