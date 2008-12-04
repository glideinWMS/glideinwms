#!/bin/bash

if [ $# -lt 4 ]; then
 echo "At least 4 args expected!" 1>&2
 echo "Usage: job_submit.sh entry_name client count [attrs]* -- [params]*"
 1>&2
 exit 1
fi
GLIDEIN_ENTRY_NAME="$1"
shift
export GLIDEIN_CLIENT="$1"
shift
export GLIDEIN_COUNT=$1
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
condor_submit -name $GLIDEIN_SCHEDD entry_${GLIDEIN_ENTRY_NAME}/job.condor
