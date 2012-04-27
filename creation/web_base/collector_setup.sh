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

# import add_config_line function
add_config_line_source=`grep '^ADD_CONFIG_LINE_SOURCE ' $glidein_config | awk '{print $2}'`
source $add_config_line_source

error_gen=`grep '^ERROR_GEN_PATH ' $glidein_config | awk '{print $2}'`

condor_vars_file=`grep -i "^CONDOR_VARS_FILE " $glidein_config | awk '{print $2}'`

head_nodes=`grep '^GLIDEIN_Collector ' $glidein_config | awk '{print $2}'`
if [ -z "$head_nodes" ]; then
    #echo "No GLIDEIN_Collector found!" 1>&2
    STR="			No GLIDEIN_Collector found!"
    echo -e $STR > string
    "$error_gen" -error "collector_setup.sh" "Corruption" "file" "$glidein_config" "attribute" "GLIDEIN_Collector"
    exit 1
fi

##########################################################
# random order
##########################################################

# randomly select from the list of nodes 
let random_seed=`date +%s`+$$
head_node_wports=`echo "$head_nodes" | awk "BEGIN{srand($random_seed)}"'{split($0,g,","); for (i in g) print rand() "\t" g[i]}' | sort -n |awk '{print $2}'|tail -1`

#randomly select from the range of ports
let random_seed=`date +%s`+$$'*'2 
head_node=`echo "$head_node_wports" | awk "BEGIN{srand($random_seed)}"'{split($0,g,":"); if (g[2]=="") { print 0 "\t" $0} else {split(g[2],p,"-"); if (p[2]=="") {print 0 "\t" $0} else {for (i=p[1]; i<=p[2]; i++) {print rand() "\t" g[1] ":" i}}}}' | sort -n |awk '{print $2}'|tail -1`


add_config_line GLIDEIN_Collector $head_node

##########################################################
# check if it should use CCB
##########################################################
use_ccb=`grep '^USE_CCB ' $glidein_config | awk '{print $2}'`
if [ "$use_ccb" == "True" -o "$use_ccb" == "TRUE" -o "$use_ccb" == "T" -o "$use_ccb" == "Yes" -o "$use_ccb" == "Y" -o "$use_ccb" == "1" ]; then
  # ok, we need to define CCB variable
  add_config_line CCB_ADDRESS $head_node
  # and export it to Condor
  add_condor_vars_line CCB_ADDRESS C "-" "+" Y N "-"
fi

"$error_gen" -ok "collector_setup.sh" "Collector" "$head_nodes"

exit 0
