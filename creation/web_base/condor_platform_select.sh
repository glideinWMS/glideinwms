#!/bin/bash

#
# Project:
#   glideinWMS
#
# File Version: 
#
# Description:
#   This script will select the appropriate condor tarball
#   Must be listed in the file_list before the condor tarballs
#   as it turns on one of them
#

glidein_config=$1
tmp_fname=${glidein_config}.$$.tmp

error_gen=`grep '^ERROR_GEN_PATH ' $glidein_config | awk '{print $2}'`

condor_vars_file=`grep -i "^CONDOR_VARS_FILE " $glidein_config | awk '{print $2}'`

# import add_config_line and add_condor_vars_line functions
add_config_line_source=`grep '^ADD_CONFIG_LINE_SOURCE ' $glidein_config | awk '{print $2}'`
source $add_config_line_source

condor_os=`grep '^CONDOR_OS ' $glidein_config | awk '{print $2}'`
if [ -z "$condor_os" ]; then
    condor_os="default"
fi

function findversion_redhat {
  # content of /etc/redhat-release
  #Scientific Linux release 6.2 (Carbon)
  #Red Hat Enterprise Linux Server release 5.8 (Tikanga)
  #Scientific Linux SL release 5.5 (Boron)
  #CentOS release 4.2 (Final)
  #
  #Do we support FC:Fedora Core release 11 ... ?
  #
  # should I check that it is SL/RHEL/CentOS ? 
  # no 
  grep -q 'release 7.' /etc/redhat-release && condor_os='linux-rhel7' && return
  grep -q 'release 6.' /etc/redhat-release && condor_os='linux-rhel6' && return
  grep -q 'release 5.' /etc/redhat-release && condor_os='linux-rhel5' && return
}

function findversion_debian {
  #cat /etc/*release
  #DISTRIB_ID=Ubuntu
  #DISTRIB_RELEASE=11.10
  #DISTRIB_CODENAME=oneiric
  #DISTRIB_DESCRIPTION="Ubuntu 11.10"
  #
  #user@bellatrix:~$ lsb_release
  #No LSB modules are available.
  #
  #user@bellatrix:~$ lsb_release -a  
  #No LSB modules are available.
  #
  #Distributor ID:    Ubuntu
  #Description:    Ubuntu 11.10
  #Release:    11.10
  #Codename:    oneiric       

  dist_id_line="`grep "DISTRIB_ID" /etc/lsb-release`"
  dist_rel_line="`grep "DISTRIB_RELEASE" `"
  if [[ $dist_id_line == *"Debian"* ]]; then
    [ ${dist_rel_line:16:2} = "7\." ] && condor_os='linux-debian7' && return
    [ ${dist_rel_line:16:2} = "8\." ] && condor_os='linux-debian8' && return
  elif [[ $dist_id_line == *"Ubuntu"* ]]; then
    [ ${dist_rel_line:16:2} = "12\." ] && condor_os='linux-ubuntu12' && return
    [ ${dist_rel_line:16:2} = "14\." ] && condor_os='linux-ubuntu14' && return
  fi
}



if [ "$condor_os" == "auto" ]; then
    if [ -f "/etc/redhat-release" ]; then 
    # rhel, now determine the version
        # default RHEL
        condor_os='linux-rhel6'
        findversion_redhat
	#strings /lib/libc.so.6  |grep -q GLIBC_2.4
	#if [ $? -ne 0 ]; then
	#    # pre-RHEL5
	#    condor_os='linux-rhel3'
	#else
	#    # I am not aware of anything newer right now
	#    condor_os='linux-rhel5'
	#fi
    elif [ -f "/etc/lsb-release" ]; then 
    # debian/ubuntu, now determine the version
        # default debian
        condor_os='linux-debian8'
        findversion_debian
#    elif [ -f "/etc/debian_version" ]; then 
#    # debian, now determine the version
#    grep -q '^5' /etc/debian_version
#    if [ $? -ne 0 ]; then
#        # pre-Debian 5
#	     condor_os='linux-debian40'
#	     else
#	         # I am not aware of anything newer right now
#		     condor_os='linux-debian50'
#		     fi

    else 
        #echo "Not a RHEL not Debian compatible system. Autodetect not supported"  1>&2
        STR="Not a RHEL not Debian compatible system. Autodetect not supported"
        "$error_gen" -error "condor_platform_select.sh" "Config" "$STR" "SupportAutodetect" "False" "OSType" "Unknown"
        exit 1
    fi
fi

condor_arch=`grep '^CONDOR_ARCH ' $glidein_config | awk '{print $2}'`
if [ -z "$condor_arch" ]; then
    condor_arch="default"
fi

if [ "$condor_arch" == "auto" ]; then
    condor_arch=`uname -m`
    if [ "$condor_arch" == "x86_64" ]; then
    condor_arch="x86_64,x86"
    elif [ "$condor_arch" == "i386" -o "$condor_arch" == "i486" -o "$condor_arch" == "i586" -o "$condor_arch" == "i686" ]; then
    condor_arch="x86"
    else
        #echo "Not a x86 compatible system. Autodetect not supported"  1>&2
        STR="Not a x86 compatible system. Autodetect not supported"
        "$error_gen" -error "condor_platform_select.sh" "Config" "$STR" "SupportAutodetect" "False" "ArchType" "Unknown"
        exit 1
    fi
fi

condor_version=`grep '^CONDOR_VERSION ' $glidein_config | awk '{print $2}'`
if [ -z "$condor_version" ]; then
    condor_version="default"
fi

condor_platform_check=""
for version_el in `echo "$condor_version" |awk '{split($0,l,","); for (i in l) s=s " " l[i]; print s}'`; do
  if [ -z "$condor_platform_check" ]; then
    # not yet found, try to find it
    for os_el in `echo "$condor_os" |awk '{split($0,l,","); for (i in l) s=s " " l[i]; print s}'`; do
      if [ -z "$condor_platform_check" ]; then
        # not yet found, try to find it
        for arch_el in `echo "$condor_arch" |awk '{split($0,l,","); for (i in l) s=s " " l[i]; print s}'`; do
          if [ -z "$condor_platform_check" ]; then
            # not yet found, try to find it
            # combine the three
            condor_platform="${version_el}-${os_el}-${arch_el}"
            condor_platform_id="CONDOR_PLATFORM_$condor_platform"
  
            condor_platform_check=`grep "^$condor_platform_id " "$glidein_config" | awk '{print $2}'`
          fi
        done
      fi
    done
  fi
done

if [ -z "$condor_platform_check" ]; then
    # uhm... all tries failed
    #echo "Cannot find a supported platform" 1>&2
    #echo "CONDOR_VERSION '$condor_version'" 1>&2
    #echo "CONDOR_OS      '$condor_os'" 1>&2
    #echo "CONDOR_ARCH    '$condor_arch'" 1>&2
    #echo "Quitting" 1>&2
    STR="Cannot find a supported platform\n"
    STR+="CONDOR_VERSION '$condor_version'\n"
    STR+="CONDOR_OS      '$condor_os'\n"
    STR+="CONDOR_ARCH    '$condor_arch'\n"
    STR+="Quitting"
    STR1=`echo -e "$STR"`
    "$error_gen" -error "condor_platform_select.sh" "Config" "$STR1" "ReqVersion" "$condor_version" "ReqOS" "$condor_os" "ReqArch" "$condor_arch"
    exit 1
fi

# this will enable this particular Condor version to be downloaded and unpacked
add_config_line "$condor_platform_id" "1"

"$error_gen" -ok "condor_platform_select.sh" "Condor_platform" "${version_el}-${os_el}-${arch_el}"

exit 0
