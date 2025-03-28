#!/bin/bash

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

# Description:
#   This script checks that the node is not in a blacklist

check_blacklist() {
    # Checking host name
    if ! myname=$(uname -n); then
        #echo "Cannot get my name!" 1>&2
        STR="Cannot get my name!"
        "$error_gen" -error "check_blacklist.sh" "WN_Resource" "$STR" "command" "uname"
        exit 1
    fi
    if grep -q -e "^'${myname//\./\\\.}'" "$blacklist_file"; then
        #echo "My name '$myname' is in blacklist! Exiting." 1>&2
        STR="My name '$myname' is in blacklist! Exiting."
        "$error_gen" -error "check_blacklist.sh" "WN_Resource" "$STR" "hostname" "$myname"
        exit 1
    fi
    # Checking IP
    if ! myip=$(host "$myname" | awk '{print $4}'); then
        if ! myip=$(hostname -I); then
            # Ignore errors, here, since host and hostname may both fail
            return 0
        fi
    fi
    for i in $myip; do
        if grep -q -e "^'${i//\./\\\.}'" "$blacklist_file"; then
            #echo "My ip '$i' is in blacklist! Exiting." 1>&2
            STR="My ip '$i' is in blacklist! Exiting."
            "$error_gen" -error "check_blacklist.sh" "WN_Resource" "$STR" "IP" "$i"
            exit 1
        fi
    done
    # All OK
    return 0
}

_main() {
    # Assume all functions exit on error
    config_file="$1"
    dir_id="$2"

    # import add_config_line function
    add_config_line_source=$(grep -m1 '^ADD_CONFIG_LINE_SOURCE ' "$config_file" | cut -d ' ' -f 2-)
    # shellcheck source=./add_config_line.source
    . "$add_config_line_source"

    error_gen=$(gconfig_get ERROR_GEN_PATH "$config_file")

    # import get_prefix function
    get_id_selectors_source=$(gconfig_get GET_ID_SELECTORS_SOURCE "$config_file")
    # shellcheck source=get_id_selectors.source
    . "$get_id_selectors_source"

    id_prefix=$(get_prefix "$dir_id")

    blacklist_file=$(gconfig_get "${id_prefix}"BLACKLIST_FILE "$config_file")
    if [[ -n "$blacklist_file" ]]; then
      check_blacklist
    fi

    "$error_gen" -ok "check_blacklist.sh"
    exit 0
}

# Alt: [[ "$(caller)" != "0 "* ]] || _main "$@"
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    _main "$@"
fi
