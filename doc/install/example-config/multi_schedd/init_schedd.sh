#!/bin/sh
CONDOR_LOCATION=/opt/glidecondor
script=$CONDOR_LOCATION/new_schedd_setup.sh
source $script $1
if [ "$?" != "0" ];then
  echo "ERROR in $script"
  exit 1
fi
# add whatever other config you need
# create needed directories
$CONDOR_LOCATION/sbin/condor_init
exit 0
