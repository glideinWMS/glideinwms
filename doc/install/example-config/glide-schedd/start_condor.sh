#!/bin/bash
/opt/glidecondor/sbin/condor_master
sleep 1
/opt/glidecondor/start_master_schedd.sh jobs1
/opt/glidecondor/start_master_schedd.sh jobs2
/opt/glidecondor/start_master_schedd.sh jobs3
/opt/glidecondor/start_master_schedd.sh jobs4
