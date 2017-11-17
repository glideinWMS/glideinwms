#!/bin/bash
cd `dirname $0`
source ./setup.sh

#ssh root@$fact_fqdn condor_q -g -nob -all  | grep ' R ' > /dev/null 2>&1
./factory.condor_q.sh | grep ' R ' > /dev/null 2>&1
if [ $? -eq 0 ]; then
    if [ "$1" = "-v" ]; then
        echo glideins running on $fact_fqdn
    fi
    exit 0
else
    if [ "$1" == "-v" ]; then
        echo no glideins running on $fact_fqdn
    fi
    exit 1
fi
