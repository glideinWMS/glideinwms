#!/bin/bash
cd `dirname $0`
source ./setup.sh
out=$(ssh -t root@$vofe_fqdn 'find /var/log/gwms-frontend -type f | xargs grep -iE "exception" | grep -v "OK"' )
if [ "$out" = "" ]; then
    if [ "$1" = "-v" ]; then
        echo "no python exceptions found on on vofrontend $vofe_fqdn"
    fi
    exit 0
else
    echo python exceptions on $vofe_fqdn
    while IFS= read ; do
        echo $REPLY
    done <<< "$out"
    exit 1
fi
