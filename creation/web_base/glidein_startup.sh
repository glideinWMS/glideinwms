#!/bin/bash
#
# Project:
#   glideinWMS
#
# File Version: 
#

global_args="$@"

export LANG=C

function on_die {
        echo "Received kill signal... shutting down child processes" 1>&2
        ON_DIE=1
        kill %1
}

function ignore_signal {
        echo "Ignoring SIGHUP signal... Use SIGTERM or SIGINT to kill processes" 1>&2
}

function warn {
 echo `date` $@ 1>&2
}

function usage {
    echo "Usage: glidein_startup.sh <options>"
    echo "where <options> is:"
    echo "  -factory <name>             : name of this factory"
    echo "  -name <name>                : name of this glidein"
    echo "  -entry <name>               : name of this glidein entry"
    echo "  -clientname <name>          : name of the requesting client"
    echo "  -clientgroup <name>         : group name of the requesting client"
    echo "  -web <baseURL>              : base URL from where to fetch"
    echo "  -proxy <proxyURL>           : URL of the local proxy"
    echo "  -dir <dirID>                : directory ID (supports ., Condor, CONDOR, OSG, TMPDIR, AUTO)"
    echo "  -sign <sign>                : signature of the signature file"
    echo "  -signtype <id>              : type of signature (only sha1 supported for now)"
    echo "  -signentry <sign>           : signature of the entry signature file"
    echo "  -cluster <ClusterID>        : condorG ClusterId"
    echo "  -subcluster <ProcID>        : condorG ProcId"
    echo "  -submitcredid <CredentialID>: Credential ID of this condorG job"
    echo "  -schedd <name>              : condorG Schedd Name"
    echo "  -descript <fname>           : description file name"
    echo "  -descriptentry <fname>      : description file name for entry"
    echo "  -clientweb <baseURL>        : base URL from where to fetch client files"
    echo "  -clientwebgroup <baseURL>   : base URL from where to fetch client group files"
    echo "  -clientsign <sign>          : signature of the client signature file"
    echo "  -clientsigntype <id>        : type of client signature (only sha1 supported for now)"
    echo "  -clientsigngroup <sign>     : signature of the client group signature file"
    echo "  -clientdescript <fname>     : client description file name"
    echo "  -clientdescriptgroup <fname>: client description file name for group"
    echo "  -slotslayout <type>         : how Condor will set up slots (fixed, partitionable)"
    echo "  -v <id>                     : operation mode (std, nodebug, fast, check supported)"
    echo "  -param_* <arg>              : user specified parameters"
    exit 1
}


# params will contain the full list of parameters
# -param_XXX YYY will become "XXX YYY"
params=""

while [ $# -gt 0 ]
do case "$1" in
    -factory)    glidein_factory="$2";;
    -name)       glidein_name="$2";;
    -entry)      glidein_entry="$2";;
    -clientname) client_name="$2";;
    -clientgroup) client_group="$2";;
    -web)        repository_url="$2";;
    -proxy)      proxy_url="$2";;
    -dir)        work_dir="$2";;
    -sign)       sign_id="$2";;
    -signtype)   sign_type="$2";;
    -signentry)  sign_entry_id="$2";;
    -cluster)    condorg_cluster="$2";;
    -subcluster) condorg_subcluster="$2";;
    -submitcredid) glidein_cred_id="$2";;
    -schedd)     condorg_schedd="$2";;
    -descript)   descript_file="$2";;
    -descriptentry)   descript_entry_file="$2";;
    -clientweb)             client_repository_url="$2";;
    -clientwebgroup)        client_repository_group_url="$2";;
    -clientsign)            client_sign_id="$2";;
    -clientsigntype)        client_sign_type="$2";;
    -clientsigngroup)       client_sign_group_id="$2";;
    -clientdescript)        client_descript_file="$2";;
    -clientdescriptgroup)   client_descript_group_file="$2";;
    -slotslayout)			slots_layout="$2";;
    -v)          operation_mode="$2";;
    -param_*)    params="$params `echo $1 | awk '{print substr($0,8)}'` $2";;
    *)  (warn "Unknown option $1"; usage) 1>&2; exit 1
esac
shift
shift
done

# make sure we have a valid slots_layout
if (echo "x$slots_layout" | grep -i fixed) >/dev/null 2>&1 ; then
    slots_layout="fixed"
else
    slots_layout="partitionable"
fi

function python_b64uuencode {
    echo "begin-base64 644 -"
    python -c 'import binascii,sys;fd=sys.stdin;buf=fd.read();size=len(buf);idx=0
while size>57:
 print binascii.b2a_base64(buf[idx:idx+57]),;
 idx+=57;
 size-=57;
print binascii.b2a_base64(buf[idx:]),'
    echo "===="
}

function base64_b64uuencode {
    echo "begin-base64 644 -"
    base64 -
    echo "===="
}

# not all WNs have all the tools installed
function b64uuencode {
    which uuencode >/dev/null 2>&1
    if [ $? -eq 0 ]; then
	uuencode -m -
    else
	which base64 >/dev/null 2>&1
	if [ $? -eq 0 ]; then
	    base64_b64uuencode
	else
	    python_b64uuencode
	fi
    fi
}

function construct_xml {
  result="$1"

  glidein_end_time=`date +%s`

  echo "<?xml version=\"1.0\"?>
<OSGTestResult id=\"glidein_startup.sh\" version=\"4.3.1\">
  <operatingenvironment>
    <env name=\"cwd\">$start_dir</env>
  </operatingenvironment>
  <test>
    <cmd>$0 ${global_args}</cmd>
    <tStart>`date --date=@${startup_time} +%Y-%m-%dT%H:%M:%S%:z`</tStart>
    <tEnd>`date --date=@${glidein_end_time} +%Y-%m-%dT%H:%M:%S%:z`</tEnd>
  </test>
$result
</OSGTestResult>"
}


function extract_parent_fname {
  exitcode=$1

  if [ -s otrx_output.xml ]; then
      # file exists and is not 0 size
      last_result=`cat otrx_output.xml`
 
      if [ "$exitcode" -eq 0 ]; then
	  echo "SUCCESS"
      else
	  last_script_name=`echo "$last_result" |awk '/<OSGTestResult /{split($0,a,"id=\""); split(a[2],b,"\""); print b[1];}'`
	  echo ${last_script_name}
      fi
  else
      echo "Unknown" 
  fi
}

function extract_parent_xml_detail {
  exitcode=$1
  glidein_end_time=`date +%s`

  if [ -s otrx_output.xml ]; then
      # file exists and is not 0 size
      last_result=`cat otrx_output.xml`
 
      if [ "$exitcode" -eq 0 ]; then
	  echo "  <result>"
	  echo "    <status>OK</status>"
	  # propagate metrics as well
	  echo "$last_result" | grep '<metric '
	  echo "  </result>"
      else
	  last_script_name=`echo "$last_result" |awk '/<OSGTestResult /{split($0,a,"id=\""); split(a[2],b,"\""); print b[1];}'`

	  last_script_reason=`echo "$last_result" | awk 'BEGIN{fr=0;}/<[/]detail>/{fr=0;}{if (fr==1) print $0}/<detail>/{fr=1;}'`
	  my_reason="     Validation failed in $last_script_name.

$last_script_reason"

	  echo "  <result>"
	  echo "    <status>ERROR</status>
    <metric name=\"TestID\" ts=\"`date --date=@${glidein_end_time} +%Y-%m-%dT%H:%M:%S%:z`\" uri=\"local\">$last_script_name</metric>"
	  # propagate metrics as well (will include the failure metric)
	  echo "$last_result" | grep '<metric '
	  echo "  </result>"
	  echo "  <detail>
${my_reason}
  </detail>"
      fi
  else
      # create a minimal XML file, else
      echo "  <result>"
      if [ "$exitcode" -eq 0 ]; then
	  echo "    <status>OK</status>"
      else
	  echo "    <status>ERROR</status>"
	  echo "    <metric name=\"failure\" ts=\"`date --date=@${glidein_end_time} +%Y-%m-%dT%H:%M:%S%:z`\" uri=\"local\">Unknown</metric>"
      fi
      echo "  </result>
  <detail>
    No detail. Could not find source XML file.
  </detail>"
  fi
}

