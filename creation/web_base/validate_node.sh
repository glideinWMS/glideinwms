#!/bin/bash

#
# Project:
#   glideinWMS
#
# File Version: 
#
# Description:
#   This script checks that the node is in good shape
#

function check_df {
    chdf_dir="$1"
    chdf_reqmbs=$2

    free=`df -kP $chdf_dir | awk '{if (NR==2) print $4}'`
    let "chdf_reqkbs=$chdf_reqmbs * 1024"
    if [ $free -lt $chdf_reqkbs ]; then
        #echo "Space on '$chdf_dir' not enough." 1>&2
        #echo "At least $chdf_reqmbs MBs required, found $free KBs" 1>&2
        STR="			Space on '$chdf_dir' not enough.\n"
        STR=$STR"			At least $chdf_reqmbs MBs required, found $free KBs"
        echo -e $STR > string
        "$error_gen" -error "validate_node.sh" "WN_Resource" "space" "$chdf_dir"
        exit 1
    fi
    return 0
}

function check_quotas {
    chq_dir="$1"
    chq_reqmbs=$2

    fs=`df -kP $chq_dir | awk '{if (NR==2) print $1}'`
    myquotastr=`quota 2>/dev/null | awk '{if (NR>2) {if (NF==1) {n=$1; getline; print n " " $2-$1} else {print $1 " " $3-$2}}}' |grep $fs`
    if [ $? -eq 0 ]; then
        # check only if there are any quotas, else ignore
        myquota=`echo $myquotastr|awk '{print $2}'`
        let "blocks=$chdf_reqmbs * 1024 * 2"
        if [ $myquota -lt $blocks ]; then
            #echo "Quota on '$chdf_dir' too small." 1>&2
            #echo "At least $chdf_reqmbs MBs required, found $myquota blocks" 1>&2
            STR="			Quota on '$chdf_dir' too small.\n"
            STR=$STR"			At least $chdf_reqmbs MBs required, found $myquota blocks"
            echo -e $STR > string
            "$error_gen" -error "validate_node.sh" "WN_Resource" "space" "$chdf_dir"
            exit 1
        fi
    fi

    return 0
}

############################################################
#
# Main
#
############################################################
glidein_config=$1
tmp_fname=${glidein_config}.$$.tmp

error_gen=`grep '^ERROR_GEN_PATH ' $glidein_config | awk '{print $2}'`

# Assume all functions exit on error
config_file=$1

#
# Check space on current directory
#
reqgbs=`grep -i "^MIN_DISK_GBS " $config_file | awk '{print $2}'`
if [ -n "$reqgbs" ]; then
 # can only check if defined
 let "reqmbs=$reqgbs * 1024"

 check_df . $reqmbs

 reqquotas=`grep -i "^CHECK_QUOTA " $config_file | awk '{print $2}'`
 if [ "$reqquotas" == "1" ]; then
    check_quotas . $reqmbs
 fi
fi

#
# Check availablity of /tmp
#

# check there is at least a few megs of space free
check_df /tmp 10

# and that I can create a temo dir in it
tmp_dir=`mktemp -d "/tmp/wmsglide_XXXXXX"`
if [ $? -ne 0 ]; then
  if [ $myquota -lt $blocks ]; then
    #echo "Cannot create a dir in /tmp" 1>&2
    STR="			Cannot create a dir in /tmp"
    echo -e $STR > string
    "$error_gen" -error "validate_node.sh" "WN_Resource" "space" "/tmp/wmsglide_XXXXXX"
    exit 1
   fi
fi

rmdir $tmp_dir

