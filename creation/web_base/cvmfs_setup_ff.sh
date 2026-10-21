#!/bin/bash

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

is_cvmfs_locally_mounted() {
    # checking if CVMFS is natively available
    variables_reset
    detect_local_cvmfs
    gconfig_add GWMS_IS_CVMFS_LOCAL_MNT $GWMS_IS_CVMFS_LOCAL_MNT
    if [[ $GWMS_IS_CVMFS_LOCAL_MNT -eq 0 ]]; then
        # if it is so...
        return 0
    fi
    return 1
}

combine_requirements() {
    frontend_req=$1
    factory_req=$2
    # combine the Frontend and Factory requirements for using CVMFS
    res=FAIL
    case $frontend_req in
        0)
            if [[ "$factory_req" = "NEVER" || "$factory_req" = "PREFERRED" ]]; then
                res_str="VO does not mandate the use of CVMFS"
                [[ "$factory_req" = "NEVER" ]] && res=NEVER || res=PREFERRED
                echo "$res,$res_str"
                return 0
            fi
            res_str="Factory requires glidein to use CVMFS. VO is against."
            res=REQUIRED
            ;;
        1)
            if [[ "$factory_req" = "NEVER" ]]; then
                res_str="VO mandates the use of CVMFS but site requires not to use it"
                echo "FAIL,$res_str"
                return 1
            fi
            res_str="VO mandates the use of CVMFS."
            res=REQUIRED
            ;;
    esac

    # Return RESULT value and explanation
    echo "$res,$res_str"
    return 0
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

echo "$(date) Starting cvmfs_setup_ff.sh. Importing cvmfs_helper_funcs_ff.sh."

[[ -e "$glidein_config" ]] && work_dir=$(gconfig_get GLIDEIN_WORK_DIR "$glidein_config")
# shellcheck source=./cvmfs_helper_funcs_ff.sh
. "$work_dir"/cvmfs_helper_funcs_ff.sh

# get the Frontend requirement for CVMFS
use_cvmfs=$(gconfig_get GLIDEIN_USE_CVMFS "$glidein_config")
if [[ -z $use_cvmfs ]]; then
    loginfo "GLIDEIN_USE_CVMFS not configured. Defaulting to false (0)."
    use_cvmfs=0
fi

# get the Factory requirement for CVMFS
require_cvmfs=$(gconfig_get GLIDEIN_CVMFS_REQUIRE "$glidein_config")
if [[ -z $require_cvmfs ]]; then
    loginfo "GLIDEIN_CVMFS_REQUIRE not configured. Defaulting to PREFERRED."
    require_cvmfs="PREFERRED"
fi
# uncomment the following if need to convert to lowercase
# require_cvmfs=${require_cvmfs,,}

loginfo "Factory's desire to use CVMFS: $require_cvmfs"
loginfo "VO's desire to use CVMFS:      $use_cvmfs"
gwms_cvmfs=$(combine_requirements $use_cvmfs $require_cvmfs)
gwms_cvmfs_ec=$?
gwms_cvmfs_status="${gwms_cvmfs%%,*}"
gwms_cvmfs_str="${gwms_cvmfs#*,}"
logdebug "Combining VO ($use_cvmfs) and Entry ($require_cvmfs) requirements: $gwms_cvmfs_ec, $gwms_cvmfs_status, $gwms_cvmfs_str"
gconfig_add GWMS_CVMFS_STATUS $gwms_cvmfs_status

case "${gwms_cvmfs_status}" in
    FAIL)
        "$error_gen" -error "$(basename $0)" "combined_requirement" "${gwms_cvmfs_str}"
        return 1
        ;;
    NEVER)
        # No attempt to mount CVMFS
        loginfo "Not mounting CVMFS; continuing without CVMFS."
        return 0
        ;;
    PREFERRED|REQUIRED)
        # OK to continue mounting CVMFS
        ;;
esac

# Using CVMFS. After this point $gwms_cvmfs_status is PREFERRED|REQUIRED, all other would have returned to the caller (i.e. glidein_startup.sh)

# first, check whether a native installation of CVMFS is available...
if is_cvmfs_locally_mounted; then
    loginfo "CVMFS found locally; using native CVMFS"
    "$error_gen" -ok "$(basename $0)" "mnt_msg1" "CVMFS natively available on the node; not using cvmfsexec utilities."
    return 0
fi

# if native installation not available, use cvmfsexec to mount CVMFS on demand
loginfo "Starting on-demand CVMFS setup..."
# make sure that perform_system_check has run
[[ -z "${GWMS_SYSTEM_CHECK}" ]] && perform_system_check
cvmfsexec_mode=$(setup_cvmfsexec_use)
if ! [[ $cvmfsexec_mode =~ ^[1-3]$ ]]; then
    loginfo "cvmfsexec cannot be used in any of the three modes"
    if [[ "$gwms_cvmfs_status" = "REQUIRED" ]]; then
        logerror "Cannot mount CVMFS as cvmfsexec utilities cannot be used; aborting glidein setup."
        "$error_gen" -error "$(basename $0)" "mnt_msg2" "CVMFS cannot be mounted because cvmfsexec utilities cannot be used, aborting glidein startup (CVMFS $gwms_cvmfs_status)."
        return 1
    else
        # when gwms_cvmfs_status is preferred => user jobs do not require CVMFS but the site prefers CVMFS (not required)
        logwarn "Cannot mount CVMFS as cvmfsexec utilities cannot be used; continuing without CVMFS."
        "$error_gen" -ok "$(basename $0)" "mnt_msg3" "CVMFS cannot be mounted because cvmfsexec utilities cannot be used, continuing glidein startup(CVMFS $gwms_cvmfs_status)."
        return 0
    fi
