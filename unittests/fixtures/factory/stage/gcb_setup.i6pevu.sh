#!/bin/bash

#
# Project:
#   glideinWMS
#
# File Version: 
#
# Description:
#   This script will setup the GCB parameters
#

glidein_config=$1

# fail catastrophically on error
function append_config {
    echo "$1" >> condor_config
    if [ $? -ne 0 ]; then
	echo "Failed to to update condor_config!" 1>&2
	exit 1
    fi    
}

# return rank (higher is better) if success
# in stdout it returns "score ip:port"
# return 0 on success, >0 on error
function check_gcb {
    vg_gcb_ip=`echo "$1" | awk -F ":" '{print $1}'`
    if [ -z "$vg_gcb_ip" ]; then
	echo "GCB name is an empty string!" 1>&2
	return 1
    fi
    vg_gcb_port=`echo "$1" | awk -F ":" '{print $2}'`
    if [ -z "$vg_gcb_port" ]; then
	vg_gcb_port=$gcb_port
    fi

    if [ "$vg_gcb_port" -ne "$default_gcb_port" ]; then
	echo "Non standard port $vg_gcb_port (not $default_gcb_port) not supported!" 1>&2
	return 2
    fi

    # check if I can connect to that port
    which nc >/dev/null 2>&1
    ret=$?
    if [ "$ret" -eq 0 ]; then
	# try only if nc does indeed exists
	nc -z -w 2 $vg_gcb_ip $vg_gcb_port  >/dev/null 2>&1
	ret=$?
	if [ $ret -ne 0 ]; then
	    echo "Cannot talk to GCB $vg_gcb_ip:$vg_gcb_port via nc" 1>&2
	    return 3
	fi
    fi

    if [ "$gcb_query_exists" -eq 1 ]; then
	restr=`$condor_dir/sbin/gcb_broker_query $vg_gcb_ip freesockets`
	ret=$?
	if [ $ret -ne 0 ]; then
	    echo "Cannot talk to GCB $vg_gcb_ip:$vg_gcb_port via gcb_broker_query" 1>&2
	    return 4
	fi
	vg_free_sockets=`echo "$restr" | awk '{print $3}'`
    else
	# set a pessimistic guess
	vg_free_sockets=1
    fi

    if [ -n "$gcb_min_free" ]; then
	if [ "$vg_free_sockets" -lt "$gcb_min_free" ]; then
	    echo "GCB $vg_gcb_ip:$vg_gcb_port has only $vg_free_sockets free, needed $gcb_min_free" 1>&2
	    return 5
	fi
    fi

    echo "$vg_free_sockets $vg_gcb_ip:$vg_gcb_port"
    return 0
}

# fail catastrophically on unrecoverable error
function setup_gcb {
    sg_gcb_ip=`echo "$1" | awk -F ":" '{print $1}'`
    sg_gcb_port=`echo "$1" | awk -F ":" '{print $2}'`

    # configure Condor to use it
    # will exit drastically if fails
    # this is irreversable anyhow
    append_config "BIND_ALL_INTERFACES = true"
    append_config "NET_REMAP_ENABLE = true"
    append_config "NET_REMAP_SERVICE = GCB"
    append_config "NET_REMAP_INAGENT = $sg_gcb_ip"

    echo "Using GCB $sg_gcb_ip:$sg_gcb_port"
    return 0
}

gcb_order=`grep '^GCB_ORDER ' $glidein_config | awk '{print $2}'`
if [ -z "$gcb_order" ]; then
    gcb_order="NONE"
fi

if [ "$gcb_order" == "NONE" ]; then
    echo "Not using GCB"
    exit 0
fi

condor_dir=`grep '^CONDOR_DIR ' $glidein_config | awk '{print $2}'`
if [ -z "$condor_dir" ]; then
    echo "No CONDOR_DIR found!" 1>&2
    exit 1
fi

gcb_query_exists=0
if [ -e "$condor_dir/sbin/gcb_broker_query" ]; then
    gcb_query_exists=1
fi

gcb_min_free=`grep '^GCB_MIN_FREE ' $glidein_config | awk '{print $2}'`
if [ -n "$gcb_min_free" ]; then
    if [ "$gcb_query_exists" -eq 0 ]; then
	echo "GCB_MIN_FREE defined, but gcb_broker_query not present." 1>&2
	exit 1
    fi
