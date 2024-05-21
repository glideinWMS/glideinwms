#!/usr/bin/env bash

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

is_cvmfs_locally_mounted() {
    # checking if CVMFS is natively available
    variables_reset
    detect_local_cvmfs
    if [[ $GWMS_IS_CVMFS_LOCAL_MNT -eq 0 ]]; then
        # if it is so...
        return 0
    fi
    return 1
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

[[ -e "$glidein_config" ]] && work_dir=$(gconfig_get GLIDEIN_WORK_DIR "$1")
# shellcheck source=./cvmfs_helper_funcs.sh
. "$work_dir"/cvmfs_helper_funcs.sh

# get the use_cvmfs attribute value; passed as one of the frontend attributes
use_cvmfs=$(gconfig_get GLIDEIN_USE_CVMFS "$1")
if [[ -z $use_cvmfs ]]; then
    loginfo "CVMFS not requested (GLIDEIN_USE_CVMFS: $use_cvmfs); skipping CVMFS setup."
    "$error_gen" -ok "$(basename $0)" "mnt_msg1" "CVMFS not requested; skipping setup."
    return 0
elif ! [[ $use_cvmfs =~ ^[0-1]$ ]]; then
    # TODO: add this check at the xml level maybe?
    logerror "Invalid attribute value: GLIDEIN_USE_CVMFS = ${use_cvmfs}"
    "$error_gen" -error "$(basename $0)" "mnt_msg2" "Invalid attribute value: GLIDEIN_USE_CVMFS = ${use_cvmfs}"
    exit 1
fi

# get the CVMFS requirement setting; passed as one of the factory attributes
glidein_cvmfs_require=$(gconfig_get GLIDEIN_CVMFS_REQUIRE "$glidein_config")
glidein_cvmfs_require=${glidein_cvmfs_require,,}
# check whether glidein_cvmfs_require value is valid
# TODO: add this check at the xml level perhaps?
if ! [[ "${glidein_cvmfs_require}" =~ ^(required|preferred|never)$ ]]; then
    logerror "Invalid attribute value: GLIDEIN_CVMFS_REQUIRE = ${glidein_cvmfs_require}"
    "$error_gen" -error "$(basename $0)" "mnt_msg3" "Invalid attribute value: GLIDEIN_CVMFS_REQUIRE = ${glidein_cvmfs_require}"
    exit 1
fi

if [[ $use_cvmfs -ne 1 ]]; then
    if ! [[ "${glidein_cvmfs_require}" =~ ^(required|preferred)$ ]]; then
        loginfo "CVMFS not used; skipping related setup."
        "$error_gen" -ok "$(basename $0)" "mnt_msg4" "CVMFS not used. Skipping related setup."
        return 0
    fi
else
    # use_cvmfs is set to true, then do the following
    if [[ "${glidein_cvmfs_require}" == "never" ]]; then
        loginfo "CVMFS to be used (GLIDEIN_USE_CVMFS: $use_cvmfs) but GLIDEIN_CVMFS_REQUIRE set to $glidein_cvmfs_require; skipping related setup."
        "$error_gen" -ok "$(basename $0)" "mnt_msg5" "CVMFS to be used but GLIDEIN_CVMFS_REQUIRE set to ${glidein_cvmfs_require}"
        return 0
    fi
fi

# following block runs attempting to add CVMFS when either:
# 1. use_cvmfs is false and glidein_cvmfs_require is required or preferred (OR)
# 2. use_cvmfs is true
if is_cvmfs_locally_mounted; then
    loginfo "CVMFS found locally; skipping CVMFS setup via cvmfsexec."
    loginfo "Continuing to execute the rest of the glidein setup..."
    "$error_gen" -ok "$(basename $0)" "mnt_msg6" "CVMFS is natively available on the node; skipping setup using cvmfsexec utilities."
    return 0
fi
# if native CVMFS not there, do the following
loginfo "Starting on-demand CVMFS setup..."
# make sure that perform_system_check has run
[[ -z "${GWMS_SYSTEM_CHECK}" ]] && perform_system_check
cvmfsexec_mode=$(setup_cvmfsexec_use)
if ! [[ $cvmfsexec_mode =~ ^[1-3]$ ]]; then
    if [[ $use_cvmfs -eq 1 || "${glidein_cvmfs_require}" == "required" ]]; then
        # when (1) use_cvmfs is 1, or (2) use_cvmfs is 0 and glidein_cvmfs_require is set to required
        logerror "GLIDEIN_USE_CVMFS set to $use_cvmfs but GLIDEIN_CVMFS_REQUIRE is $glidein_cvmfs_require; aborting glidein setup."
        "$error_gen" -error "$(basename $0)" "mnt_msg7" "cvmfsexec cannot be used (GLIDEIN_USE_CVMFS: $use_cvmfs, GLIDEIN_CVMFS_REQUIRE: $glidein_cvmfs_require)"
        exit 1
    fi
    # when use_cvmfs is 0 and glidein_cvmfs_require is set to preferred, just warn the user
    logwarn "GLIDEIN_USE_CVMFS set to $use_cvmfs, GLIDEIN_CVMFS_REQUIRE: $glidein_cvmfs_require"
    loginfo "Proceeding to execute the remainder of the glidein setup (without CVMFS)..."
    "$error_gen" -ok "$(basename $0)" "mnt_msg8" "cvmfsexec cannot be used but still continuing (GLIDEIN_USE_CVMFS: $use_cvmfs, GLIDEIN_CVMFS_REQUIRE: $glidein_cvmfs_require)"
    return 0
fi

loginfo "GLIDEIN_USE_CVMFS: $use_cvmfs, GLIDEIN_CVMFS_REQUIRE: $glidein_cvmfs_require"
loginfo "cvmfsexec mode $cvmfsexec_mode is being used..."
echo ""
if [[ $cvmfsexec_mode -eq 3 || $cvmfsexec_mode -eq 2 ]]; then
    perform_cvmfs_mount $cvmfsexec_mode $glidein_cvmfs_require
    # before exiting out of this block, do two things...
    # one, set a variable indicating this script has been executed once
    gwms_cvmfs_reexec="yes"
    gconfig_add GWMS_CVMFS_REEXEC "$gwms_cvmfs_reexec"

    # two, export required variables with some necessary information for use inside cvmfsexec before reinvoking the glidein...
    original_workspace=$(gconfig_get GLIDEIN_WORKSPACE_ORIG "$glidein_config")
    export GLIDEIN_WORKSPACE=$original_workspace
    export GWMS_CVMFS_REEXEC=$gwms_cvmfs_reexec
    export GWMS_CVMFSEXEC_MODE=$cvmfsexec_mode
    export GLIDEIN_WORK_DIR="$work_dir"
    export GLIDEIN_CVMFS_CONFIG_REPO="$GLIDEIN_CVMFS_CONFIG_REPO"
    export GLIDEIN_CVMFS_REPOS="$GLIDEIN_CVMFS_REPOS"

    exec "$glidein_cvmfsexec_dir"/"$dist_file" -- "$GWMS_STARTUP_SCRIPT"
    echo "!!WARNING!! Outside of reinvocation of glidein_startup"   
    # the above line of code should not run; but is here as a safety check for debugging incorrect behavior of exec from previous line
fi
# the following is run if cvmfsexec cannot be used in mode 3/2
perform_cvmfs_mount $cvmfsexec_mode
if [[ $? -eq 0 ]]; then
    if [[ $GWMS_IS_CVMFS -ne 0 ]]; then
        # Error occurred during mount of CVMFS repositories"
        logerror "Error occured during mount of CVMFS repositories."
        "$error_gen" -error "$(basename $0)" "mnt_msg9" "Mount unsuccessful... CVMFS is still unavailable on the node."
        exit 1
    fi
    # CVMFS is available on the worker node now"
    gwms_cvmfs_reexec="no"
    gconfig_add GWMS_CVMFS_REEXEC "$gwms_cvmfs_reexec"
    # exporting the variables as an environment variable for use in glidein reinvocation
    export GWMS_CVMFS_REEXEC=$gwms_cvmfs_reexec
    export GWMS_CVMFSEXEC_MODE=$cvmfsexec_mode
    loginfo "Proceeding to execute the remainder of glidein setup..."
    "$error_gen" -ok "$(basename $0)" "mnt_msg10" "CVMFS mounted successfully and is now available."
    return 0
elif [[ $? -eq 1 ]]; then
    # if exit status is 1
    if [[ $cvmfs_required == "required" ]]; then
        # if mount CVMFS is not successful, report an error and exit with failure exit code
        loginfo "CVMFS is required but unable to mount CVMFS on worker node."
        "$error_gen" -error "$(basename $0)" "WN_Resource" "CVMFS is required but unable to mount CVMFS on the worker node."
        exit 1
    fi
    # if cvmfs_required is set to preferred and mount CVMFS is not successful, report a warning/error in the logs and continue with glidein startup
    # script status must be OK, otherwise the glidein will fail
    "$error_gen" -ok "$(basename $0)" "WN_Resource" "Unable to mount required CVMFS on the worker node. Continuing without CVMFS."
    return 0
else
    # if exit status is 2
    if [[ $cvmfs_required == "required" ]]; then
        logerror "Non-RHEL OS found but not supported; aborting glidein setup!"
        "$error_gen" -error "$(basename $0)" "WN_Resource" "Non-RHEL OS found but not supported; aborting glidein startup"
        exit 1
    fi
    # if CVMFS is not required, display operating system information and a user-friendly message
    "$error_gen" -ok "$(basename $0)" "WN_Resource" "Non-RHEL OS found but not supported; continuing without CVMFS setup"
    return 0   
fi
