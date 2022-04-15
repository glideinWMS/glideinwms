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

sys_tmp=$(echo $TMPDIR)
if [[ -z "$sys_tmp" ]]; then
    sys_tmp=/tmp
fi

# first, checking in the work-dir location for the current version of cvmfsexec
work_dir=$(grep -m 1 "submit" /etc/gwms-factory/glideinWMS.xml | awk -F"\"" '{print $6}')
cvmfsexec_tarballs=$work_dir/cvmfsexec/tarballs
if [[ -d $cvmfsexec_tarballs && -f "$cvmfsexec_tarballs/.cvmfsexec_version" ]]; then
    curr_ver=$(cat $cvmfsexec_tarballs/.cvmfsexec_version)
    echo "Current version found: $curr_ver"
fi

# otherwise, .cvmfsexec_version file does not exist from a previous upgrade or it's a first-time factory upgrade
# check if the temp directory for cvmfsexec from previous run exists
ls -d $sys_tmp/cvmfsexec.*/ > /dev/null 2>&1
if [[ $? -eq 0 ]]; then
    # cvmfsexec.XXX (temp) directory exists; reuse this
    cvmfsexec_temp=$(ls -d $sys_tmp/cvmfsexec.*/)
    cvmfsexec_temp=${cvmfsexec_temp%?}   # removes the trailing '/' to avoid incorrect paths later
else
    # cvmfsexec.XXX (temp) directory does not exist; so create one
    cvmfsexec_temp=$(mktemp -d -t cvmfsexec.XXX)
    chmod 755 $cvmfsexec_temp
fi

cvmfsexec_latest=$cvmfsexec_temp/latest
CVMFSEXEC_REPO="https://www.github.com/cvmfs/cvmfsexec.git"
git clone $CVMFSEXEC_REPO $cvmfsexec_latest &> /dev/null
latest_ver=$($cvmfsexec_latest/cvmfsexec -v)
if [[ "$curr_ver" == "$latest_ver" ]]; then
    # if current version and latest version are the same
    echo "Current version and latest version of cvmfsexec are identical!"
    if [[ -f "$cvmfsexec_tarballs/.cvmfsexec_version" ]]; then
        echo "Using (existing) cvmfsexec version `cat $cvmfsexec_tarballs/.cvmfsexec_version`"
    fi
    echo "Skipping the building of cvmfsexec distribution tarballs..."
    rm -rf $cvmfsexec_latest
    exit 0
else
    # if current version and latest version are different
    if [[ -z "$curr_ver" ]]; then
        # $curr_ver is empty; first time run of factory upgrade
        # no version info stored in work-dir/cvmfsexec/tarballs
        echo "Building cvmfsexec distributions..."
    else
        # $curr_ver is not empty; subsequent run of factory upgrade (and not the first time)
        echo "Found newer version of cvmfsexec..."
        echo "Rebuilding cvmfsexec distributions using the latest version..."
    fi

    # build the distributions for cvmfsexec based on the source, os and platform combination
    cvmfsexec_distros=$cvmfsexec_temp/distros
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
            $cvmfsexec_latest/makedist -m $mach_type $cvmfs_src &> /dev/null
            if [[ $? -eq 0 ]]; then
                $cvmfsexec_latest/makedist -o $cvmfsexec_distros/cvmfsexec-${cvmfs_src}-${os}-${arch} &> /dev/null
                if [[ -e $cvmfsexec_distros/cvmfsexec-${cvmfs_src}-${os}-${arch} ]]; then
                    echo " Success"
                    tar -cvzf $cvmfsexec_tarballs/cvmfsexec_${cvmfs_src}_${os}_${arch}.tar.gz -C $cvmfsexec_distros cvmfsexec-${cvmfs_src}-${os}-${arch} &> /dev/null
                fi
            else
                echo " Failed! REASON: $cvmfs_src may not yet have a $mach_type build."
            fi

            # delete the dist directory within cvmfsexec to download the cvmfs configuration
            # and repositories for another machine type
            rm -rf $cvmfsexec_latest/dist
        done
    done

fi


# TODO: store/update version information in the $cvmfsexec_tarballs location for future reconfig/upgrade
echo "$latest_ver" > $cvmfsexec_tarballs/.cvmfsexec_version

end=`date +%s`

runtime=$((end-start))
echo "Took $runtime seconds to create the cvmfsexec distributions"
