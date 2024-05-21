#!/bin/bash

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

# Project:
#	GlideinWMS
#
#
# Description:
#	This script contains helper functions that support the mount/unmount of
#	CVMFS on worker nodes.
#
#
# Used by:
#	cvmfs_setup.sh, cvmfs_unmount.sh
#
# Author:
#	Namratha Urs
#


# to implement custom logging
# https://stackoverflow.com/questions/42403558/how-do-i-manage-log-verbosity-inside-a-shell-script
# WORKAROUND: redirect stdout and stderr to some file
#LOGFILE="cvmfs_all.log"
#exec &> $LOGFILE

variables_reset() {
    # DESCRIPTION: This function lists and initializes the common variables
    # to empty strings. These variables also become available to scripts
    # that import functions defined in this script.
    #
    # INPUT(S): None
    # RETURN(S): Variables initialized to empty strings

    # indicates whether the perform_system_check function has been run
    GWMS_SYSTEM_CHECK=

    # following set of variables used to store operating system and kernel info
    GWMS_OS_DISTRO=
    GWMS_OS_VERSION=
    GWMS_OS_KRNL_ARCH=
    GWMS_OS_KRNL_NUM=
    GWMS_OS_KRNL_VER=
    GWMS_OS_KRNL_MAJOR_REV=
    GWMS_OS_KRNL_MINOR_REV=
    GWMS_OS_KRNL_PATCH_NUM=

    # indicates whether CVMFS is locally mounted on the worker node (CE)
    GWMS_IS_CVMFS_LOCAL_MNT=
    # to indicate the status of on-demand mounting of CVMFS by the glidein after evaluating the worker node (CE)
    GWMS_IS_CVMFS=

    # indicates if unpriv userns is available (or supported); not if it is enabled
    GWMS_IS_UNPRIV_USERNS_SUPPORTED=
    # indicates if unpriv userns is enabled (and available)
    GWMS_IS_UNPRIV_USERNS_ENABLED=

    # following variables store FUSE-related information
    GWMS_IS_FUSE_INSTALLED=
    GWMS_IS_FUSERMOUNT=
    GWMS_IS_USR_IN_FUSE_GRP=
}


loginfo() {
    # DESCRIPTION: This function prints informational messages to STDOUT
    # along with hostname and date/time.
    #
    # INPUT(S): String containing the message
    # RETURN(S): Prints message to STDOUT

    echo -e "$(date +%m-%d-%Y\ %T\ %Z) \t INFO: $1" >&2
}


logwarn(){
    # DESCRIPTION: This function prints warning messages to STDOUT along
    # with hostname and date/time.
    #
    # INPUT(S): String containing the message
    # RETURN(S): Prints message to STDOUT

    echo -e "$(date +%m-%d-%Y\ %T\ %Z) \t WARNING: $1" >&2
}


logerror() {
    # DESCRIPTION: This function prints error messages to STDOUT along with
    # hostname and date/time.
    #
    # INPUT(S): String containing the message
    # RETURN(S): Prints message to STDOUT

    echo -e "$(date +%m-%d-%Y\ %T\ %Z) \t ERROR: $1" >&2
}


print_exit_status () {
    # DESCRIPTION: This function prints an appropriate message to the
    # console to indicate what the exit status means.
    #
    # INPUT(S): Number (exit status of a previously run command)
    # RETURN(S): Prints "yes" or "no" to indicate the result of the command

    [[ $1 -eq 0 ]] && echo yes || echo no
}

detect_local_cvmfs() {
    CVMFS_ROOT="/cvmfs"
    repo_name=oasis.opensciencegrid.org
    # Second check...
    GWMS_IS_CVMFS_LOCAL_MNT=0
    if [[ -f $CVMFS_ROOT/$repo_name/.cvmfsdirtab || "$(ls -A $CVMFS_ROOT/$repo_name)" ]] &>/dev/null
    then
        loginfo "Validating CVMFS with ${repo_name}..."
    else
        logwarn "Validating CVMFS with ${repo_name}: directory empty or does not have .cvmfsdirtab"
        GWMS_IS_CVMFS_LOCAL_MNT=1
    fi

    loginfo "CVMFS locally installed: $(print_exit_status $GWMS_IS_CVMFS_LOCAL_MNT)"
}

