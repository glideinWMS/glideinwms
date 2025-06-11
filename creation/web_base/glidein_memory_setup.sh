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
#   This script will setup the memory available to the glidein
#

glidein_config="$1"
tmp_fname="${glidein_config}.$$.tmp"

# import add_config_line and add_condor_vars_line functions
add_config_line_source=$(grep -m1 '^ADD_CONFIG_LINE_SOURCE ' "$glidein_config" | cut -d ' ' -f 2-)
# shellcheck source=./add_config_line.source
. "$add_config_line_source"

error_gen=$(gconfig_get ERROR_GEN_PATH "$glidein_config")

condor_vars_file=$(gconfig_get CONDOR_VARS_FILE "$glidein_config")

# Use GLIDEIN_MaxMemMBs if configured by the factory
GLIDEIN_MaxMemMBs=$(gconfig_get GLIDEIN_MaxMemMBs "$glidein_config")
GLIDEIN_OVERLOAD_MEMORY=$(gconfig_get GLIDEIN_OVERLOAD_MEMORY "$glidein_config")
GLIDEIN_OVERLOAD_ENABLED=$(gconfig_get GLIDEIN_OVERLOAD_ENABLED "$glidein_config")

if [ "${GLIDEIN_MaxMemMBs}" = "" ]; then
    echo "`date` GLIDEIN_MaxMemMBs not set in $glidein_config."

    # Calculate Mem/CPU if the VO prefers an approx value
    estimate=$(gconfig_get GLIDEIN_MaxMemMBs_Estimate "$glidein_config" | tr [:lower:] [:upper:])

    if [ "$estimate" = "TRUE" ]; then
        echo "`date` Estimating Max memory based on the CPUs and total memory."

        # Figure out how much free memory is available
        mem=`free -m | grep "^Mem:" | awk '{print $2}'`

        glidein_cpus=$(gconfig_get GLIDEIN_CPUS "$glidein_config")

        if [ "$glidein_cpus" != "" ]; then
            # GLIDEIN_CPUS is set. Set Max to all the free. Let HTCondor handle the memory.
            # Also handles GLIDEIN_CPUS=0/-1, ie estimate the available cpus (auto/node/slot).
            echo "`date` Estimate: memory=$mem GLIDEIN_CPUS=$glidein_cpus mem/core controlled by HTCondor"
            GLIDEIN_MaxMemMBs=$mem
        else
            # Assume GLIDEIN_CPUS=1 and figure out the available memory/core
            core_proc=`awk -F: '/^physical/ && !ID[$2] { P++; ID[$2]=1 }; /^physical/ { N++ };  END { print N, P }' /proc/cpuinfo`
            cores=`echo "$core_proc" | awk -F' ' '{print $1}'`
            if [ "$cores" = "" ]; then
                # Old style, no multiple cores or hyperthreading
                cores=`grep processor /proc/cpuinfo  | wc -l`
            fi

            GLIDEIN_MaxMemMBs=`echo "$mem / $cores" | bc`

            echo "`date` Estimate: memory=$mem cores=$cores mem/core=$GLIDEIN_MaxMemMBs"
        fi

        if [[ -z "$GLIDEIN_MaxMemMBs" || "$GLIDEIN_MaxMemMBs" = "0" ]]; then
            echo "`date` Error estimating mem/core. Using default memory value provided by Condor."
	    "$error_gen" -ok "glidein_memory_setup.sh" "MaxMemMBs" "default"
            exit 0
        fi

    else
        echo "`date` VO does not want to estimate mem/core. Using default memory value provided by Condor."
	"$error_gen" -ok "glidein_memory_setup.sh"  "MaxMemMBs" "default"
        exit 0
    fi
fi

function setup_overload() {
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

    if [[ "$should_enable_overload" == "true" ]]; then
        if [[ -n "$GLIDEIN_OVERLOAD_CPUS" ]]; then
            echo "GLIDEIN_OVERLOAD_CPUS is set to $GLIDEIN_OVERLOAD_CPUS. Adjusting GLIDEIN_CPUS from base value $GLIDEIN_CPUS"
            local result
            result=$(bc <<< "scale=2; $GLIDEIN_CPUS * $GLIDEIN_OVERLOAD_CPUS")
            GLIDEIN_CPUS=$(printf "%.0f" "$result")
        fi

        if [[ -n "$GLIDEIN_OVERLOAD_MEMORY" ]]; then
            echo "GLIDEIN_OVERLOAD_MEMORY is set to $GLIDEIN_OVERLOAD_MEMORY. Adjusting GLIDEIN_MaxMemMBs from base value $GLIDEIN_MaxMemMBs"
            local result
            result=$(bc <<< "scale=2; $GLIDEIN_MaxMemMBs * $GLIDEIN_OVERLOAD_MEMORY")
            GLIDEIN_MaxMemMBs=$(printf "%.0f" "$result")
        fi
    fi
}

setup_overload

# Export the GLIDEIN_MaxMemMBs
echo "`date` Setting GLIDEIN_MaxMemMBs=$GLIDEIN_MaxMemMBs"

gconfig_add MEMORY "${GLIDEIN_MaxMemMBs}"
add_condor_vars_line MEMORY "C" "-" "+" "N" "N" "-"

"$error_gen" -ok "glidein_memory_setup.sh" "MaxMemMBs" "${GLIDEIN_MaxMemMBs}"
exit 0
