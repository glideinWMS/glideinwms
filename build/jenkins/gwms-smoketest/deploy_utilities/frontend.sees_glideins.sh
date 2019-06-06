#!/bin/bash
cd `dirname $0`
source ./setup.sh

./frontend.condor_status.sh   | grep 'glidein' | grep ' Job '  > /dev/null 2>&1
if [ $? -eq 0 ]; then
    if [ "$1" = "-v" ]; then
        echo glideins connected to  $vofe_fqdn
    fi
    exit 0
else
    if [ "$1" == "-v" ]; then
        echo no glideins connected to  $vofe_fqdn
    fi
    exit 1
fi
