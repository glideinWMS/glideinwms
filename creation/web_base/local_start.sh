#!/bin/bash
#
# Project:
#   glideinWMS
#
# File Version: 
#

export GLIDEIN_USER=`id -u -n`

if [ $# -lt 2 ]; then
 echo "At least 2 args expected!" 1>&2
 echo "Usage: local_start.sh entry_name mode [params]* --" 1>&2
 echo "" 1>&2
 echo "For example: " 1>&2
 echo "  Assuming you want to point the glidein to  collector.mydomain.org:9621,collector.mydomain.org:9622" 1>&2
 echo "  ./local_start.sh gp9 fast -param_GLIDEIN_Collector collector.dot,mydomain.dot,org.colon,9621.comma,collector.dot,mydomain.dot,org.colon,9622 --" 1>&2
 exit 1
fi
GLIDEIN_ENTRY_NAME="$1"
shift
GLIDEIN_VERBOSITY=$1
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

export GLIDEIN_CLIENT="test"
export GLIDEIN_X509_SEC_CLASS="test"
export GLIDEIN_X509_ID="test"

GLIDEIN_FACTORY=`grep "^FactoryName " glidein.descript | awk '{print $2}'`
GLIDEIN_NAME=`grep "^GlideinName " glidein.descript | awk '{print $2}'`

WEB_BASE=`grep "^WebURL " glidein.descript | awk '{print $2}'`

SIGN=`grep " main$" signatures.sha1 | awk '{print $1}'`
SIGNENTRY=`grep " entry_$GLIDEIN_ENTRY_NAME$" signatures.sha1 | awk '{print $1}'`
if [ -z "$SIGNENTRY" ]; then
  echo "Failed to load entry signature!" 1>&2
fi

DESCRIPT=`grep " main$" signatures.sha1 | awk '{print $2}'`
DESCRIPTENTRY=`grep " entry_$GLIDEIN_ENTRY_NAME$" signatures.sha1 | awk '{print $2}'`
if [ -z "$SIGNENTRY" ]; then
  echo "Failed to load entry description!" 1>&2
fi

./glidein_startup.sh -v $GLIDEIN_VERBOSITY -cluster 0 -name $GLIDEIN_NAME -entry $GLIDEIN_ENTRY_NAME -subcluster 0 -schedd local -factory $GLIDEIN_FACTORY -web $WEB_BASE -sign $SIGN -signentry $SIGNENTRY -signtype sha1 -descript $DESCRIPT -descriptentry $DESCRIPTENTRY -dir . -param_GLIDEIN_Client local $GLIDEIN_PARAMS



