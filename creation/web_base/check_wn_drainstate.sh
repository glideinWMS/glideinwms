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
#   in the $JOBFEATURES directory (or shutdowntime in $MACHINEFEATURES).
#   If one of the files is present then
#   a shutdown is scheduled and the script will output
#   "SiteWMS_WN_Draining = True" so the pilot will stop accepting jobs.
#   $JOBFEATURES/shutdowntime_job ($MACHINEFEATURES/shutdowntime) could also
#    be a URL that the script tries to download.
#   More details about this:
#   https://twiki.cern.ch/twiki/bin/view/LCG/WMTEGEnvironmentVariables
#

function fileOrURLExists {
    FILENAME="$1"
    VARNAME="$2"
    if [ -n "$VARNAME" ]; then
        if [ -f "$VARNAME/$FILENAME" ]; then
            echo true
            return
        else
            #check if shutdowntime job is a URL and wget it
            ADDRESS="$VARNAME/$FILENAME"
            echo $ADDRESS | grep -E '^https?' > /dev/null
            if [ $? -eq 0 ]; then
                #use quiet mode and redirect file to stdout
                wget -qO- $ADDRESS > /dev/null
                if [ $? -eq 0 ]; then
                    echo true
                    return
                fi
            fi
        fi
    fi
    echo false
}

J=$(fileOrURLExists shutdowntime_job "$JOBFEATURES")
M=$(fileOrURLExists shutdowntime "$MACHINEFEATURES")

if [ "$J" == true ] || [ "$M" == true ] ; then
    echo SiteWMS_WN_Draining = True
else
    echo SiteWMS_WN_Draining = False
fi

exit 0
