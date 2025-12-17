
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

glidein_config=$1

# import add_config_line to use gconfig_ utilities
add_config_line_source=$(grep -m1 '^ADD_CONFIG_LINE_SOURCE ' "$glidein_config" | awk '{print $2}')
# shellcheck source=./add_config_line.source
. "$add_config_line_source"
# import error_gen
error_gen=$(gconfig_get ERROR_GEN_PATH "$glidein_config")

# get the cvmfsexec attribute switch value from the config file
use_cvmfs=$(gconfig_get GLIDEIN_USE_CVMFS "$glidein_config")
# TODO: int or string? if string, make the attribute value case insensitive
#use_cvmfs=${use_cvmfs,,}

if [[ $use_cvmfs -ne 1 ]]; then
    "$error_gen" -ok "$(basename $0)" "umnt_msg1" "Not using cvmfsexec; skipping cleanup."
    exit 0
fi

# get the glidein work directory location from glidein_config file
work_dir=$(gconfig_get GLIDEIN_WORK_DIR "$glidein_config")
# $PWD=/tmp/glide_xxx and every path is referenced with respect to $PWD
# source the helper script
# shellcheck source=./cvmfs_helper_funcs_ff.sh
. "$work_dir"/cvmfs_helper_funcs_ff.sh

# check if CVMFS was mounted on demand
ondemand_cvmfs_mntd=$(gconfig_get GWMS_IS_CVMFS "$glidein_config")
if [[ -z $ondemand_cvmfs_mntd ]]; then
    # first check if CVMFS is locally mounted on the worker node
    detect_local_cvmfs
    if [[ $GWMS_IS_CVMFS_LOCAL_MNT -eq 0 ]]; then
        # CVMFS is mounted locally in the filesystem; DO NOT UNMOUNT!
        loginfo "Skipping unmounting of CVMFS as it already is locally provisioned in the node!"
        exit 0
    fi
    # CVMFS might be mounted locally in the filesystem; DO NOT UNMOUNT!
    #loginfo "Skipping unmounting of CVMFS as it may be locally provisioned in the node!"
    #"$error_gen" -ok "$(basename $0)" "umnt_msg2" "CVMFS might be locally mounted on the node; skipping CVMFS cleanup."
    #exit 0
fi

# if not, CVMFS was mounted on-demand, so unmount based on the cvmfsexec mode
# get info about the mode that was used to mount CVMFS on demand
gwms_cvmfsexec_mode=$(gconfig_get GWMS_CVMFSEXEC_MODE "$glidein_config")
# get the cvmfsexec directory location
glidein_cvmfsexec_dir=$(gconfig_get CVMFSEXEC_DIR "$glidein_config")
loginfo "Found CVMFS mounted on demand using mode $gwms_cvmfsexec_mode..."
loginfo "Starting to unmount CVMFS provisioned by the glidein..."
mnt_dir=$(gconfig_get CVMFS_MOUNT_DIR "$glidein_config")
[[ -n "$mnt_dir" ]] && loginfo "CVMFS_MOUNT_DIR set to $mnt_dir"
if [[ $gwms_cvmfsexec_mode -eq 1 ]]; then
    "$glidein_cvmfsexec_dir"/.cvmfsexec/umountrepo -a
    # mode 1 uses /dev/fuse as SOURCE
    search_pattern="/dev/fuse"
elif [[ $gwms_cvmfsexec_mode -eq 3  || $gwms_cvmfsexec_mode -eq 2 ]]; then
    [[ -z "$CVMFSMOUNT" ]] && false || true
    repos=($(echo $GLIDEIN_CVMFS_REPOS | tr ":" "\n"))
    loginfo "Unmounting CVMFS repositories..."
    # mount every repository that was previously unpacked
    for repo in "${repos[@]}"
    do
        $CVMFSUMOUNT "$repo"
    done
    loginfo "Unmounting CVMFS config repo now..."
    $CVMFSUMOUNT "${GLIDEIN_CVMFS_CONFIG_REPO}"
    # mode 3 uses cvmfs2 as SOURCE
    search_pattern="cvmfs2"
fi
# clear the mount_dir variable if it was set during the mounting of CVMFS regardless of the mode
if [[ -n "$mnt_dir" ]]; then
    CVMFS_MOUNT_DIR=
    export CVMFS_MOUNT_DIR
    gconfig_add CVMFS_MOUNT_DIR ""
fi

# check again to ensure all CVMFS repositories were unmounted by umountrepo
# searching for "/dev/fuse" or "cvmfs2" since "/cvmfs" might return false positives (/etc/auto.fs/cvmfs line)
cat /proc/$$/mounts | grep ${search_pattern} &> /dev/null && logerror "One or more CVMFS repositories might not be completely unmounted" || loginfo "CVMFS repositories unmounted"
"$error_gen" -ok "$(basename $0)" "umnt_msg1" "Glidein-based CVMFS unmount was successful."
# returning 0 to indicate the unmount process was successful
exit 0

############################################################################
# End: main program
############################################################################
