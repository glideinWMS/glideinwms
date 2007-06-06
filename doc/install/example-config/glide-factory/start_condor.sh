#!/bin/bash
/opt/glidecondor/sbin/condor_master
sleep 1
/opt/glidecondor/start_master_schedd.sh glideins1
/opt/glidecondor/start_master_schedd.sh glideins2
/opt/glidecondor/start_master_schedd.sh glideins3
/opt/glidecondor/start_master_schedd.sh glideins4
