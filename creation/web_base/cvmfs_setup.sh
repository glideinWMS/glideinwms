#!/usr/bin/env bash

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

printinfo() {
	# DESCRIPTION: This function prints informational messages to STDOUT
	# along with date/time.
	#
	# INPUT(S): String containing the message
	# RETURN(S): Prints message to STDOUT

	echo -e "$(date +%m-%d-%Y\ %T\ %Z) \t INFO: $1" >&2
}

determine_cvmfsexec_mode_usage() {
    if [[ $GWMS_IS_UNPRIV_USERNS_SUPPORTED && $GWMS_IS_UNPRIV_USERNS_ENABLED && $GWMS_IS_FUSERMOUNT ]]; then
        if [[ $GWMS_OS_KRNL_VER -ge 4 && $GWMS_OS_KRNL_MAJOR_REV -ge 18 || $GWMS_OS_KRNL_VER -ge 3 && $GWMS_OS_KRNL_MAJOR_REV -ge 10 && $GWMS_OS_KRNL_MINOR_REV -ge 0 && $GWMS_OS_KRNL_PATCH_NUM -ge 1127 ]]; then
            # cvmfsexec mode 3 can be used
            echo 3     # true
        else
            # cvmfsexec mode 3 unavailable; use mode 1 of cvmfsexec instead
            echo 1     # false
        fi
    else
        # User namespaces and/or fuse mounts not available in unprivileged mode
        # Defaulting to mode 1 of cvmfsexec
        echo 1         # false
    fi
}

is_cvmfs_needed() {
    # get the cvmfsexec attribute switch value from the config file
    [[ -e "$1" ]] && use_cvmfsexec=$(gconfig_get GLIDEIN_USE_CVMFSEXEC "$1")
    # TODO: change this variable to 'GLIDEIN_CVMFS' [convention for external variables]
    # TODO: when changed, the GLIDEIN_CVMFS variable takes on possible values from {required, preferred, optional, never}
    # TODO: int or string?? if string, make the attribute value case insensitive
    #use_cvmfsexec=${use_cvmfsexec,,}

    # source the helper script if use_cvmfsexec variable is not empty
    if [[ -z $use_cvmfsexec ]]; then
        # printinfo used instead of loginfo (from cvmfs_helper_funcs.sh) because
        # helper functions are designed to be downloaded based on conditional download logic; GLIDEIN_USE_CVMFSEXEC should be set to 1
        printinfo "On-demand CVMFS provisioning not requested. Skipping related setup."
        "$error_gen" -ok "$(basename $0)" "msg" "On-demand CVMFS provisioning not requested; skipping related setup."
        false
        # exit 0
    elif [[ $use_cvmfsexec -ne 1 ]]; then
        # printinfo used instead of loginfo (from cvmfs_helper_funcs.sh) because
        # helper functions are designed to be downloaded based on conditional download logic; GLIDEIN_USE_CVMFSEXEC should be set to 1
        printinfo "Not using on-demand CVMFS provisioning; skipping related setup."
        "$error_gen" -ok "$(basename $0)" "msg" "On-demand CVMFS provisioning requested and not used. Skipping related setup."
        false
        # exit 0
    else
        # $use_cvmfsexec -eq 1
        [[ -e "$1" ]] && work_dir=$(gconfig_get GLIDEIN_WORK_DIR "$1")

        # shellcheck source=./cvmfs_helper_funcs.sh
        . "$work_dir"/cvmfs_helper_funcs.sh
        true
    fi
}

is_cvmfs_locally_mounted() {
    variables_reset

    detect_local_cvmfs

    # check if CVMFS is already locally mounted...
    if [[ $GWMS_IS_CVMFS_LOCAL_MNT -eq 0 ]]; then
        # if it is so...
        loginfo "CVMFS is found locally; skipping on-demand CVMFS setup."
        "$error_gen" -ok "$(basename $0)" "msg" "CVMFS is locally mounted on the node; skipping setup using cvmfsexec utilities."
        exit 0
    fi

    loginfo "CVMFS is not found locally on the worker node..."
    false
}