function basexml2simplexml {
  final_result="$1"

  # augment with node info
  echo "${final_result}" | awk 'BEGIN{fr=1;}{if (fr==1) print $0}/<operatingenvironment>/{fr=0;}'

  echo "    <env name=\"client_name\">$client_name</env>"
  echo "    <env name=\"client_group\">$client_group</env>"

  echo "    <env name=\"user\">`id -un`</env>"
  echo "    <env name=\"arch\">`uname -m`</env>"
  if [ -e '/etc/redhat-release' ]; then
      echo "    <env name=\"os\">`cat /etc/redhat-release`</env>"
  fi
  echo "    <env name=\"hostname\">`uname -n`</env>"

  echo "${final_result}" | awk 'BEGIN{fr=0;}{if (fr==1) print $0}/<operatingenvironment>/{fr=1;}'
}

function simplexml2longxml {
  final_result_simple="$1"
  global_result="$2"

  echo "${final_result_simple}" | awk 'BEGIN{fr=1;}{if (fr==1) print $0}/<OSGTestResult /{fr=0;}'

  if [ "${global_result}" != "" ]; then
      # subtests first, so it is more readable, when tailing
      echo '  <subtestlist>'
      echo '    <OSGTestResults>'
      echo "${global_result}" | awk '{print "      " $0}'
      echo '    </OSGTestResults>'
      echo '  </subtestlist>'
  fi

  echo "${final_result_simple}" | awk 'BEGIN{fr=0;}{if (fr==1) print $0}/<OSGTestResult /{fr=1;}/<operatingenvironment>/{fr=0;}'

  echo "    <env name=\"glidein_factory\">$glidein_factory</env>"
  echo "    <env name=\"glidein_name\">$glidein_name</env>"
  echo "    <env name=\"glidein_entry\">$glidein_entry</env>"
  echo "    <env name=\"condorg_cluster\">$condorg_cluster</env>"
  echo "    <env name=\"condorg_subcluster\">$condorg_subcluster</env>"
  echo "    <env name=\"glidein_credential_id\">$glidein_cred_id</env>"
  echo "    <env name=\"condorg_schedd\">$condorg_schedd</env>"

  echo "${final_result_simple}" | awk 'BEGIN{fr=0;}{if (fr==1) print $0}/<operatingenvironment>/{fr=1;}'
}

function print_tail {
  exit_code=$1
  final_result_simple="$2"
  final_result_long="$3"

  glidein_end_time=`date +%s`
  let total_time=$glidein_end_time-$startup_time
  echo "=== Glidein ending `date` ($glidein_end_time) with code ${exit_code} after $total_time ==="
 
  echo ""
  echo "=== XML description of glidein activity ==="
  echo  "${final_result_simple}" | grep -v "<cmd>"
  echo "=== End XML description of glidein activity ==="

  echo "" 1>&2
  echo "=== Encoded XML description of glidein activity ===" 1>&2
  echo "${final_result_long}" | gzip --stdout - | b64uuencode 1>&2
  echo "=== End encoded XML description of glidein activity ===" 1>&2
}

####################################
# Cleaup, print out message and exit
work_dir_created=0
glide_local_tmp_dir_created=0

# use this for early failures, when we cannot assume we can write to disk at all
# too bad we end up with some repeated code, but difficult to do better
function early_glidein_failure {
  error_msg="$1"

  warn "${error_msg}"

  sleep $sleep_time 
  # wait a bit in case of error, to reduce lost glideins

  glidein_end_time=`date +%s`
  result="    <metric name=\"failure\" ts=\"`date --date=@${glidein_end_time} +%Y-%m-%dT%H:%M:%S%:z`\" uri=\"local\">WN_RESOURCE</metric>
    <status>ERROR</status>
    <detail>
     $error_msg
    </detail>"

  final_result=`construct_xml "$result"`
  final_result_simple=`basexml2simplexml "${final_result}"`
  # have no global section
  final_result_long=`simplexml2longxml "${final_result_simple}" ""`
  
  cd "$start_dir"
  if [ "$work_dir_created" -eq "1" ]; then
    rm -fR "$work_dir"
  fi
  if [ "$glide_local_tmp_dir_created" -eq "1" ]; then
    rm -fR "$glide_local_tmp_dir"
  fi

  print_tail 1 "${final_result_simple}" "${final_result_long}"

  exit 1
}


# use this one once the most basic ops have been done
function glidein_exit {
  # lock file for whole machine 
  if [ "x$lock_file" != "x" ]; then
    rm -f $lock_file
  fi

  global_result=""
  if [ -f otr_outlist.list ]; then
      global_result=`cat otr_outlist.list`
      chmod u+w otr_outlist.list
  fi

  ge_last_script_name=`extract_parent_fname $1`
  result=`extract_parent_xml_detail $1`
  final_result=`construct_xml "$result"`

  # augment with node info
  final_result_simple=`basexml2simplexml "${final_result}"`

  # Create a richer version, too
  final_result_long=`simplexml2longxml "${final_result_simple}" "${global_result}"`

  if [ $1 -ne 0 ]; then
      report_failed=`grep -i "^GLIDEIN_Report_Failed " $glidein_config | awk '{print $2}'`

      if [ -z "$report_failed" ]; then
	  report_failed="NEVER"
      fi

      factory_report_failed=`grep -i "^GLIDEIN_Factory_Report_Failed " $glidein_config | awk '{print $2}'`

      if [ -z "$factory_report_failed" ]; then
          factory_collector=`grep -i "^GLIDEIN_Factory_Collector " $glidein_config | awk '{print $2}'`
          if [ -z "$factory_collector" ]; then
              # no point in enabling it if there are no collectors
              factory_report_failed="NEVER"
          else
              factory_report_failed="ALIVEONLY"
          fi
      fi

      do_report=0
      if [ "$report_failed" != "NEVER" ] || [ "$factory_report_failed" != "NEVER" ]; then
          do_report=1
      fi


      # wait a bit in case of error, to reduce lost glideins
      let "dl=`date +%s` + $sleep_time"
      dlf=`date --date="@$dl"`
      add_config_line "GLIDEIN_ADVERTISE_ONLY" "1"
      add_config_line "GLIDEIN_Failed" "True"
      add_config_line "GLIDEIN_EXIT_CODE" "$1"
      add_config_line "GLIDEIN_ToDie" "$dl"
      add_config_line "GLIDEIN_Expire" "$dl"
      add_config_line "GLIDEIN_LAST_SCRIPT" "${ge_last_script_name}"
      add_config_line "GLIDEIN_ADVERTISE_TYPE" "Retiring"

      add_config_line "GLIDEIN_FAILURE_REASON" "Glidein failed while running ${ge_last_script_name}. Keeping node busy until $dl ($dlf)."

      condor_vars_file=`grep -i "^CONDOR_VARS_FILE " $glidein_config | awk '{print $2}'`
      if [ -n "${condor_vars_file}" ]; then
         # if we are to advertise, this should be available... else, it does not matter anyhow
         add_condor_vars_line "GLIDEIN_ADVERTISE_ONLY" "C" "True" "+" "Y" "Y" "-"
         add_condor_vars_line "GLIDEIN_Failed" "C" "True" "+" "Y" "Y" "-"
         add_condor_vars_line "GLIDEIN_EXIT_CODE" "I" "-" "+" "Y" "Y" "-"
         add_condor_vars_line "GLIDEIN_ToDie" "I" "-" "+" "Y" "Y" "-"
         add_condor_vars_line "GLIDEIN_Expire" "I" "-" "+" "Y" "Y" "-"
	 add_condor_vars_line "GLIDEIN_LAST_SCRIPT" "S" "-" "+" "Y" "Y" "-"
         add_condor_vars_line "GLIDEIN_FAILURE_REASON" "S" "-" "+" "Y" "Y" "-"
      fi
      main_work_dir=`get_work_dir main`

      for ((t=`date +%s`; $t<$dl;t=`date +%s`))
      do
	if [ -e "${main_work_dir}/$last_script" ] && [ "$do_report" == "1" ] ; then
	    # if the file exists, we should be able to talk to the collectors
	    # notify that things went badly and we are waiting
            if [ "$factory_report_failed" != "NEVER" ]; then
                add_config_line "GLIDEIN_ADVERTISE_DESTINATION" "Factory"
                warn "Notifying Factory of error"
                "${main_work_dir}/$last_script" glidein_config
            fi
            if [ "$report_failed" != "NEVER" ]; then
                add_config_line "GLIDEIN_ADVERTISE_DESTINATION" "VO"
                warn "Notifying VO of error"
                "${main_work_dir}/$last_script" glidein_config
            fi
	fi

	# sleep for about 5 mins... but randomize a bit
	let "ds=250+$RANDOM%100"
	let "as=`date +%s` + $ds"
	if [ $as -gt $dl ]; then
	    # too long, shorten to the deadline
	    let "ds=$dl - `date +%s`"
	fi
        warn "Sleeping $ds"
	sleep $ds
      done

      if [ -e "${main_work_dir}/$last_script" ] && [ "$do_report" == "1" ]; then
	  # notify that things went badly and we are going away
          if [ "$factory_report_failed" != "NEVER" ]; then
              add_config_line "GLIDEIN_ADVERTISE_DESTINATION" "Factory"
              if [ "$factory_report_failed" == "ALIVEONLY" ]; then
                  add_config_line "GLIDEIN_ADVERTISE_TYPE" "INVALIDATE"
              else
                  add_config_line "GLIDEIN_ADVERTISE_TYPE" "Killing"
                  add_config_line "GLIDEIN_FAILURE_REASON" "Glidein failed while running ${ge_last_script_name}. Terminating now. ($dl) ($dlf)"
              fi
              "${main_work_dir}/$last_script" glidein_config
              warn "Last notification sent to Factory"
          fi
          if [ "$report_failed" != "NEVER" ]; then
              add_config_line "GLIDEIN_ADVERTISE_DESTINATION" "VO"
              if [ "$report_failed" == "ALIVEONLY" ]; then
                  add_config_line "GLIDEIN_ADVERTISE_TYPE" "INVALIDATE"
              else
                  add_config_line "GLIDEIN_ADVERTISE_TYPE" "Killing"
                  add_config_line "GLIDEIN_FAILURE_REASON" "Glidein failed while running ${ge_last_script_name}. Terminating now. ($dl) ($dlf)"
              fi
              "${main_work_dir}/$last_script" glidein_config
              warn "Last notification sent to VO"
          fi
      fi
  fi

  cd "$start_dir"
  if [ "$work_dir_created" -eq "1" ]; then
    rm -fR "$work_dir"
  fi
  if [ "$glide_local_tmp_dir_created" -eq "1" ]; then
    rm -fR "$glide_local_tmp_dir"
  fi

  print_tail $1 "${final_result_simple}" "${final_result_long}"

  exit $1
}

