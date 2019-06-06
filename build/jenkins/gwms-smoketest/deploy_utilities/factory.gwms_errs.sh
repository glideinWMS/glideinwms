#!/bin/bash
cd `dirname $0`
source ./setup.sh
echo gwms errors for $fact_fqdn
ssh -t root@$fact_fqdn 'find /var/log/gwms-factory -type f | xargs grep -iE "exception|error|failed" | grep -v GLIDEIN_Report_Failed | grep -v OK | grep -v ERROR_GEN_PATH | grep -v "Failed\ to\ load" '
