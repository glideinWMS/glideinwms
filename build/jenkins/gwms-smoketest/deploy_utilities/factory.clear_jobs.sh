#!/bin/bash -x
cd `dirname $0`
source ./setup.sh
if [ "$1" = "" ] ; then
    USER=frontend
else
    USER=$1
fi
for NM in `ssh -t root@${fact_fqdn} condor_status -schedd -af name 2>/dev/null | tr '\r' ' ' | tr '\n' ' '`; do
    ssh -t  root@"$fact_fqdn" condor_rm -name "$NM" "${USER}"
done

