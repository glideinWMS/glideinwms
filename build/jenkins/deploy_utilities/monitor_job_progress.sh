#!/bin/bash
cd `dirname $0`
source ./setup.sh
sleepval=10
echo "checking progress of submission from frontend $vofe_fqdn to factory $fact_fqdn"
echo "wait for glideins to launch "
echo -n "$(date): "
while ! ./factory.has_idle_glideins.sh -v ; do
    sleep $sleepval
    echo -n "$(date): "
done
echo "wait for glideins to run "
while ! ./factory.has_running_glideins.sh -v ; do
    sleep $sleepval
    echo -n "$(date): "
done
echo "wait for glideins to connect to $vofe_fqdn"
while ! ./frontend.sees_glideins.sh -v ; do
    sleep $sleepval
    echo -n "$(date): "
done
echo "wait for user jobs to start "
while ! ./frontend.jobs_running.sh  -v ; do
    sleep $sleepval
    echo -n "$(date): "
done
echo SUCCESS!!
exit 0
