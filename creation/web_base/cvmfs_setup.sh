#!/bin/bash

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

# first parameter passed to this script will always be the glidein configuration file (glidein_config)
glidein_config=$1

# import add_config_line function
add_config_line_source=$(grep -m1 '^ADD_CONFIG_LINE_SOURCE ' "$glidein_config" | awk '{print $2}')
# shellcheck source=./add_config_line.source
. "$add_config_line_source"

# fetch the error reporting helper script
error_gen=$(gconfig_get ERROR_GEN_PATH "$glidein_config")

# get the use_cvmfs attribute switch value from the config file
use_cvmfs=$(gconfig_get GLIDEIN_USE_CVMFS "$glidein_config")
# TODO: int or string?? if string, make the attribute value case insensitive
#use_cvmfs=${use_cvmfs,,}

if [[ $use_cvmfs -ne 1 ]]; then
    "$error_gen" -ok "$(basename $0)" "msg" "Not using cvmfsexec; skipping setup."
    return 0
fi

# if GLIDEIN_USE_CVMFS is set to 1 - check if CVMFS is locally available in the node
# validate CVMFS by examining the directories within CVMFS... checking just one directory should be sufficient?
# get the glidein work directory location from glidein_config file
work_dir=$(gconfig_get GLIDEIN_WORK_DIR "$glidein_config")
# $PWD=/tmp/glide_xxx and every path is referenced with respect to $PWD

# source the helper script
# TODO: Is this file somewhere in the source tree? use: # shellcheck source=./cvmfs_helper_funcs_ff.sh
. $work_dir/cvmfs_helper_funcs_ff.sh

variables_reset

detect_local_cvmfs

# check if CVMFS is already locally mounted...
if [[ $GWMS_IS_CVMFS_LOCAL_MNT -eq 0 ]]; then
    # if it is so...
    "$error_gen" -ok "$(basename $0)" "msg" "CVMFS is locally mounted on the node; skipping setup."
    return 0
fi

# if CVMFS is not found locally...
# get the CVMFS source information from <attr> in the glidein configuration
cvmfs_source=$(gconfig_get CVMFS_SRC "$glidein_config")

# get the directory where cvmfsexec is unpacked
glidein_cvmfsexec_dir=$(gconfig_get CVMFSEXEC_DIR "$glidein_config")

# get the CVMFS requirement setting passed as one of the factory attributes
glidein_cvmfs=$(gconfig_get GLIDEIN_CVMFS_REQUIRE "$glidein_config")

perform_system_check

# gather the worker node information; perform_system_check sets a few variables that can be helpful here
os_like=$GWMS_OS_DISTRO
os_ver=$GWMS_OS_VERSION_MAJOR
arch=$GWMS_OS_KRNL_ARCH
# construct the name of the cvmfsexec distribution file based on the worker node specs
dist_file=cvmfsexec-${cvmfs_source}-${os_like}${os_ver}-${arch}
# the appropriate distribution file does not have to manually untarred as the glidein setup takes care of this automatically

if [[ $use_cvmfs -eq 1 ]]; then
    if [[ ! -d "$glidein_cvmfsexec_dir" && ! -f ${glidein_cvmfsexec_dir}/${dist_file} ]]; then
        # neither the cvmfsexec directory nor the cvmfsexec distribution is found -- this happens when a directory named 'cvmfsexec' does not exist on the glidein because an appropriate distribution tarball is not found in the list of all the available tarballs and was not unpacked [trying to unpack osg-rhel8 on osg-rhel7 worker node]
        # if use_cvmfs is set to 1, then warn that cvmfs will not be mounted and flag an error
        logerror "Error occurred during cvmfs setup: None of the available cvmfsexec distributions is compatible with the worker node specifications."
        "$error_gen" -error "$(basename $0)" "WN_Resource" "Error occurred during cvmfs setup... no matching cvmfsexec distribution available."
        return 1
    elif [[ -d "$glidein_cvmfsexec_dir" && ! -f ${glidein_cvmfsexec_dir}/${dist_file} ]]; then
        # something might have gone wrong during the unpacking of the tarball into the glidein_cvmfsexec_dir
        logerror "Something went wrong during the unpacking of the cvmfsexec distribution tarball!"
        "$error_gen" -error "$(basename $0)" "WN_Resource" "Error: Something went wrong during the unpacking of the cvmfsexec distribution tarball"
        return 1
    fi
fi

