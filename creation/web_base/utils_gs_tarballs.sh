#!/bin/bash

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

#*******************************************************************#
# utils_gs_tarballs.sh                                              #
# This script contains tarballs utility functions for the           #
# glidein_startup.sh script                                         #
#*******************************************************************#

###########################################
# Untar support function
# Arguments:
#   1: id
#   2: filename
# Globals (r/w):
#   gus_id
#   gus_fname
#   gus_prefix
#   gus_config_cfg
#   gus_config_file
#   gus_dir
# Returns:
#   0 in case of success, otherwise glidein_exit with 1
get_untar_subdir() {
    gus_id="$1"
    gus_fname="$2"

    gus_prefix="$(get_prefix "${gus_id}")"
    gus_config_cfg="${gus_prefix}UNTAR_CFG_FILE"

    gus_config_file="$(grep "^${gus_config_cfg} " glidein_config | cut -d ' ' -f 2-)"
    if [ -z "${gus_config_file}" ]; then
        log_warn "Error, cannot find '${gus_config_cfg}' in glidein_config."
        glidein_exit 1
    fi

    gus_dir="$(grep -i "^${gus_fname} " "${gus_config_file}" | cut -s -f 2-)"
    if [ -z "${gus_dir}" ]; then
        log_warn "Error, untar dir for '${gus_fname}' cannot be empty."
        glidein_exit 1
    fi

    echo "${gus_dir}"
    return 0
}

########################################
# Removes the native condor tarballs directory to allow factory ops to use native condor tarballs
# All files in the native condor tarballs have a directory like condor-9.0.11-1-x86_64_CentOS7-stripped
# However the (not used anymore) gwms create_condor_tarball removes that dir
# Used:
#   gs_id_work_dir
fixup_condor_dir() {
    # Check if the condor dir has only one subdir, the one like "condor-9.0.11-1-x86_64_CentOS7-stripped"
    # See https://stackoverflow.com/questions/32429333/how-to-test-if-a-linux-directory-contain-only-one-subdirectory-and-no-other-file
    if [ $(find "${gs_id_work_dir}/condor" -maxdepth 1 -type d -printf 1 | wc -m) -eq 2 ]; then
        echo "Fixing directory structure of condor tarball"
        mv "${gs_id_work_dir}"/condor/condor*/* "${gs_id_work_dir}"/condor > /dev/null
    else
        echo "Condor tarball does not need to be fixed"
    fi
}
