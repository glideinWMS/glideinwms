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
# Version:
#	1.0
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
	GWMS_OS_NAME=
	GWMS_OS_VERSION_FULL=
	GWMS_OS_VERSION_MAJOR=
	GWMS_OS_VERSION_MINOR=
	GWMS_OS_KRNL_ARCH=
	GWMS_OS_KRNL_NUM=
	GWMS_OS_KRNL_VER=
	GWMS_OS_KRNL_MAJOR_REV=
	GWMS_OS_KRNL_MINOR_REV=
	GWMS_OS_KRNL_PATCH_NUM=

	# indicates whether CVMFS is locally mounted on the node
	GWMS_IS_CVMFS_MNT=
	# to indicate the status of mounting CVMFS by the glidein after evaluating the worker node
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

	echo -e "$(hostname -s) $(date +%m-%d-%Y\ %T\ %Z) \t INFO: $1" >&2
}


logwarn(){
	# DESCRIPTION: This function prints warning messages to STDOUT along
	# with hostname and date/time.
	#
	# INPUT(S): String containing the message
	# RETURN(S): Prints message to STDOUT

	echo -e "$(hostname -s) $(date +%m-%d-%Y\ %T\ %Z) \t WARNING: $1" >&2
}


logerror() {
	# DESCRIPTION: This function prints error messages to STDOUT along with
	# hostname and date/time.
	#
        # INPUT(S): String containing the message
	# RETURN(S): Prints message to STDOUT

	echo -e "$(hostname -s) $(date +%m-%d-%Y\ %T\ %Z) \t ERROR: $1" >&2
}


