#!/bin/bash

############################################################
#
# This script will setup the Collector parameters
# when the frontend provides a list of collectors
# The glidein will take a random one from the list
#
############################################################

glidein_config=$1
tmp_fname=${glidein_config}.$$.tmp

function warn {
 echo `date` $@
}

# import add_config_line function
add_config_line_source=`grep '^ADD_CONFIG_LINE_SOURCE ' $glidein_config | awk '{print $2}'`
source $add_config_line_source

head_nodes=`grep '^GLIDEIN_Collector ' $glidein_config | awk '{print $2}'`
if [ -z "$head_nodes" ]; then
    echo "No GLIDEIN_Collector found!" 1>&2
    exit 1
fi

##########################################################
# random order
##########################################################
head_node=`echo "$head_nodes" | awk 'BEGIN{srand()}{split($0,g,","); for (i in g) print rand() "\t" g[i]}' | sort -n |awk '{print $2}'|tail -1`

add_config_line GLIDEIN_Collector $head_node

exit 0
