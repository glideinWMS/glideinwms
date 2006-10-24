#!/bin/bash

############################################################
#
# This script will setup the GCB parameters
#
############################################################

glidein_config=$1

# fail catastrophically on error
function append_config {
    echo "$1" >> condor_config
    if [ $? -ne 0 ]; then
	echo "Failed to to update condor_config!" 2>&1
	exit 1
    fi    
}

# return 0 if success
# return !=0  on recoverable error
# fail catastrophically on unrecoverable error
function setup_gcb {
    vg_gcb_ip=`echo "$0" | awk -F ":" '{print $1}'`
    if [ -z "$vg_gcb_ip" ]; then
	echo "GCB name is an empty string!"
	return 1
    fi
    vg_gcb_port=`echo "$0" | awk -F ":" '{print $2}'`
    if [ -z "$vg_gcb_port"]; then
	vg_gcb_port=$gcb_port
    fi

    if [ "$vg_gcb_port" -ne "$default_gcb_port" ]; then
	echo "Non standard port $vg_gcb_port (not $default_gcb_port) not supported!"
	return 1
    fi

    nc -z $vg_gcb_ip $vg_gcb_port
    ret=$?
    if [ $ret -ne 0 ]; then
	echo "Cannot talk to GCB $vg_gcb_ip:$vg_gcb_port via nc"
	return 1
    fi

    # configure Condor to use it
    # will exit drastically if fails
    # this is irreversable anyhow
    append_config "BIND_ALL_INTERFACES = true"
    append_config "NET_REMAP_ENABLE = true"
    append_config "NET_REMAP_SERVICE = GCB"
    append_config "NET_REMAP_INAGENT = $gcb_ip"

    echo "Using GCB $vg_gcb_ip:$vg_gcb_port"
    return 0
}

gcb_ip=`grep '^GCB_LIST ' $glidein_config | awk '{print $2}'`
if [ -z "$gcb_list" ]; then
    echo "No GCB_LIST found!" 2>&1
    exit 1
fi

gcb_order=`grep '^GCB_ORDER ' $glidein_config | awk '{print $2}'`
if [ -z "$gcb_order" ]; then
    gcb_order="RANDOM"
fi

default_gcb_port=65432
gcb_port=`grep '^GCB_PORT ' $glidein_config | awk '{print $2}'`
if [ -z "$gcb_port" ]; then
    gcb_port=$default_gcb_port
fi


gcb_els=`echo "$gcb_list" | awk '{split($0,g,","); nr=0; for (i in g) nr=nr+1; for (i=1; i<=nr; i=i+1) print g[i]}`

if [ "$gcb_order" == "RANDOM" ];then
    gcb_els=`echo "$gcb_els" | awk 'BEGIN{srand()}{print rand() "\t" $0}' | sort -n |awk '{print $2}'`
elif [ "$gcb_order" == "SEQ" -o "$gcb_order" == "SEQUENTIAL" ]; then
    # nothing to do, alreqdy in order
    echo > /dev/null
else
    echo "Invalid GCB_ORDER specified ($gcb_order)!" 2>&1
    exit 1
fi

gcb_configured=0
for gcb in $gcb_els; do
    msg=`setup_gcb $gcb`
    ret=$?
    if [ "$ret" -eq 0 ]; then
	echo "$msg"
	gcb_configured=1
	break
    else
	echo "$msg" 2>&1
    fi
done

if [ "$gcb_configured" -eq 0 ]; then
    echo "All GCBs failed!" 2>&1
    exit 1
fi

# setup the routing tables
gcb_port=`grep '^GCB_REMAP_ROUTE ' $glidein_config | awk '{print $2}'`
if [ -n "$gcb_remap" ]; then
    if [ -r "$gcb_remap" ]; then
	append_config "NET_REMAP_ROUTE = $PWD/$gcb_remap"
    else
	echo "GCB_REMAP_ROUTE specified ($gcb_remap) but file not found!" 2>&1
	exit 1
    fi
fi

exit 0
