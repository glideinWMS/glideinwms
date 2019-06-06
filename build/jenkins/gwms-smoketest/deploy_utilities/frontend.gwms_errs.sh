#!/bin/bash
cd `dirname $0`
source ./setup.sh
echo gwms errors for $vofe_fqdn
ssh -t root@$vofe_fqdn 'find /var/log/gwms-frontend -type f | xargs grep -iE "failed|error|exception"' 
