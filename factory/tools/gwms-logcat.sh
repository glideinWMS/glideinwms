#!/bin/bash
# Cat log GWMS files using tools

TOOLDIR=/usr/lib/python2.6/site-packages/glideinwms/factory/tools
JOBLOGROOTPREFIX=/var/log/gwms-factory/client
FEUSER=user_frontend
JOBLOGPREFIX=/var/log/gwms-factory/client/user_frontend/glidein_gfactory_instance/entry_
#server logs JOBLOGPREFIX=/var/log/gwms-factory/server/entry_
# TODO: substitute with a real temp file and delete after use (or print file name)
TMPLOG=/tmp/pilot_launcher.log.$UID

CONFIG_FNAME=/etc/gwms-factory/glideinWMS.xml


function help_msg {
  cat << EOF
$0 [options] LOG_TYPE LOGFILE
$0 [options] LOG_TYPE ENTRY [JOB_ID]
$0 -f URL [options] LOG_TYPE
$0 -r [options] LOG_TYPE JOB_ID
$0 -l
  LOG_TYPE HTCondor log to extract from the job logfile: 
           all (all logs), master, startd, starter, startdhistory, xml
  LOGFILE  Job log file (stderr from a glidein)
  ENTRY    Entry name
  JOB_ID   HTCondor job (glidein) id. By default picks the last job with a valid log file
  -v       verbose
  -h       print this message
  -l       list all entries (arguments are ignored)
  -a       list only entries that were active (has at least one job) - used with '-l', ignored otherwise
  -u USER  to use a different user (job owner) from the default frontend one
  -r       Remote running jobs. pilot_launcher.log is fetched form the VM 
  -c FNAME Factory configuration file (default: /etc/gwms-factory/glideinWMS.xml)
  -f URL   Forward the information (to a folder: file:///path/ via copy or a URL http:// via post)
EOF
}

function find_dirs {
  if [ ! -f "$TOOLDIR/cat_logs.py" ]; then 
    TOOLDIR="$(dirname "$(readlink -f $0)")"
    if [ ! -f "$TOOLDIR/cat_logs.py" ]; then 
      TOOLDIR=/usr/lib/python2.4/site-packages/glideinwms/factory/tools
    fi
    if [ ! -f "$TOOLDIR/cat_logs.py" ]; then 
      echo "Unable to find the directory with the factory tools."
      exit 1
    fi
  fi
  if [ ! -d "$JOBLOGROOTPREFIX" ]; then
    #    <submit base_client_log_dir="/var/log/gwms-factory/client" base_client_proxies_
    # log_dir=$(grep -E 'submit[ '$'\t'']+base_client_log_dir' | sed 's/.*base_client_log_dir="\(.*\)".*/\1/' )
    log_dir=$(grep -E 'submit[ '$'\t'']+base_client_log_dir' "$CONFIG_FNAME" | sed 's/.*base_client_log_dir="\([^"]*\)".*/\1/' )
    #if [ ! -d "${log_dir}/user_frontend/glidein_gfactory_instance" ]; then
    if [ ! -d "${log_dir}" ]; then
      echo "Unable to find the factory client log directory."
      exit 1
    fi
    JOBLOGROOTPREFIX="${log_dir}"
    #JOBLOGPREFIX="$JOBLOGROOTPREFIX/$FEUSER/glidein_gfactory_instance/entry_"
  fi
}

function get_last_log {
  # return last error log file
  echo "`find $1 -size +1 -name 'job*err' -printf '%T@ %p\n' | sort -nk1 | sed 's/^[^ ]* //' | tail -1`"
}

function list_all_entries {
  # list or forward entries depending on FORWARD_URL being defined
  ulist=`ls "$JOBLOGROOTPREFIX/"`
  if [ "$ulist" = "user_frontend" ]; then
    [ -n "$FORWARD_URL" ] && forward_entries || list_entries
    return
  fi
  echo "#USERS LIST:"
  echo "$ulist"
  for i in $ulist; do
    echo "#ENTRY LIST for USER: $i"
    JOBLOGPREFIX="$JOBLOGROOTPREFIX/$i/glidein_gfactory_instance/entry_"
    [ -n "$FORWARD_URL" ] && forward_entries || list_entries
  done
}

function list_entries {
  local elist=`ls -d $JOBLOGPREFIX*`
  for i in $elist; do
    entry_count="`ls $i/job*err 2>/dev/null | wc -l`"
    [ -n "$ACTIVE" ] && [ "$entry_count" -eq 0 ] && continue
    echo -n "$entry_count"
    echo -n " (`get_last_log $i`) "
    echo ${i#$JOBLOGPREFIX}
  done
}

function get_unique_name {
  # $1 file name 
  # $2 log type
  dir_name="`dirname $1`"
  file_name="`basename $1`"
  entry_part="`basename "$dir_name"`"
  log_type=$2
  [ -z "$log_type" ] && log_type="$logoption"
  # prefix-host-user?-entry-jobID-logType
  echo "job_log-`hostname`-${entry_part#entry_}-${file_name%.err}-$log_type"
}

function forward_file {
  # 1. file name (logid) 
  # 2. log type (logoption)
  # Using: LOGNAME was set using log type
  local logid=$1
  local logoption=$2
  if [ ! -s "$logid" ]; then
    echo "Check Entry and Job IDs. File not found or zero length: $logid"
    return 1
  fi
  if [[ "$FORWARD_URL" =~ file://.* ]]; then
    # If starts w/ file:// consider it an output directory
    ${TOOLDIR}/${LOGNAME} $logid > "${FORWARD_URL#file://}/`get_unique_name $logid $logoption`"
  elif [[ "$FORWARD_URL" =~ http://.* ]]; then
    # http:// URL trigger a post to the URL
    # TODO: elaborate more (e.g. use logstash to forward to elastic search)
    # TODO: may need to re-encode the file before sending it
    fname="$FORWARD_TMP_DIR/`get_unique_name $logid $logoption`"
    ${TOOLDIR}/${LOGNAME} $logid > "$fname"
    curl -F fname="`get_unique_name $logid $logoption`" -F logfile=@$fname $FORWARD_URL
  else
    echo "ERROR: Don't know how to handle $FORWARD_URL (for $i)"
  fi
}

FORWARD_STATS_FNAME=forwarding_stats_last_
function forward_entry {
  # 1. entry directory
  # 2. log option 
  local stats_fname="$1/$FORWARD_STATS_FNAME$2" 
  touch "${stats_fname}.new"
  date_opts=""
  if [ -f "$stats_fname" ]; then
    date_opts="-newer $stats_fname "
  fi
  FORWARD_TMP_DIR="`mktemp -d 2>/dev/null || mktemp -d -t 'mytmpdir'`"
  flist="`find "$1" -type f $date_opts -size +1 -name 'job*err' -printf '%T@ %p\n'  | sort -nk1 | sed 's/^[^ ]* //'`"
  for i in $flist; do
    forward_file "$i" "$2"
  done
  rm -r "$FORWARD_TMP_DIR"
  mv "${stats_fname}.new" "${stats_fname}"
}

function forward_entries {
  # Forwarding all the entries from a user
  # 1. entry name
  # Using: $logoption - log option
  local elist=`ls -d $JOBLOGPREFIX*`
  for i in $elist; do
    # forward all the info for that entry
    [ -n "$VERBOSE" ] && echo "Forwarding entry: ${i#$JOBLOGPREFIX}"
    forward_entry "$i" $logoption
  done
}


while getopts "lhc:o:u:f:rav" option
do
  case "${option}"
  in
  "h") help_msg; exit 0;;
  "v") VERBOSE=yes;;
  l) LIST_ENTRIES=yes;;
  r) REMOTE=yes;;
  c) CONFIG_FNAME=$OPTARG;;
  u) FEUSER=$OPTARG;;
  f) FORWARD_URL=$OPTARG;; 
  a) ACTIVE=yes
  esac
