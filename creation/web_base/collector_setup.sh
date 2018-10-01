#!/bin/bash

#
# Project:
#   glideinWMS
#
# File Version: 
#
# Description:
#   This script will setup the Collector and CCB parameters
#   when the frontend provides a list of collectors
#   The glidein will take a random one from the list
#

glidein_config="$1"
tmp_fname="${glidein_config}.$$.tmp"

function warn {
 echo `date` $@ 1>&2
}

# initialize random seed for awk
# should not be used twice without being incremented
let random_seed=`date +%s`+$$


function replace_range {
    # The input is a valid collector address (only host:port or full sinful string)
    # that can contain a port range or a range in the sock names
    # The output replaces ranges N1-N2 with $RANDOM_INTEGER(N1,N2)
    # The Frontend is verifying the correctnes when checking the configuration
    echo "$(echo "$1" | sed -E 's;^([^?:]+):([0-9]+)-([0-9]+);\1:\$RANDOM_INTEGER(\2,\3);;s;^([^?\-]+)\?(.*&)*sock=([^&\-]*[^0-9&]+)([0-9]+)-([0-9]+)(&.*)*$;\1?\2sock=\3\$RANDOM_INTEGER(\4,\5)\6;')"
}

function select_collector {
    # choose one element at random from the comma separated list
    # if one element has not ? and is of the form MY_ID:START-END, the element is expanded assuming that START and END
    # are integers and you want the range between them MY_ID:START,MY_ID:START+1,... MY_ID:END
    local group="$1"

    # select one element from the csv list
    let random_seed=$random_seed+$$  # increment the random_seed, so it is always unique
    head_node_wports=`echo "$group" | awk "BEGIN{srand($random_seed)}"'{split($0,g,","); for (i in g) print rand() "\t" g[i]}' | sort -n |awk '{print $2}'|tail -1`

    # select one element from the port range using replace_range
    # old version, explicit expansion working only for port range - let random_seed=$random_seed+$$; head_node=`echo "$head_node_wports" | awk "BEGIN{srand($random_seed)}"'{split($0,g,":"); if (g[2]=="" || index($0, "?") != 0) { print 0 "\t" $0} else {split(g[2],p,"-"); if (p[2]=="") {print 0 "\t" $0} else {for (i=p[1]; i<=p[2]; i++) {print rand() "\t" g[1] ":" i}}}}' | sort -n |awk '{print $2}'|tail -1`
    echo "$(replace_range "$head_node_wports")"
}

function parse_and_select_collectors {
    # In:
    #   $glidein_config, global variable w/ the configuration file name
    #   $1 - key to get a value from glidein_config (e.g. GLIDEIN_Collector, ...)
    # The value is a semicolon(;) separated list of comma(,) separated lists
    # Out:
    #   The output is a comma separated list with one element for each csv list separated by semicolon.
    #   The element is choosen at random between the elements of the comma separated list, using select_collector.
    #   The output cardinality is the # of semicolon separated lists in input.
    #   output is '' if no key is fount in glidein_config
    # Used for both User collectors and CCBs
    local inattr="$1"

    local inlist="$(grep "^$inattr " "$glidein_config" | cut -d ' ' -f 2-)"
    [ -z "$inlist" ] && return 0

    # Split the groups
    # local ingroups="`echo "$inlist" | awk '{split($0,g,";"); for (i in g) print g[i] }'`"
    local was_ifs="$IFS"
    IFS=\;
    local -a ingroups=($(echo "${inlist}"))
    IFS="$was_ifs"

    local outlist=""

    # Select one element randomly per group
    local lgroup
    local lcoll
    for lgroup in "${ingroups[@]}"  # loop protecting also spaces
    do
        # randomly select from the list and let HTCondor pick from port ranges
        lcoll="`select_collector "$lgroup"`"

        if [ -z "$outlist" ]; then
          outlist="$lcoll"
        else
          outlist="$outlist,$lcoll"
        fi
    done

    # The output is a comma separated list, but commas are also in the HTC macro $RANDOM_INTEGER(A,B)
    # Pay attention when handling it!
    echo "$outlist"
}

#TODO: probably not used, can be removed after checking w/ HTC team
#TODO: if shuffle is needed, make sure that , in RANDOM_INTEGER(A,B) is not interfering, maybe replace after shuffle?
#      e.g add shuffle option in parse_and_select_collectors
function csv_shuffle {
    # using shuf: outlist="`echo "$inlist," | sed -r 's/(.[^,]*,)/ \1 /g' | tr " " "\n" | shuf | tr -d "\n" | sed -r 's/,+/,/g'`"

    local inlist="$1"

    local outlist="`echo "$inlist," | sed -r 's/(.[^,]*,)/ \1 /g' | tr " " "\n" | while IFS= read -r line
do
    printf "%06d %s\n" $RANDOM "$line"
done | sort -n | cut -c8- | tr -d "\n" | sed -r 's/,+/,/g'`"

    echo ${outlist%,}
}


# import add_config_line function
add_config_line_source="$(grep '^ADD_CONFIG_LINE_SOURCE ' "$glidein_config" | cut -d ' ' -f 2-)"
source "$add_config_line_source"

error_gen="$(grep '^ERROR_GEN_PATH ' "$glidein_config" | cut -d ' ' -f 2-)"

condor_vars_file="$(grep -i "^CONDOR_VARS_FILE " "$glidein_config" | cut -d ' ' -f 2-)"

collector_host="$(parse_and_select_collectors GLIDEIN_Collector)"
if [ -z "$collector_host" ]; then
    #echo "No GLIDEIN_Collector found!" 1>&2
    STR="No GLIDEIN_Collector found!"
    "$error_gen" -error "collector_setup.sh" "Corruption" "$STR" "attribute" "GLIDEIN_Collector"
    exit 1
fi
add_config_line GLIDEIN_Collector "$collector_host"

# If $CONDORCE_COLLECTOR_HOST is set in the glidein's environment, site
# wants to have some visibility into the glidein. Add to COLLECTOR_HOST
if [ -n "$CONDORCE_COLLECTOR_HOST" ]; then
    add_config_line GLIDEIN_Site_Collector "$CONDORCE_COLLECTOR_HOST"
fi

ccb_host="$(parse_and_select_collectors GLIDEIN_CCB)"
if [ -z "ccb_host" ]; then
    echo "No GLIDEIN_CCB found (will use collectors if CCB is enabled)!" 1>&2
    # This is taken care in setup_network.sh
else
    # No need to shuffle the CCBs. HTC connects to all the given CCBs servers and include all
    # of them in its sinful string. When other daemon tries to contact that daemon, it will try
    # the CCB servers in ranmdom order until it gets a successful connection.
    # add a last shuffle to change the order between groups
    # add_config_line GLIDEIN_CCB "`csv_shuffle $ccb_host`"
    add_config_line GLIDEIN_CCB "$ccb_host"
fi


factory_collector_host="$(parse_and_select_collectors GLIDEIN_Factory_Collector)"
if [ -z "$factory_collector_host" ]; then
    # no factory collector, master will use the standard collector list
    master_collector_host="$collector_host"
else
    # factory has a collector, add it to the master collector list 
    master_collector_host="$collector_host,$factory_collector_host"
    add_config_line GLIDEIN_Factory_Collector "$factory_collector_host"
fi
add_config_line GLIDEIN_Master_Collector "$master_collector_host"

"$error_gen" -ok "collector_setup.sh" "Collector" "$collector_host" "MasterCollector" "$master_collector_host"

exit 0