if [[ "$glidein_cvmfs" == "NEVER" ]]; then
    # do nothing; test the node and print the results but do not even try to mount CVMFS
    # just continue with glidein startup
    loginfo "Not trying to mount CVMFS (GLIDEIN_CVMFS set to NEVER)"
    "$error_gen" -ok "$(basename "$0")" "msg" "Not trying to mount CVMFS."
fi

# by this point, it would have been established that CVMFS is not locally available, so mount CVMFS via mountrepo
prepare_for_cvmfs_mount
loginfo "CVMFS is NOT locally mounted on the worker node! Mounting now..."
# check the operating system distribution
if [[ "$GWMS_OS_DISTRO" = "rhel" ]]; then
    # evaluate the worker node's system configuration to decide whether CVMFS can be mounted or not
    loginfo "Evaluating the worker node..."
    # assess the worker node based on its existing system configurations and perform next steps accordingly
    if evaluate_worker_node_config ; then
        # if evaluation was true, then proceed to mount CVMFS
        loginfo "Mounting CVMFS repositories..."
        if mount_cvmfs_repos 1 $GLIDEIN_CVMFS_CONFIG_REPO $GLIDEIN_CVMFS_REPOS ; then
            :
        else
            if [[ "$glidein_cvmfs" == "REQUIRED" ]]; then
                # if mount CVMFS is not successful, report an error and exit with failure exit code
                "$error_gen" -error "$(basename "$0")" "WN_Resource" "CVMFS is required but unable to mount CVMFS on the worker node."
                return 1
            elif [[ "$glidein_cvmfs" == "PREFERRED" || "$glidein_cvmfs" == "OPTIONAL" ]]; then
                # if mount CVMFS is not successful, report a warning/error in the logs and continue with glidein startup
                # script status must be OK, otherwise the glidein will fail
                "$error_gen" -ok "$(basename "$0")" "WN_Resource" "Unable to mount required CVMFS on the worker node. Continuing without CVMFS."
            else
                "$error_gen" -error "$(basename "$0")" "WN_Resource" "Invalid factory attribute value specified for CVMFS requirement."
                return 1
            fi
        fi
    else
        # if evaluation was false, then exit from this activity of mounting CVMFS
        if [[ "$glidein_cvmfs" == "REQUIRED" ]]; then
            # report an error and exit with failure exit code
            logerror "Worker node did not pass evaluation checks; aborting CVMFS setup (GLIDEIN_CVMFS_REQUIRE set to $glidein_cvmfs)"
            "$error_gen" -error "$(basename "$0")" "WN_Resource" "Worker node configuration did not pass evaluation checks; CVMFS could not be mounted."
            return 1
        elif [[ "$glidein_cvmfs" == "PREFERRED" || "$glidein_cvmfs" == "OPTIONAL" ]]; then
            # report a warning in the logs and continue with glidein startup
            logwarn "Worker node did not pass evaluation checks; continuing without CVMFS (GLIDEIN_CVMFS_REQUIRE set to $glidein_cvmfs)"
            "$error_gen" -ok "$(basename "$0")" "WN_Resource" "Worker node configuration did not pass evaluation checks; CVMFS will not be mounted."
            return 0
        fi
    fi
else
    # if operating system distribution is non-RHEL (any non-rhel OS)
    # display operating system information and a user-friendly message
    #print_os_info
    logwarn "This is a non-RHEL OS and is not covered in the implementation yet!"
    # ----- Further Implementation: TBD (To Be Done) ----- #
    return
fi

if [[ $GWMS_IS_CVMFS -ne 0 ]]; then
    # Error occurred during mount of CVMFS repositories"
    logerror "Error occurred during mount of CVMFS repositories."
    "$error_gen" -error "$(basename $0)" "WN_Resource" "Mount unsuccessful... CVMFS is still unavailable on the node."
    return 1
fi

# TODO: Verify the findmnt ... will always find the correct CVMFS mount
mount_point=$(findmnt -t fuse -S /dev/fuse | tail -n 1 | cut -d ' ' -f 1 )
if [[ -n "$mount_point" && "$mount_point" != TARGET* ]]; then
    mount_point=$(dirname "$mount_point")
    if [[ -n "$mount_point" && "$mount_point" != /cvmfs ]]; then
        CVMFS_MOUNT_DIR="$mount_point"
        export CVMFS_MOUNT_DIR
        gconfig_add CVMFS_MOUNT_DIR "$mount_point"
    fi
fi

# CVMFS is now available on the worker node"
loginfo "Proceeding to execute user job..."
"$error_gen" -ok "$(basename $0)" "WN_Resource" "CVMFS mounted successfully and is now available."
