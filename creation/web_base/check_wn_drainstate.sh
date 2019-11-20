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
#   be a URL that the script tries to download.
#   The script also checks the shutdown time contaned in the file and if
#   less than 30 minutes are left before it, then it will preempt the job
#   by setting SiteWMS_WN_Preempt
#   If one of the two files contains a non numeric value the script will exit
#   leaving everything untouched (it considers this an error)
#   More details about this:
#   https://twiki.cern.ch/twiki/bin/view/LCG/WMTEGEnvironmentVariables
#

LIBLOCATION=$(dirname $0)
source "$LIBLOCATION/glidein_lib.sh"

EXIT_MESSAGE_FILE=$start_dir/exit_message

function logmsg {
    if touch $EXIT_MESSAGE_FILE 2> /dev/null; then
        echo "$1" >> $EXIT_MESSAGE_FILE
    fi
}

function isNumberOrFalse {
    # the function verifies that the argument (i.e.: $1) is a number, and exits otherwise
    # printing a message to stderr
    echo $1 | grep -Eq '(^\-?[0-9]+$)|(^"Unknown"$)'
    if [ $? -eq 1 ]; then
        logmsg "JOBFEATURES ($JOBFEATURES) or MACHINEFEATURES ($MACHINEFEATURES) variable found, but shutdown file NOT containing a number (contains '$1' instead)"
        exit 1
    fi
}

J=$(getValueFromFileOrURL shutdowntime_job "$JOBFEATURES")
isNumberOrFalse $J
M=$(getValueFromFileOrURL shutdowntime "$MACHINEFEATURES")
isNumberOrFalse $M

# Ignoring if cannot find the shutdown files
if [ "$J" == '"Unknown"' ] && [ "$M" == '"Unknown"' ] ; then
    echo "SiteWMS_WN_Draining = False"
    echo "SiteWMS_WN_Preempt = False"
    exit 0
fi

# Get the shutdown time (the lowest number between J and M)
# We know either J or M contains the timestamp, but one can contain "Unknwown".
# Replace the "Unknwon" with the other timestamp
J=$([ "$J" == '"Unknown"' ] && echo $M || echo $J)
M=$([ "$M" == '"Unknown"' ] && echo $J || echo $M)
SHTUDOWN_TIME=$([ $J -le $M ] && echo "$J" || echo "$M")

TO_DIE=$(grep -i '^GLIDEIN_ToDie =' $CONDOR_CONFIG | tr -d '"' | tail -1 | awk '{print $NF;}')
TO_RETIRE=$(grep -i '^GLIDEIN_TORETIRE =' $CONDOR_CONFIG | tr -d '"' | tail -1 | awk '{print $NF;}')
GRACE_TIME="$(($TO_DIE-$TO_RETIRE))"
CURR_TIME=$(date +%s)

if [ $((SHTUDOWN_TIME - CURR_TIME)) -lt 0 ] ; then
    logmsg "Ignoring potentially stale MJF shutdown files since their shoutdown time is in the past"
    echo "SiteWMS_WN_Draining = False"
    echo "SiteWMS_WN_Preempt = False"
    exit 0
fi

if [ $((SHTUDOWN_TIME - CURR_TIME)) -lt $GRACE_TIME ]; then
    echo "SiteWMS_WN_Draining = True"
    logmsg "Stopping accepting jobs since site admins are going to shut down the node. Time is `date`"
    if [ $((SHTUDOWN_TIME - CURR_TIME)) -lt 1800 ] ; then
        logmsg "Preempting user job since less then 1800 seconds are left before machine shutdown. Time is `date`"
        echo "SiteWMS_WN_Preempt = True"
    fi
else
    if [ -f $EXIT_MESSAGE_FILE ] ; then
        logmsg "Aborting shutdown of pilot. New jobs will be accepted. Time is `date`"
        #shutdown can be aborted. Do not print in the logs
        rm $EXIT_MESSAGE_FILE
    fi
    echo "SiteWMS_WN_Draining = False"
    echo "SiteWMS_WN_Preempt = False"
fi

exit 0
