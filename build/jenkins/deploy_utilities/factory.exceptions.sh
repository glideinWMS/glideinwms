#!/bin/bash
cd `dirname $0`
source ./setup.sh
out=$(ssh root@$fact_fqdn 'find /var/log/gwms-factory -type f | xargs grep -iE "exception"' )
if [ "$out" = "" ]; then
    if [ "$1" = "-v" ]; then
        echo "no python exceptions found on on factory $fact_fqdn"
    fi
    exit 0
else
    while IFS= read ; do
        echo $REPLY
    done <<< "$out"
    exit 1
fi
