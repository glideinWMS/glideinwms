#!/bin/bash

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

################################## main #################################

# first parameter passed to this script will always be the glidein configuration file (glidein_config)
glidein_config=$1

# import add_config_line function
add_config_line_source=$(grep -m1 '^ADD_CONFIG_LINE_SOURCE ' "$glidein_config" | cut -d ' ' -f 2-)
# shellcheck source=./add_config_line.source
. "$add_config_line_source"

# get the glidein work directory location from glidein_config file
[[ -e "$glidein_config" ]] && error_gen=$(gconfig_get ERROR_GEN_PATH "$glidein_config")

cvmfs_reexec=$(printenv GWMS_CVMFS_REEXEC | sed "s/ //g")
# if glidein reinvocation has not occurred
[[ -z "$cvmfs_reexec" || -n "$cvmfs_reexec" && "$cvmfs_reexec" == "no" ]] && exit 0

[[ -e "$glidein_config" ]] && work_dir=$(gconfig_get GLIDEIN_WORK_DIR "$glidein_config")
# shellcheck source=./cvmfs_helper_funcs_ff.sh
. "$work_dir"/cvmfs_helper_funcs_ff.sh

if [[ -n "$cvmfs_reexec" && "$cvmfs_reexec" == "yes" ]]; then
    # for glidein reinvocation
    cvmfs_config_repo=$(printenv GLIDEIN_CVMFS_CONFIG_REPO | sed "s/ //g")
    cvmfs_add_repos=$(printenv GLIDEIN_CVMFS_REPOS | sed "s/ //g")
    cvmfsexec_mode=$(printenv GWMS_CVMFSEXEC_MODE | sed "s/ //g")

    # get the CVMFS requirement that was evaluated/determined previously
    cvmfs_status=$(gconfig_get GWMS_CVMFS_STATUS "$glidein_config")
    if ! mount_cvmfs_repos $cvmfsexec_mode $cvmfs_config_repo $cvmfs_add_repos; then
        if [[ "$cvmfs_status" == "REQUIRED" ]]; then
            logerror "Error during mounting of CVMFS; aborting glidein setup! (CVMFS ${cvmfs_status})"
            "$error_gen" -error "$(basename $0)" "mnt_msg1" "Error during mounting of CVMFS; aborting glidein startup (CVMFS ${cvmfs_status})."
            exit 1
        fi
        # if CVMFS is not required, display a user-friendly message
        logwarn "Error during mounting of CVMFS; continuing without CVMFS (CVMFS ${cvmfs_status})"
        "$error_gen" -ok "$(basename $0)" "mnt_msg2" "Error during mounting of CVMFS; continuing without CVMFS (CVMFS ${cvmfs_status})."
        exit 0
    fi
fi

# if everything went OK, exit with success flag
exit 0
