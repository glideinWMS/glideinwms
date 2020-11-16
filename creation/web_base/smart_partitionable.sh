#!/bin/bash

#
# Project:
#   glideinWMS
#
# Description:
#   This script will make sure single core glidein
#   do not use partitionable slots
#   unless the user insists on it
#

glidein_config="$1"
tmp_fname="${glidein_config}.$$.tmp"

function warn {
 echo `date` "$@" 1>&2
}

# import add_config_line function
add_config_line_source="`grep '^ADD_CONFIG_LINE_SOURCE ' "$glidein_config" | cut -d ' ' -f 2-`"
source "$add_config_line_source"

error_gen="`grep '^ERROR_GEN_PATH ' "$glidein_config" | cut -d ' ' -f 2-`"

# not used - to remove
# condor_vars_file="`grep -i "^CONDOR_VARS_FILE " "$glidein_config" | cut -d ' ' -f 2-`"

slots_layout=`grep '^SLOTS_LAYOUT ' "$glidein_config" | cut -d ' ' -f 2-`
# fixed slot layout with resources added to the main slot can cause the startd to fail
# if the number of resources is insufficient for the available slots
# mainextra adds extra virtual cpus for the resource, so it is sure to fail with fixed slots
condor_config_resource_slots="`grep -i "^GLIDEIN_Resource_Slots " "$glidein_config" | cut -d ' ' -f 2-`"
echo "$condor_config_resource_slots" | grep mainextra > /dev/null
if [[ "$?" -eq 0 ]]; then
  # sure error with fixed: force partitionable
  RES_SLOT=mainextra
else
  echo "$condor_config_resource_slots" | grep main > /dev/null
  if [[ "$?" -eq 0 ]]; then
    # possible error with fixed: do nothing or warn
    RES_SLOT=main
  fi
fi

# Logic of next section:
# 1. If GLIDEIN_CPUS==1 or not defined and not FORCE_PARTITIONABLE and no mainextra ResourceSlot is defined,
# then switch partitionable to fixed
# 2. If mainextra ResourceSlot is defined then switch fixed to partitionable
if [[ "X$slots_layout" = "Xpartitionable" ]]; then
  # only need to worry about the partitionable use case
  num_cpus=`grep '^GLIDEIN_CPUS ' "$glidein_config" | cut -d ' ' -f 2-`
  if [[ -z "$num_cpus" ]]; then
    # the default is single core
    # there could be virtual cpus (mainextra) or more real CPUs (due to RSL request) both not in GLIDEIN_CPUS
    num_cpus=1
  fi

  if [[ "$num_cpus" -eq 1 ]]; then
    # matches 1, 01, ... no match for other numbers or string values (AUTO, ...)
    # do not want single core partitionable slots

    force_part=`grep '^FORCE_PARTITIONABLE ' "$glidein_config" | cut -d ' ' -f 2-`
    if [[ "X$force_part" = "XTrue" ]]; then
      # unless forced to
      "$error_gen" -ok "smart_partitionable.sh" "Action" "ForcedSinglePartitionable"
    elif [[ "X$RES_SLOT" = "Xmainextra" ]]; then
      # unless resource slot have mainextra type
      "$error_gen" -ok "smart_partitionable.sh" "Action" "ResourceSlotKeptPartitionable"
    else
      add_config_line SLOTS_LAYOUT fixed
      "$error_gen" -ok "smart_partitionable.sh" "Action" "SwitchSingleToFixed" 
    fi
  else
    # GLIDEIN_CPUS>1 or 0 (auto-node) or -1 (auto-slot)
    "$error_gen" -ok "smart_partitionable.sh" "Action" "None"
  fi
else
    if [[ "X$RES_SLOT" = "Xmainextra" ]]; then
      # do not want fixed with mainextra resource slots (sure problem)
      add_config_line SLOTS_LAYOUT partitionable
      "$error_gen" -ok "smart_partitionable.sh" "Action" "SwitchResourceSlotToPartitionable"
    elif [[ "X$RES_SLOT" = "Xmain" ]] && [[ "$num_cpus" > "1" ||  "$num_cpus" -gt "1" ]]; then
      # do not want fixed with main resource slots and more than one CPU (possible problem)
      # if the number of resources is insufficient for the available slots
      # NOTE: $num_cpus can be a string AUTO, SLOT, NODE or a number. 
      # - "$num_cpus" > "1" catches strings and numbers w/o prefixes
      # -  "$num_cpus" -gt "1" catches numbers with prefixed 0s, e.g. 03 -gt 1
      # conditions are separated to be safer and more clear:
      #  tests show precedence left to right, but documentation no: https://www.tldp.org/LDP/abs/html/opprecedence.html
      add_config_line SLOTS_LAYOUT partitionable
      "$error_gen" -ok "smart_partitionable.sh" "Action" "SwitchResourceSlotToPartitionable"
    else
      "$error_gen" -ok "smart_partitionable.sh" "Action" "None"
    fi
fi

exit 0

