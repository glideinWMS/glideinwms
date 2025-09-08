#!/bin/bash

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

# This script generates cvmfsexec distributions for various cvmfs configurations
# and supported machine types, as supported by the open-source cvmfsexec utility.

# Hardcoded variables
CVMFSEXEC_REPO="https://www.github.com/cvmfs/cvmfsexec.git"
DEFAULT_WORK_DIR="/var/lib/gwms-factory/work-dir"
# TODO: periodically add rhel, suse and other derivatives as supported by cvmfsexec
# NOTE: Although rhel9-x86_64 is supported, el7 tools might not work with el9 files (as suggested by Dave Dykstra) as of July 03, 2023
DEFAULT_MACHINE_TYPES="rhel9-x86_64,rhel8-x86_64,rhel7-x86_64,suse15-x86_64,rhel8-aarch64,rhel8-ppc64le"

usage() {
cat << EOF
Usage:
$0 [--work-dir DIR] SOURCES_LIST [PLATFORMS_LIST]   Build cvmfsexec distributions
$0 --list-platforms                                 List all available platforms
$0 -h | --help                                      Print this help message

DIR: full, absolute path to the factory work directory (default: /var/lib/gwms-factory/work-dir)

SOURCES_LIST (required): specifies the source(s) to download the latest
cvmfs configuration and repositories from. Must be at least one value
or a comma-separated list of values from the options {osg|egi|default}.

PLATFORMS_LIST (optional): indicates machine types (platform- and architecture-based)
for which distributions is to be built. Can be empty, a single value or a
comma-separated list of values from the options {rhel9-x86_64|rhel8-x86_64|rhel7-x86_64|suse15-x86_64|rhel8-aarch64|rhel8-ppc64le}.
Use '$0 --list-platforms' for the updated list of all available platforms.
EOF
}

ensure_directory_exists() {
	# if the directory does not exist (create one) or exists (proceed to reuse)
	if ! mkdir -p "$1" || ! chmod 755 "$1" ; then
		# if the directory creation or permission change fails, print a message and exit from the script
		echo "Unable to create directory $1" >&2
		exit 1
	fi
}

