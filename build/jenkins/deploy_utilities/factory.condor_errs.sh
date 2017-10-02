#!/bin/bash
cd `dirname $0`
source ./setup.sh

ssh root@$fact_fqdn 'find /var/log/condor -type f | xargs grep -iE "failed|error|exception"' 
