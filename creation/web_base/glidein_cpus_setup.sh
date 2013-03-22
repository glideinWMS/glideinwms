#!/bin/bash

#
# Project:
#   glideinWMS
#
# File Version: 
#
# Description:
#   This script will determine the number of cpus on a machine if
#   GLIDEIN_CPUS is set to 'auto'
#

glidein_config=$1
tmp_fname=${glidein_config}.$$.tmp

error_gen=`grep '^ERROR_GEN_PATH ' $glidein_config | awk '{print $2}'`

condor_vars_file=`grep -i "^CONDOR_VARS_FILE " $glidein_config | awk '{print $2}'`

# import add_config_line and add_condor_vars_line functions
add_config_line_source=`grep '^ADD_CONFIG_LINE_SOURCE ' $glidein_config | awk '{print $2}'`
source $add_config_line_source

# Use GLIDEIN_MaxMemMBs if configured by the factory
GLIDEIN_CPUS=`grep -i "^GLIDEIN_CPUS " $glidein_config | awk '{print $2}'`

# auto and 0 means the same thing - detect
if (echo "${GLIDEIN_CPUS}" | grep -i "auto") >/dev/null 2>&1; then
    GLIDEIN_CPUS=0
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
fi

# xxport the GLIDEIN_CPUS
echo "`date` Setting GLIDEIN_CPUS=$GLIDEIN_CPUS"

add_config_line GLIDEIN_CPUS "${GLIDEIN_CPUS}"
add_condor_vars_line GLIDEIN_CPUS "C" "-" "+" "N" "N" "-"

"$error_gen" -ok "glidein_cpu_setup.sh" "GLIDEIN_CPUS" "${GLIDEIN_CPUS}"
exit 0

