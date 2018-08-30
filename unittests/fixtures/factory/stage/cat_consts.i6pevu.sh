#!/bin/bash
#
# Project:
#   glideinWMS
#
# File Version: 
#

glidein_config=$1
tmp_fname=${glidein_config}.$$.tmp

dir_id=$2

function warn {
 echo `date` $@ 1>&2
}

# import add_config_line function
add_config_line_source=`grep '^ADD_CONFIG_LINE_SOURCE ' $glidein_config | awk '{print $2}'`
source $add_config_line_source

# import get_prefix function
get_id_selectors_source=`grep '^GET_ID_SELECTORS_SOURCE ' $glidein_config | awk '{print $2}'`
source $get_id_selectors_source

error_gen=`grep '^ERROR_GEN_PATH ' $glidein_config | awk '{print $2}'`

id_prefix=`get_prefix $dir_id`

###################################
# Find file names
consts_file=`grep "^${id_prefix}CONSTS_FILE " $glidein_config | awk '{print $2}'`
if [ -z "$consts_file" ]; then
    #warn "Cannot find ${id_prefix}CONSTS_FILE in $glidein_config!"
    STR="Cannot find ${id_prefix}CONSTS_FILE in $glidein_config!"
    "$error_gen" -error "cat_consts.sh" "Corruption" "$STR" "attribute" "${id_prefix}CONSTS_FILE"
    exit 1
fi

##################################
# Merge constants with config file
nr_lines=0
if [ -n "$consts_file" ]; then
    echo "# --- Provided $dir_id constants  ---" >> $glidein_config
    # merge constants
    while read line
    do
        # disable globbing but keep the splitting in $line
        ( set -f; add_config_line $line )
        let ++nr_lines
    done < "$consts_file"
    echo "# --- End $dir_id constants       ---" >> $glidein_config
fi

"$error_gen" -ok "cat_consts.sh" "NrAttributes" "$nr_lines"
exit 0
