#!/bin/bash

# first parameter passed to this script will always be the glidein configuration file (glidein_config)
glidein_config=$1

# fetch the error reporting helper script
error_gen=`grep '^ERROR_GEN_PATH ' $glidein_config | awk '{print $2}'`

# get the cvmfsexec attribute switch value from the config file
use_cvmfsexec=`grep '^GLIDEIN_USE_CVMFSEXEC ' $glidein_config | awk '{print $2}'`
# TODO: int or string?? if string, make the attribute value case insensitive
#use_cvmfsexec=${use_cvmfsexec,,}
echo "GLIDEIN_USE_CVMFSEXEC set to $use_cvmfsexec"

if [[ $use_cvmfsexec -ne 1 ]]; then
    "$error_gen" -ok "`basename $0`" "msg" "Not using cvmfsexec; skipping setup."
    exit 0
fi

# if GLIDEIN_USE_CVMFSEXEC is set to 1 - check if CVMFS is locally available in the node
# validate CVMFS by examining the directories within CVMFS... checking just one directory should be sufficient?
# get the glidein work directory location from glidein_config file
work_dir=`grep '^GLIDEIN_WORK_DIR ' $glidein_config | awk '{print $2}'`
# store the directory location, to where the tarball is unpacked by the glidein, to a variable
cvmfs_utils_dir=$work_dir/cvmfs_utils
# $PWD=/tmp/glide_xxx and every path is referenced with respect to $PWD
# source the helper script
source $cvmfs_utils_dir/utils/cvmfs_helper_funcs.sh

variables_reset

detect_local_cvmfs

# check if CVMFS is already locally mounted...
if [[ $GWMS_IS_CVMFS_MNT -eq 0 ]]; then
    # if it is so...
    "$error_gen" -ok "`basename $0`" "msg" "CVMFS is locally mounted on the node; skipping setup."
    exit 0
fi

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

if [[ $GWMS_IS_CVMFS -ne 0 ]]; then
    # Error occured during mount of CVMFS repositories"
    logerror "Error occured during mount of CVMFS repositories."
    "$error_gen" -error "`basename $0`" "WN_Resource" "Mount unsuccessful... CVMFS is still unavailable on the node."
    exit 1
fi

# CVMFS is now available on the worker node"
loginfo "Proceeding to execute user job..."
"$error_gen" -ok "`basename $0`" "WN_Resource" "CVMFS mounted successfully and is now available."