perform_system_check() {
    # DESCRIPTION: This functions performs required system checks (such as
    # operating system and kernel info, unprivileged user namespaces, FUSE
    # status) and stores the results in the common variables for later use.
    #
    # INPUT(S): None
    # RETURN(S):
    # 	-> common variables containing the exit status of the
    # 	corresponding commands
    # 	-> results from running the print_exit_status function
    # 	for logging purposes (variables starting with res_)
    # 	-> assigns "yes" to GWMS_SYSTEM_CHECK to indicate this function
    # 	has been run.

    if [[ -f "/etc/redhat-release" ]]; then
        GWMS_OS_DISTRO=rhel
    else
        GWMS_OS_DISTRO=non-rhel
    fi

    GWMS_OS_VERSION=$(lsb_release -r | awk -F'\t' '{print $2}')
    GWMS_OS_KRNL_ARCH=$(arch)
    GWMS_OS_KRNL_NUM=$(uname -r | awk -F'-' '{split($2,a,"."); print $1,a[1]}' | cut -f 1 -d " " )
    GWMS_OS_KRNL_VER=$(uname -r | awk -F'-' '{split($2,a,"."); print $1,a[1]}' | cut -f 1 -d " " | awk -F'.' '{print $1}')
    GWMS_OS_KRNL_MAJOR_REV=$(uname -r | awk -F'-' '{split($2,a,"."); print $1,a[1]}' | cut -f 1 -d " " | awk -F'.' '{print $2}')
    GWMS_OS_KRNL_MINOR_REV=$(uname -r | awk -F'-' '{split($2,a,"."); print $1,a[1]}' | cut -f 1 -d " " | awk -F'.' '{print $3}')
    GWMS_OS_KRNL_PATCH_NUM=$(uname -r | awk -F'-' '{split($2,a,"."); print $1,a[1]}' | cut -f 2 -d " ")

    #df -h | grep /cvmfs &>/dev/null
    #GWMS_IS_CVMFS_LOCAL_MNT=$?
    # call function to detect local CVMFS only if the GWMS_IS_CVMFS_LOCAL_MNT variable is not set; if the variable is not empty, do nothing
    [[ -z "${GWMS_IS_CVMFS_LOCAL_MNT}" ]] && detect_local_cvmfs || :

    sysctl user.max_user_namespaces &>/dev/null
    GWMS_IS_UNPRIV_USERNS_SUPPORTED=$?

    unshare -U true &>/dev/null
    GWMS_IS_UNPRIV_USERNS_ENABLED=$?

    yum list installed *fuse* &>/dev/null
    GWMS_IS_FUSE_INSTALLED=$?

    fusermount -V &>/dev/null
    GWMS_IS_FUSERMOUNT=$?

    getent group fuse | grep $USER &>/dev/null
    GWMS_IS_USR_IN_FUSE_GRP=$?

    # set the variable indicating this function has been run
    GWMS_SYSTEM_CHECK=yes
}


print_os_info () {
    # DESCRIPTION: This functions prints operating system and kernel
    # information to STDOUT.
    #
    # INPUT(S): None
    # RETURN(S): Prints a message containing OS and kernel details

    loginfo "Found $GWMS_OS_DISTRO${GWMS_OS_VERSION}-${GWMS_OS_KRNL_ARCH} with kernel $GWMS_OS_KRNL_NUM-$GWMS_OS_KRNL_PATCH_NUM"
}