build_cvmfsexec_distros() {
	local cvmfs_src mach_type curr_ver latest_ver
    local cvmfs_configurations supported_machine_types
    local cvmfsexec_tarballs="$work_dir"/cvmfsexec/tarballs
	local cvmfsexec_temp="$work_dir"/cvmfsexec/cvmfsexec.tmp
	local cvmfsexec_latest="$cvmfsexec_temp"/latest
	local cvmfsexec_distros="$cvmfsexec_temp"/distros
    local work_dir="$1"
    cvmfs_configurations_list="$2"
    supported_machine_types_list="$3"
	start=$(date +%s)

	# rhel6-x86_64 is not included; currently not supported due to EOL
	# egi for rhel8-x86_64 results in an error - egi does not yet have a centos8 build (as confirmed with Dave)
	# TODO: verify the logic when egi provides a centos8 build

	# protect against non-existence of cvmfsexec/tarballs directory; fresh install of GWMS with first run of factory upgrade
	if [[ -d "$work_dir/cvmfsexec/tarballs" ]]; then
		if [[ -f "$cvmfsexec_tarballs/.cvmfsexec_version" ]]; then
			curr_ver=$(cat "$cvmfsexec_tarballs"/.cvmfsexec_version)
			echo "Current version found: $curr_ver"
		fi
	else
		# if the cvmfsexec directory does not exist, create one
		# also, create a directory named tarballs under cvmfsexec directory
		# check if tarballs directory exists; if not, create one; else proceed as usual
		ensure_directory_exists "$cvmfsexec_tarballs"
	fi

	# otherwise, .cvmfsexec_version file does not exist from a previous upgrade or it's a first-time factory upgrade
	# check if the temp directory for cvmfsexec exists
	ensure_directory_exists "$cvmfsexec_temp"

	git clone $CVMFSEXEC_REPO "$cvmfsexec_latest" &> /dev/null
	# cvmfsexec exits with 0, so the output should be checked as well
	if ! latest_ver=$("$cvmfsexec_latest"/cvmfsexec -v) || [[ -z "$latest_ver" ]]; then
	    echo "Failed to run the downloaded cvmfsexec" >&2
	    # line to allow testing when cvmfs is not supported
	    [[ -n "$CVMFSEXEC_FAILURES_OK" ]] && exit 0 || true
	    exit 1
    fi
	if [[ -z "$latest_ver" || "$curr_ver" == "$latest_ver" ]]; then
		# if current version and latest version are the same
		echo "Current version and latest version of cvmfsexec are identical!"
		# no need to recheck if .cvmfsexec_version exists as it is previously verified
		echo "Using cvmfsexec version $(cat "$cvmfsexec_tarballs"/.cvmfsexec_version)"
		echo "Skipping the building of cvmfsexec distribution tarballs..."
		rm -rf "$cvmfsexec_latest"
		exit 0
	else
		# if current version and latest version are different
		if [[ -z "$curr_ver" ]]; then
			# $curr_ver is empty; first time run of factory upgrade
			# no version info stored in work-dir/cvmfsexec/tarballs
			echo "Building cvmfsexec distribution(s)..."
		else
			# $curr_ver is not empty; subsequent run of factory upgrade (and not the first time)
			echo "Found newer version of cvmfsexec..."
			echo "Rebuilding cvmfsexec distribution(s) using the latest version ${latest_ver}..."
		fi

		# build the distributions for cvmfsexec based on the source, os and platform combination
		ensure_directory_exists "$cvmfsexec_distros"

		cvmfs_configurations=($(echo "$cvmfs_configurations_list" | tr "," "\n"))
		supported_machine_types=($(echo "$supported_machine_types_list" | tr "," "\n"))

		local successful_builds=0
		for cvmfs_src in "${cvmfs_configurations[@]}"
		do
			for mach_type in "${supported_machine_types[@]}"
			do
				echo -n "Making $cvmfs_src distribution for $mach_type machine..."
				os=${mach_type%-*}
				arch=${mach_type#*-}
				if "$cvmfsexec_latest"/makedist -m "$mach_type" "$cvmfs_src" &> /dev/null ; then
					"$cvmfsexec_latest"/makedist -o "$cvmfsexec_distros"/cvmfsexec-"${cvmfs_src}"-"${os}"-"${arch}" &> /dev/null
					if [[ -e "$cvmfsexec_distros"/cvmfsexec-${cvmfs_src}-${os}-${arch} ]]; then
						echo " Success"
						if tar -cvzf "$cvmfsexec_tarballs"/cvmfsexec_"${cvmfs_src}"_"${os}"_"${arch}".tar.gz -C "$cvmfsexec_distros" cvmfsexec-"${cvmfs_src}"-"${os}"-"${arch}" &> /dev/null; then
							((successful_builds+=1))
						fi
					else
						echo "Something went wrong!"
						exit 1
					fi
				else
					echo " Failed! REASON: $cvmfs_src may not yet have a $mach_type build."
				fi

				# delete the dist directory within cvmfsexec to download the cvmfs configuration
				# and repositories for another machine type
				rm -rf "$cvmfsexec_latest"/dist
			done
		done

		# remove the distros and latest folder under cvmfsexec.tmp
		rm -rf "$cvmfsexec_distros"
		rm -rf "$cvmfsexec_latest"
	fi


	# TODO: store/update version information in the $cvmfsexec_tarballs location for future reconfig/upgrade
	if [[ "$successful_builds" -gt 0 ]]; then
		# update only if there was at least one successful build of cvmfsexec
		echo "$latest_ver" > "$cvmfsexec_tarballs"/.cvmfsexec_version
	fi

	echo "Took $(($(date +%s)-start)) seconds to create $successful_builds cvmfsexec distribution(s)"
}

error_handler() {
	echo "ERROR: $1"
	usage
	exit 1
}


####################### MAIN SCRIPT STARTS FROM HERE #######################

# parsing the command-line arguments
if [[ $1 == "-h" || $1 == "--help" ]]; then
    # print help message
    usage
    exit 0
fi

if [[ $1 == "--list-platforms" ]]; then
    # checkout the latest version of cvmfsexec into a temp location
    git clone $CVMFSEXEC_REPO /tmp &> /dev/null
    echo "Functionality not implemented!"
    exit 0
fi

# if neither of the two options above, check whether the first argument passed is the option '--work-dir'
if [[ $1 == "--work-dir" && -z $2 ]]; then
    error_handler "--work-dir option must be supplied with a valid directory location."
elif [[ $1 == "--work-dir" && ! -d "$2" ]]; then
	# if value after this option is not a valid path, invoke the error handler
	error_handler "The value of --work-dir option must be an existing directory."
elif [[ $1 != "--work-dir" ]]; then
    # if --work-dir is not passed, assume default work-dir (RPM install)
    work_dir="$DEFAULT_WORK_DIR"
else
    work_dir="$2"
    shift 2
fi

# check whether there are any remaining arguments passed to the script after the option
if [[ $# -eq 0 ]]; then
	echo "No sources specified. Building/Rebuilding of cvmfsexec distributions disabled!"
	exit 0
elif [[ $# -gt 2 ]]; then
	error_handler "Invalid number of arguments passed!"
fi

# after confirming that the remaining number of arguments to be either 1 or 2
re_sources="^((osg|egi|default),)*(osg|egi|default),?$"
# TODO: update the regex for other machine types upon checking with `makedist -h` periodically
re_mtypes="^((rhel(7|8|9)|suse15)(-(x86_64|aarch64|ppc64le),?))+$"
# check whether the first argument is sources (strict ordering followed)
if ! [[ "$1" =~ $re_sources ]]; then
	error_handler "Invalid source(s) provided (comma-separated list with osg|egi|default), not '$1'"
fi
configurations=$1
if [[ -z "$2" ]]; then
	machine_types=$DEFAULT_MACHINE_TYPES
elif [[ "$2" =~ $re_mtypes ]]; then
	machine_types=$2
else
	# handle if there were typos in the arguments passed
	error_handler "Invalid platform provided. Must be empty or comma-separated list with (rhel9-x86_64|rhel8-x86_64|rhel7-x86_64|suse15-x86_64|rhel8-aarch64|rhel8-ppc64le), not '$2'"
fi

echo "(Re)Building of cvmfsexec distributions enabled!"
build_cvmfsexec_distros "$work_dir" "$configurations" "$machine_types"
