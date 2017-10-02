#!/bin/bash
cd `dirname $0`
source ./setup.sh
ssh root@$fact_fqdn condor_status -any $1 
