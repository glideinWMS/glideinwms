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


sitewms="Unknown"
sitewms_slot="Unknown"
sitewms_jobid="Unknown"
sitewms_queue="Unknown"

# NOTE: For HTCondor _CONDOR_SLOT can be empty so check using _CONDOR_JOB_AD
[ "$sitewms" = "Unknown" ] && [ -n "$_CONDOR_JOB_AD" ] && sitewms="HTCondor"
[ "$sitewms" = "Unknown" ] && [ -n "$JOB_ID" ] && sitewms="SGE"
[ "$sitewms" = "Unknown" ] && [ -n "$PBS_O_JOBID" ] && sitewms="PBS"
[ "$sitewms" = "Unknown" ] && [ -n "$LSB_JOBID" ] && sitewms="LSF"
[ "$sitewms" = "Unknown" ] && [ -n "$SLURM_JOBID" ] && sitewms="SLURM"

case $sitewms in
    HTCondor)
        slotid=`grep -i "^remoteslotid = " $_CONDOR_JOB_AD | awk -F'=' '{print $NF}' | tr -d ' '`
        sitewms_slot="${_CONDOR_SLOT}"
        [ "$sitewms_slot" = "" ] && sitewms_slot=${slotid:-Unknown}
        procid=`grep -i "^procid = " $_CONDOR_JOB_AD | awk -F'=' '{print $NF}' | tr -d ' '`
        clusterid=`grep -i "^clusterid = " $_CONDOR_JOB_AD | awk -F'=' '{print $NF}' | tr -d ' '`
        jobid="$clusterid.$procid"
        [ "$jobid" != "." ] && sitewms_jobid=$jobid
        queue=`grep -i "^GlobalJobId = " $_CONDOR_JOB_AD | awk -F'"' '{print $2}' | awk -F'#' '{print $1}'`
        sitewms_queue=${queue:-Unknown}
        ;;
    SGE)
        sitewms_jobid=$JOB_ID
        sitewms_queue=$QUEUE
        ;;
    
    PBS)
        sitewms_jobid=$PBS_O_JOBID
        sitewms_queue=$PBS_QUEUE
        ;;

    LSF)
        sitewms_jobid=$LSB_JOBID
        sitewms_queue=$LSB_QUEUE
        ;;

    SLURM)
        sitewms_jobid=$SLURM_JOBID
        ;;
    *)
        echo "Unsupported GLIDEIN_SiteWMS encountered"
        ;;
esac


add_config_line GLIDEIN_SiteWMS "${sitewms}"
add_config_line GLIDEIN_SiteWMS_Slot "${sitewms_slot}"
add_config_line GLIDEIN_SiteWMS_JobId "${sitewms_jobid}"
add_config_line GLIDEIN_SiteWMS_Queue "${sitewms_queue}"

add_condor_vars_line GLIDEIN_SiteWMS "S" "Unknown" "+" "N" "Y" "-"
add_condor_vars_line GLIDEIN_SiteWMS_Slot "S" "Unknown" "+" "N" "Y" "-"
add_condor_vars_line GLIDEIN_SiteWMS_JobId "S" "Unknown" "+" "N" "Y" "-"
add_condor_vars_line GLIDEIN_SiteWMS_Queue "S" "Unknown" "+" "N" "Y" "-"

"$error_gen" -ok "glidein_sitewms_setup.sh" "GLIDEIN_SiteWMS" "${sitewms}" "GLIDEIN_SiteWMS_Slot" "${sitewms_slot}" "GLIDEIN_SiteWMS_JobId" "${sitewms_jobid}" "GLIDEIN_SiteWMS_Queue" "${sitewms_queue}" 

exit 0
