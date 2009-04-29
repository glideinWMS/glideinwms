#!/bin/bash

# This script starts the condor daemons
# expects a config file as a parameter

# first of all, clean up any CONDOR variable
condor_vars=`env |awk '/^_[Cc][Oo][Nn][Dd][Oo][Rr]_/{split($1,a,"=");print a[1]}'`
for v in $condor_vars; do
 unset $v
done
echo "Removed condor variables $condor_vars" 1>&2


# pstr = variable representing an appendix
pstr='"'

config_file=$1

debug_mode=`grep -i "^DEBUG_MODE " $config_file | awk '{print $2}'`

if [ "$debug_mode" == "1" ]; then
    echo "-------- $config_file in condor_startup.sh ----------" 1>&2
    cat $config_file 1>&2
    echo "-----------------------------------------------------" 1>&2
fi

entry_name=`grep -i "^GLIDEIN_Entry_Name " $config_file | awk '{print $2}'`

description_file=`grep -i "^DESCRIPTION_FILE " $config_file | awk '{print $2}'`

export CONDOR_CONFIG="${PWD}/`grep -i '^condor_config ' $description_file | awk '{print $2}'`"

echo "# ---- start of condor_startup generated part ----" >> $CONDOR_CONFIG

wrapper_list=`grep -i "^WRAPPER_LIST " $config_file | awk '{print $2}'`

#
# Create the job wrapper
#
condor_job_wrapper="condor_job_wrapper.sh"
cat > $condor_job_wrapper <<EOF
#!/bin/bash

# This script is started just before the user job
# It is referenced by the USER_JOB_WRAPPER

EOF

for fname in `cat $wrapper_list`; 
do 
  cat "$fname" >> $condor_job_wrapper
done

cat >> $condor_job_wrapper <<EOF

# Condor job wrappers must replace its own image
exec "\$@"
EOF

chmod a+x $condor_job_wrapper
echo "USER_JOB_WRAPPER = \$(LOCAL_DIR)/$condor_job_wrapper" >> $CONDOR_CONFIG


# glidein_variables = list of additional variables startd is to publish
glidein_variables=""

# job_env = environment to pass to the job
job_env=""

#
# Set a variable read from a file
#
function set_var {
    var_name=$1
    var_type=$2
    var_def=$3
    var_condor=$4
    var_req=$5
    var_exportcondor=$6
    var_user=$7

    if [ -z "$var_name" ]; then
	# empty line
	return 0
    fi

    var_val=`grep "^$var_name " $config_file | awk '{print substr($0,index($0,$2))}'`
    if [ -z "$var_val" ]; then
	if [ "$var_req" == "Y" ]; then
	    # needed var, exit with error
	    echo "Cannot extract $var_name from '$config_file'" 1>&2
	    exit 1
	elif [ "$var_def" == "-" ]; then
	    # no default, do not set
	    return 0
	else
	    eval var_val=$var_def
	fi
    fi
    
    if [ "$var_condor" == "+" ]; then
	var_condor=$var_name
    fi
    if [ "$var_type" == "S" ]; then
	var_val_str="${pstr}${var_val}${pstr}"
    else
	var_val_str="$var_val"
    fi

    # insert into condor_config
    echo "$var_condor=$var_val_str" >> $CONDOR_CONFIG

    if [ "$var_exportcondor" == "Y" ]; then
	# register var_condor for export
	if [ -z "$glidein_variables" ]; then
	   glidein_variables="$var_condor"
	else
	   glidein_variables="$glidein_variables,$var_condor"
	fi
    fi

    if [ "$var_user" != "-" ]; then
	# - means do not export
	if [ "$var_user" == "+" ]; then
	    var_user=$var_name
	elif [ "$var_user" == "@" ]; then
	    var_user=$var_condor
	fi

	if [ -z "$job_env" ]; then
	   job_env="$var_user=$var_val"
	else
	   job_env="$job_env;$var_user=$var_val"
	fi
    fi

    # define it for future use
    eval "$var_name='$var_val'"
    return 0
}

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

function cond_print_log {
    # $1 = fname
    # $2 = fpath
    if [ -f  "$2" ]; then
	echo "$1" 1>&2
	echo "======== gzip | uuencode =============" 1>&2
	gzip --stdout "$2" | b64uuencode 1>&2
	echo
    fi
}