log_all_system_info () {
    # DESCRIPTION: This function prints all the necessary system information
    # stored in common and result variables (see perform_system_check
    # function) for easy debugging. This has been done as collecting
    # information about the worker node can be useful for troubleshooting
    # and gathering stats about what is out there.
    #
    # INPUT(S): None
    # RETURN(S): Prints user-friendly messages to STDOUT

    loginfo "..."
    loginfo "Worker node details: "
    loginfo "Hostname: $(hostname)"
    loginfo "Operating system distro: $GWMS_OS_DISTRO"
    loginfo "Operating System version: $GWMS_OS_VERSION"
    loginfo "Kernel Architecture: $GWMS_OS_KRNL_ARCH"
    loginfo "Kernel version: $GWMS_OS_KRNL_VER"
    loginfo "Kernel major revision: $GWMS_OS_KRNL_MAJOR_REV"
    loginfo "Kernel minor revision: $GWMS_OS_KRNL_MINOR_REV"
    loginfo "Kernel patch number: $GWMS_OS_KRNL_PATCH_NUM"

    loginfo "CVMFS locally installed: $(print_exit_status $GWMS_IS_CVMFS_LOCAL_MNT)"
    loginfo "Unprivileged user namespaces supported: $(print_exit_status $GWMS_IS_UNPRIV_USERNS_SUPPORTED)"
    loginfo "Unprivileged user namespaces enabled: $(print_exit_status $GWMS_IS_UNPRIV_USERNS_ENABLED)"
    loginfo "FUSE installed: $(print_exit_status $GWMS_IS_FUSE_INSTALLED)"
    loginfo "fusermount available: $(print_exit_status $GWMS_IS_FUSERMOUNT)"
    loginfo "Is the user in 'fuse' group: $(print_exit_status $GWMS_IS_USR_IN_FUSE_GRP)"
    loginfo "..."
}