check_exit_status () {
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
	if [[ -f $CVMFS_ROOT/$repo_name/.cvmfsdirtab || "$(ls -A $CVMFS_ROOT/$repo_name)" ]] &>/dev/null
	then
		loginfo "Validating CVMFS with ${repo_name}..."
		true
	else
		logwarn "Validating CVMFS with ${repo_name}: directory empty or does not have .cvmfsdirtab"
		false
	fi

	GWMS_IS_CVMFS_MNT=$?
	loginfo "CVMFS locally installed: $(check_exit_status $GWMS_IS_CVMFS_MNT)"
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
	# 	-> results from running the check_exit_status function
	# 	for logging purposes (variables starting with res_)
	# 	-> assigns "yes" to GWMS_SYSTEM_CHECK to indicate this function
	# 	has been run.

	if [[ -f "/etc/redhat-release" ]]; then
		GWMS_OS_DISTRO=rhel
	else
		GWMS_OS_DISTRO=non-rhel
	fi

	# source the os-release file to access the variables defined
	. /etc/os-release
	GWMS_OS_VERSION_FULL=$VERSION_ID
	GWMS_OS_VERSION_MAJOR=$(echo "$GWMS_OS_VERSION_FULL" | awk -F'.' '{print $1}')
	GWMS_OS_VERSION_MINOR=$(echo "$GWMS_OS_VERSION_FULL" | awk -F'.' '{print $2}')
	GWMS_OS_NAME=${NAME,,}
	GWMS_OS_KRNL_ARCH=$(arch)
	GWMS_OS_KRNL_NUM=$(uname -r | awk -F'-' '{split($2,a,"."); print $1,a[1]}' | cut -f 1 -d " " )
	GWMS_OS_KRNL_VER=$(uname -r | awk -F'-' '{split($2,a,"."); print $1,a[1]}' | cut -f 1 -d " " | awk -F'.' '{print $1}')
	GWMS_OS_KRNL_MAJOR_REV=$(uname -r | awk -F'-' '{split($2,a,"."); print $1,a[1]}' | cut -f 1 -d " " | awk -F'.' '{print $2}')
	GWMS_OS_KRNL_MINOR_REV=$(uname -r | awk -F'-' '{split($2,a,"."); print $1,a[1]}' | cut -f 1 -d " " | awk -F'.' '{print $3}')
	GWMS_OS_KRNL_PATCH_NUM=$(uname -r | awk -F'-' '{split($2,a,"."); print $1,a[1]}' | cut -f 2 -d " ")

	#df -h | grep /cvmfs &>/dev/null
	#GWMS_IS_CVMFS_MNT=$?
	# call function to detect local CVMFS only if the GWMS_IS_CVMFS_MNT variable is not set; if the variable is not empty, do nothing
	[[ -z "${GWMS_IS_CVMFS_MNT}" ]] && detect_local_cvmfs || :

	max_user_namespaces=$(cat /proc/sys/user/max_user_namespaces)
	[[ $max_user_namespaces -gt 0 ]] && true || false
	GWMS_IS_UNPRIV_USERNS_SUPPORTED=$?

	unshare -U true &>/dev/null
	GWMS_IS_UNPRIV_USERNS_ENABLED=$?

	[[ $GWMS_OS_VERSION_MAJOR -ge 9 ]] && dnf list installed fuse3 &>/dev/null || yum list installed fuse &>/dev/null
	GWMS_IS_FUSE_INSTALLED=$?

	[[ $GWMS_OS_VERSION_MAJOR -ge 9 ]] && fusermount3 -V &>/dev/null || fusermount -V &>/dev/null
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

        loginfo "Found $GWMS_OS_NAME [$GWMS_OS_DISTRO] ${GWMS_OS_VERSION_FULL}-${GWMS_OS_KRNL_ARCH} with kernel $GWMS_OS_KRNL_NUM-$GWMS_OS_KRNL_PATCH_NUM"
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
	loginfo "Operating system name: $GWMS_OS_NAME"
	loginfo "Operating System version: $GWMS_OS_VERSION_FULL"
	loginfo "Kernel Architecture: $GWMS_OS_KRNL_ARCH"
	loginfo "Kernel version: $GWMS_OS_KRNL_VER"
	loginfo "Kernel major revision: $GWMS_OS_KRNL_MAJOR_REV"
	loginfo "Kernel minor revision: $GWMS_OS_KRNL_MINOR_REV"
	loginfo "Kernel patch number: $GWMS_OS_KRNL_PATCH_NUM"

	loginfo "CVMFS locally installed: $(check_exit_status $GWMS_IS_CVMFS_MNT)"
	loginfo "Unprivileged user namespaces supported: $(check_exit_status $GWMS_IS_UNPRIV_USERNS_SUPPORTED)"
	loginfo "Unprivileged user namespaces enabled: $(check_exit_status $GWMS_IS_UNPRIV_USERNS_ENABLED)"
	loginfo "FUSE installed: $(check_exit_status $GWMS_IS_FUSE_INSTALLED)"
	loginfo "fusermount available: $(check_exit_status $GWMS_IS_FUSERMOUNT)"
	loginfo "Is the $(whoami) user in 'fuse' group: $(check_exit_status $GWMS_IS_USR_IN_FUSE_GRP)"
	loginfo "..."
}


