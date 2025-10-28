#!/bin/bash

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

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

glidein_config="$1"
# is tmp_fname used? to remove?
tmp_fname="${glidein_config}.$$.tmp"

# import add_config_line and add_condor_vars_line functions
add_config_line_source=$(grep -m1 '^ADD_CONFIG_LINE_SOURCE ' "$glidein_config" | cut -d ' ' -f 2-)
# shellcheck source=./add_config_line.source
. "$add_config_line_source"

error_gen=$(gconfig_get ERROR_GEN_PATH "$glidein_config")

condor_vars_file=$(gconfig_get CONDOR_VARS_FILE "$glidein_config")

# Use GLIDEIN_CPUS if configured by the factory
GLIDEIN_CPUS=$(gconfig_get GLIDEIN_CPUS "$glidein_config")
GLIDEIN_OVERLOAD_CPUS=$(gconfig_get GLIDEIN_OVERLOAD_CPUS "$glidein_config")
GLIDEIN_OVERLOAD_ENABLED=$(gconfig_get GLIDEIN_OVERLOAD_ENABLED "$glidein_config")

# 3.2.16 Meaning of "auto" changed from "node" to "slot"
# node and 0 mean the same thing - detect the hardware resources
# auto, slot and -1 mean the same thing - detect the slot resources
if (echo "${GLIDEIN_CPUS}" | grep -i "auto") >/dev/null 2>&1; then
    GLIDEIN_CPUS=-1
elif (echo "${GLIDEIN_CPUS}" | grep -i "node") >/dev/null 2>&1; then
    GLIDEIN_CPUS=0
elif (echo "${GLIDEIN_CPUS}" | grep -i "slot") >/dev/null 2>&1; then
    GLIDEIN_CPUS=-1
fi

glidein_cpus_how=

# Suggested by G.Thain:
# _CONDOR_MACHINE_AD is a file containing the whole machine ClassAd. Cpus are the cores in the machine
function detect_cpus_htcondor {
    if [ -r "$_CONDOR_MACHINE_AD" ]; then
       cores=`condor_status -ads "$_CONDOR_MACHINE_AD" -af Cpus 2>/dev/null`
       [ "$cores" = "" ] && cores=`egrep "^Cpus " "$_CONDOR_MACHINE_AD" | awk '{print $3}'`
    fi
    [ "$cores" = "" ] && return 1
    return 0
}

# Alt. to verify, using PBS_NODEFILE (incomplete, multinode jobs!)
# http://stackoverflow.com/questions/17804614/determine-total-cpu-count-after-qsub-within-pbs-script
# NP=$(wc -l $PBS_NODEFILE | awk '{print $1}')
#
# https://wiki.hpcc.msu.edu/display/hpccdocs/Advanced+Scripting+Using+PBS+Environment+Variables
# PBS_NUM_PPN
#
# Use the bigger number (and flag a warning if are different) between:
#  PBS_NUM_PPN
#  the occurrences of the host in PBS_NODEFILE
#  and PBS_NP if PBS_NUM_NODES=1
# This will compensate for misconfiguration and is OK to be optimistic

function detect_cpus_pbs {
    cores=$PBS_NUM_PPN
    different_values=no
    if [ "$PBS_NUM_NODES" = "1" ] && [ -n "$PBS_NP" ]; then
        if [ "$cores" = "" ]; then
            cores=$PBS_NP
        else
            [ "$PBS_NP" -gt "$cores" ] && cores=$PBS_NP
            [ "$PBS_NP" -ne "$cores" ] && different_values=yes
        fi
    fi
    if [ -r "$PBS_NODEFILE" ]; then
        cores_file=$(grep -c "$(hostname -s)" "$PBS_NODEFILE")
        if [ "$cores" = "" ]; then
            cores=$cores_file
        else
            [ "$cores_file" -gt "$cores" ] && cores=$cores_file
            [ "$cores_file" -ne "$cores" ] && different_values=yes
        fi
    fi
    [ "$cores" = "" ] && return 1
    [ $different_values = yes ] && echo "glidein_cpu_setup.sh: WARNING Different core counts in PBS (PBS_NUM_NODES:$PBS_NUM_NODES, PBS_NP:$PBS_NP, PBS_NODEFILE:$cores_file)"
    return 0
}

# https://www-01.ibm.com/support/knowledgecenter/SSETD4_9.1.3/lsf_config_ref/lsf_envars_job_exec.dita
# e.g.  LSB_MCPU_HOSTS=hequ0190 2 fell0247 2
function detect_cpus_lsf {
    local host_info="`hostname -s`"
    if [ -n "$LSB_MCPU_HOSTS" ]; then
        array=(${LSB_MCPU_HOSTS})
        for i in "${!array[@]}"; do
            if [[ ${array[i]} =~ ${host_info}* ]]; then
                let 'i += 1'
                cores=${array[i]}
                return 0
            fi
        done
    fi
    return 1
}

# https://computing.llnl.gov/linux/slurm/mc_support.html
# http://www.accre.vanderbilt.edu/?page_id=2154#envvariables
function detect_cpus_slurm {
    cores=$SLURM_CPUS_PER_NODE
    [ "$cores" = "" ] && return 1
    return 0
}

