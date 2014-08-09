#!/bin/bash

#
# Project:
#   glideinWMS
#
# File Version: 
#
# Description:
#   This script will setup the Collector parameters
#   when the frontend provides a list of collectors
#   The glidein will take a random one from the list
#

glidein_config=$1
tmp_fname=${glidein_config}.$$.tmp

function warn {
 echo `date` $@ 1>&2
}

# initialize random seed for awk
# should not be used twice without being incremented
let random_seed=`date +%s`+$$

function select_collector {
    local group="$1"

    # increment the random_seed, so it is always unique
    let random_seed=$random_seed+$$
    head_node_wports=`echo "$group" | awk "BEGIN{srand($random_seed)}"'{split($0,g,","); for (i in g) print rand() "\t" g[i]}' | sort -n |awk '{print $2}'|tail -1`

    # increment the random_seed, so it is always unique
    let random_seed=$random_seed+$$
    head_node=`echo "$head_node_wports" | awk "BEGIN{srand($random_seed)}"'{split($0,g,":"); if (g[2]=="") { print 0 "\t" $0} else {split(g[2],p,"-"); if (p[2]=="") {print 0 "\t" $0} else {for (i=p[1]; i<=p[2]; i++) {print rand() "\t" g[1] ":" i}}}}' | sort -n |awk '{print $2}'|tail -1`

    echo "$head_node"
}

# import add_config_line function
add_config_line_source=`grep '^ADD_CONFIG_LINE_SOURCE ' $glidein_config | awk '{print $2}'`
source $add_config_line_source

error_gen=`grep '^ERROR_GEN_PATH ' $glidein_config | awk '{print $2}'`

condor_vars_file=`grep -i "^CONDOR_VARS_FILE " $glidein_config | awk '{print $2}'`

head_nodes=`grep '^GLIDEIN_Collector ' $glidein_config | awk '{print $2}'`
if [ -z "$head_nodes" ]; then
    #echo "No GLIDEIN_Collector found!" 1>&2
    STR="No GLIDEIN_Collector found!"
    "$error_gen" -error "collector_setup.sh" "Corruption" "$STR" "attribute" "GLIDEIN_Collector"
    exit 1
fi

node_groups="`echo $head_nodes | awk '{split($0,g,";"); for (i in g) print g[i] }'`"

collector_host=""

##########################################################
# Select one randomly per group
##########################################################

for group in $node_groups
do
    # randomly select from the list of nodes and ports
    head_node=`select_collector "$group"`

    if [ "$collector_host" = "" ]; then
        collector_host=$head_node
    else
        collector_host="$collector_host,$head_node"
    fi
done

add_config_line GLIDEIN_Collector $collector_host

##########################################################
# check if it should use CCB
##########################################################
out_ccb_str="False"
use_ccb=`grep '^USE_CCB ' $glidein_config | awk '{print $2}'`
if [ "$use_ccb" == "True" -o "$use_ccb" == "TRUE" -o "$use_ccb" == "T" -o "$use_ccb" == "Yes" -o "$use_ccb" == "Y" -o "$use_ccb" == "1" ]; then
    # ok, we need to define CCB variable
    add_config_line CCB_ADDRESS $collector_host
    # and export it to Condor
    add_condor_vars_line CCB_ADDRESS C "-" "+" Y N "-"
    out_ccb_str="True"
fi

"$error_gen" -ok "collector_setup.sh" "CollectorList" "${head_nodes}" "Collector" "$collector_host" "UseCCB" "${out_ccb_str}"

exit 0