mount_cvmfs_repos () {
        # DESCRIPTION: This function mounts all the required and additional
        # CVMFS repositories that would be needed for user jobs.
        #
        # INPUT(S): 1. CVMFS configuration repository (string); 2. Additional CVMFS
        # repositories (colon-delimited string)
        # RETURN(S): Mounts the defined repositories on the worker node filesystem

	$glidein_cvmfsexec_dir/$dist_file $1 -- echo "setting up mount utilities..." &> /dev/null
	if [[ $(df -h|grep /cvmfs|wc -l) -eq 1 ]]; then
		loginfo "CVMFS config repo already mounted!"
		continue
	else
		# mounting the configuration repo (pre-requisite)
		loginfo "Mounting CVMFS config repo now..."
		$glidein_cvmfsexec_dir/.cvmfsexec/mountrepo $1
	fi

	# using an array to unpack the names of additional CVMFS repositories
	# from the colon-delimited string
	declare -a cvmfs_repos
	repos=($(echo $2 | tr ":" "\n"))
	#echo ${repos[@]}

	loginfo "Mounting additional CVMFS repositories..."
	# mount every repository that was previously unpacked
	for repo in "${repos[@]}"
	do
		$glidein_cvmfsexec_dir/.cvmfsexec/mountrepo $repo
	done

	# see if all the repositories got mounted
	num_repos_mntd=`df -h | grep /cvmfs | wc -l`
	total_num_repos=$(( ${#repos[@]} + 1 ))
	if [ "$num_repos_mntd" -eq "$total_num_repos" ]; then
		loginfo "All CVMFS repositories mounted successfully on the worker node"
		true
	else
		logwarn "One or more CVMFS repositories might not be mounted on the worker node"
		false
	fi

	GWMS_IS_CVMFS=$?
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
		else
			# unprivileged user namespaces is not supported
			logerror "Inconsistent system configuration: unprivileged userns is enabled but not supported"
        		echo error
		fi
		true
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
		false
	fi

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
	unpriv_userns_config=$(has_unpriv_userns)

	# exit from the script if unprivileged namespaces are not supported but enabled in the kernel
	if [[ "${unpriv_userns_config}" == error ]]; then
		"$error_gen" -error "`basename $0`" "WN_Resource" "Unprivileged user namespaces are not supported but enabled in the kernel! Check system configuration."
		exit 1
	# determine if mountrepo/umountrepo could be used by checking availability of fuse, fusermount and user being in fuse group...
	elif [[ "${GWMS_IS_FUSE_INSTALLED}" -eq 0 ]]; then
		# fuse is installed
		if [[ $unpriv_userns_config == unavailable ]]; then
			# unprivileged user namespaces unsupported, i.e. kernels 2.x (scenarios 5b,6b)
			if [[ "${GWMS_IS_USR_IN_FUSE_GRP}" -eq 0 ]]; then
				# user is in fuse group -> fusermount is available (scenario 6b)
                                if [[ "${GWMS_IS_FUSERMOUNT}" -ne 0 ]]; then
                                        logwarn "Inconsistent system configuration: fusermount is available with fuse installed and when user is in fuse group"
                                        echo error
                                else
                                        loginfo "FUSE requirements met by the worker node"
                                        echo yes
                                fi
                        else
                                # user is not in fuse group -> fusermount is unavailable (scenario 5b)
				if [[ "${GWMS_IS_FUSERMOUNT}" -eq 0 ]]; then
                                        logwarn "Inconsistent system configuration: fusermount is available only when user is in fuse group and fuse is installed"
                                        echo error
                                else
                                        loginfo "FUSE requirements not satisfied: user is not in fuse group"
                                        echo no
                                fi
			fi
		else
			# unprivileged user namespaces is either enabled or disabled
			if [[ "${GWMS_IS_FUSERMOUNT}" -eq 0 ]]; then
				# fusermount is available (scenarios 7,8)
				loginfo "FUSE requirements met by the worker node"
				echo yes
			else
				# fusermount is not available (scenarios 5a,6a)
				logwarn "Inconsistent system configuration: fusermount is available when fuse is installed "
				echo error
			fi
		fi
	else
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
	fi

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
		true
	elif [[ $fuse_config_status == no ]]; then
		# failure;
		logerror "CVMFS cannot be mounted on the worker node using mountrepo utility"
		false
	elif [[ $fuse_config_status == error ]]; then
		# inconsistent system configurations detected in the worker node
		logerror "Detected inconsistent configurations on the worker node. mountrepo utility cannot be used!!"
		false
	fi

}


perform_cvmfs_mount () {
        # reset all variables used in this script's namespace before executing the rest of the script
        variables_reset

        # perform checks on the worker node that will be used to assess whether CVMFS can be mounted or not
        perform_system_check

        # print/display all information pertaining to system checks performed previously (facilitates easy troubleshooting)
        log_all_system_info

        loginfo "CVMFS Source = $cvmfs_source"
        # initializing CVMFS repositories to a variable for easy modification in the future
        local cvmfs_source_repolist combined_repos
        case $cvmfs_source in
            osg)
                GLIDEIN_CVMFS_CONFIG_REPO=config-osg.opensciencegrid.org
                cvmfs_source_repolist=singularity.opensciencegrid.org:cms.cern.ch
                ;;
            egi)
                GLIDEIN_CVMFS_CONFIG_REPO=config-egi.egi.eu
                cvmfs_source_repolist=config-osg.opensciencegrid.org:singularity.opensciencegrid.org:cms.cern.ch
                ;;
            default)
                GLIDEIN_CVMFS_CONFIG_REPO=cvmfs-config.cern.ch
                cvmfs_source_repolist=config-osg.opensciencegrid.org:singularity.opensciencegrid.org:cms.cern.ch
                ;;
            *)
                "$error_gen" -error "`basename $0`" "WN_Resource" "Invalid factory attribute value specified for CVMFS source."
                exit 1
        esac
        GLIDEIN_CVMFS_REPOS=$(gconfig_get GLIDEIN_CVMFS_REPOS)
        if [[ -z $GLIDEIN_CVMFS_REPOS ]]; then
            GLIDEIN_CVMFS_REPOS="$cvmfs_source_repolist"
        else
            combined_repos="$cvmfs_source_repolist:$GLIDEIN_CVMFS_REPOS"
            combined_repos=$(echo "${combined_repos}" | tr ':' '\n' | sort -u)
            GLIDEIN_CVMFS_REPOS=$(echo "$combined_repos" | tr '\n' ':')
        fi
        GLIDEIN_CVMFS_REPOS="${GLIDEIN_CVMFS_REPOS%:}"

        # (optional) set an environment variable that suggests additional repos to be mounted after config repos are mounted
        loginfo "CVMFS Config Repo = $GLIDEIN_CVMFS_CONFIG_REPO"

        # by this point, it would have been established that CVMFS is not locally available
        # so, install CVMFS via mountrepo or cvmfsexec
        loginfo "CVMFS is NOT locally mounted on the worker node! Mounting now..."
        # check the operating system distribution
        #if [[ $GWMS_OS_DISTRO = RHEL ]]; then
            # evaluate the worker node's system configurations to decide whether CVMFS can be mounted or not
            loginfo "Evaluating the worker node..."
            # display operating system information
            print_os_info

        # assess the worker node based on its existing system configurations and perform next steps accordingly
        if evaluate_worker_node_config ; then
            # if evaluation was true, then proceed to mount CVMFS
            if [[ $glidein_cvmfs = never ]]; then
                # do nothing; test the node and print the results but do not even try to mount CVMFS
                # just continue with glidein startup
                echo $?
                "$error_gen" -ok "`basename $0`" "msg" "Not trying to install CVMFS."
            else
                loginfo "Mounting CVMFS repositories..."
                if mount_cvmfs_repos $GLIDEIN_CVMFS_CONFIG_REPO $GLIDEIN_CVMFS_REPOS ; then
                    :
                else
                    if [[ $glidein_cvmfs = required ]]; then
                        # if mount CVMFS is not successful, report an error and exit with failure exit code
                        echo $?
                        "$error_gen" -error "`basename $0`" "WN_Resource" "CVMFS is required but unable to mount CVMFS on the worker node."
                        exit 1
                    elif [[ $glidein_cvmfs = preferred || $glidein_cvmfs = optional ]]; then
                        # if mount CVMFS is not successful, report a warning/error in the logs and continue with glidein startup
                        # script status must be OK, otherwise the glidein will fail
                        echo $?
                        "$error_gen" -ok "`basename $0`" "WN_Resource" "Unable to mount required CVMFS on the worker node. Continuing without CVMFS."
                    else
                        "$error_gen" -error "`basename $0`" "WN_Resource" "Invalid factory attribute value specified for CVMFS requirement."
                        exit 1
                    fi
                fi
            fi
        else
            # if evaluation was false, then exit from this activity of mounting CVMFS
            "$error_gen" -error "`basename $0`" "WN_Resource" "Worker node configuration did not pass the evaluation checks. CVMFS will not be mounted."
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

        #loginfo "End log for mounting CVMFS"
}

glidein_config="$1"

# import add_config_line function
add_config_line_source=$(grep -m1 '^ADD_CONFIG_LINE_SOURCE ' "$glidein_config" | cut -d ' ' -f 2-)
# shellcheck source=./add_config_line.source
. "$add_config_line_source"

# adding system information about unprivileged user namespaces to the glidein classad
gconfig_add "HAS_UNPRIVILEGED_USER_NAMESPACES" "$(has_unpriv_userns)"
condor_vars_file=$(gconfig_get CONDOR_VARS_FILE "${glidein_config}" "-i")
add_condor_vars_line "HAS_UNPRIVILEGED_USER_NAMESPACES" "S" "-" "+" "Y" "Y" "+"
