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
# Version:
#       1.0
#

echo "Unmounting CVMFS as part of glidein cleanup..."

glidein_config=$1

# Set and import error_gen and add_config_line
error_gen=$(grep '^ERROR_GEN_PATH ' $glidein_config | awk '{print $2}')
add_config_line_source=$(grep '^ADD_CONFIG_LINE_SOURCE ' $glidein_config | awk '{print $2}')
# shellcheck source=./add_config_line.source
. $add_config_line_source

# get the cvmfsexec attribute switch value from the config file
use_cvmfsexec=$(grep '^GLIDEIN_USE_CVMFSEXEC ' $glidein_config | awk '{print $2}')
# TODO: int or string? if string, make the attribute value case insensitive
#use_cvmfsexec=${use_cvmfsexec,,}

if [[ $use_cvmfsexec -ne 1 ]]; then
    "$error_gen" -ok "$(basename $0)" "umnt_msg1" "Not using cvmfsexec; skipping cleanup."
    exit 0
fi

# get the glidein work directory location from glidein_config file
work_dir=$(grep '^GLIDEIN_WORK_DIR ' $glidein_config | awk '{print $2}')
# $PWD=/tmp/glide_xxx and every path is referenced with respect to $PWD

# source the helper script
# TODO: Is this file somewhere in the source tree? use: # shellcheck source=./cvmfs_helper_funcs.sh
. $work_dir/cvmfs_helper_funcs.sh

# get the cvmfsexec directory location
glidein_cvmfsexec_dir=$(grep '^CVMFSEXEC_DIR ' $glidein_config | awk '{print $2}')

########################################################################################################
# Start: main program
########################################################################################################

loginfo "..."
loginfo  "Start log for unmounting CVMFS"

# check if CVMFS is locally mounted on the worker node
detect_local_cvmfs

if [[ $GWMS_IS_CVMFS_MNT -eq 0 ]]; then
    # CVMFS is mounted locally in the filesystem; DO NOT UNMOUNT!
    loginfo "Skipping unmounting of CVMFS as it already is locally provisioned in the node!"
    "$error_gen" -ok "$(basename $0)" "umnt_msg2" "CVMFS is locally mounted on the node; skipping cleanup."
    exit 0
fi

loginfo "Unmounting CVMFS mounted by the glidein..."
$glidein_cvmfsexec_dir/.cvmfsexec/umountrepo -a

if [[ -n "$CVMFS_MOUNT_DIR" ]]; then
    CVMFS_MOUNT_DIR=
    export CVMFS_MOUNT_DIR
    add_config_line CVMFS_MOUNT_DIR ""
fi

# check again to ensure all CVMFS repositories were unmounted by umountrepo
# searching for "/dev/fuse" since "/cvmfs" returns false positives (/etc/auto.fs /cvmfs line)
cat /proc/$$/mounts | grep /dev/fuse &> /dev/null && logerror "One or more CVMFS repositories might not be completely unmounted" || loginfo "CVMFS repositories unmounted"

"$error_gen" -ok "$(basename $0)" "umnt_msg3" "Glidein-based CVMFS unmount was successful."
# returning 0 to indicate the unmount process was successful
true

########################################################################################################
# End: main program
########################################################################################################
