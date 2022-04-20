#!/bin/bash

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

usage() {
	echo "This script is used to generate cvmfsexec distributions for all"
	echo "supported machine types (platform- and architecture-based)."
	echo "The script takes one parameter {osg|egi|default} which specifies"
	echo "the source to download the latest cvmfs configuration and repositories."
}

start=`date +%s`

CVMFS_SOURCES=osg:egi:default
# rhel6-x86_64 is not included; currently not supported due to EOL
# egi for rhel8-x86_64 results in an error - egi does not yet have a centos8 build (as confirmed with Dave)
# TODO: verify the logic when egi provides a centos8 build
SUPPORTED_TYPES=rhel7-x86_64:rhel8-x86_64:suse15-x86_64
cvmfsexec_temp=/tmp/cvmfsexec_pkg
cvmfsexec_base=$cvmfsexec_temp/cvmfsexec
cvmfsexec_latest=$cvmfsexec_temp/latest
cvmfsexec_distros=$cvmfsexec_temp/distros
work_dir=/var/lib/gwms-factory/work-dir
cvmfsexec_tarballs=$work_dir/cvmfsexec/tarballs

if [[ -d $cvmfsexec_temp ]]; then
#    rm -rf $cvmfsexec_pkg
    if [[ -d $cvmfsexec_base ]]; then
        curr_ver=`$cvmfsexec_base/cvmfsexec -v`
        git clone https://www.github.com/cvmfs/cvmfsexec.git $cvmfsexec_latest &> /dev/null
        latest_ver=`$cvmfsexec_latest/cvmfsexec -v`
        if [[ $curr_ver != $latest_ver ]]; then
            # if current version and latest version are different, use the latest
            echo "Current version of cvmfsexec: $curr_ver"
            echo "Found newer version of cvmfsexec..."
            rm -rf $cvmfsexec_base
            mv $cvmfsexec_latest $cvmfsexec_base
            echo "Latest version of cvmfsexec: `$cvmfsexec_base/cvmfsexec -v`"
            echo "Using cvmfsexec version: `$cvmfsexec_base/cvmfsexec -v`"
        else
            # if current version and latest version are the same
            echo "Current version and latest version of cvmfsexec are identical!"
            echo "cvmfsexec version: `$cvmfsexec_base/cvmfsexec -v`"
            rm -rf $cvmfsexec_latest
            exit 0
        fi
    else
        # $cvmfsexec_base does not exist
        git clone https://www.github.com/cvmfs/cvmfsexec.git $cvmfsexec_base &> /dev/null
        echo "cvmfsexec version: `$cvmfsexec_base/cvmfsexec -v`"
    fi
else
    # $cvmfsexec_temp does not exist
    git clone https://www.github.com/cvmfs/cvmfsexec.git $cvmfsexec_base &> /dev/null
    echo "cvmfsexec version: `$cvmfsexec_base/cvmfsexec -v`"

fi

if [[ ! -d $cvmfsexec_distros ]]; then
    mkdir -p $cvmfsexec_distros
fi

if [[ ! -d $cvmfsexec_tarballs ]]; then
    mkdir -p $cvmfsexec_tarballs
fi

declare -a cvmfs_sources
cvmfs_sources=($(echo $CVMFS_SOURCES | tr ":" "\n"))

declare -a machine_types
machine_types=($(echo $SUPPORTED_TYPES | tr ":" "\n"))

for cvmfs_src in "${cvmfs_sources[@]}"
do
    for mach_type in "${machine_types[@]}"
    do
        echo -n "Making $cvmfs_src distribution for $mach_type machine..."
        os=`echo $mach_type | awk -F'-' '{print $1}'`
        arch=`echo $mach_type | awk -F'-' '{print $2}'`
        $cvmfsexec_base/makedist -m $mach_type $cvmfs_src &> /dev/null
        if [[ $? -eq 0 ]]; then
           $cvmfsexec_base/makedist -o $cvmfsexec_distros/cvmfsexec-${cvmfs_src}-${os}-${arch} &> /dev/null
           if [[ -e $cvmfsexec_distros/cvmfsexec-${cvmfs_src}-${os}-${arch} ]]; then
               echo " Success"
               tar -cvzf $cvmfsexec_tarballs/cvmfsexec_${cvmfs_src}_${os}_${arch}.tar.gz -C $cvmfsexec_distros cvmfsexec-${cvmfs_src}-${os}-${arch} &> /dev/null
           fi
        else
            echo " Failed! REASON: $cvmfs_src may not yet have a $mach_type build."
        fi

        # delete the dist directory within cvmfsexec to download the cvmfs configuration
        # and repositories for another machine type
        rm -rf $cvmfsexec_base/dist
    done
done

# TODO: store version information in the $cvmfsexec_tarballs location for future reconfig/upgrade
#echo "$curr_ver" > $cvmfsexec_tarballs/.version_info

end=`date +%s`

runtime=$((end-start))
echo "Took $runtime seconds (the two for-loops)"
