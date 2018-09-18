#!/bin/bash

#
# Project:
#   glideinWMS
#
# File Version: 
#
# Description:
#   This script will setup the Collector parameters

glidein_config=$1
tmp_fname=${glidein_config}.$$.tmp

# import add_config_line function
add_config_line_source=`grep '^ADD_CONFIG_LINE_SOURCE ' $glidein_config | awk '{print $2}'`
source $add_config_line_source

error_gen=`grep '^ERROR_GEN_PATH ' $glidein_config | awk '{print $2}'`

condor_vars_file=`grep -i "^CONDOR_VARS_FILE " $glidein_config | awk '{print $2}'`

collector_host="`grep -i "^GLIDEIN_Collector " $glidein_config | awk '{$1=""; print $0}'`"
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

ccb_host="`grep -i "^GLIDEIN_CCB " $glidein_config | awk '{$1=""; print $0}'`"
if [ -z "ccb_host" ]; then
    echo "No GLIDEIN_CCB found (using collectors)!" 1>&2
else
    # add a last shuffle to change the order between groups
    add_config_line GLIDEIN_CCB $ccb_host
fi


factory_collector_host="`grep -i "^GLIDEIN_Factory_Collector " $glidein_config | awk '{$1=""; print $0}'`"
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