fi

gcb_list=`grep '^GCB_LIST ' $glidein_config | awk '{print $2}'`
if [ -z "$gcb_list" ]; then
    echo "No GCB_LIST found!" 1>&2
    exit 1
fi

default_gcb_port=65432
gcb_port=`grep '^GCB_PORT ' $glidein_config | awk '{print $2}'`
if [ -z "$gcb_port" ]; then
    gcb_port=$default_gcb_port
fi


if [ "$gcb_order" == "RANDOM" ];then
    ##########################################################
    # random order
    ##########################################################
    let random_seed=`date +%s`+$$
    gcb_els=`echo "$gcb_list" | awk "BEGIN{srand($random_seed)}"'{split($0,g,","); for (i in g) print rand() "\t" g[i]}' | sort -n |awk '{print $2}'`
elif [ "$gcb_order" == "RR" -o "$gcb_order" == "ROUNDROBIN" ]; then
    ##########################################################
    # round robin, based on the cluster number
    ##########################################################
    nr1=`grep '^CONDORG_CLUSTER ' $glidein_config | awk '{print $2}'`
    nr2=`grep '^CONDORG_SUBCLUSTER ' $glidein_config | awk '{print $2}'`
    let nr=$nr1+$nr2
    nr_gcb_els=`echo "$gcb_list" | awk '{split($0,g,","); nr=0; for (i in g) nr=nr+1; print nr}'`
    let start_nr=$nr%$nr_gcb_els
    gcb_els=`echo "$gcb_list" | awk "{split(\\\$0,g,\",\"); for (i=1; i<=$nr_gcb_els; i=i+1) print g[((i+$start_nr)%$nr_gcb_els)+1]}"`
elif [ "$gcb_order" == "GCBLOAD" ]; then
    ################################################################
    # will probe all of them and select the one that is less loaded
    ################################################################
    if [ "$gcb_query_exists" -eq 0 ]; then
	echo "GCB_ORDER==GCBLOAD, but gcb_broker_query not present." 1>&2
	exit 1
    fi
    # get array
    base1_gcb_els=`echo "$gcb_list" | awk '{split($0,g,","); for (i in g) print g[i]}'`
    # associate number of free slots
    base2_gcb_els=""
    for gcb in $base1_gcb_els; do
	msg=`check_gcb $gcb`
	ret=$?
	if [ "$ret" -eq 0 ]; then
	    if [ -z "$base2_gcb_els" ]; then
		base2_gcb_els="$msg"
	    else
		base2_gcb_els=`echo "$base2_gcb_els"; echo "$msg"`
	    fi
	else
	    echo "$msg" 1>&2
	fi
    done
    # sort by number of free slots
    gcb_els=`echo "$base2_gcb_els" | sort -nr | awk '{print $2}'`
elif [ "$gcb_order" == "SEQ" -o "$gcb_order" == "SEQUENTIAL" ]; then
    ##########################################################
    # sequential, first always first
    ##########################################################
    gcb_els=`echo "$gcb_list" | awk '{split($0,g,","); nr=0; for (i in g) nr=nr+1; for (i=1; i<=nr; i=i+1) print g[i]}'`
else
    echo "Invalid GCB_ORDER specified ($gcb_order)!" 1>&2
    exit 1
fi

gcb_configured=0
for gcb in $gcb_els; do
    msg=`check_gcb $gcb`
    ret=$?
    if [ "$ret" -eq 0 ]; then
	setup_gcb `echo "$msg" |awk '{print $2}'`
	echo GCB `echo "$msg" |awk '{print $2}'` has `echo "$msg" |awk '{print $1}'` "free sockets"
	gcb_configured=1
	break
    else
	echo "$msg" 1>&2
    fi
done

if [ "$gcb_configured" -eq 0 ]; then
    echo "All GCBs failed!" 1>&2
    exit 1
fi

# setup the routing tables
gcb_port=`grep '^GCB_REMAP_ROUTE ' $glidein_config | awk '{print $2}'`
if [ -n "$gcb_remap" ]; then
    if [ -r "$gcb_remap" ]; then
	append_config "NET_REMAP_ROUTE = $PWD/$gcb_remap"
    else
	echo "GCB_REMAP_ROUTE specified ($gcb_remap) but file not found!" 1>&2
	exit 1
    fi
fi

exit 0