setup_cvmfsexec_use() {
    gwms_cvmfsexec_mode=$(determine_cvmfsexec_mode_usage)
    if [[ $gwms_cvmfsexec_mode -eq 3 ]]; then
        loginfo "cvmfsexec can be used in mode 3"
    elif [[ $gwms_cvmfsexec_mode -eq 1 ]]; then
        loginfo "cvmfsexec will be used in mode 1 only"
    else
        logerror "invalid value for GWMS_CVMFSEXEC_MODE"
        exit 1
    fi

    gconfig_add GWMS_CVMFSEXEC_MODE "$gwms_cvmfsexec_mode"
}

################################## main #################################

# first parameter passed to this script will always be the glidein configuration file (glidein_config)
glidein_config=$1

# import add_config_line function
add_config_line_source=$(grep -m1 '^ADD_CONFIG_LINE_SOURCE ' "$glidein_config" | cut -d ' ' -f 2-)
# shellcheck source=./add_config_line.source
. "$add_config_line_source"

# get the glidein work directory location from glidein_config file
[[ -e "$glidein_config" ]] && error_gen=$(gconfig_get ERROR_GEN_PATH "$glidein_config")

if is_cvmfs_needed "$glidein_config" ; then
    echo "On-demand CVMFS provisioning requested and is being setup..."

    is_cvmfs_locally_mounted

    prepare_for_cvmfs_mount

    setup_cvmfsexec_use

    printinfo "cvmfsexec mode $gwms_cvmfsexec_mode is being used..."
    if [[ $gwms_cvmfsexec_mode -eq 3 ]]; then
        # before exiting out of this block, do two things...
        # one, set a variable indicating this script has been executed once
        gwms_cvmfs_reexec="yes"
        gconfig_add GWMS_CVMFS_REEXEC "$gwms_cvmfs_reexec"

        # two, export required variables before reinvoking the glidein...
        original_workspace=$(grep -m1 '^GLIDEIN_WORKSPACE_ORIG ' "$glidein_config" | cut -d ' ' -f 2-)
        export GLIDEIN_WORKSPACE=$original_workspace
        # export some necessary information for use inside cvmfsexec
        export GWMS_CVMFS_REEXEC=$gwms_cvmfs_reexec
        export GWMS_CVMFSEXEC_MODE=$gwms_cvmfsexec_mode
        export GLIDEIN_WORK_DIR="$work_dir"
        export GLIDEIN_CVMFS_CONFIG_REPO="$GLIDEIN_CVMFS_CONFIG_REPO"
        export GLIDEIN_CVMFS_REPOS="$GLIDEIN_CVMFS_REPOS"
        exec "$glidein_cvmfsexec_dir"/"$dist_file" -- "$GWMS_STARTUP_SCRIPT"
        echo "!!WARNING!! Outside of reinvocation of glidein_startup"       # this should not run; here as a safety check for debugging incorrect behavior of exec from previous line

    elif [[ $gwms_cvmfsexec_mode -eq 1 ]]; then
        perform_cvmfs_mount $gwms_cvmfsexec_mode

        if [[ $GWMS_IS_CVMFS -ne 0 ]]; then
            # Error occurred during mount of CVMFS repositories"
            logerror "Error occured during mount of CVMFS repositories."
            "$error_gen" -error "$(basename $0)" "WN_Resource" "Mount unsuccessful... CVMFS is still unavailable on the node."
            exit 1
        fi

        gwms_cvmfs_reexec="no"
        gconfig_add GWMS_CVMFS_REEXEC "$gwms_cvmfs_reexec"
        # exporting the variables as an environment variable for use in glidein reinvocation
        export GWMS_CVMFS_REEXEC=$gwms_cvmfs_reexec
        export GWMS_CVMFSEXEC_MODE=$gwms_cvmfsexec_mode

        # CVMFS is now available on the worker node"
        loginfo "Proceeding to execute the rest of the glidein setup..."
        "$error_gen" -ok "$(basename $0)" "WN_Resource" "CVMFS mounted successfully and is now available."
    else
        logerror "Invalid value of gwms_cvmfsexec_mode!"
        exit 1
    fi
else
    # if CVMFS is not requested/not needed to be setup by the glidein
    printinfo "Proceeding to execute the rest of the glidein setup..."
fi
