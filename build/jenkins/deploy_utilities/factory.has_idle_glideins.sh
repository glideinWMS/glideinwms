#!/bin/bash
cd `dirname $0`
source ./setup.sh

#ssh root@$fact_fqdn condor_q -g -nob -all | grep ' I ' > /dev/null 2>&1
./factory.condor_q.sh | grep ' I ' > /dev/null 2>&1
if [ $? -eq 0 ]; then
    if [ "$1" = "-v" ]; then
        echo glideins idle on $fact_fqdn 
    fi
    exit 0
else
    echo no glideins idle  on $fact_fqdn
    exit 1
fi
