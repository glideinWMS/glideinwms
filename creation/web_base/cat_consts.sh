#!/bin/bash

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

glidein_config="$1"

dir_id=$2

warn() {
  echo "$(date)" "$@" 1>&2
}

# import add_config_line function
add_config_line_source=$(grep -m1 '^ADD_CONFIG_LINE_SOURCE ' "$glidein_config" | cut -d ' ' -f 2-)
# shellcheck source=./add_config_line.source
. "$add_config_line_source"

# import get_prefix function
get_id_selectors_source=$(gconfig_get GET_ID_SELECTORS_SOURCE "$glidein_config")
# shellcheck source=./get_id_selectors.source
. "$get_id_selectors_source"

error_gen=$(gconfig_get ERROR_GEN_PATH "$glidein_config")

id_prefix=$(get_prefix $dir_id)

###################################
# Find name of file with constants
# The file with constants have some initial header/comment lines that start with "#" and
# the following lines that start with the constant name, followed by space and tab and the constant value
consts_file=$(gconfig_get "${id_prefix}CONSTS_FILE" "$glidein_config")
if [[ -z "$consts_file" ]]; then
    #warn "Cannot find ${id_prefix}CONSTS_FILE in $glidein_config!"
    STR="Cannot find ${id_prefix}CONSTS_FILE in $glidein_config!"
    "$error_gen" -error "cat_consts.sh" "Corruption" "$STR" "attribute" "${id_prefix}CONSTS_FILE"
    exit 1
fi

##################################
# Merge constants with config file
nr_lines=0
if [[ -n "$consts_file" ]]; then
    echo "# --- Provided $dir_id constants  ---" >> "$glidein_config"
    # Removing comment lines from the constant file and merge constants
    grep -v "^#" "$consts_file" | sed -E -e 's/^[[:blank:]]*//' -e 's/[[:blank:]]+/ /' -e 's/[[:blank:]]*$//' | gconfig_add_multi
    echo "# --- End $dir_id constants       ---" >> "$glidein_config"
fi

"$error_gen" -ok "cat_consts.sh" "NrAttributes" "$(grep -cv "^#" "$consts_file")"
exit 0
