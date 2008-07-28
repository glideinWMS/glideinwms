#!/bin/bash

# This script starts the condor daemons
# expects a config file as a parameter


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

condor_job_wrapper=`grep -i "^condor_job_wrapper " $description_file | awk '{print $2}'`
echo "USER_JOB_WRAPPER = $(LOCAL_DIR)/$condor_job_wrapper" >> $CONDOR_CONFIG


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

condor_vars=`grep -i "^CONDOR_VARS_FILE " $config_file | awk '{print $2}'`
condor_vars_entry=`grep -i "^CONDOR_VARS_ENTRY_FILE " $config_file | awk '{print $2}'`

grep -v "^#" "$condor_vars" > condor_vars.lst.tmp 
grep -v "^#" "$condor_vars_entry" >> condor_vars.lst.tmp 
while read line
do
    set_var $line
done < condor_vars.lst.tmp

#let "max_job_time=$job_max_hours * 3600"

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

MASTER_NAME = ${GLIDEIN_Site}_$$
GLIDEIN_MASTER_NAME = "${GLIDEIN_Site}_$$"

EOF
# ##################################
if [ $? -ne 0 ]; then
    echo "Error customizing the condor_config" 1>&2
    exit 1
fi

if [ "$debug_mode" == "1" ]; then
  echo "--- condor_config ---" 1>&2
  cat $CONDOR_CONFIG 1>&2
  echo "--- ============= ---" 1>&2
  env 1>&2
  echo "--- ============= ---" 1>&2
  echo 1>&2
  #env 1>&2
fi

start_time=`date +%s`
echo "=== Condor starting `date` (`date +%s`) ==="

let "retmins=$GLIDEIN_Retire_Time / 60 - 1"
$CONDOR_DIR/sbin/condor_master -r $retmins -dyn -f 
ret=$?

end_time=`date +%s`
let elapsed_time=$end_time-$start_time
echo "=== Condor ended `date` (`date +%s`) after $elapsed_time ==="
echo

# log dir is always different
# get the real name
log_dir=`/bin/ls -d log*`

echo ===   Stats of vm2   ===
if [ -f "${log_dir}/StarterLog.vm2" ]; then
  awk -f parse_starterlog.awk ${log_dir}/StarterLog.vm2
fi
echo === End Stats of vm2 ===

if [ "$debug_mode" == "1" ]; then
    ls -l log*/* 1>&2
    echo
    for fname in MasterLog StartdLog StarterLog.vm2 StarterLog.vm1; do
     fpath="${log_dir}/${fname}"
     if [ -f  "$fpath" ]; then
       echo "$fname" 1>&2
       echo "======== gzip | uuencode =============" 1>&2
       gzip --stdout "$fpath" | b64uuencode 1>&2
       echo
     fi
    done
fi

exit $ret
