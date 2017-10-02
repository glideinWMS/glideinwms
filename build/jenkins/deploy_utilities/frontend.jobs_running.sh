#!/bin/bash
cd `dirname $0`
source ./setup.sh

ssh root@$vofe_fqdn condor_q -g -nob -all  | grep ' R ' > /dev/null 2>&1
if [ $? -eq 0 ]; then
    if [ "$1" = "-v" ]; then
        echo user jobs running on $vofe_fqdn
    fi
    exit 0
else
    if [ "$1" = "-v" ]; then
        echo no user jobs running on $vofe_fqdn
    fi
    exit 1
fi
