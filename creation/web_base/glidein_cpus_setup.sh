#!/bin/bash

#
# Project:
#   glideinWMS
#
# File Version: 
#
# Description:
#   This script will determine the number of cpus on a machine if
#   GLIDEIN_CPUS is set to 'auto' ('node') or 'slot'
#

glidein_config=$1
tmp_fname=${glidein_config}.$$.tmp

error_gen=`grep '^ERROR_GEN_PATH ' $glidein_config | awk '{print $2}'`

condor_vars_file=`grep -i "^CONDOR_VARS_FILE " $glidein_config | awk '{print $2}'`

# import add_config_line and add_condor_vars_line functions
add_config_line_source=`grep '^ADD_CONFIG_LINE_SOURCE ' $glidein_config | awk '{print $2}'`
source $add_config_line_source

# Use GLIDEIN_CPUS if configured by the factory
GLIDEIN_CPUS=`grep -i "^GLIDEIN_CPUS " $glidein_config | awk '{print $2}'`

# auto, node and 0 mean the same thing - detect the hardware resources
# slot and -1 mean the same thing - detect the slot resources
if (echo "${GLIDEIN_CPUS}" | grep -i "auto") >/dev/null 2>&1; then
    GLIDEIN_CPUS=0
elif (echo "${GLIDEIN_CPUS}" | grep -i "node") >/dev/null 2>&1; then
    GLIDEIN_CPUS=0
elif (echo "${GLIDEIN_CPUS}" | grep -i "slot") >/dev/null 2>&1; then
    GLIDEIN_CPUS=-1
fi

glidein_cpus_how=

# detect the number of cores made available to the slot 
if [ "${GLIDEIN_CPUS}" = "-1" ]; then
    # this works in HTCondor for now
    if [ -r "$_CONDOR_MACHINE_AD" ]; then
       cores=`condor_status -ads pp1 -af Cpus 2>/dev/null`
       [ "$cores" = "" ] && cores=`egrep "^Cpus " $_CONDOR_MACHINE_AD | awk '{print $3}'`
    fi
    # fall back to auto (node) if unable to detect
    if [ "$cores" = "" ]; then
       GLIDEIN_CPUS=0
    else
       GLIDEIN_CPUS="$cores"
       glidein_cpus_how="(HTCondor slot cpus)"
    fi
fi

if [ "X${GLIDEIN_CPUS}" = "X" ]; then
    echo "`date` GLIDEIN_CPUS not set in $glidein_config. Setting to default of 1."
    GLIDEIN_CPUS="1"
elif [ "${GLIDEIN_CPUS}" = "0" ]; then
    # detect the number of cores
    core_proc=`awk -F: '/^physical/ && !ID[$2] { P++; ID[$2]=1 }; /^physical/ { N++ };  END { print N, P }' /proc/cpuinfo`
    cores=`echo "$core_proc" | awk -F' ' '{print $1}'`
    if [ "$cores" = "" ]; then
        # Old style, no multiple cores or hyperthreading
        cores=`grep processor /proc/cpuinfo  | wc -l`
    fi
    GLIDEIN_CPUS="$cores"
    glidein_cpus_how="(host cpus)"
fi

# xxport the GLIDEIN_CPUS
echo "`date` Setting GLIDEIN_CPUS=$GLIDEIN_CPUS $glidein_cpus_how"

add_config_line GLIDEIN_CPUS "${GLIDEIN_CPUS}"
add_condor_vars_line GLIDEIN_CPUS "C" "-" "+" "N" "N" "-"

"$error_gen" -ok "glidein_cpu_setup.sh" "GLIDEIN_CPUS" "${GLIDEIN_CPUS}"
exit 0

