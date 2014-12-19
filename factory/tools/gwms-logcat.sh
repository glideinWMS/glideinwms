#!/bin/bash
# Cat log GWMS files using tools

TOOLDIR=/usr/lib/python2.6/site-packages/glideinwms/factory/tools
JOBLOGPREFIX=/var/log/gwms-factory/client/user_frontend/glidein_gfactory_instance/entry_
#server logs JOBLOGPREFIX=/var/log/gwms-factory/server/entry_
# TODO: substitute with a real temp file and delete after use (or print file name)
TMPLOG=/tmp/pilot_launcher.log.$UID

LOGNAME=


function help_msg {
  cat << EOF
$0 [options] LOG_TYPE LOGFILE
$0 [options] LOG_TYPE ENTRY [JOB_ID]
$0 -r [options] LOG_TYPE JOB_ID
$0 -l
  LOG_TYPE HTCondor log to extract from the job logfile: 
           all (all logs), master, startd, starter, startdhistory, xml
  LOGFILE  Job log file
  ENTRY    Entry name
  JOB_ID   HTCondor job id. By default picks the last job with a valid log file
  -v       verbose
  -h       print this message
  -l       list all entries (arguments are ignored)
  -r       Remote running jobs. pilot_launcher.log is fetched form the VM 
EOF
}

function get_last_log {
  # return last error log file
  echo "`find $1 -size +1 -name 'job*err' -printf '%T@ %p\n' | sort -nk1 | sed 's/^[^ ]* //' | tail -1`"
}

function list_entries {
  elist=`ls -d $JOBLOGPREFIX*`
  for i in $elist; do
    echo -n "`ls $i/job*err 2>/dev/null | wc -l` "
    echo -n "(`get_last_log $i`) "
    echo ${i#$JOBLOGPREFIX}
  done
}

while getopts "lhc:o:rv" option
do
  case "${option}"
  in
  "h") help_msg; exit 0;;
  "v") VERBOSE=yes;;
  l) list_entries; exit 0;;
  r) REMOTE=yes;;
  esac
done

shift $((OPTIND-1))

logoption=$1
logid="$2"

if [ -z "$logid" ]; then
  echo "You must specify a log type and an entry (or log file)"
  help_msg
  exit 1
fi

case $logoption in
  all) LOGNAME=cat_logs.py;;
  master) LOGNAME=cat_MasterLog.py;;
  startd) LOGNAME=cat_StartdLog.py;;
  starter) LOGNAME=cat_StarterLog.py;;
  xml) LOGNAME=cat_XMLResults.py;;
  startdhistory) LOGNAME=cat_StartdHistory.py;;
  *) echo "Unknown LOG_TYPE: $logoption"; help_msg; exit 1;;
esac

if [ -n "$REMOTE" ]; then
  # Copying file locally
  echo "Copying remote pilot_launcher.log to $TMPLOG"
  hostid="`condor_q -af EC2RemoteVirtualMachineName - $logid`"
  if [ -z "$hostid" ] || [ "$hostid" = "undefined" ]; then
    echo "Unable to retrieve remote host for job $logid"
    exit 1
  fi
  scp root@$hostid:/home/glidein_pilot/pilot_launcher.log $TMPLOG
  if [ $? -ne 0 ]; then
    echo "Copy of remote log file (root@$hostid:/home/glidein_pilot/pilot_launcher.log) failed"
    echo "Remote pilot directory:"
    ssh root@$hostid /bin/ls -al /home/glidein_pilot/
    exit 1
  fi
  logid=$TMPLOG
fi

if [ ! -e "$logid" ]; then
  # find the log file of this job ID
  entryname=$logid 
  jobid=$3 
  if [ -z "$jobid" ]; then
    # select the last log file 
    logid="`get_last_log ${JOBLOGPREFIX}${entryname}`"
    [ -z "$logid" ] && echo "Entry $entryname has no valid log file"
  else
    [[ ! "$jobid" =~ .*\..* ]] && jobid="${jobid}.0" 
    logid="${JOBLOGPREFIX}${entryname}/job.$jobid.err"
  fi
fi

# logid contains the file name
if [ ! -s "$logid" ]; then
  echo "Check Entry and Job IDs. File not found or zero length: $logid"
  exit 1
fi
[ -n "$VERBOSE" ] && echo -e "Available logs:\n`grep "======== gzip | uuencode =============" -B 1  /tmp/pilot_launcher.log | grep -v "======== gzip | uuencode =============" | grep -v "\-\-"`"
[ -n "$VERBOSE" ] && echo "Log $logoption from $logid:"

# TODO: I'd like to verify the output but am aftraid it may be too big (and being cut)
exec ${TOOLDIR}/${LOGNAME} $logid