done

find_dirs
JOBLOGPREFIX="$JOBLOGROOTPREFIX/$FEUSER/glidein_gfactory_instance/entry_"

if [ -n "$LIST_ENTRIES" ]; then 
  list_all_entries 
  exit 0
fi 

if [ ! -d "${JOBLOGPREFIX%/entry_}" ]; then
  echo "Unable to find the factory client log directory for this user (${JOBLOGPREFIX%/entry_})."
  exit 1
fi

shift $((OPTIND-1))

logoption=$1
logid="$2"

[ -n "$FORWARD_URL" ] && logid=ALL

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
  startdhistory) LOGNAME=cat_StartdHistoryLog.py;;
  *) echo "Unknown LOG_TYPE: $logoption"; help_msg; exit 1;;
esac


if [ -n "$FORWARD_URL" ]; then
  # forward info using list_all_entries (after LOGNAME evaluation)
  list_all_entries
  exit 0
fi


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
[ -n "$VERBOSE" ] && echo -e "Available logs:\n`grep "======== gzip | uuencode =============" -B 1  "$logid" | grep -v "======== gzip | uuencode =============" | grep -v "\-\-"`"
[ -n "$VERBOSE" ] && echo "Log $logoption from $logid:"

# TODO: I'd like to verify the output but am aftraid it may be too big (and being cut)
exec ${TOOLDIR}/${LOGNAME} $logid

