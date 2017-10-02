#!/bin/bash
cd `dirname $0`
source ./setup.sh
if [ "$1" = "" ] ; then
    USER=frontend
else
    USER=$1
fi
for NM in $(ssh root@$fact_fqdn condor_status -schedd -af name); do
    ssh root@$fact_fqdn condor_rm -name $NM $USER
done

