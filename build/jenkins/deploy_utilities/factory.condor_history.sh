#!/bin/bash
cd `dirname $0`
source ./setup.sh

ssh root@$fact_fqdn find /var/lib/condor -name history 2>&1 | grep history > /dev/null
has_completed=$?
for H in $(ssh root@$fact_fqdn find /var/lib/condor -name history); do ssh root@$fact_fqdn condor_history -file $H ; done
exit $has_completed