mount_cvmfs_repos () {
    # DESCRIPTION: This function mounts all the required and additional
    # CVMFS repositories that would be needed for user jobs.
    #
    # INPUT(S):
    #    1. cvmfsexec mode (integer)
    #    2. CVMFS configuration repository (string)
    #    3. Additional CVMFS repositories (colon-delimited string)
    # RETURN(S): Mounts the defined repositories on the worker node filesystem
    local cvmfsexec_mode=$1
    local config_repository=$2
    local additional_repos=$3

    if [[ $cvmfsexec_mode -eq 1 ]]; then
        "$glidein_cvmfsexec_dir/$dist_file" "$1" -- echo "setting up mount utilities..." &> /dev/null
    fi
    # at this point in the execution flow, it would have been determined that cvmfs is not locally available
    # which implies no repositories are mounted but only config repo will be mounted
    if [[ $(df -h|grep /cvmfs|wc -l) -eq 1 ]]; then
        loginfo "CVMFS config repo already mounted!"
    else
        # mounting the configuration repo (pre-requisite)
        loginfo "Mounting CVMFS config repo now..."
        [[ $cvmfsexec_mode -eq 1 ]] && "$glidein_cvmfsexec_dir"/.cvmfsexec/mountrepo "$config_repository"
        [[ $cvmfsexec_mode -eq 3 ]] && $CVMFSMOUNT "$config_repository"
    fi

    # using an array to unpack the names of additional CVMFS repositories
    # from the colon-delimited string
    repos=($(echo $additional_repos | tr ":" "\n"))

    loginfo "Mounting additional CVMFS repositories..."
    # mount every repository that was previously unpacked
    [[ "$cvmfsexec_mode" -ne 1 && "$cvmfsexec_mode" -ne 3 ]] && { logerror "Invalid cvmfsexec mode: mode $cvmfsexec_mode; aborting!"; return 1; }
    for repo in "${repos[@]}"
    do
        case $cvmfsexec_mode in
            1)
                "$glidein_cvmfsexec_dir"/.cvmfsexec/mountrepo "$repo"
                ;;
            3)
                $CVMFSMOUNT "$repo"
                ;;
        esac
    done

    # see if all the repositories got mounted
    num_repos_mntd=$(df -h | grep /cvmfs | wc -l)
    total_num_repos=$(( ${#repos[@]} + 1 ))
    GWMS_IS_CVMFS=0
    if [[ "$num_repos_mntd" -eq "$total_num_repos" ]]; then
        loginfo "All CVMFS repositories mounted successfully on the worker node"
        echo 0
    else
        logwarn "One or more CVMFS repositories might not be mounted on the worker node"
        GWMS_IS_CVMFS=1
        echo 1
    fi

    # export this info to the glidein environment after CVMFS is provisioned on demand
    gconfig_add GWMS_IS_CVMFS $(print_exit_status $GWMS_IS_CVMFS)

    get_mount_point
}


get_mount_point() {
    # TODO: Verify the findmnt ... will always find the correct CVMFS mount
    mount_point=$(findmnt -t fuse -S /dev/fuse | tail -n 1 | cut -d ' ' -f 1 )
    if [[ -n "$mount_point" && "$mount_point" != TARGET* ]]; then
        mount_point=$(dirname "$mount_point")
        if [[ -n "$mount_point" && "$mount_point" != /cvmfs ]]; then
            CVMFS_MOUNT_DIR="$mount_point"
            export CVMFS_MOUNT_DIR=$mount_point
            gconfig_add CVMFS_MOUNT_DIR "$mount_point"
        fi
    fi
}


has_unpriv_userns() {
    # DESCRIPTION: This function checks the status of unprivileged user
    # namespaces being supported and enabled on the worker node. Depending
    #
    # INPUT(S): None
    # RETURN(S):
    #	-> true (0) if unpriv userns can be used (supported and enabled),
    #	false otherwise
    #	-> status of unpriv userns (unavailable, disabled, enabled,
    #	error) to stdout

    # make sure that perform_system_check has run
    [[ -z "${GWMS_SYSTEM_CHECK}" ]] && perform_system_check

    # determine whether unprivileged user namespaces are supported and/or enabled...
    if [[ "${GWMS_IS_UNPRIV_USERNS_ENABLED}" -eq 0 ]]; then
        # unprivileged user namespaces is enabled
        if [[ "${GWMS_IS_UNPRIV_USERNS_SUPPORTED}" -eq 0 ]]; then
            # unprivileged user namespaces is supported
            loginfo "Unprivileged user namespaces supported and enabled"
            echo enabled
	    return 0
	fi
        # unprivileged user namespaces is not supported
        logerror "Inconsistent system configuration: unprivileged userns is enabled but not supported"
        echo error
    else
        # unprivileged user namespaces is disabled
        if [[ "${GWMS_IS_UNPRIV_USERNS_SUPPORTED}" -eq 0 ]]; then
            # unprivileged user namespaces is supported
            logwarn "Unprivileged user namespaces disabled: can be enabled by the root user via sysctl"
            echo disabled
        else
            # unprivileged user namespaces is not supported
            logwarn "Unprivileged user namespaces disabled and unsupported: can be supported/enabled only after a system upgrade"
            echo unavailable
        fi
    fi
    return 1
}


has_fuse() {
    # DESCRIPTION: This function checks FUSE-related configurations on the
    # worker node. This is a pre-requisite before evaluating whether CVMFS
    # is mounted on the filesystem.
    #
    # FUSE Documentation references:
    # https://www.kernel.org/doc/html/latest/filesystems/fuse.html
    # https://en.wikipedia.org/wiki/Filesystem_in_Userspace
    #
    # INPUT(S): None
    # RETURN(S): string denoting fuse availability (yes, no, error)

    # make sure that perform_system_check has run
    [[ -n "${GWMS_SYSTEM_CHECK}" ]] && perform_system_check

    # check what specific configuration of unprivileged user namespaces exists in the system (worker node)
    local unpriv_userns_status
    unpriv_userns_status=$(has_unpriv_userns)

    # exit from the script if unprivileged namespaces are not supported but enabled in the kernel
    if [[ "${unpriv_userns_status}" == error ]]; then
        "$error_gen" -error "$(basename $0)" "WN_Resource" "Unprivileged user namespaces are not supported but enabled in the kernel! Check system configuration."
        exit 1
    fi

    # determine if mountrepo/umountrepo could be used by checking availability of fuse, fusermount and user being in fuse group...
    if [[ "${GWMS_IS_FUSE_INSTALLED}" -eq 0 ]]; then
        # fuse is not installed
	if [[ "${GWMS_IS_FUSERMOUNT}" -eq 0 ]]; then
	    # fusermount is somehow available and user is/is not in fuse group (scenarios 3,4)
	    logwarn "Inconsistent system configuration: fusermount is only available with fuse and/or when user belongs to the fuse group"
            echo error
        else
            # fusermount is not available and user is/is not in fuse group (scenarios case 1,2)
            loginfo "FUSE requirements not satisfied: fusermount is not available"
            echo no
        fi
	return 1
    fi

    # fuse is installed
    local ret_state
    if [[ $unpriv_userns_status == unavailable ]]; then
        # unprivileged user namespaces unsupported, i.e. kernels 2.x (scenarios 5b,6b)
        if [[ "${GWMS_IS_USR_IN_FUSE_GRP}" -eq 0 ]]; then
            # user is in fuse group -> fusermount is available (scenario 6b)
            if [[ "${GWMS_IS_FUSERMOUNT}" -ne 0 ]]; then
                logwarn "Inconsistent system configuration: fusermount is available with fuse installed and when user is in fuse group"
                ret_state=error
            else
                loginfo "FUSE requirements met by the worker node"
                ret_state=yes
            fi
        else
            # user is not in fuse group -> fusermount is unavailable (scenario 5b)
            if [[ "${GWMS_IS_FUSERMOUNT}" -eq 0 ]]; then
                logwarn "Inconsistent system configuration: fusermount is available only when user is in fuse group and fuse is installed"
                ret_state=error
            else
                loginfo "FUSE requirements not satisfied: user is not in fuse group"
                ret_state=no
            fi
        fi
    else
        # unprivileged user namespaces is either enabled or disabled
        if [[ "${GWMS_IS_FUSERMOUNT}" -eq 0 ]]; then
            # fusermount is available (scenarios 7,8)
            loginfo "FUSE requirements met by the worker node"
            ret_state=yes
        else
            # fusermount is not available (scenarios 5a,6a)
            logwarn "Inconsistent system configuration: fusermount is not available when fuse is installed "
            ret_state=error
        fi
    fi
    echo ret_state
    [[ "$ret_state" == "yes"]]
    return
}


evaluate_worker_node_config () {
    # DESCRIPTION: This function evaluates the worker using FUSE and
    # unpriv. userns configurations to determine whether CVMFS can be
    # mounted using mountrepo utility.
    #
    # INPUT(S): None
    # RETURN(S): string message whether CVMFS can be mounted

    # collect info about FUSE configuration on the worker node
    fuse_config_status=$(has_fuse)

    # check fuse related configurations in the system (worker node)
    if [[ $fuse_config_status == yes ]]; then
        # success;
        loginfo "CVMFS can be mounted and unmounted on the worker node using mountrepo/umountrepo utility"
        return 0
    fi
    if [[ $fuse_config_status == no ]]; then
        # failure;
        logerror "CVMFS cannot be mounted on the worker node using mountrepo utility"
    elif [[ $fuse_config_status == error ]]; then
        # inconsistent system configurations detected in the worker node
        logerror "Detected inconsistent configurations on the worker node. mountrepo utility cannot be used!!"
    fi
    return 1
}


prepare_for_cvmfs_mount () {
    # reset all variables used in this script's namespace before executing the rest of the script
    variables_reset

    # perform checks on the worker node that will be used to assess whether CVMFS can be mounted or not
    perform_system_check

    # print/display all information pertaining to system checks performed previously (facilitates easy troubleshooting)
    log_all_system_info

    # get the CVMFS source information from <attr> in the glidein configuration
    cvmfs_source=$(gconfig_get CVMFS_SRC "$glidein_config")

    # get the directory where cvmfsexec is unpacked
    glidein_cvmfsexec_dir=$(gconfig_get CVMFSEXEC_DIR "$glidein_config")

    # get the CVMFS requirement setting passed as one of the factory attributes
    glidein_cvmfs=$(gconfig_get GLIDEIN_CVMFS "$glidein_config")

    # # gather the worker node information; perform_system_check sets a few variables that can be helpful here
    os_like=$GWMS_OS_DISTRO
    os_ver=$(echo "$GWMS_OS_VERSION" | awk -F'.' '{print $1}')
    arch=$GWMS_OS_KRNL_ARCH
    # construct the name of the cvmfsexec distribution file based on the worker node specs
    dist_file=cvmfsexec-${cvmfs_source}-${os_like}${os_ver}-${arch}
    # the appropriate distribution file does not have to manually untarred as the glidein setup takes care of this automatically

    loginfo "CVMFS Source = $cvmfs_source"
    # initializing CVMFS repositories to a variable for easy modification in the future
    case $cvmfs_source in
        osg)
            GLIDEIN_CVMFS_CONFIG_REPO=config-osg.opensciencegrid.org
            GLIDEIN_CVMFS_REPOS=singularity.opensciencegrid.org:cms.cern.ch:oasis.opensciencegrid.org
            ;;
        egi)
            GLIDEIN_CVMFS_CONFIG_REPO=config-egi.egi.eu
            GLIDEIN_CVMFS_REPOS=config-osg.opensciencegrid.org:singularity.opensciencegrid.org:cms.cern.ch:oasis.opensciencegrid.org
            ;;
        default)
            GLIDEIN_CVMFS_CONFIG_REPO=cvmfs-config.cern.ch
            GLIDEIN_CVMFS_REPOS=config-osg.opensciencegrid.org:singularity.opensciencegrid.org:cms.cern.ch:oasis.opensciencegrid.org
            ;;
        *)
            "$error_gen" -error "$(basename "$0")" "WN_Resource" "Invalid factory attribute value specified for CVMFS source."
            exit 1
    esac
    # (optional) set an environment variable that suggests additional repos to be mounted after config repos are mounted
    loginfo "CVMFS Config Repo = $GLIDEIN_CVMFS_CONFIG_REPO"
    loginfo "CVMFS Repos = $GLIDEIN_CVMFS_REPOS"
}