fi

loginfo "cvmfsexec mode $cvmfsexec_mode is being used..."
perform_cvmfs_mount $cvmfsexec_mode $gwms_cvmfs_status
ret_val=$?
if [[ $ret_val -eq 0 ]]; then
    if [[ $cvmfsexec_mode -eq 3 || $cvmfsexec_mode -eq 2 ]]; then
        # the following is run if cvmfsexec can be used in mode 3/2
        # before exiting out of this block, do two things...
        # one, set a variable indicating this script has been executed once
        gwms_cvmfs_reexec="yes"
        gconfig_add GWMS_CVMFS_REEXEC "$gwms_cvmfs_reexec"

        # two, export required variables with some necessary information for use inside cvmfsexec before reinvoking the glidein...
        original_workspace=$(gconfig_get GLIDEIN_WORKSPACE_ORIG "$glidein_config")
        export GLIDEIN_WORKSPACE=$original_workspace
        export GWMS_CVMFS_REEXEC=$gwms_cvmfs_reexec
        export GWMS_CVMFSEXEC_MODE=$cvmfsexec_mode
        export GWMS_GLIDEIN_WORK_DIR="$work_dir"
        export GLIDEIN_CVMFS_CONFIG_REPO="$GLIDEIN_CVMFS_CONFIG_REPO"
        export GLIDEIN_CVMFS_REPOS="$GLIDEIN_CVMFS_REPOS"
        export PATH=$PATH
        echo "Reinvoking glidein now..."
        exec "$glidein_cvmfsexec_dir"/"$dist_file" -- "$GWMS_STARTUP_SCRIPT"
        echo "!!WARNING!! Outside of reinvocation of glidein_startup"
        # the above line of code should not run; but is here as a safety check for debugging incorrect behavior of exec from previous line
    fi
    # the following is run if cvmfsexec can be used in mode 1 only
    # CVMFS is available on the worker node now
    gwms_cvmfs_reexec="no"
    gconfig_add GWMS_CVMFS_REEXEC "$gwms_cvmfs_reexec"
    # exporting the variables as an environment variable for use in glidein reinvocation
    export GWMS_CVMFS_REEXEC=$gwms_cvmfs_reexec
    export GWMS_CVMFSEXEC_MODE=$cvmfsexec_mode
    loginfo "CVMFS mounted successfully and is now available."
    "$error_gen" -ok "$(basename $0)" "mnt_msg4" "CVMFS successfully mounted and available."
    return 0
elif [[ $ret_val -eq 1 ]]; then
    # if return value is 1 (something went wrong during perform_cvmfs_mount)
    if [[ "${gwms_cvmfs_status}" == "REQUIRED" ]]; then
        # if mount CVMFS is not successful, report an error and return with failure exit code
        logerror "Unable to mount CVMFS on worker node; aborting glidein setup (CVMFS ${gwms_cvmfs_status})"
        "$error_gen" -error "$(basename $0)" "WN_Resource" "CVMFS required but unable to mount CVMFS on the worker node (CVMFS ${gwms_cvmfs_status})."
        return 1
    fi
    # if gwms_cvmfs_status is set to preferred and mount CVMFS is not successful, report a warning/error in the logs and continue with glidein startup
    logwarn "Unable to mount CVMFS on worker node; continuing without CVMFS (CVMFS ${gwms_cvmfs_status})"
    "$error_gen" -ok "$(basename $0)" "WN_Resource" "CVMFS preferred but could not be mounted. Continuing without CVMFS (CVMFS ${gwms_cvmfs_status})."
    return 0
else
    # if return value is 2
    if [[ "$gwms_cvmfs_status" == "REQUIRED" ]]; then
        logerror "Non-RHEL OS found but not supported; aborting glidein setup! (CVMFS ${gwms_cvmfs_status})"
        "$error_gen" -error "$(basename $0)" "mnt_msg13" "Non-RHEL OS found but not supported; aborting glidein startup (CVMFS ${gwms_cvmfs_status})."
        return 1
    fi
    # if CVMFS is not required, display operating system information and a user-friendly message
    logwarn "Found non-RHEL OS which is not supported; continuing without CVMFS (CVMFS ${gwms_cvmfs_status})"
    "$error_gen" -ok "$(basename $0)" "mnt_msg14" "Non-RHEL OS found but not supported; continuing without CVMFS (CVMFS ${gwms_cvmfs_status})."
    return 0
fi