condor_vars=`grep -i "^CONDOR_VARS_FILE " $config_file | awk '{print $2}'`
condor_vars_entry=`grep -i "^CONDOR_VARS_ENTRY_FILE " $config_file | awk '{print $2}'`

grep -v "^#" "$condor_vars" > condor_vars.lst.tmp 
grep -v "^#" "$condor_vars_entry" >> condor_vars.lst.tmp 
while read line
do
    set_var $line
done < condor_vars.lst.tmp

#let "max_job_time=$job_max_hours * 3600"

# randomize the retire time, to smooth starts and terminations
org_GLIDEIN_Retire_Time=$GLIDEIN_Retire_Time
let "random100=$RANDOM%100"
let "GLIDEIN_Retire_Time=$GLIDEIN_Retire_Time - $GLIDEIN_Retire_Time_Spread * $random100 / 100"

# but protect from going too low
if [ "$GLIDEIN_Retire_Time" -lt "600" ]; then
  GLIDEIN_Retire_Time=600
fi
echo "Retire time set to $GLIDEIN_Retire_Time" 1>&2

now=`date +%s`
let "x509_duration=$X509_EXPIRE - $now - 1"

#if [ $max_proxy_time -lt $max_job_time ]; then
#    max_job_time=$max_proxy_time
#    glidein_expire=$x509_expire
#else
#    let "glidein_expire=$now + $max_job_time"
#fi

#let "glidein_toretire=$now + $glidein_retire_time"

# put some safety margin
let "session_duration=$x509_duration + 300"

cat >> "$CONDOR_CONFIG" <<EOF
# ---- start of condor_startup fixed part ----

SEC_DEFAULT_SESSION_DURATION = $session_duration

LOCAL_DIR = $PWD

#GLIDEIN_EXPIRE = $glidein_expire
#GLIDEIN_TORETIRE = $glidein_toretire
GLIDEIN_START_TIME = $now

STARTER_JOB_ENVIRONMENT = $job_env
GLIDEIN_VARIABLES = $glidein_variables

MASTER_NAME = glidein_$$
STARTD_NAME = glidein_$$

#This can be used for locating the proper PID for monitoring
GLIDEIN_PARENT_PID = $$

EOF
# ##################################
if [ $? -ne 0 ]; then
    echo "Error customizing the condor_config" 1>&2
    exit 1
fi

monitor_mode=`grep -i "^MONITOR_MODE " $config_file | awk '{print $2}'`

if [ "$monitor_mode" == "MULTI" ]; then
    use_multi_monitor=1
else
    use_multi_monitor=0
fi


if [ "$use_multi_monitor" -eq 1 ]; then
    condor_config_multi_include="${PWD}/`grep -i '^condor_config_multi_include ' $description_file | awk '{print $2}'`"
    echo "# ---- start of include part ----" >> "$CONDOR_CONFIG"
    cat $condor_config_multi_include >> "$CONDOR_CONFIG"
    if [ $? -ne 0 ]; then
	echo "Error appending multi_include to condor_config" 1>&2
	exit 1
    fi
else
    condor_config_main_include="${PWD}/`grep -i '^condor_config_main_include ' $description_file | awk '{print $2}'`"
    condor_config_monitor_include="${PWD}/`grep -i '^condor_config_monitor_include ' $description_file | awk '{print $2}'`"
    echo "# ---- start of include part ----" >> "$CONDOR_CONFIG"

    # using two different configs... one for monitor and one for main
    condor_config_monitor=${CONDOR_CONFIG}.monitor
    cp "$CONDOR_CONFIG" "$condor_config_monitor"
    if [ $? -ne 0 ]; then
	echo "Error copying condor_config into condor_config.monitor" 1>&2
	exit 1
    fi
    cat $condor_config_monitor_include >> "$condor_config_monitor"
    if [ $? -ne 0 ]; then
	echo "Error appending monitor_include to condor_config.monitor" 1>&2
	exit 1
    fi

    cat >> "$condor_config_monitor" <<EOF
# use a different name for monitor
MASTER_NAME = monitor_$$
STARTD_NAME = monitor_$$

