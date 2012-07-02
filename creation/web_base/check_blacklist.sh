#!/bin/bash
#
# Project:
#   glideinWMS
#
# File Version: 
#
# Description:
#   This script checks that the node is not in a blacklist
#

function check_blacklist {
    myname=`uname -n`
    if [ $? -ne 0 ]; then
        #echo "Cannot get my name!" 1>&2
        STR="Cannot get my name!"
        "$error_gen" -error "check_blacklist.sh" "WN_Resource" "$STR" "command" "uname"
        exit 1
    fi
    emyname=`echo $myname | sed 's/\./\\\./g'`
    grep -q -e "^'$emyname'" "$blacklist_file"
    if [ $? -eq 0 ]; then
        #echo "My name '$myname' is in blacklist! Exiting." 1>&2
        STR="My name '$myname' is in blacklist! Exiting."
        "$error_gen" -error "check_blacklist.sh" "WN_Resource" "$STR" "blacklist" "$myname"
        exit 1
    fi

    myip=`host $myname | awk '{print $4}'`
    if [ $? -ne 0 ]; then
        #ignore errors, here, since host may fail
        return 0
    fi
    emyip=`echo $myip | sed 's/\./\\\./g'`
    grep -q -e "^'$emyip'" "$blacklist_file"
    if [ $? -eq 0 ]; then
        #echo "My ip '$myip' is in blacklist! Exiting." 1>&2
        STR="My ip '$myip' is in blacklist! Exiting."
        "$error_gen" -error "check_blacklist.sh" "WN_Resource" "$STR" "blacklist" "$myip"
        exit 1
    fi

    return 0
}

############################################################
#
# Main
#
############################################################

glidein_config=$1
tmp_fname=${glidein_config}.$$.tmp

error_gen=`grep '^ERROR_GEN_PATH ' $glidein_config | awk '{print $2}'`

# Assume all functions exit on error
config_file=$1
dir_id=$2

# import get_prefix function
get_id_selectors_source=`grep '^GET_ID_SELECTORS_SOURCE ' $config_file | awk '{print $2}'`
source $get_id_selectors_source

id_prefix=`get_prefix $dir_id`

blacklist_file=`grep -i "^${id_prefix}BLACKLIST_FILE " $config_file | awk '{print $2}'`
if [ -n "$blacklist_file" ]; then
  check_blacklist
fi

"$error_gen" -ok "check_blacklist.sh" "Blacklist" "${id_prefix}BLACKLIST_FILE"
