#!/bin/bash

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

usage() {
	echo "This script is used to generate cvmfsexec distributions for all"
	echo "supported machine types (platform- and architecture-based)."
	echo "The script takes one parameter {osg|egi|default} which specifies"
	echo "the source to download the latest cvmfs configuration and repositories."
}

glidein_config=$1

error_gen=`grep '^ERROR_GEN_PATH ' $glidein_config | awk '{print $2}'`

# parameter is 'osg', 'egi' or 'default' to download the latest cvmfs and configuration
# rpm from one of these three sources (Ref. https://www.github.com/cvmfs/cvmfsexec)
cvmfs_src=`grep '^CVMFS_SRC ' $glidein_config | awk '{print $2}'`
cvmfs_src=${cvmfs_src,,}

# check if the value of cvmfs_src is valid
if [[ ! $cvmfs_src =~ ^(osg|egi|default)$ ]]; then
    echo "Invalid command line argument: Must be one of {osg, egi, default}"
    "$error_gen" -error "`basename $0`" "fail_msg" "Invalid command line argument: Must be one of {osg, egi, default}"
    exit 1
fi

# import add_config_line function
add_config_line_source=`grep '^ADD_CONFIG_LINE_SOURCE ' $glidein_config | awk '{print $2}'`
source $add_config_line_source

# TODO: is it possible to reuse cvmfs_helper_funcs.sh by sourcing it during the execution of this file????
if [ -f '/etc/redhat-release' ]; then
    os_distro=rhel
else
    os_distro=non-rhel
fi

os_ver=`lsb_release -r | awk -F'\t' '{print $2}' | awk -F"." '{print $1}'`
krnl_arch=`arch`
mach_type=${os_distro}${os_ver}-${krnl_arch}

cvmfsexec_platform="${cvmfs_src}-${mach_type}"
cvmfsexec_platform_id="CVMFSEXEC_PLATFORM_$cvmfsexec_platform"

# add the attribute to enable the appropriate distro file
add_config_line "$cvmfsexec_platform_id" "1"

# if everything goes well, report the good part too!
"$error_gen" -ok "`basename $0`" "Cvmfsexec_platform" "${cvmfs_src}-${mach_type}"

exit 0