# use plural names, since there may be more than one if multiple job VMs
Monitored_Names = "glidein_$$@\$(FULL_HOSTNAME)"
EOF

    cat $condor_config_main_include >> "$CONDOR_CONFIG"
    if [ $? -ne 0 ]; then
	echo "Error appending main_include to condor_config" 1>&2
	exit 1
    fi

    cat >> "$CONDOR_CONFIG" <<EOF

Monitoring_Name = "monitor_$$@\$(FULL_HOSTNAME)"
EOF

    # also needs to create "monitor" dir for log and execute dirs
    mkdir monitor monitor/log monitor/execute 
    if [ $? -ne 0 ]; then
	echo "Error creating monitor dirs" 1>&2
	exit 1
    fi
fi

mkdir log execute 
if [ $? -ne 0 ]; then
    echo "Error creating condor dirs" 1>&2
    exit 1
fi

# ##################################

if [ "$debug_mode" == "1" ]; then
  echo "--- condor_config ---" 1>&2
  cat $CONDOR_CONFIG 1>&2
  echo "--- ============= ---" 1>&2
  env 1>&2
  echo "--- ============= ---" 1>&2
  echo 1>&2
  #env 1>&2
fi

if [ "$use_multi_monitor" -ne 1 ]; then
    # start monitoring satrtd
    # use the appropriate configuration file
    tmp_condor_config=$CONDOR_CONFIG
    export CONDOR_CONFIG=$condor_config_monitor

    monitor_start_time=`date +%s`
    echo "Starting monitoring condor at `date` (`date +%s`)" 1>&2

    # set the worst case limit
    # should never hit it, but let's be safe and shutdown automatically at some point
    let "monretmins=( $GLIDEIN_Retire_Time + $GLIDEIN_Job_Max_Time ) / 60 - 1"
    $CONDOR_DIR/sbin/condor_master -f -r $monretmins -pidfile $PWD/monitor/condor_master.pid  >/dev/null 2>&1 </dev/null &
    ret=$?
    if [ "$ret" -ne 0 ]; then
	echo 'Failed to start monitoring condor... still going ahead' 1>&2
    fi

    # clean back
    export CONDOR_CONFIG=$tmp_condor_config

    main_starter_log='log/StarterLog'
    monitor_starter_log='monitor/log/StarterLog'
else
    main_starter_log='log/StarterLog.vm2'
    monitor_starter_log='log/StarterLog.vm1'
fi

start_time=`date +%s`
echo "=== Condor starting `date` (`date +%s`) ==="

let "retmins=$GLIDEIN_Retire_Time / 60 - 1"
$CONDOR_DIR/sbin/condor_master -r $retmins -f 
condor_ret=$?

end_time=`date +%s`
let elapsed_time=$end_time-$start_time
echo "=== Condor ended `date` (`date +%s`) after $elapsed_time ==="
echo

# log dir is always different
# get the real name
log_dir='log'

echo ===   Stats of main   ===
if [ -f "${main_starter_log}" ]; then
  awk -f parse_starterlog.awk ${main_starter_log}
fi
echo === End Stats of main ===

if [ "$debug_mode" == "1" ]; then
    ls -l log 1>&2
    echo
    cond_print_log MasterLog log/MasterLog
    cond_print_log StartdLog log/StartdLog
    cond_print_log StarterLog ${main_starter_log}
    if [ "$use_multi_monitor" -ne 1 ]; then
	cond_print_log MasterLog.monitor monitor/log/MasterLog
	cond_print_log StartdLog.monitor monitor/log/StartdLog
    fi
    cond_print_log StarterLog.monitor ${monitor_starter_log}
fi

if [ "$use_multi_monitor" -ne 1 ]; then
    # terminate monitoring startd
    # use the appropriate configuration file
    tmp_condor_config=$CONDOR_CONFIG
    export CONDOR_CONFIG=$condor_config_monitor

    monitor_start_time=`date +%s`
    echo "Terminating monitoring condor at `date` (`date +%s`)" 1>&2
    $CONDOR_DIR/sbin/condor_master -k $PWD/monitor/condor_master.pid 
    ret=$?
    if [ "$ret" -ne 0 ]; then
	echo 'Failed to terminate monitoring condor... still going ahead' 1>&2
    fi

    # clean back
    export CONDOR_CONFIG=$tmp_condor_config
fi

exit $condor_ret
