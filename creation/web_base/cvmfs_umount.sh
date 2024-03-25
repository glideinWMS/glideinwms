#!/bin/bash

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

# Project:
#       GlideinWMS
#
#
# Description:
#       This script checks the status of CVMFS mounted on the filesystem in the worker node.
#	If CVMFS is mounted, the script unmounts all CVMFS repositories using the umountrepo utility and
#	prints appropriate message. If CVMFS is not found to be mounted, then an appropriate message
#	will be displayed.
#
# Dependencies:
#	cvmfs_helper_funcs.sh
#
# Author:
#       Namratha Urs
#

echo "Unmounting on-demand CVMFS as part of glidein cleanup..."
glidein_config=$1

# import add_config_line to use gconfig_ utilities
add_config_line_source=$(grep -m1 '^ADD_CONFIG_LINE_SOURCE ' "$glidein_config" | awk '{print $2}')
# shellcheck source=./add_config_line.source
. "$add_config_line_source"
# import error_gen
error_gen=$(gconfig_get ERROR_GEN_PATH "$glidein_config")
# get the cvmfsexec attribute switch value from the config file
use_cvmfs=$(gconfig_get GLIDEIN_USE_CVMFS "$glidein_config")
# get the glidein work directory location from glidein_config file
work_dir=$(gconfig_get GLIDEIN_WORK_DIR "$glidein_config")
# $PWD=/tmp/glide_xxx and every path is referenced with respect to $PWD

# source the helper script
# shellcheck source=./cvmfs_helper_funcs.sh
. "$work_dir"/cvmfs_helper_funcs.sh

loginfo "..."
is_cvmfs_mntd=$(gconfig_get GWMS_IS_CVMFS "$glidein_config")
loginfo "CVMFS mounted on demand: $is_cvmfs_mntd"
if [[ "${is_cvmfs_mntd}" == "yes" ]]; then
    gwms_cvmfsexec_mode=$(gconfig_get GWMS_CVMFSEXEC_MODE "$glidein_config")
    # get the cvmfsexec directory location
    glidein_cvmfsexec_dir=$(gconfig_get CVMFSEXEC_DIR "$glidein_config")
    loginfo "Unmounting CVMFS provisioned by the glidein..."
    if [[ "$gwms_cvmfsexec_mode" -eq 1 ]]; then
        "$glidein_cvmfsexec_dir"/.cvmfsexec/umountrepo -a

        if [[ -n "$CVMFS_MOUNT_DIR" ]]; then
            CVMFS_MOUNT_DIR=
            export CVMFS_MOUNT_DIR
            gconfig_add CVMFS_MOUNT_DIR ""
        fi
    elif [[ "$gwms_cvmfsexec_mode" -eq 3  || "$gwms_cvmfsexec_mode" -eq 2 ]]; then
        loginfo "CVMFS_MOUNT_DIR set to $CVMFS_MOUNT_DIR"
        loginfo "CVMFSUMOUNT set to $CVMFSUMOUNT"
    fi
    # check again to ensure all CVMFS repositories were unmounted by umountrepo
    # searching for "/dev/fuse" since "/cvmfs" might return false positives (/etc/auto.fs /cvmfs line)
    cat /proc/$$/mounts | grep /dev/fuse &> /dev/null && logerror "One or more CVMFS repositories might not be completely unmounted" || loginfo "CVMFS repositories unmounted"
    "$error_gen" -ok "$(basename $0)" "umnt_msg1" "Glidein-based CVMFS unmount was successful."
    # returning 0 to indicate the unmount process was successful
    return 0
else
    # CVMFS was not mounted on-demand, so check if CVMFS is locally mounted on the worker node
    detect_local_cvmfs
    if [[ $GWMS_IS_CVMFS_LOCAL_MNT -eq 0 ]]; then
        # CVMFS is mounted locally in the filesystem; DO NOT UNMOUNT!
        loginfo "Skipping unmounting of CVMFS as it already is locally provisioned in the node!"
        "$error_gen" -ok "$(basename $0)" "umnt_msg2" "CVMFS is locally mounted on the node; skipping cleanup."
    else
        # CVMFS is not found natively either
        loginfo "CVMFS not found natively; so nothing to do here... continuing."
        "$error_gen" -ok "$(basename $0)" "umnt_msg3" "No native CVMFS; nothing to cleanup before glidein shutdown."
    fi
    return 0
fi

############################################################################
# End: main program
############################################################################
