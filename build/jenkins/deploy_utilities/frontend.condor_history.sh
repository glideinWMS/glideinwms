#!/bin/bash
cd `dirname $0`
source ./setup.sh
ssh root@$vofe_fqdn condor_history
