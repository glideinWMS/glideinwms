#!/bin/bash
cd `dirname $0`
source ./setup.sh
echo condor errors for $vofe_fqdn
ssh -t root@$vofe_fqdn 'find /var/log/condor -type f | xargs grep -iE "failed|error|exception"| grep -v D_ERROR | grep -v "RequestsFailed\ =\ 0" | grep -iv ganglia' 
