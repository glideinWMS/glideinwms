#!/bin/bash

if [ $# -lt 8 ]; then
 echo "At least 5 args expected!" 1>&2
 echo "Usage: job_submit.sh entry_name schedd client count mode [params]*"
 1>&2
 exit 1
fi
GLIDEIN_ENTRY_NAME="$1"
shift
export GLIDEIN_SCHEDD=$1
shift
export GLIDEIN_CLIENT="$1"
shift
export GLIDEIN_COUNT=$1
shift
export GLIDEIN_VERBOSITY=$1
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
export GLIDEIN_LOGNR=`date +%Y%m%d`
condor_submit -append "$GLIDEIN_GRIDOPTS" -name $GLIDEIN_SCHEDD entry_${GLIDEIN_ENTRY_NAME}/job.condor
