#!/bin/bash

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

# first parameter passed to this script will always be the glidein configuration file (glidein_config)
glidein_config=$1

# fetch the error reporting helper script
error_gen=$(grep '^ERROR_GEN_PATH ' $glidein_config | awk '{print $2}')

# import add_config_line function
add_config_line_source=$(grep '^ADD_CONFIG_LINE_SOURCE ' $glidein_config | awk '{print $2}')
# shellcheck source=./add_config_line.source
. $add_config_line_source

# get the cvmfsexec attribute switch value from the config file
use_cvmfsexec=$(grep '^GLIDEIN_USE_CVMFSEXEC ' $glidein_config | awk '{print $2}')
# TODO: int or string?? if string, make the attribute value case insensitive
#use_cvmfsexec=${use_cvmfsexec,,}

if [[ $use_cvmfsexec -ne 1 ]]; then
    "$error_gen" -ok "$(basename $0)" "msg" "Not using cvmfsexec; skipping setup."
    exit 0
fi

# if GLIDEIN_USE_CVMFSEXEC is set to 1 - check if CVMFS is locally available in the node
# validate CVMFS by examining the directories within CVMFS... checking just one directory should be sufficient?
# get the glidein work directory location from glidein_config file
work_dir=$(grep '^GLIDEIN_WORK_DIR ' $glidein_config | awk '{print $2}')
# $PWD=/tmp/glide_xxx and every path is referenced with respect to $PWD

# source the helper script
# TODO: Is this file somewhere in the source tree? use: # shellcheck source=./cvmfs_helper_funcs.sh
. $work_dir/cvmfs_helper_funcs.sh

variables_reset

detect_local_cvmfs

# check if CVMFS is already locally mounted...
if [[ $GWMS_IS_CVMFS_MNT -eq 0 ]]; then
    # if it is so...
    "$error_gen" -ok "$(basename $0)" "msg" "CVMFS is locally mounted on the node; skipping setup."
    exit 0
fi

# if CVMFS is not found locally...
# get the CVMFS source information from <attr> in the glidein configuration
cvmfs_source=$(grep '^CVMFS_SRC ' $glidein_config | awk '{print $2}')

# get the directory where cvmfsexec is unpacked
glidein_cvmfsexec_dir=$(grep '^CVMFSEXEC_DIR ' $glidein_config | awk '{print $2}')

# get the CVMFS requirement setting passed as one of the factory attributes
glidein_cvmfs=$(grep '^GLIDEIN_CVMFS ' $glidein_config | awk '{print $2}')

perform_system_check

# gather the worker node information; perform_system_check sets a few variables that can be helpful here
os_like=$GWMS_OS_DISTRO
os_ver=$(echo $GWMS_OS_VERSION | awk -F'.' '{print $1}')
arch=$GWMS_OS_KRNL_ARCH
# construct the name of the cvmfsexec distribution file based on the worker node specs
dist_file=cvmfsexec-${cvmfs_source}-${os_like}${os_ver}-${arch}
# the appropriate distribution file does not have to manually untarred as the glidein setup takes care of this automatically

perform_cvmfs_mount

if [[ $GWMS_IS_CVMFS -ne 0 ]]; then
    # Error occurred during mount of CVMFS repositories"
    logerror "Error occured during mount of CVMFS repositories."
    "$error_gen" -error "$(basename $0)" "WN_Resource" "Mount unsuccessful... CVMFS is still unavailable on the node."
    exit 1
fi

# TODO: Verify the findmnt ... will always find the correct CVMFS mount
mount_point=$(findmnt -t fuse -S /dev/fuse | tail -n 1 | cut -d ' ' -f 1 )
if [[ -n "$mount_point" && "$mount_point" != TARGET* ]]; then
    mount_point=$(basename "$mount_point")
    if [[ -n "$mount_point" && "$mount_point" != /cvmfs ]]; then
        CVMFS_MOUNT_DIR="$mount_point"
        export CVMFS_MOUNT_DIR
        add_config_line CVMFS_MOUNT_DIR "$mount_point"
    fi
fi

# CVMFS is now available on the worker node"
loginfo "Proceeding to execute user job..."
"$error_gen" -ok "$(basename $0)" "WN_Resource" "CVMFS mounted successfully and is now available."
