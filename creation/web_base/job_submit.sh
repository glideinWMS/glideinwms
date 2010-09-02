#!/bin/bash
# Sets the environment and submits the Condor-G job that starts the glideins

export GLIDEIN_USER=`id -u -n`

if [ $# -lt 6 ]; then
 echo "At least 6 args expected!" 1>&2
 echo "Usage: job_submit.sh entry_name client x509_id count add_rsl chunk_size [attrs]* -- [params]*"
 1>&2
 exit 1
fi
GLIDEIN_ENTRY_NAME="$1"
shift
export GLIDEIN_CLIENT="$1"
shift
export GLIDEIN_X509_ID="$1"
shift
export GLIDEIN_COUNT=$1
shift
export GLIDEIN_ADDITIONAL_RSL=$1
shift
export GLIDEIN_CHUNK_SIZE=$1
shift
GLIDEIN_PARAMS=""
while [ "$1" != "--" ]; do
 GLIDEIN_PARAMS="$GLIDEIN_PARAMS $1"
 shift
done
shift # remove --
while [ $# -ge 2 ]; do
 GLIDEIN_PARAMS="$GLIDEIN_PARAMS -param_$1 $2"
 shift
 shift
done
export GLIDEIN_PARAMS

export GLIDEIN_SCHEDD=`grep -i "^Schedd "  entry_${GLIDEIN_ENTRY_NAME}/job.descript | awk '{print $2}'`
export GLIDEIN_VERBOSITY=`grep -i "^Verbosity "  entry_${GLIDEIN_ENTRY_NAME}/job.descript | awk '{print $2}'`

export GLIDEIN_LOGNR=`date +%Y%m%d`

log_base_dir=`grep -i "^ClientLogBaseDir " glidein.descript | awk '{print $2}'`
glidein_name=`grep -i "^GlideinName " glidein.descript | awk '{print $2}'`
log_dir="${log_base_dir}/user_${GLIDEIN_USER}/glidein_${glidein_name}/entry_${GLIDEIN_ENTRY_NAME}"
error_log_fname="${log_dir}/submit_${GLIDEIN_LOGNR}_${GLIDEIN_CLIENT}.log"

echo "`date '+%y/%m/%d %H:%M'` Submitting ${GLIDEIN_COUNT} glideins with chunk size ${GLIDEIN_CHUNK_SIZE} using X509 id ${GLIDEIN_X509_ID=}" >> "$error_log_fname"
condor_submit -name $GLIDEIN_SCHEDD entry_${GLIDEIN_ENTRY_NAME}/job.condor 2>> "$error_log_fname"
