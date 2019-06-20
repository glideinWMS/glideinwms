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
#   If one of the files is present then a shutdown is scheduled
#   based on the timestamp in that file.
#   $JOBFEATURES/shutdowntime_job ($MACHINEFEATURES/shutdowntime) could also
#   be a URL that the script tries to download.
#   The script checks the shutdown time contaned in the file and:
#     1. if less than 4h left, it will output "SiteWMS_WN_Draining = True" so the
#        pilot will stop accepting jobs.
#     2. if less than 30 minutes are left before it, then it will preempt the job
#        by setting "SiteWMS_WN_Preempt = True"
#   If one of the two files contains a non numeric value the script will exit
#   leaving everything untouched (it considers this an error)
#   More details about this:
#   https://twiki.cern.ch/twiki/bin/view/LCG/WMTEGEnvironmentVariables
#

LIBLOCATION=$(dirname $0)
source "$LIBLOCATION/glidein_lib.sh"

function isNumberOrFalse {
    # the function verifies that the argument (i.e.: $1) is a number, and exts otherwise
    # printing a message to stderr
    echo $1 | grep -Eq '(^\-?[0-9]+$)|(^"Unknown"$)'
    if [ $? -eq 1 ]; then
        echo "JOBFEATURES ($JOBFEATURES) or MACHINEFEATURES ($MACHINEFEATURES) variable found, but shutdown file NOT containing a number (contains '$1' instead)" >&2
        exit 1
    fi
}

J=$(getValueFromFileOrURL shutdowntime_job "$JOBFEATURES")
isNumberOrFalse $J
M=$(getValueFromFileOrURL shutdowntime "$MACHINEFEATURES")
isNumberOrFalse $M

WN_Preempt='False'
WN_Drain='False'

EXIT_MESSAGE_FILE=$start_dir/exit_message
if [ "$J" != '"Unknown"' ] || [ "$M" != '"Unknown"' ] ; then
    CURR_TIME=$(date +%s)
    # If Left time is lower than 4hours (14400seconds), this will set WN_Drain Flag to True
    if ( [ "$J" != '"Unknown"' ] && [ $((J - CURR_TIME)) -lt 14400 ] ) || ( [ "$M" != '"Unknown"' ] && [ $((M - CURR_TIME)) -lt 14400 ] ); then
        WN_Drain='True'
        if [ ! -f $EXIT_MESSAGE_FILE ] ; then
            echo "Stopping accepting jobs since site admins are going to shut down the node. Time is `date`" >> $EXIT_MESSAGE_FILE
        fi
    fi
    if ( [ "$J" != '"Unknown"' ] && [ $((J - CURR_TIME)) -lt 1800 ] ) || ( [ "$M" != '"Unknown"' ] && [ $((M - CURR_TIME)) -lt 1800 ] ); then
        echo "Preempting user job since less then 1800 seconds are left before machine shutdown. Time is `date`" >> $EXIT_MESSAGE_FILE
        WN_Preempt='True'
    fi
else
    if [ -f $EXIT_MESSAGE_FILE ] ; then
        echo "Aborting shutdown of pilot. New jobs will be accepted. Time is `date`" >> $EXIT_MESSAGE_FILE
        #shutdown can be aborted. Do not print in the logs
        rm $EXIT_MESSAGE_FILE
    fi
fi

echo "SiteWMS_WN_Draining = $WN_Drain"
echo "SiteWMS_WN_Preempt = $WN_Preempt"

exit 0
