#!/bin/bash
cd `dirname $0`
source ./setup.sh
if [ "$1" = "" ] ; then
    USER=testuser
else
    USER=$1
fi
ssh -t root@$vofe_fqdn 'cd ~testuser/testjobs; su testuser -c "condor_submit testjob.singularity.jdf"'
