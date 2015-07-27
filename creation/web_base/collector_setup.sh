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

# TODO: REMOVE THIS THIS export USED FOR TESTING
export CONDORCE_COLLECTOR_HOST="fermicloud102.fnal.gov"

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

function parse_and_select_collectors {
    local inattr="$1"

    local inlist=`grep "^$inattr " $glidein_config | awk '{print $2}'`
    if [ -z "$inlist" ]; then
        echo ""
        return 0
    fi
    
    local ingroups="`echo $inlist | awk '{split($0,g,";"); for (i in g) print g[i] }'`"

    local outlist=""

    ##########################################################
    # Select one randomly per group
    ##########################################################

    local lgroup
    for lgroup in $ingroups
      do
      # randomly select from the list of nodes and ports
      local lcoll=`select_collector "$lgroup"`
      
      if [ "$outlist" = "" ]; then
          outlist=$lcoll
      else
          outlist="$outlist,$lcoll"
      fi
    done

    echo "$outlist"
}

function csv_shuffle {
    # using shuf: outlist="`echo "$inlist," | sed -r 's/(.[^,]*,)/ \1 /g' | tr " " "\n" | shuf | tr -d "\n" | sed -r 's/,+/,/g'`"
    
    local inlist="$1"

    local outlist="`echo "$inlist" | sed -r 's/(.[^,]*,)/ \1 /g' | tr " " "\n" | while IFS= read -r line
do
    printf "%06d %s\n" $RANDOM "$line"
done | sort -n | cut -c8- | tr -d "\n" | sed -r 's/,+/,/g'`"

    echo ${outlist}
}

function csv_expand_and_shuffle {
    # expand port ranges and shuffle all the elements
    local inlist="$1"

    # increment the random_seed, so it is always unique
    let random_seed=$random_seed+$$
    outlist="`echo "$inlist" | awk "BEGIN{srand($random_seed)}"'{split($0,g,","); for (i in g) print  g[i]}' | awk "BEGIN{srand($random_seed)}"'{split($0,g,":"); if (g[2]=="") { print rand() "\t" $0} else {split(g[2],p,"-"); if (p[2]=="") {print rand() "\t" $0} else {for (i=p[1]; i<=p[2]; i++) {print rand() "\t" g[1] ":" i}}}}' | sort -n |awk '{print $2}'| tr "\n" "," | sed "s;^,*;;" | sed "s;,*$;;"`"

    echo "${outlist}"
}

function parse_and_shuffle_ccbs {
    local inattr="$1"

    local inlist="`grep "^$inattr " $glidein_config | awk '{print $2}'`"
    if [ -z "$inlist" ]; then
        echo ""
        return 0
    fi
    
    local outlist="`csv_expand_and_shuffle "$inlist,"`"

    echo "${outlist}"
}

# import add_config_line function
add_config_line_source=`grep '^ADD_CONFIG_LINE_SOURCE ' $glidein_config | awk '{print $2}'`
source $add_config_line_source

error_gen=`grep '^ERROR_GEN_PATH ' $glidein_config | awk '{print $2}'`

condor_vars_file=`grep -i "^CONDOR_VARS_FILE " $glidein_config | awk '{print $2}'`

collector_host="`parse_and_select_collectors GLIDEIN_Collector`"
if [ -z "$collector_host" ]; then
    #echo "No GLIDEIN_Collector found!" 1>&2
    STR="No GLIDEIN_Collector found!"
    "$error_gen" -error "collector_setup.sh" "Corruption" "$STR" "attribute" "GLIDEIN_Collector"
    exit 1
fi

# If $CONDORCE_COLLECTOR_HOST is set in the glidein's environment, site
# wants to have some visibility into the glidein. Add to COLLECTOR_HOST
if [ -n "$CONDORCE_COLLECTOR_HOST" ]; then
    add_config_line GLIDEIN_Site_Collector $CONDORCE_COLLECTOR_HOST
fi

add_config_line GLIDEIN_Collector $collector_host

ccb_host="`parse_and_shuffle_ccbs GLIDEIN_CCB`"
if [ -z "ccb_host" ]; then
    echo "No GLIDEIN_CCB found (use collectors)!" 1>&2
    #STR="No GLIDEIN_CCB found!"
    #"$error_gen" -ok "collector_setup.sh" "Corruption" "$STR" "attribute" "GLIDEIN_Collector"
else
    add_config_line GLIDEIN_CCB $ccb_host
fi



factory_collector_host="`parse_and_select_collectors GLIDEIN_Factory_Collector`"
if [ -z "$factory_collector_host" ]; then
    # no factory collector, master will use the standard collector list
    master_collector_host="$collector_host"
else
    # factory has a collector, add it to the master collector list 
    master_collector_host="$collector_host,$factory_collector_host"
    add_config_line GLIDEIN_Factory_Collector $factory_collector_host
fi
add_config_line GLIDEIN_Master_Collector $master_collector_host

"$error_gen" -ok "collector_setup.sh" "Collector" "$collector_host" "MasterCollector" "$master_collector_host"

exit 0
