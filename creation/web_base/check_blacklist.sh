#!/bin/bash

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

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
        "$error_gen" -error "check_blacklist.sh" "WN_Resource" "$STR" "hostname" "$myname"
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
        "$error_gen" -error "check_blacklist.sh" "WN_Resource" "$STR" "IP" "$myip"
        exit 1
    fi

    return 0
}

############################################################
#
# Main
#
############################################################

# Assume all functions exit on error
config_file="$1"
dir_id=$2

# import add_config_line function
add_config_line_source=$(grep -m1 '^ADD_CONFIG_LINE_SOURCE ' "$config_file" | cut -d ' ' -f 2-)
# shellcheck source=./add_config_line.source
. "$add_config_line_source"

error_gen=$(gconfig_get ERROR_GEN_PATH "$config_file")

# import get_prefix function
get_id_selectors_source=$(gconfig_get GET_ID_SELECTORS_SOURCE "$config_file")
. "$get_id_selectors_source"

id_prefix=$(get_prefix $dir_id)

blacklist_file=$(gconfig_get "${id_prefix}"BLACKLIST_FILE "$config_file")
if [ -n "$blacklist_file" ]; then
  check_blacklist
fi

"$error_gen" -ok "check_blacklist.sh"
exit 0
