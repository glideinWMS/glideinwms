#!/bin/sh
source /opt/glidecondor/new_schedd_setup.sh $1
# add whatever other config you need
/opt/glidecondor/sbin/condor_master
