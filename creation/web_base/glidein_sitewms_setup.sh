#!/bin/sh

#
# Project:
#   glideinWMS
#
# File Version: 
#
# Description:
#   This script will determine the glidein jobs info as in the site's wms
#

glidein_config=$1
tmp_fname=${glidein_config}.$$.tmp
error_gen=`grep '^ERROR_GEN_PATH ' $glidein_config | awk '{print $2}'`
condor_vars_file=`grep -i "^CONDOR_VARS_FILE " $glidein_config | awk '{print $2}'`
# import add_config_line and add_condor_vars_line functions
add_config_line_source=`grep '^ADD_CONFIG_LINE_SOURCE ' $glidein_config | awk '{print $2}'`
source $add_config_line_source

UNKNOWN="Unknown"

sitewms=$UNKNOWN
sitewms_slot=$UNKNOWN
sitewms_jobid=$UNKNOWN
sitewms_queue=$UNKNOWN

# NOTE: For HTCondor _CONDOR_SLOT can be empty so check using _CONDOR_JOB_AD
[ "$sitewms" = $UNKNOWN ] && [ -n "$_CONDOR_JOB_AD" ] && sitewms="HTCondor"
[ "$sitewms" = $UNKNOWN ] && [ -n "$JOB_ID" ] && sitewms="SGE"
[ "$sitewms" = $UNKNOWN ] && [ -n "$PBS_JOBID" ] && sitewms="PBS"
[ "$sitewms" = $UNKNOWN ] && [ -n "$LSB_JOBID" ] && sitewms="LSF"
[ "$sitewms" = $UNKNOWN ] && [ -n "$SLURM_JOBID" ] && sitewms="SLURM"

case $sitewms in
    HTCondor)
        # HTCondor v7.7.x - v8.1.x and earlier versions have a bug and do not set
        # _CONDOR_SLOT="slot1" in job's environment if its not multislot startd
        # Also, for dynamic slots, RemoteSlotId points to partitionable slot
        # and not the real slot that runs the job. i.e it will always report id
        # for slotx instead of slotx_y
      
        hostname=`uname -n`
        slot="${_CONDOR_SLOT}"
        [ "$slot" = "" ] && slot="slot1"
        sitewms_slot="$slot@$hostname"

        #slotid=`grep -i "^remoteslotid = " $_CONDOR_JOB_AD | awk -F'=' '{print $NF}' | tr -d ' '`
        #slotname="slot${slotid}"
        #[ "$sitewms_slot" = "" ] && sitewms_slot=${slotname:-Unknown}
        procid=`grep -i "^procid = " $_CONDOR_JOB_AD | awk -F'=' '{print $NF}' | tr -d ' '`
        clusterid=`grep -i "^clusterid = " $_CONDOR_JOB_AD | awk -F'=' '{print $NF}' | tr -d ' '`
        jobid="$clusterid.$procid"
        [ "$jobid" != "." ] && sitewms_jobid=$jobid
        queue=`grep -i "^GlobalJobId = " $_CONDOR_JOB_AD | awk -F'"' '{print $2}' | awk -F'#' '{print $1}'`
        sitewms_queue=${queue:-$UNKNOWN}
        ;;
    SGE)
        sitewms_jobid=${JOB_ID:-$UNKNOWN}
        sitewms_queue=${QUEUE:-$UNKNOWN}
        ;;
    
    PBS)
        sitewms_jobid=${PBS_JOBID:-$UNKNOWN}
        sitewms_queue=${PBS_QUEUE:-$UNKNOWN}
        ;;

    LSF)
        sitewms_jobid=${LSB_JOBID:-$UNKNOWN}
        sitewms_queue=${LSB_QUEUE:-$UNKNOWN}
        ;;

    SLURM)
        sitewms_jobid=${SLURM_JOBID:-$UNKNOWN}
        ;;
    *)
        echo "Unsupported GLIDEIN_SiteWMS encountered"
        ;;
esac


add_config_line GLIDEIN_SiteWMS "${sitewms}"
add_config_line GLIDEIN_SiteWMS_Slot "${sitewms_slot}"
add_config_line GLIDEIN_SiteWMS_JobId "${sitewms_jobid}"
add_config_line GLIDEIN_SiteWMS_Queue "${sitewms_queue}"

add_condor_vars_line GLIDEIN_SiteWMS "S" "$UNKNOWN" "+" "N" "Y" "-"
add_condor_vars_line GLIDEIN_SiteWMS_Slot "S" "$UNKNOWN" "+" "N" "Y" "-"
add_condor_vars_line GLIDEIN_SiteWMS_JobId "S" "$UNKNOWN" "+" "N" "Y" "-"
add_condor_vars_line GLIDEIN_SiteWMS_Queue "S" "$UNKNOWN" "+" "N" "Y" "-"

"$error_gen" -ok "glidein_sitewms_setup.sh" "GLIDEIN_SiteWMS" "${sitewms}" "GLIDEIN_SiteWMS_Slot" "${sitewms_slot}" "GLIDEIN_SiteWMS_JobId" "${sitewms_jobid}" "GLIDEIN_SiteWMS_Queue" "${sitewms_queue}" 

exit 0
