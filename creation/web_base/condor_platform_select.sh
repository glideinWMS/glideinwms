#!/bin/bash

############################################################
#
# This script will select the appropriate condor tarball
# Must be listed in the file_list before the condor tarballs
#  as it turns on one of them
#
############################################################

glidein_config=$1
tmp_fname=${glidein_config}.$$.tmp

condor_vars_file=`grep -i "^CONDOR_VARS_FILE " $glidein_config | awk '{print $2}'`

# import add_config_line and add_condor_vars_line functions
add_config_line_source=`grep '^ADD_CONFIG_LINE_SOURCE ' $glidein_config | awk '{print $2}'`
source $add_config_line_source

condor_os=`grep '^CONDOR_OS ' $glidein_config | awk '{print $2}'`
if [ -z "$condor_os" ]; then
    condor_os="default"
fi

if [ "$condor_os" == "auto" ]; then
    if [ -f "/etc/redhat-release" ]; then 
	# rhel, now determine the version
	strings /lib/libc.so.6  |grep -q GLIBC_2.4
	if [ $? -ne 0 ]; then
	    # pre-RHEL5
	    condor_os='linux-rhel3'
	else
	    # I am not aware of anything newer right now
	    condor_os='linux-rhel5'
	fi
    elif [ -f "/etc/debian_version" ]; then 
	# debian, now determine the version
	grep -q '^5' /etc/debian_version
	if [ $? -ne 0 ]; then
	    # pre-Debian 5
	    condor_os='linux-debian40'
	else
	    # I am not aware of anything newer right now
	    condor_os='linux-debian50'
	fi

    else 
	echo "Not a RHEL not Debian compatible system. Autodetect not supported"  1>&2
	exit 1
    fi
fi

condor_arch=`grep '^CONDOR_ARCH ' $glidein_config | awk '{print $2}'`
if [ -z "$condor_arch" ]; then
    condor_arch="default"
fi

if [ "$condor_arch" == "auto" ]; then
    condor_arch=`uname -m`
    if [ "$condor_arch" -eq "x86_64" ]; then
	condor_arch="x86_64"
    elif [ "$condor_arch" == "i386" -o "$condor_arch" == "i486" -o "$condor_arch" == "i586" -o "$condor_arch" == "i686" ]; then
	condor_arch="x86"
    else
	echo "Not a x86 compatible system. Autodetect not supported"  1>&2
	exit 1
    fi
fi

# combine the two
condor_platform="${condor_os}-${condor_arch}"
condor_platform_id="CONDOR_PLATFORM_$condor_platform"

condor_platform_check=`grep "^$condor_platform_id " "$glidein_config" | awk '{print $2}'`
if [ -z "$condor_platform_check" ]; then
    # the line does not exist, so the platform is not supported
    echo "Condor platform $condor_platform not supported. Quitting" 1>&2
    exit 1
fi

# this will enable this particular Condor version to be downloaded and unpacked
add_config_line "$condor_platform_id" "1"

exit 0