function detect_cpus_sge {
    # no method for SGE
    return 1
}

function detect_slot_cpus {
    # LRM selector
    # 1. if present is a name of a LRM, otherwise they are tried in order
    # each function exit w/ 0 if cores are found and values is stored in "cores"
    # glidein_cpus_how is set as well
    cores=
    if [ -n "$1" ]; then
        case $1 in
            "htcondor"|"condor")
                detect_cpus_htcondor;;
            "pbs")
                detect_cpus_pbs;;
            "slurm")
                detect_cpus_slurm;;
            "lsf")
                detect_cpus_lsf;;
            "sge")
                detect_cpus_sge;;
            *)
                pass;;
        esac
        ec=$?
        if [ $ec -eq 0 ]; then
            glidein_cpus_how="(slot cpus - $1)"
            return 0
        fi
    else
        local lrm_fun
        for lrm_fun in detect_cpus_htcondor detect_cpus_pbs detect_cpus_slurm detect_cpus_lsf detect_cpus_sge; do
            $lrm_fun
            if [ $? -eq 0 ]; then
                glidein_cpus_how="(slot cpus - $lrm_fun)"
                return 0
            fi
        done
    fi
    return 1
}

function setup_overload {
   local should_enable_overload=false

    if [[ -n "$GLIDEIN_OVERLOAD_ENABLED" ]]; then
        local value="${GLIDEIN_OVERLOAD_ENABLED,,}"  # Normalize to lowercase

        if [[ "$value" == "true" ]]; then
            should_enable_overload=true
        elif [[ "$value" == "false" ]]; then
            should_enable_overload=false
        elif [[ "$value" =~ ^([0-9]{1,3})%$ ]]; then
            local percent="${BASH_REMATCH[1]}"
            if (( percent > 0 && percent <= 100 )); then
                local rand=$(( RANDOM % 100 + 1 ))  # 1 to 100
                if (( rand <= percent )); then
                    should_enable_overload=true
                    echo "GLIDEIN_OVERLOAD_ENABLED set to $GLIDEIN_OVERLOAD_ENABLED: random=$rand <= $percent, enabling overload."
                else
                    echo "GLIDEIN_OVERLOAD_ENABLED set to $GLIDEIN_OVERLOAD_ENABLED: random=$rand > $percent, not enabling overload."
                fi
            fi
        fi
        gconfig_add GLIDEIN_OVERLOAD_ENABLED "${should_enable_overload}"
        add_condor_vars_line GLIDEIN_OVERLOAD_ENABLED "C" "-" "+" "N" "N" "-"
    fi

    if [[ "$should_enable_overload" == "true" && -n "$GLIDEIN_OVERLOAD_CPUS" ]]; then
        echo "GLIDEIN_OVERLOAD_CPUS is set to $GLIDEIN_OVERLOAD_CPUS. Adjusting GLIDEIN_CPUS from base value $GLIDEIN_CPUS"
        # Multiply the two variables using bc
        local result
        result=$(bc <<< "scale=2; $GLIDEIN_CPUS * $GLIDEIN_OVERLOAD_CPUS")
        # Round up the result
        GLIDEIN_CPUS=$(printf "%.0f" "$result")
    fi
}

# default is 1 (was slot CPUs, -1, in 3.2.16)
if [ "X${GLIDEIN_CPUS}" = "X" ]; then
    echo "`date` GLIDEIN_CPUS not set in $glidein_config. Setting to default of 1."
    GLIDEIN_CPUS="1"
fi

# detect the number of cores made available to the slot
if [ "${GLIDEIN_CPUS}" = "-1" ]; then
    # this works in HTCondor, PBS, SLURM, LSF for now
    # this function sets "cores" and "glidein_cpus_how"
    detect_slot_cpus
    # fall back to auto (node) if unable to detect
    if [ "$cores" = "" ]; then
       GLIDEIN_CPUS=0
    else
       GLIDEIN_CPUS="$cores"
    fi
fi

if [ "${GLIDEIN_CPUS}" = "0" ]; then
    # detect the number of (physical) cores on the node
    core_proc=`awk -F: '/^physical/ && !ID[$2] { P++; ID[$2]=1 }; /^physical/ { N++ };  END { print N, P }' /proc/cpuinfo`
    cores=`echo "$core_proc" | awk -F' ' '{print $1}'`
    if [ "$cores" = "" ]; then
        # Old style, no multiple cores or hyperthreading
        cores=`grep processor /proc/cpuinfo  | wc -l`
    fi
    GLIDEIN_CPUS="$cores"
    glidein_cpus_how="(host cpus)"
fi

setup_overload

# export the GLIDEIN_CPUS
echo "`date` Setting GLIDEIN_CPUS=$GLIDEIN_CPUS $glidein_cpus_how"

gconfig_add GLIDEIN_CPUS "${GLIDEIN_CPUS}"
add_condor_vars_line GLIDEIN_CPUS "C" "-" "+" "N" "N" "-"

"$error_gen" -ok "glidein_cpu_setup.sh" "GLIDEIN_CPUS" "${GLIDEIN_CPUS}"
exit 0