####################################################
# automatically determine and setup work directories
function automatic_work_dir {
    targets="$_CONDOR_SCRATCH_DIR $OSG_WN_TMP $TG_NODE_SCRATCH $TG_CLUSTER_SCRATCH $SCRATCH $TMPDIR $TMP $PWD"
    unset TMPDIR

    # kb
    disk_required=1000000

    for d in $targets; do

        echo "Checking $d for potential use as work space... " 1>&2

        # does the target exist?
        if [ ! -e $d ]; then
            echo "  Workdir: $d does not exist" 1>&2
            continue
        fi

        # make sure there is enough available diskspace
        #cd $d
        free=`df -kP $d | awk '{if (NR==2) print $4}'`
        if [ "x$free" == "x" -o $free -lt $disk_required ]; then
            echo "  Workdir: not enough disk space available in $d" 1>&2
            continue
        fi

        if touch $d/.dirtest.$$ >/dev/null 2>&1; then
            echo "  Workdir: $d selected" 1>&2
            rm -f $d/.dirtest.$$ >/dev/null 2>&1
            work_dir=$d
            return 0
        fi
        echo "  Workdir: not allowed to write to $d" 1>&2
    done
    return 1
}


# Create a script that defines add_config_line
#   and add_condor_vars_line
# This way other depending scripts can use it
function create_add_config_line {
    cat > "$1" << EOF

function warn {
 echo \`date\` \$@ 1>&2
}

###################################
# Add a line to the config file
# Arg: line to add, first element is the id
# Uses global variablr glidein_config
function add_config_line {
    rm -f \${glidein_config}.old #just in case one was there
    mv \$glidein_config \${glidein_config}.old
    if [ \$? -ne 0 ]; then
        warn "Error renaming \$glidein_config into \${glidein_config}.old"
        exit 1
    fi
    grep -v "^\$1 " \${glidein_config}.old > \$glidein_config
    echo "\$@" >> \$glidein_config
    rm -f \${glidein_config}.old
}

####################################
# Add a line to the condor_vars file
# Arg: line to add, first element is the id
# Uses global variablr condor_vars_file
function add_condor_vars_line {
    id=\$1

    rm -f \${condor_vars_file}.old #just in case one was there
    mv \$condor_vars_file \${condor_vars_file}.old
    if [ \$? -ne 0 ]; then
        warn "Error renaming \$condor_vars_file into \${condor_vars_file}.old"
        exit 1
    fi
    grep -v "^\$id\b" \${condor_vars_file}.old > \$condor_vars_file
    echo "\$@" >> \$condor_vars_file
    rm -f \${condor_vars_file}.old
}
EOF
}

# Create a script that defines various id based functions 
# This way other depending scripts can use it
function create_get_id_selectors {
    cat > "$1" << EOF
############################################
# Get entry/client/group work dir
# Arg: type (main/entry/client/client_group)
function get_work_dir {
    if [ "\$1" == "main" ]; then
        grep "^GLIDEIN_WORK_DIR " \${glidein_config} | awk '{print \$2}'
        return \$?
    elif [ "\$1" == "entry" ]; then
        grep "^GLIDEIN_ENTRY_WORK_DIR " \${glidein_config} | awk '{print \$2}'
        return \$?
    elif [ "\$1" == "client" ]; then
        grep "^GLIDECLIENT_WORK_DIR " \${glidein_config} | awk '{print \$2}'
        return \$?
    elif [ "\$1" == "client_group" ]; then
        grep "^GLIDECLIENT_GROUP_WORK_DIR " \${glidein_config} | awk '{print \$2}'
        return \$?
    fi
    echo "[get_work_dir] Invalid id: \$1" 1>&2
    return 1
}

################################################
# Get entry/client/group description file name
# Arg: type (main/entry/client/client_group)
function get_descript_file {
    if [ "\$1" == "main" ]; then
        grep "^DESCRIPTION_FILE " \${glidein_config} | awk '{print \$2}'
        return \$?
    elif [ "\$1" == "entry" ]; then
        grep "^DESCRIPTION_ENTRY_FILE " \${glidein_config} | awk '{print \$2}'
        return \$?
    elif [ "\$1" == "client" ]; then
        grep "^GLIDECLIENT_DESCRIPTION_FILE " \${glidein_config} | awk '{print \$2}'
        return \$?
    elif [ "\$1" == "client_group" ]; then
        grep "^GLIDECLIENT_DESCRIPTION_GROUP_FILE " \${glidein_config} | awk '{print \$2}'
        return \$?
    fi
    echo "[get_descript_file] Invalid id: \$1" 1>&2
    return 1
}

############################################
# Get entry/client/group signature
# Arg: type (main/entry/client/client_group)
function get_signature {
    if [ "\$1" == "main" ]; then
        grep "^GLIDEIN_Signature " \${glidein_config} | awk '{print \$2}'
        return \$?
    elif [ "\$1" == "entry" ]; then
        grep "^GLIDEIN_Entry_Signature " \${glidein_config} | awk '{print \$2}'
        return \$?
    elif [ "\$1" == "client" ]; then
        grep "^GLIDECLIENT_Signature " \${glidein_config} | awk '{print \$2}'
        return \$?
    elif [ "\$1" == "client_group" ]; then
        grep "^GLIDECLIENT_Group_Signature " \${glidein_config} | awk '{print \$2}'
        return \$?
    fi
    echo "[get_signature] Invalid id: \$1" 1>&2
    return 1
}

############################################
# Get entry/client/group prefix
# Arg: type (main/entry/client/client_group)
function get_prefix {
    if [ "\$1" == "main" ]; then
        echo ""
    elif [ "\$1" == "entry" ]; then
        echo "ENTRY_"
    elif [ "\$1" == "client" ]; then
        echo "GLIDECLIENT_"
    elif [ "\$1" == "client_group" ]; then
        echo "GLIDECLIENT_GROUP_"
    else
        echo "[get_prefix] Invalid id: \$1" 1>&2
        return 1
    fi
}

EOF
}

###################################
# Put parameters into the config file
function params2file {
    param_list=""

    while [ $# -gt 0 ]
    do
       pfval=`echo "$2" | sed\
 -e 's/\.nbsp,/ /g'\
 -e 's/\.semicolon,/;/g'\
 -e 's/\.colon,/:/g'\
 -e 's/\.tilde,/~/g'\
 -e 's/\.not,/!/g'\
 -e 's/\.question,/?/g'\
 -e 's/\.star,/*/g'\
 -e 's/\.dollar,/$/g'\
 -e 's/\.comment,/#/g'\
 -e 's/\.sclose,/]/g'\
 -e 's/\.sopen,/[/g'\
 -e 's/\.gclose,/}/g'\
 -e 's/\.gopen,/{/g'\
 -e 's/\.close,/)/g'\
 -e 's/\.open,/(/g'\
 -e 's/\.gt,/>/g'\
 -e 's/\.lt,/</g'\
 -e 's/\.minus,/-/g'\
 -e 's/\.plus,/+/g'\
 -e 's/\.eq,/=/g'\
 -e "s/\.singquot,/'/g"\
 -e 's/\.quot,/"/g'\
 -e 's/\.fork,/\`/g'\
 -e 's/\.pipe,/|/g'\
 -e 's/\.backslash,/\\\/g'\
 -e 's/\.amp,/\&/g'\
 -e 's/\.comma,/,/g'\
 -e 's/\.dot,/./g'`
	add_config_line "$1 $pfval"
        if [ $? -ne 0 ]; then
	    glidein_exit 1
	fi
	if [ -z "$param_list" ]; then
	    param_list="$1"
	else
	    param_list="${param_list},$1"
	fi
	shift;shift
    done
    echo "PARAM_LIST ${param_list}"
    return 0
}


################
# Parse arguments
set_debug=1
sleep_time=1199
if [ "$operation_mode" == "nodebug" ]; then
 set_debug=0
elif [ "$operation_mode" == "fast" ]; then
 sleep_time=150
 set_debug=1
elif [ "$operation_mode" == "check" ]; then
 sleep_time=150
 set_debug=2
fi
 
if [ -z "$descript_file" ]; then
    warn "Missing descript fname." 1>&2
    usage
fi

if [ -z "$descript_entry_file" ]; then
    warn "Missing descript fname for entry." 1>&2
    usage
fi

if [ -z "$glidein_name" ]; then
    warn "Missing gliden name." 1>&2
    usage
fi

if [ -z "$glidein_entry" ]; then
    warn "Missing glidein entry name." 1>&2
    usage
fi


if [ -z "$repository_url" ]; then
    warn "Missing Web URL." 1>&2
    usage
fi

repository_entry_url="${repository_url}/entry_${glidein_entry}"

if [ -z "$proxy_url" ]; then
  proxy_url="None"
fi

if [ "$proxy_url" == "OSG" ]; then
  if [ -z "$OSG_SQUID_LOCATION" ]; then
     # if OSG does not define a Squid, then don't use any
     proxy_url="None"
     warn "OSG_SQUID_LOCATION undefined, not using any Squid URL" 1>&2
  else
     proxy_url=`echo $OSG_SQUID_LOCATION |awk -F ':' '{if ($2 =="") {print $1 ":3128"} else {print $0}}'`
  fi
fi

if [ -z "$sign_id" ]; then
    warn "Missing signature." 1>&2
    usage
fi

if [ -z "$sign_entry_id" ]; then
    warn "Missing entry signature." 1>&2
    usage
fi

if [ -z "$sign_type" ]; then
    sign_type="sha1"
fi

if [ "$sign_type" == "sha1" ]; then
    sign_sha1="$sign_id"
    sign_entry_sha1="$sign_entry_id"
else
    warn "Unsupported signtype $sign_type found." 1>&2
    usage
fi
    
if [ -n "$client_repository_url" ]; then
  # client data is optional, user url as a switch
  if [ -z "$client_sign_type" ]; then
      client_sign_type="sha1"
  fi

  if [ "$client_sign_type" == "sha1" ]; then
    client_sign_sha1="$client_sign_id"
  else
    warn "Unsupported clientsigntype $client_sign_type found." 1>&2
    usage
  fi
    
  if [ -z "$client_descript_file" ]; then
    warn "Missing client descript fname." 1>&2
    usage
  fi

  if [ -n "$client_repository_group_url" ]; then
      # client group data is optional, user url as a switch
      if [ -z '$client_group' ]; then
	  warn "Missing client group name." 1>&2
	  usage
      fi

      if [ -z "$client_descript_group_file" ]; then
	  warn "Missing client descript fname for group." 1>&2
	  usage
      fi

      if [ "$client_sign_type" == "sha1" ]; then
	  client_sign_group_sha1="$client_sign_group_id"
      else
	  warn "Unsupported clientsigntype $client_sign_type found." 1>&2
	  usage
      fi
  fi
fi

startup_time=`date +%s`
echo "Starting glidein_startup.sh at `date` ($startup_time)"
echo "debug_mode        = '$operation_mode'"
echo "condorg_cluster   = '$condorg_cluster'"
echo "condorg_subcluster= '$condorg_subcluster'"
echo "condorg_schedd    = '$condorg_schedd'"
echo "glidein_credential_id = '$glidein_cred_id'"
echo "glidein_factory   = '$glidein_factory'"
echo "glidein_name      = '$glidein_name'"
echo "glidein_entry     = '$glidein_entry'"
if [ -n '$client_name' ]; then
    # client name not required as it is not used for anything but debug info
    echo "client_name       = '$client_name'"
fi
if [ -n '$client_group' ]; then
    echo "client_group       = '$client_group'"
fi
echo "work_dir          = '$work_dir'"
echo "web_dir           = '$repository_url'"
echo "sign_type         = '$sign_type'"
echo "proxy_url         = '$proxy_url'"
echo "descript_fname    = '$descript_file'"
echo "descript_entry_fname = '$descript_entry_file'"
echo "sign_id           = '$sign_id'"
echo "sign_entry_id     = '$sign_entry_id'"
if [ -n "$client_repository_url" ]; then
    echo "client_web_dir              = '$client_repository_url'"
    echo "client_descript_fname       = '$client_descript_file'"
    echo "client_sign_type            = '$client_sign_type'"
    echo "client_sign_id              = '$client_sign_id'"
    if [ -n "$client_repository_group_url" ]; then
	echo "client_web_group_dir        = '$client_repository_group_url'"
	echo "client_descript_group_fname = '$client_descript_group_file'"
	echo "client_sign_group_id        = '$client_sign_group_id'"
    fi
fi
echo
echo "Running on `uname -n`"
echo "System: `uname -a`"
if [ -e '/etc/redhat-release' ]; then
 echo "Release: `cat /etc/redhat-release 2>&1`"
fi
echo "As: `id`"
echo "PID: $$"
echo

if [ $set_debug -ne 0 ]; then
  echo "------- Initial environment ---------------"  1>&2
  env 1>&2
  echo "------- =================== ---------------" 1>&2
fi

########################################
# make sure nobody else can write my files
# In the Grid world I cannot trust anybody
umask 0022
if [ $? -ne 0 ]; then
    early_glidein_failure "Failed in umask 0022"
fi

########################################
# Setup OSG and/or Globus
if [ -r "$OSG_GRID/setup.sh" ]; then
    . "$OSG_GRID/setup.sh"
else
  if [ -r "${GLITE_LOCAL_CUSTOMIZATION_DIR}/cp_1.sh" ]; then
    . "${GLITE_LOCAL_CUSTOMIZATION_DIR}/cp_1.sh"
  fi
fi

if [ -z "$GLOBUS_PATH" ]; then
  if [ -z "$GLOBUS_LOCATION" ]; then
    # if GLOBUS_LOCATION not defined, try to guess it
    if [ -r "/opt/globus/etc/globus-user-env.sh" ]; then
       GLOBUS_LOCATION=/opt/globus
    elif  [ -r "/osgroot/osgcore/globus/etc/globus-user-env.sh" ]; then
       GLOBUS_LOCATION=/osgroot/osgcore/globus
    else
       warn "GLOBUS_LOCATION not defined and could not guess it." 1>&2
       warn "Looked in:" 1>&2
       warn ' /opt/globus/etc/globus-user-env.sh' 1>&2
       warn ' /osgroot/osgcore/globus/etc/globus-user-env.sh' 1>&2
       warn 'Continuing like nothing happened' 1>&2
    fi
  fi

  if [ -r "$GLOBUS_LOCATION/etc/globus-user-env.sh" ]; then
    . "$GLOBUS_LOCATION/etc/globus-user-env.sh"
  else
    warn "GLOBUS_PATH not defined and $GLOBUS_LOCATION/etc/globus-user-env.sh does not exist." 1>&2
    warn 'Continuing like nothing happened' 1>&2
  fi
fi

function set_proxy_fullpath {
    # Set the X509_USER_PROXY path to full path to the file
    fullpath="`readlink -f $X509_USER_PROXY`"
    if [ $? -eq 0 ]; then
        echo "Setting X509_USER_PROXY $X09_USER_PROXY to canonical path $fullpath" 1>&2
        export X509_USER_PROXY="$fullpath"
    else
        echo "Unable to get canonical path for X509_USER_PROXY, using $X09_USER_PROXY" 1>&2
    fi
}


[ -n "$X509_USER_PROXY" ] && set_proxy_fullpath

########################################
# prepare and move to the work directory
if [ "$work_dir" == "Condor" ]; then
    work_dir="$_CONDOR_SCRATCH_DIR"
elif [ "$work_dir" == "CONDOR" ]; then
    work_dir="$_CONDOR_SCRATCH_DIR"
elif [ "$work_dir" == "OSG" ]; then
    work_dir="$OSG_WN_TMP"
elif [ "$work_dir" == "TMPDIR" ]; then
    work_dir="$TMPDIR"
elif [ "$work_dir" == "AUTO" ]; then
    automatic_work_dir
elif [ "$work_dir" == "." ]; then
    work_dir=`pwd`
elif [ -z "$work_dir" ]; then
    work_dir=`pwd`
fi

if [ -z "$work_dir" ]; then
    early_glidein_failure "Startup dir is empty."
fi

if [ -e "$work_dir" ]; then
    echo >/dev/null
else
    early_glidein_failure "Startup dir $work_dir does not exist."
fi

start_dir=`pwd`
echo "Started in $start_dir"

def_work_dir="$work_dir/glide_XXXXXX"
work_dir=`mktemp -d "$def_work_dir"`
if [ $? -ne 0 ]; then
    early_glidein_failure "Cannot create temp '$def_work_dir'"
else
    cd "$work_dir"
    if [ $? -ne 0 ]; then
	early_glidein_failure "Dir '$work_dir' was created but I cannot cd into it."
    else
	echo "Running in $work_dir"
    fi
fi
work_dir_created=1

# mktemp makes it user readable by definition (ignores umask)
chmod a+rx "$work_dir"
if [ $? -ne 0 ]; then
    early_glidein_failure "Failed chmod '$work_dir'"
fi

def_glide_local_tmp_dir="/tmp/glide_`id -u -n`_XXXXXX"
glide_local_tmp_dir=`mktemp -d "$def_glide_local_tmp_dir"`
if [ $? -ne 0 ]; then
    early_glidein_failure "Cannot create temp '$def_glide_local_tmp_dir'"
fi
glide_local_tmp_dir_created=1

# the tmpdir should be world writable
# This way it will work even if the user spawned by the glidein is different
# than the glidein user
chmod 1777 "$glide_local_tmp_dir"
if [ $? -ne 0 ]; then
    early_glidein_failure "Failed chmod '$glide_local_tmp_dir'"
fi

glide_tmp_dir="${work_dir}/tmp"
mkdir "$glide_tmp_dir"
if [ $? -ne 0 ]; then
    early_glidein_failure "Cannot create '$glide_tmp_dir'"
fi
# the tmpdir should be world writable
# This way it will work even if the user spawned by the glidein is different
# than the glidein user
chmod 1777 "$glide_tmp_dir"
if [ $? -ne 0 ]; then
    early_glidein_failure "Failed chmod '$glide_tmp_dir'"
fi

short_main_dir=main
main_dir="${work_dir}/${short_main_dir}"
mkdir "$main_dir"
if [ $? -ne 0 ]; then
    early_glidein_failure "Cannot create '$main_dir'"
fi

short_entry_dir=entry_${glidein_entry}
entry_dir="${work_dir}/${short_entry_dir}"
mkdir "$entry_dir"
if [ $? -ne 0 ]; then
    early_glidein_failure "Cannot create '$entry_dir'"
fi

if [ -n "$client_repository_url" ]; then
    short_client_dir=client
    client_dir="${work_dir}/${short_client_dir}"
    mkdir "$client_dir"
    if [ $? -ne 0 ]; then
	early_glidein_failure "Cannot create '$client_dir'"
    fi

    if [ -n "$client_repository_group_url" ]; then
	short_client_group_dir=client_group_${client_group}
	client_group_dir="${work_dir}/${short_client_group_dir}"
	mkdir "$client_group_dir"
	if [ $? -ne 0 ]; then
	    early_glidein_failure "Cannot create '$client_group_dir'"
	fi
    fi
fi

create_add_config_line add_config_line.source
source add_config_line.source

create_get_id_selectors get_id_selectors.source
source get_id_selectors.source

wrapper_list="$PWD/wrapper_list.lst"
touch $wrapper_list

# create glidein_config
glidein_config="$PWD/glidein_config"
echo > glidein_config
if [ $? -ne 0 ]; then
    early_glidein_failure "Could not create '$glidein_config'"
fi
echo "# --- glidein_startup vals ---" >> glidein_config
echo "GLIDEIN_Factory $glidein_factory" >> glidein_config
echo "GLIDEIN_Name $glidein_name" >> glidein_config
echo "GLIDEIN_Entry_Name $glidein_entry" >> glidein_config
if [ -n '$client_name' ]; then
    # client name not required as it is not used for anything but debug info
    echo "GLIDECLIENT_Name $client_name" >> glidein_config
fi
if [ -n '$client_group' ]; then
    # client group not required as it is not used for anything but debug info
    echo "GLIDECLIENT_Group $client_group" >> glidein_config
fi
echo "GLIDEIN_CredentialIdentifier $glidein_cred_id" >> glidein_config
echo "CONDORG_CLUSTER $condorg_cluster" >> glidein_config
echo "CONDORG_SUBCLUSTER $condorg_subcluster" >> glidein_config
echo "CONDORG_SCHEDD $condorg_schedd" >> glidein_config
echo "DEBUG_MODE $set_debug" >> glidein_config
echo "GLIDEIN_STARTUP_PID $$" >> glidein_config 
echo "GLIDEIN_WORK_DIR $main_dir" >> glidein_config
echo "GLIDEIN_ENTRY_WORK_DIR $entry_dir" >> glidein_config
echo "TMP_DIR $glide_tmp_dir" >> glidein_config
echo "GLIDEIN_LOCAL_TMP_DIR $glide_local_tmp_dir" >> glidein_config
echo "PROXY_URL $proxy_url" >> glidein_config
echo "DESCRIPTION_FILE $descript_file" >> glidein_config
echo "DESCRIPTION_ENTRY_FILE $descript_entry_file" >> glidein_config
echo "GLIDEIN_Signature $sign_id" >> glidein_config
echo "GLIDEIN_Entry_Signature $sign_entry_id" >> glidein_config
if [ -n "$client_repository_url" ]; then
    echo "GLIDECLIENT_WORK_DIR $client_dir" >> glidein_config
    echo "GLIDECLIENT_DESCRIPTION_FILE $client_descript_file" >> glidein_config
    echo "GLIDECLIENT_Signature $client_sign_id" >> glidein_config
    if [ -n "$client_repository_group_url" ]; then
	echo "GLIDECLIENT_GROUP_WORK_DIR $client_group_dir" >> glidein_config
	echo "GLIDECLIENT_DESCRIPTION_GROUP_FILE $client_descript_group_file" >> glidein_config
	echo "GLIDECLIENT_Group_Signature $client_sign_group_id" >> glidein_config
    fi
fi
echo "ADD_CONFIG_LINE_SOURCE $PWD/add_config_line.source" >> glidein_config
echo "GET_ID_SELECTORS_SOURCE $PWD/get_id_selectors.source" >> glidein_config
echo "WRAPPER_LIST $wrapper_list" >> glidein_config
echo "SLOTS_LAYOUT $slots_layout" >> glidein_config
# Add a line saying we are still initializing
echo "GLIDEIN_INITIALIZED 0" >> glidein_config
# but be optimist, and leave advertise_only for the actual error handling script
echo "GLIDEIN_ADVERTISE_ONLY 0" >> glidein_config
echo "# --- User Parameters ---" >> glidein_config
if [ $? -ne 0 ]; then
    # we should probably be testing all others as well, but this is better than nothing
    early_glidein_failure "Failed in updating '$glidein_config'"
fi
params2file $params

###################################
# Find out what kind of wget I have

wget_nocache_flag=""
wget --help |grep -q "\-\-no-cache "
if [ $? -eq 0 ]; then
  wget_nocache_flag="--no-cache"
else
  wget --help |grep -q "\-\-cache="
  if [ $? -eq 0 ]; then
    wget_nocache_flag="--cache=off"
  else
    warn "Unknown kind of wget, cannot disable caching" 1>&2
  fi
fi

############################################
# get the proper descript file based on id
# Arg: type (main/entry/client/client_group)
function get_repository_url {
    if [ "$1" == "main" ]; then
	echo $repository_url
    elif [ "$1" == "entry" ]; then
	echo $repository_entry_url
    elif [ "$1" == "client" ]; then
	echo $client_repository_url
    elif [ "$1" == "client_group" ]; then
	echo $client_repository_group_url
    else
	echo "[get_repository_url] Invalid id: $1" 1>&2
	return 1
    fi
}

#####################
# Check signature
function check_file_signature {
    cfs_id="$1"
    cfs_fname="$2"

    cfs_work_dir=`get_work_dir $cfs_id`

    cfs_desc_fname="${cfs_work_dir}/$cfs_fname"
    cfs_signature="${cfs_work_dir}/signature.sha1"

    if [ $check_signature -gt 0 ]; then # check_signature is global for simplicity
	tmp_signname="${cfs_signature}_$$_`date +%s`_$RANDOM"
	grep " $cfs_fname$" "$cfs_signature" > $tmp_signname
	if [ $? -ne 0 ]; then
	    rm -f $tmp_signname
	    echo "No signature for $cfs_desc_fname." 1>&2
	else
	    (cd "$cfs_work_dir" && sha1sum -c "$tmp_signname") 1>&2
	    cfs_rc=$?
	    if [ $cfs_rc -ne 0 ]; then
		$main_dir/error_augment.sh -init
		$main_dir/error_gen.sh -error "check_file_signature" "Corruption" "File $cfs_desc_fname is corrupted." "file" "$cfs_desc_fname" "source_type" "$cfs_id"
		$main_dir/error_augment.sh  -process $cfs_rc "check_file_signature" "$PWD" "sha1sum -c $tmp_signname" "`date +%s`" "`date +%s`"
		$main_dir/error_augment.sh -concat
		warn "File $cfs_desc_fname is corrupted." 1>&2
		rm -f $tmp_signname
		return 1
	    fi
	    rm -f $tmp_signname
	    echo "Signature OK for ${cfs_id}:${cfs_fname}." 1>&2
	fi
    fi
    return 0
}

#####################
# Untar support func

function get_untar_subdir {
    gus_id="$1"
    gus_fname="$2"

    gus_prefix=`get_prefix $gus_id`
    gus_config_cfg="${gus_prefix}UNTAR_CFG_FILE"

    gus_config_file=`grep "^$gus_config_cfg " glidein_config | awk '{print $2}'`
    if [ -z "$gus_config_file" ]; then
	warn "Error, cannot find '$gus_config_cfg' in glidein_config." 1>&2
	glidein_exit 1
    fi

    gus_dir=`grep -i "^$gus_fname " $gus_config_file | awk '{print $2}'`
    if [ -z "$gus_dir" ]; then
	warn "Error, untar dir for '$gus_fname' cannot be empty." 1>&2
	glidein_exit 1
    fi

    echo "$gus_dir"
    return 0
}

#####################
# Fetch a single file
function fetch_file_regular {
    fetch_file "$1" "$2" "$2" "regular" "TRUE" "FALSE"
}

function fetch_file {
    if [ $# -ne 6 ]; then
	warn "Not enough arguments in fetch_file $@" 1>&2
	glidein_exit 1
    fi

    fetch_file_try "$1" "$2" "$3" "$4" "$5" "$6"
    if [ $? -ne 0 ]; then
	glidein_exit 1
    fi
    return 0
}

function fetch_file_try {
    fft_id="$1"
    fft_target_fname="$2"
    fft_real_fname="$3"
    fft_file_type="$4"
    fft_config_check="$5"
    fft_config_out="$6"

    if [ "$fft_config_check" == "TRUE" ]; then
	# TRUE is a special case
	fft_get_ss=1
    else
	fft_get_ss=`grep -i "^$fft_config_check " glidein_config | awk '{print $2}'`
    fi

    if [ "$fft_get_ss" == "1" ]; then
       fetch_file_base "$fft_id" "$fft_target_fname" "$fft_real_fname" "$fft_file_type" "$fft_config_out"
       fft_rc=$?
    fi

    return $fft_rc
}

function fetch_file_base {
    ffb_id="$1"
    ffb_target_fname="$2"
    ffb_real_fname="$3"
    ffb_file_type="$4"
    ffb_config_out="$5"

    ffb_work_dir=`get_work_dir $ffb_id`

    ffb_repository=`get_repository_url $ffb_id`

    ffb_tmp_outname="$ffb_work_dir/$ffb_real_fname"
    ffb_outname="$ffb_work_dir/$ffb_target_fname"
    ffb_desc_fname="$ffb_work_dir/$fname"
    ffb_signature="$ffb_work_dir/signature.sha1"


    ffb_nocache_str=""
    if [ "$ffb_file_type" == "nocache" ]; then
          ffb_nocache_str="$wget_nocache_flag"
    fi

    # Create a dummy default in case something goes wrong
    # cannot use error_*.sh helper functions
    # may not have been loaded yet
    have_dummy_otrx=1
    echo "<?xml version=\"1.0\"?>
<OSGTestResult id=\"fetch_file_base\" version=\"4.3.1\">
  <operatingenvironment>
    <env name=\"cwd\">$PWD</env>
  </operatingenvironment>
  <test>
    <cmd>Unknown</cmd>
    <tStart>`date +%Y-%m-%dT%H:%M:%S%:z`</tStart>
    <tEnd>`date +%Y-%m-%dT%H:%M:%S%:z`</tEnd>
  </test>
  <result>
    <status>ERROR</status>
    <metric name=\"failure\" ts=\"`date +%Y-%m-%dT%H:%M:%S%:z`\" uri=\"local\">Unknown</metric>
    <metric name=\"source_type\" ts=\"`date +%Y-%m-%dT%H:%M:%S%:z`\" uri=\"local\">$ffb_id</metric>
  </result>
  <detail>
     An unknown error occured.
  </detail>
</OSGTestResult>" > otrx_output.xml

    # download file
    if [ "$proxy_url" == "None" ]; then # no Squid defined, use the defaults
	START=`date +%s`
	wget --user-agent="wget/glidein/$glidein_entry/$condorg_schedd/$condorg_cluster.$condorg_subcluster/$client_name" $ffb_nocache_str -q  -O "$ffb_tmp_outname" "$ffb_repository/$ffb_real_fname"
	if [ $? -ne 0 ]; then
	    # cannot use error_*.sh helper functions
	    # may not have been loaded yet, and wget fails often
	    echo "<OSGTestResult id=\"wget\" version=\"4.3.1\">
  <operatingenvironment>
    <env name=\"cwd\">$PWD</env>
  </operatingenvironment>
  <test>
    <cmd>wget --user-agent=\"wget/glidein/$glidein_entry/$condorg_schedd/$condorg_cluster.$condorg_subcluster/$client_name\" $ffb_nocache_str -q  -O \"$ffb_tmp_outname\" \"$ffb_repository/$ffb_real_fname\"</cmd>
    <tStart>`date --date=@$START +%Y-%m-%dT%H:%M:%S%:z`</tStart>
    <tEnd>`date +%Y-%m-%dT%H:%M:%S%:z`</tEnd>
  </test>
  <result>
    <status>ERROR</status>
    <metric name=\"failure\" ts=\"`date --date=@$START +%Y-%m-%dT%H:%M:%S%:z`\" uri=\"local\">Network</metric>
    <metric name=\"URL\" ts=\"`date --date=@$START +%Y-%m-%dT%H:%M:%S%:z`\" uri=\"local\">$ffb_repository/$ffb_real_fname</metric>
    <metric name=\"source_type\" ts=\"`date --date=@$START +%Y-%m-%dT%H:%M:%S%:z`\" uri=\"local\">$ffb_id</metric>
  </result>
  <detail>
     Failed to load file '$ffb_real_fname' from '$ffb_repository'.
  </detail>
</OSGTestResult>" > otrb_output.xml
	    warn "Failed to load file '$ffb_real_fname' from '$ffb_repository'." 1>&2

	    if [ -f otr_outlist.list ]; then
		chmod u+w otr_outlist.list
	    else
		touch otr_outlist.list
	    fi
	    cat otrb_output.xml >> otr_outlist.list
	    echo "<?xml version=\"1.0\"?>
`cat otrb_output.xml`">otrx_output.xml
	    rm -f otrb_output.xml
	    chmod a-w otr_outlist.list
	    return 1
	fi
    else  # I have a Squid
	START=`date +%s`
	env http_proxy=$proxy_url wget --user-agent="wget/glidein/$glidein_entry/$condorg_schedd/$condorg_cluster.$condorg_subcluster/$client_name" $ffb_nocache_str -q  -O "$ffb_tmp_outname" "$ffb_repository/$ffb_real_fname" 
	if [ $? -ne 0 ]; then
	    # if Squid fails exit, because real jobs can try to use it too
	    # cannot use error_*.sh helper functions
	    # may not have been loaded yet, and wget fails often
	    echo "<OSGTestResult id=\"wget\" version=\"4.3.1\">
  <operatingenvironment>
    <env name=\"cwd\">$PWD</env>
  </operatingenvironment>
  <test>
    <cmd>env http_proxy=$proxy_url wget --user-agent=\"wget/glidein/$glidein_entry/$condorg_schedd/$condorg_cluster.$condorg_subcluster/$client_name\" $ffb_nocache_str -q  -O \"$ffb_tmp_outname\" \"$ffb_repository/$ffb_real_fname\"</cmd>
    <tStart>`date --date=@$START +%Y-%m-%dT%H:%M:%S%:z`</tStart>
    <tEnd>`date +%Y-%m-%dT%H:%M:%S%:z`</tEnd>
  </test>
  <result>
    <status>ERROR</status>
    <metric name=\"failure\" ts=\"`date --date=@$START +%Y-%m-%dT%H:%M:%S%:z`\" uri=\"local\">Network</metric>
    <metric name=\"URL\" ts=\"`date --date=@$START +%Y-%m-%dT%H:%M:%S%:z`\" uri=\"local\">$ffb_repository/$ffb_real_fname</metric>
    <metric name=\"http_proxy\" ts=\"`date --date=@$START +%Y-%m-%dT%H:%M:%S%:z`\" uri=\"local\">$proxy_url</metric>
    <metric name=\"source_type\" ts=\"`date --date=@$START +%Y-%m-%dT%H:%M:%S%:z`\" uri=\"local\">$ffb_id</metric>
  </result>
  <detail>
    Failed to load file '$ffb_real_fname' from '$ffb_repository' using proxy '$proxy_url'.
  </detail>
</OSGTestResult>" > otrb_output.xml
	    warn "Failed to load file '$ffb_real_fname' from '$ffb_repository' using proxy '$proxy_url'." 1>&2

	    if [ -f otr_outlist.list ]; then
		chmod u+w otr_outlist.list
	    else
		touch otr_outlist.list
	    fi
	    cat otrb_output.xml >> otr_outlist.list
	    echo "<?xml version=\"1.0\"?>
`cat otrb_output.xml`">otrx_output.xml
	    rm -f otrb_output.xml
	    chmod a-w otr_outlist.list
	    return 1
	fi
    fi

    # check signature
    check_file_signature "$ffb_id" "$ffb_real_fname"
    if [ $? -ne 0 ]; then
	# error already displayed inside the function
	return 1
    fi

    # rename it to the correct final name, if needed
    if [ "$ffb_tmp_outname" != "$ffb_outname" ]; then
      mv "$ffb_tmp_outname" "$ffb_outname"
      if [ $? -ne 0 ]; then
	  warn "Failed to rename $ffb_tmp_outname into $ffb_outname" 1>&2
	  return 1
      fi
    fi

    # if executable, execute
    if [ "$ffb_file_type" == "exec" ]; then
	chmod u+x "$ffb_outname"
	if [ $? -ne 0 ]; then
	    warn "Error making '$ffb_outname' executable" 1>&2
	    return 1
	fi
	if [ "$ffb_id" == "main" -a "$ffb_target_fname" == "$last_script" ]; then # last_script global for simplicity
	    echo "Skipping last script $last_script" 1>&2
	else
            echo "Executing $ffb_outname"
	    # have to do it here, as this will be run before any other script
            chmod u+rx $main_dir/error_augment.sh

	    # the XML file will be overwritten now, and hopefully not an error situation
            have_dummy_otrx=0
	    $main_dir/error_augment.sh -init
            START=`date +%s`
	    "$ffb_outname" glidein_config "$ffb_id"
	    ret=$?
            END=`date +%s`
            $main_dir/error_augment.sh  -process $ret "$ffb_id/$ffb_target_fname" "$PWD" "$ffb_outname glidein_config" "$START" "$END" #generating test result document
	    $main_dir/error_augment.sh -concat
	    if [ $ret -ne 0 ]; then
                echo "=== Validation error in $ffb_outname ===" 1>&2
		warn "Error running '$ffb_outname'" 1>&2
		cat otrx_output.xml | awk 'BEGIN{fr=0;}/<[/]detail>/{fr=0;}{if (fr==1) print $0}/<detail>/{fr=1;}' 1>&2
		return 1
	    fi
	fi
    elif [ "$ffb_file_type" == "wrapper" ]; then
	echo "$ffb_outname" >> "$wrapper_list"
    elif [ "$ffb_file_type" == "untar" ]; then
	ffb_short_untar_dir=`get_untar_subdir "$ffb_id" "$ffb_target_fname"`
	ffb_untar_dir="${ffb_work_dir}/${ffb_short_untar_dir}"
	START=`date +%s`
	(mkdir "$ffb_untar_dir" && cd "$ffb_untar_dir" && tar -xmzf "$ffb_outname") 1>&2
	ret=$?
	if [ $ret -ne 0 ]; then
	    $main_dir/error_augment.sh -init
	    $main_dir/error_gen.sh -error "tar" "Corruption" "Error untarring '$ffb_outname'" "file" "$ffb_outname" "source_type" "$cfs_id"
	    $main_dir/error_augment.sh  -process $cfs_rc "tar" "$PWD" "mkdir $ffb_untar_dir && cd $ffb_untar_dir && tar -xmzf $ffb_outname" "$START" "`date +%s`"
	    $main_dir/error_augment.sh -concat
	    warn "Error untarring '$ffb_outname'" 1>&2
	    return 1
	fi
    fi

    if [ "$ffb_config_out" != "FALSE" ]; then
	ffb_prefix=`get_prefix $ffb_id`
	if [ "$ffb_file_type" == "untar" ]; then
	    # when untaring the original file is less interesting than the untar dir
	    add_config_line "${ffb_prefix}${ffb_config_out}" "$ffb_untar_dir"
	    if [ $? -ne 0 ]; then
		glidein_exit 1
	    fi
	else
	    add_config_line "${ffb_prefix}${ffb_config_out}" "$ffb_outname"
	    if [ $? -ne 0 ]; then
		glidein_exit 1
	    fi
	fi

    fi

    if [ "$have_dummy_otrx" -eq 1 ]; then
        # noone should really look at this file, but just to avoid confusion
	echo "<?xml version=\"1.0\"?>
<OSGTestResult id=\"fetch_file_base\" version=\"4.3.1\">
  <operatingenvironment>
    <env name=\"cwd\">$PWD</env>
  </operatingenvironment>
  <test>
    <cmd>Unknown</cmd>
    <tStart>`date +%Y-%m-%dT%H:%M:%S%:z`</tStart>
    <tEnd>`date +%Y-%m-%dT%H:%M:%S%:z`</tEnd>
  </test>
  <result>
    <status>OK</status>
  </result>
</OSGTestResult>" > otrx_output.xml
    fi

   return 0
}

#####################################
# Fetch descript and signature files

# disable signature check before I get the signature file itself
# check_signature is global
check_signature=0

for gs_id in main entry client client_group
do
  if [ -z "$client_repository_url" ]; then
      if [ "$gs_id" == "client" ]; then
	  # no client file when no cilent_repository
	  continue
      fi
  fi
  if [ -z "$client_repository_group_url" ]; then
      if [ "$gs_id" == "client_group" ]; then
	      # no client group file when no cilent_repository_group
	  continue
      fi
  fi

  gs_id_work_dir=`get_work_dir $gs_id`

  # Fetch description file
  gs_id_descript_file=`get_descript_file $gs_id`
  fetch_file_regular "$gs_id" "$gs_id_descript_file"
  signature_file_line=`grep "^signature " "${gs_id_work_dir}/${gs_id_descript_file}"`
  if [ $? -ne 0 ]; then
      warn "No signature in description file ${gs_id_work_dir}/${gs_id_descript_file}." 1>&2
      glidein_exit 1
  fi
  signature_file=`echo $signature_file_line|awk '{print $2}'`

  # Fetch signature file
  gs_id_signature=`get_signature $gs_id`
  fetch_file_regular "$gs_id" "$signature_file"
  echo "$gs_id_signature  ${signature_file}">"${gs_id_work_dir}/signature.sha1.test"
  (cd "${gs_id_work_dir}"&&sha1sum -c signature.sha1.test) 1>&2
  if [ $? -ne 0 ]; then
      warn "Corrupted signature file '${gs_id_work_dir}/${signature_file}'." 1>&2
      glidein_exit 1
  fi
  # for simplicity use a fixed name for signature file
  mv "${gs_id_work_dir}/${signature_file}" "${gs_id_work_dir}/signature.sha1"
done

# re-enable for everything else
check_signature=1

# Now verify the description was not tampered with
# doing it so late should be fine, since nobody should have been able
# to fake the signature file, even if it faked its name in
# the description file
for gs_id in main entry client client_group
do
  if [ -z "$client_repository_url" ]; then
      if [ "$gs_id" == "client" ]; then
	  # no client file when no cilent_repository
	  continue
      fi
  fi
  if [ -z "$client_repository_group_url" ]; then
      if [ "$gs_id" == "client_group" ]; then
	      # no client group file when no cilent_repository_group
	  continue
      fi
  fi

  gs_id_descript_file=`get_descript_file $gs_id`
  check_file_signature "$gs_id" "$gs_id_descript_file"
  if [ $? -ne 0 ]; then
      gs_id_work_dir=`get_work_dir $gs_id`
      warn "Corrupted description file ${gs_id_work_dir}/${gs_id_descript_file}." 1>&2
      glidein_exit 1
  fi
done

###################################################
# get last_script, as it is used by the fetch_file
gs_id_work_dir=`get_work_dir main`
gs_id_descript_file=`get_descript_file main`
last_script=`grep "^last_script " "${gs_id_work_dir}/$gs_id_descript_file" | awk '{print $2}'`
if [ $? -ne 0 ]; then
    warn "last_script not in description file ${gs_id_work_dir}/$gs_id_descript_file." 1>&2
    glidein_exit 1
fi


##############################
# Fetch all the other files
for gs_file_id in "main file_list" "client preentry_file_list" "client_group preentry_file_list" "client aftergroup_preentry_file_list" "entry file_list" "client file_list" "client_group file_list" "client aftergroup_file_list" "main after_file_list"
do
  gs_id=`echo $gs_file_id |awk '{print $1}'`

  if [ -z "$client_repository_url" ]; then
      if [ "$gs_id" == "client" ]; then
	  # no client file when no client_repository
	  continue
      fi
  fi
  if [ -z "$client_repository_group_url" ]; then
      if [ "$gs_id" == "client_group" ]; then
	      # no client group file when no client_repository_group
	  continue
      fi
  fi

  gs_file_list_id=`echo $gs_file_id |awk '{print $2}'`
  
  gs_id_work_dir=`get_work_dir $gs_id`
  gs_id_descript_file=`get_descript_file $gs_id`
  
  # extract list file name
  gs_file_list_line=`grep "^$gs_file_list_id " "${gs_id_work_dir}/$gs_id_descript_file"`
  if [ $? -ne 0 ]; then
      if [ -z "$client_repository_group_url" ]; then
	  if [ "${gs_file_list_id:0:11}" == "aftergroup_" ]; then
	      # afterfile_.. files optional when no client_repository_group
	      continue
	  fi
      fi
      warn "No '$gs_file_list_id' in description file ${gs_id_work_dir}/${gs_id_descript_file}." 1>&2
      glidein_exit 1
  fi
  gs_file_list=`echo $gs_file_list_line |awk '{print $2}'`

  # fetch list file
  fetch_file_regular "$gs_id" "$gs_file_list"

  # Fetch files contained in list
  while read file
    do
    if [ "${file:0:1}" != "#" ]; then
	fetch_file "$gs_id" $file
    fi
  done < "${gs_id_work_dir}/${gs_file_list}"

done

###############################
# Start the glidein main script
add_config_line "GLIDEIN_INITIALIZED" "1"

echo "# --- Last Script values ---" >> glidein_config
last_startup_time=`date +%s`
let validation_time=$last_startup_time-$startup_time
echo "=== Last script starting `date` ($last_startup_time) after validating for $validation_time ==="
echo
ON_DIE=0
trap 'ignore_signal' HUP
trap 'on_die' TERM
trap 'on_die' INT
gs_id_work_dir=`get_work_dir main`
$main_dir/error_augment.sh -init
"${gs_id_work_dir}/$last_script" glidein_config &
wait $!
ret=$?
if [ $ON_DIE -eq 1 ]; then
        ret=0
fi
last_startup_end_time=`date +%s`
$main_dir/error_augment.sh  -process $ret "$last_script" "$PWD" "${gs_id_work_dir}/$last_script glidein_config" "$last_startup_time" "$last_startup_end_time"
$main_dir/error_augment.sh -concat

let last_script_time=$last_startup_end_time-$last_startup_time
echo "=== Last script ended `date` ($last_startup_end_time) with code $ret after $last_script_time ==="
echo
if [ $ret -ne 0 ]; then
    warn "Error running '$last_script'" 1>&2
fi

#########################
# clean up after I finish
glidein_exit $ret
