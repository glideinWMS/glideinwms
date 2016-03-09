#!/bin/bash
#
# Project:
#   glideinWMS
#
# Description:
#   Script to be periodically executed to check if the WN
#   is in draining mode.
#
#   The script implements one of the use case forseen by the
#   WLCG Machine / Job Features Task Force :
#   https://twiki.cern.ch/twiki/bin/view/LCG/MachineJobFeatures
#
#   The script check the existance of the shutdowntime_job file
#   in the $JOBFEATURES directory. If the file is present then
#   a shutdown is scheduled and the script will output
#   "SiteWMS_WN_Draining = True" so the pilot will stop accepting jobs.
#   $JOBFEATURES/shutdowntime_job could also be a URL that the script
#   tries to download
#   More details about JOBFEATURES:
#   https://twiki.cern.ch/twiki/bin/view/LCG/WMTEGEnvironmentVariables
#

draining=false
if [ -n "$JOBFEATURES" ]; then
    if [ -f "$JOBFEATURES/shutdowntime_job" ]; then
        draining=true
    else
        #check if shutdowntime job is a URL and wget it
        ADDRESS=$JOBFEATURES/shutdowntime_job
        echo $ADDRESS | grep -E '^https?' > /dev/null
        if [ $? -eq 0 ]; then
            #use quiet mode and redirect file to stdout
            wget -qO- $ADDRESS > /dev/null
            if [ $? -eq 0 ]; then
                draining=true
            fi
        fi
    fi
fi

if [ "$draining" = true ] ; then
    echo SiteWMS_WN_Draining = True
else
    echo SiteWMS_WN_Draining = False
fi

exit 0
