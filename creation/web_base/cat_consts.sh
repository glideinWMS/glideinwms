#!/bin/bash

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

#
# Project:
#   glideinWMS
#
# File Version:
#

glidein_config="$1"
tmp_fname="${glidein_config}.$$.tmp"

dir_id=$2

function warn {
 echo `date` "$@" 1>&2
}

# import add_config_line function
add_config_line_source=$(grep -m1 '^ADD_CONFIG_LINE_SOURCE ' "$glidein_config" | cut -d ' ' -f 2-)
# shellcheck source=./add_config_line.source
. "$add_config_line_source"

# import get_prefix function
get_id_selectors_source=$(gconfig_get GET_ID_SELECTORS_SOURCE "$glidein_config")
. "$get_id_selectors_source"

error_gen=$(gconfig_get ERROR_GEN_PATH "$glidein_config")

id_prefix=$(get_prefix $dir_id)

###################################
# Find file names
consts_file=$(gconfig_get "${id_prefix}CONSTS_FILE" "$glidein_config")
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
    echo "# --- Provided $dir_id constants  ---" >> "$glidein_config"
    # merge constants
    while read line
    do
        # disable globbing but keep the splitting in $line
	# ( set -f; add_config_line $line )
	# const file is space+tab separated but unquoted variable keeps only the splitting (not space safe for the value)
	# var_name keeps lines w/ no separator
	var_name="`echo "$line" | cut -f 1 | sed -e 's/[[:space:]]*$//'`"
	var_value="`echo "$line" | cut -s -f 2- | sed -e 's/[[:space:]]*$//'`"
        ( set -f; gconfig_add $var_name "$var_value" )
        let ++nr_lines
    done < "$consts_file"
    echo "# --- End $dir_id constants       ---" >> "$glidein_config"
fi

"$error_gen" -ok "cat_consts.sh" "NrAttributes" "$nr_lines"
exit 0
