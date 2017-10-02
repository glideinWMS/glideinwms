#!/bin/bash
cd `dirname $0`
source ./setup.sh

ssh root@$vofe_fqdn condor_history 2>&1 | grep ' C  ' > /dev/null 2>&1
if [ $? = 0 ] ; then
    if [ "$1" = "-v" ]; then
        echo some user jobs have completed on $vofe_fqdn
    fi
    exit 0
else
    if [ "$1" = "-v" ]; then
        echo no user jobs have complted  on $vofe_fqdn
    fi
    exit 1
fi
