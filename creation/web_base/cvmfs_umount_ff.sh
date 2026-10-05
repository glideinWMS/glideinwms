
#!/bin/bash

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

#
# Description:
#   This script checks the status of CVMFS mounted on the filesystem in the worker node.
#	If CVMFS is mounted, the script unmounts all CVMFS repositories using the appropriate utility based on the cvmfsexec mode that used to mount.
#	If CVMFS is not found to be mounted, then an appropriate message will be displayed.
#
# Dependencies:
#	cvmfs_helper_funcs.sh
#

glidein_config=$1

# import add_config_line to use gconfig_ utilities
add_config_line_source=$(grep -m1 '^ADD_CONFIG_LINE_SOURCE ' "$glidein_config" | awk '{print $2}')
# shellcheck source=./add_config_line.source
. "$add_config_line_source"
# import error_gen
error_gen=$(gconfig_get ERROR_GEN_PATH "$glidein_config")

# get the glidein work directory location from glidein_config file
work_dir=$(gconfig_get GLIDEIN_WORK_DIR "$glidein_config")
# $PWD=/tmp/glide_xxx and every path is referenced with respect to $PWD
# source the helper script
# shellcheck source=./cvmfs_helper_funcs_ff.sh
. "$work_dir"/cvmfs_helper_funcs_ff.sh

# check if CVMFS was mounted locally or on demand
# if mounted locally on the worker node, do nothing and exit from here
# if mounted on demand using cvmfsexec utilities, unmount before glidein terminates

# check if CVMFS was mounted on demand
cvmfs_mntd_ondemand=$(gconfig_get GWMS_IS_CVMFS "$glidein_config")
if [[ -z "$cvmfs_mntd_ondemand" ]]; then
    # first check if CVMFS is locally mounted on the worker node
    cvmfs_local=$(gconfig_get GWMS_IS_CVMFS_LOCAL_MNT "$glidein_config")
    if [[ -z $cvmfs_local ]]; then
        loginfo "No native CVMFS or on-demand CVMFS found on the node; CVMFS cleanup not required"
        "$error_gen" -ok "$(basename $0)" "umnt_msg1" "Neither native nor on-demand CVMFS found on the node; ignoring CVMFS cleanup."
         exit 0;
    elif [[ $cvmfs_local -eq 0 ]]; then
        # CVMFS might be natively available in the filesystem; DO NOT UNMOUNT!
        loginfo "Native CVMFS available; skipping CVMFS cleanup."
        "$error_gen" -ok "$(basename $0)" "umnt_msg2" "CVMFS might be locally available on the node; skipping CVMFS cleanup."
        exit 0
    fi
fi

# if not, CVMFS was mounted on-demand, so unmount based on the cvmfsexec mode
# get some helpful variables from glidein_config to determine the execution flow for cleanup of CVMFS
cvmfs_reexec=$(gconfig_get GWMS_CVMFS_REEXEC "$glidein_config")
cvmfsexec_mode=$(gconfig_get GWMS_CVMFSEXEC_MODE "$glidein_config")

loginfo "Starting to unmount CVMFS provisioned by the glidein..."
# get the cvmfsexec directory location
glidein_cvmfsexec_dir=$(gconfig_get CVMFSEXEC_DIR "$glidein_config")
if [[ -n "$cvmfs_reexec" && "$cvmfs_reexec" == "yes" ]]; then
    # CVMFS was mounted on demand using mode 3/2 (via glidein reinvocation)
    # do some checks to confirm if the determination of the mode is correct
    [[ $cvmfsexec_mode -eq 3 || $cvmfsexec_mode -eq 2 ]] && true || exit 1
    loginfo "Found CVMFS mounted using mode $cvmfsexec_mode..." || ...
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
    # mode 3 uses 'cvmfs2' as SOURCE
    search_pattern="cvmfs2"
elif [[ -n "$cvmfs_reexec" && "$cvmfs_reexec" == "no" ]]; then
    # CVMFS was mounted on demand using mode 1; verify if that is the case
    [[ $cvmfsexec_mode -eq 1 ]] && loginfo "Found CVMFS mounted using mode $cvmfsexec_mode..." || exit 1
    "$glidein_cvmfsexec_dir"/.cvmfsexec/umountrepo -a
    # mode 1 uses /dev/fuse as SOURCE
    search_pattern="/dev/fuse"
else
    logerror "ERROR: Invalid 'cvmfs_reexec' value found ($cvmfs_reexec)."
    "$error_gen" -error "$(basename $0)" "umnt_msg3" "Invalid 'cvmfs_reexec' value ($cvmfs_reexec) encountered."
    exit 1
fi

mnt_dir=$(gconfig_get CVMFS_MOUNT_DIR "$glidein_config")
# clear the mount_dir variable if it was set during the mounting of CVMFS regardless of the mode
if [[ -n "$mnt_dir" ]]; then
    loginfo "CVMFS_MOUNT_DIR set to $mnt_dir"
    CVMFS_MOUNT_DIR=
    export CVMFS_MOUNT_DIR
    gconfig_add CVMFS_MOUNT_DIR ""
fi

# check again to ensure all CVMFS repositories were unmounted by umountrepo
# searching for "/dev/fuse" or "cvmfs2" since "/cvmfs" might return false positives (/etc/auto.fs/cvmfs line)
findmnt -t fuse -S ${search_pattern} &> /dev/null && logerror "One or more CVMFS repositories might not be completely unmounted" || loginfo "CVMFS repositories unmounted"
"$error_gen" -ok "$(basename $0)" "umnt_msg4" "Glidein-based CVMFS unmount was successful."
# returning 0 to indicate the unmount process was successful
exit 0

############################################################################
# End: main program
############################################################################
