#!/bin/bash

# first parameter passed to this script will always be the glidein configuration file (glidein_config)
glidein_config=$1

# fetch the error reporting helper script
error_gen=`grep '^ERROR_GEN_PATH ' $glidein_config | awk '{print $2}'`
#echo $error_gen

# get the cvmfsexec attribute switch value from the config file
use_cvmfsexec=`grep '^GLIDEIN_USE_CVMFSEXEC ' $glidein_config | awk '{print $2}'`
# TODO: int or string?? if string, make the attribute value case insensitive
#use_cvmfsexec=${use_cvmfsexec,,}
echo "GLIDEIN_USE_CVMFSEXEC attribute set to $use_cvmfsexec"

if [[ $use_cvmfsexec -ne 1 ]]; then
        "$error_gen" -ok "`basename $0`" "msg" "Not using cvmfsexec; skipping setup."
        exit 0
fi

#test_repos=config-osg.opensciencegrid.org:singularity.opensciencegrid.org:atlas.cern.ch:glast.egi.eu:oasis.opensciencegrid.org:cms.cern.ch
# using an array to unpack the names of additional CVMFS repositories from the colon-delimited string
#declare -a repos
#repos=($(echo $test_repos | tr ":" "\n"))
#echo ${repos[@]}
#for repo_name in "${repos[@]}"
#do
#done

# if GLIDEIN_USE_CVMFSEXEC is set to 1 - check if CVMFS is locally available in the node
# validate CVMFS by examining the directories within CVMFS... checking just one directory should be sufficient?
# get the glidein work directory location from glidein_config file
work_dir=`grep '^GLIDEIN_WORK_DIR ' $glidein_config | awk '{print $2}'`
# store the directory location, to where the tarball is unpacked by the glidein, to a variable
cvmfs_utils_dir=$work_dir/cvmfs_utils
# $PWD=/tmp/glide_xxx and every path is referenced with respect to $PWD
# source the helper script
source $cvmfs_utils_dir/utils/cvmfs_helper_funcs.sh
#source cvmfs_utils/utils/cvmfs_helper_funcs.sh

variables_reset

detect_local_cvmfs

# check if CVMFS is already locally mounted...
if [[ $GWMS_IS_CVMFS_MNT -eq 0 ]]; then
	# if it is so...
	"$error_gen" -ok "`basename $0`" "msg" "CVMFS is locally mounted on the node; skipping setup."
        exit 0
else
	# if CVMFS is not found locally...
	# get the CVMFS source information from <attr> in the glidein configuration 
	cvmfs_source=`grep '^CVMFS_SRC ' $glidein_config | awk '{print $2}'`
	
	# get the CVMFS requirement setting passed as one of the factory attributes
	glidein_cvmfs=`grep '^GLIDEIN_CVMFS ' $glidein_config | awk '{print $2}'`
	
	perform_system_check
	
	os_like=$GWMS_OS_DISTRO
	os_ver=`echo $GWMS_OS_VERSION | awk -F'.' '{print $1}'`
	arch=$GWMS_OS_KRNL_ARCH
	dist_file=cvmfsexec-${cvmfs_source}-${os_like}${os_ver}-${arch}
	
	tar -xvzf $cvmfs_utils_dir/utils/cvmfs_distros.tar.gz -C $cvmfs_utils_dir distros/$dist_file
	
	. $cvmfs_utils_dir/utils/cvmfs_mount.sh
	
	if [[ $GWMS_IS_CVMFS -eq 0 ]]; then
		# CVMFS is now available on the worker node"
	        # mimicking the behavior of the glidein on the worker node (start the user job once the CVMFS repositories are mounted)
		loginfo "Starting user job..."
		# . user_job.sh
	else
	       	logerror "CVMFS is still unavailable on the worker node"
		# Error occured during mount of CVMFS repositories"
		exit 1
	fi
fi
