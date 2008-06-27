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

###################################
# Add a line to the config file
function add_config_line {
    id=$1

    rm -f $tmp_fname #just in case one was there
    mv $glidein_config $tmp_fname
    if [ $? -ne 0 ]; then
        warn "Error renaming $glidein_config into $tmp_fname"
        exit 1
    fi
    grep -v "^$id " $tmp_fname > $glidein_config
    echo "$@" >> $glidein_config
    rm -f $tmp_fname
}


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
