#!/bin/bash

############################################################
#
# This script will setup the GCB parameters
#
############################################################

glidein_config=$1

function append_config {
    echo "$1" >> condor_config
    if [ $? -ne 0 ]; then
	echo "Failed to to update condor_config!" 2>&1
	exit 1
    fi    
}

gcb_ip=`grep '^GCB_IP ' $glidein_config | awk '{print $2}'`
if [ -z "$gcb_ip" ]; then
    echo "No GCB_IP found!" 2>&1
    exit 1
fi

gcb_port=`grep '^GCB_PORT ' $glidein_config | awk '{print $2}'`
if [ -z "$gcb_port" ]; then
    gcb_port=65432
    echo "Using default GCB_PORT 65432" 
fi

# test we can talk to the GCB
nc -z $gcb_ip $gcb_port
ret=$?
if [ $ret -ne 0 ]; then
  echo "Cannot talk to GCB ${gcb_ip}:${gcb_port}" 2>&1
  exit 1
fi

# configure Condor to use it
append_config "BIND_ALL_INTERFACES = true"
append_config "NET_REMAP_ENABLE = true"
append_config "NET_REMAP_SERVICE = GCB"
append_config "NET_REMAP_INAGENT = $gcb_ip"

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