perform_cvmfs_mount () {
    # by this point, it would have been established that CVMFS is not locally available
    # so, install CVMFS via mode 1 of cvmfsexec (mountrepo) or mode 3 of cvmfsexec (cvmfsexec)
    loginfo "CVMFS is NOT locally mounted on the worker node! Mounting now..."
    # check the operating system distribution
    #if [[ $GWMS_OS_DISTRO = RHEL ]]; then
    # evaluate the worker node's system configurations to decide whether CVMFS can be mounted or not
    loginfo "Evaluating the worker node..."
    # display operating system information
    print_os_info

    local cvmfsexec_mode=$1
    # check whether the strict requirement of CVMFS mounting is defined (in the factory configuration)
    if [[ $glidein_cvmfs = never ]]; then
	    # do nothing; test the node and print the results but do not even try to mount CVMFS
            # just continue with glidein startup
            "$error_gen" -ok "$(basename $0)" "msg" "Not trying to install CVMFS."
	    return 0
    fi

    # if strict requirement of CVMFS mounting is not set to 'never' (i.e. 'required', 'preferred', or 'optional')
    # assess the worker node based on its existing system configurations and perform next steps accordingly
    if evaluate_worker_node_config ; then
	    # if evaluation was true, then proceed to mount CVMFS
        loginfo "Mounting CVMFS repositories..."
        if ! mount_cvmfs_repos $cvmfsexec_mode $GLIDEIN_CVMFS_CONFIG_REPO $GLIDEIN_CVMFS_REPOS ; then
            if [[ $glidein_cvmfs = preferred || $glidein_cvmfs = optional ]]; then
                # if mount CVMFS is not successful, report a warning/error in the logs and continue with glidein startup
                # script status must be OK, otherwise the glidein will fail
                "$error_gen" -ok "$(basename $0)" "WN_Resource" "Unable to mount required CVMFS on the worker node. Continuing without CVMFS."
                exit 0
            fi
            if [[ $glidein_cvmfs = required ]]; then
                # if mount CVMFS is not successful, report an error and exit with failure exit code
                "$error_gen" -error "$(basename $0)" "WN_Resource" "CVMFS is required but unable to mount CVMFS on the worker node."
            else
                "$error_gen" -error "$(basename $0)" "WN_Resource" "Invalid factory attribute value specified for CVMFS requirement."
            fi
            exit 1
        fi
    else
        # if evaluation of the worker node was false, then exit from this activity of mounting CVMFS
        "$error_gen" -error "$(basename $0)" "WN_Resource" "Worker node configuration did not pass the evaluation checks. CVMFS will not be mounted."
        exit 1
    fi
    #else
    # if operating system distribution is non-RHEL (any non-rhel OS)
    # display operating system information and a user-friendly message
    #print_os_info
    #logwarn "This is a non-RHEL OS and is not covered in the implementation yet!"
    # ----- Further Implementation: TBD (To Be Done) ----- #
    #fi

    #fi
}
