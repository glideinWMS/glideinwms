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

glidein_config=$1
tmp_fname=${glidein_config}.$$.tmp

function warn {
 echo `date` $@ 1>&2
}

# import add_config_line function
add_config_line_source=`grep '^ADD_CONFIG_LINE_SOURCE ' $glidein_config | awk '{print $2}'`
source $add_config_line_source

error_gen=`grep '^ERROR_GEN_PATH ' $glidein_config | awk '{print $2}'`

condor_vars_file=`grep -i "^CONDOR_VARS_FILE " $glidein_config | awk '{print $2}'`

slots_layout=`grep '^SLOTS_LAYOUT ' $glidein_config | awk '{print $2}'`
if [ "X$slots_layout" = "Xpartitionable" ]; then
  # only need to worry about the partitionable use case
  num_cpus=`grep '^GLIDEIN_CPUS ' $glidein_config | awk '{print $2}'`
  if [ -z "$num_cpus" ]; then
   # the default is single core
    num_cpus=1
  fi

  if [ "$num_cpus" == "1" ]; then
    # do not want single core partitionable slots

    force_part=`grep '^FORCE_PARTITIONABLE ' $glidein_config | awk '{print $2}'`
    if [ "X$force_part" = "XTrue" ]; then
      # unless forced to
      "$error_gen" -ok "smart_partitionable.sh" "Action" "ForcedSinglePartitionable"
    else
      add_config_line SLOTS_LAYOUT fixed
      "$error_gen" -ok "smart_partitionable.sh" "Action" "SwitchSingleToFixed" 
    fi
  else
    "$error_gen" -ok "smart_partitionable.sh" "Action" "None"
  fi
else
  "$error_gen" -ok "smart_partitionable.sh" "Action" "None"
fi

exit 0

