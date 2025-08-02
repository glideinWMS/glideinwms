#!/bin/bash

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

# Description:
#   This script will setup the knobs that
#   are related to network tuning, like incoming connections/firewalls
#

glidein_config="$1"
tmp_fname="${glidein_config}.$$.tmp"

warn() {
    echo "$(date)" "$@" 1>&2
}

# import add_config_line and add_condor_vars_line functions
add_config_line_source=$(grep -m1 '^ADD_CONFIG_LINE_SOURCE ' "$glidein_config" | cut -d ' ' -f 2-)
# shellcheck source=./add_config_line.source
. "$add_config_line_source"

error_gen=$(gconfig_get ERROR_GEN_PATH "$glidein_config")

condor_vars_file=$(gconfig_get CONDOR_VARS_FILE "$glidein_config")

##########################################################
# check if it should use CCB
##########################################################
out_ccb_str="False"
if gconfig_get_bool USE_CCB "$glidein_config"; then
    # ok, we need to define CCB variable

    ccb_host=$(gconfig_get GLIDEIN_CCB "$glidein_config")
    if [ -z "$ccb_host" ]; then
        ccb_host=$(gconfig_get GLIDEIN_Collector "$glidein_config")
        if [ -z "$ccb_host" ]; then
            #echo "No GLIDEIN_Collector found!" 1>&2
            STR="No GLIDEIN_CCB or GLIDEIN_Collector found!"
            "$error_gen" -error "setup_network.sh" "Corruption" "$STR" "attribute" "GLIDEIN_Collector"
            exit 1
        fi
    fi

    gconfig_add CCB_ADDRESS "$ccb_host"
    # and export it to Condor
    add_condor_vars_line CCB_ADDRESS C "-" "+" Y N "-"
    out_ccb_str="True"
fi


##########################################################
# check if it should use the shared_port_daemon
##########################################################
out_sharedp_str="False"
if gconfig_get_bool USE_SHARED_PORT "$glidein_config"; then
    # ok, we need to enable the shared port
    daemon_list=$(gconfig_get DAEMON_LIST "$glidein_config")
    if [ -z "$daemon_list" ]; then
        # this is the default
        daemon_list="MASTER,STARTD"
    fi
    new_daemon_list="${daemon_list},SHARED_PORT"
    gconfig_add DAEMON_LIST "${new_daemon_list}"

    gconfig_add USE_SHARED_PORT True
    out_sharedp_str="True"
fi


"$error_gen" -ok "setup_network.sh" "UseCCB" "${out_ccb_str}" "UseSharedPort" "${out_sharedp_str}"

exit 0
