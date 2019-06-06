#!/bin/bash
cd `dirname $0`
source ./setup.sh
if [ "$1" = "-v" ]; then
    echo python exceptions on $fact_fqdn
fi
out=$(ssh -t root@$fact_fqdn 'find /var/log/gwms-factory -type f | xargs grep -iE "exception" | grep -v "OK"' )
if [ "$out" = "" ]; then
    if [ "$1" = "-v" ]; then
        echo "no python exceptions found on on factory $fact_fqdn"
    fi
    exit 0
else
    echo python exceptions on $fact_fqdn
    while IFS= read ; do
        echo $REPLY
    done <<< "$out"
    exit 1
fi
