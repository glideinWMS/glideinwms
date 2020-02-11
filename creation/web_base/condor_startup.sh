#!/bin/bash
#
# Project:
#   glideinWMS
#
# File Version:
#
# Description:
# This script starts the condor daemons expects a config file as a parameter
#

function trap_with_arg {
    func="$1" ; shift
    for sig ; do
        trap "$func $sig" "$sig"
    done
}

#function to handle passing signals to the child processes
# no need to re-raise sigint, caller does unconditional exit (https://www.cons.org/cracauer/sigint.html)
#  The condor_master -k <file> sends a SIGTERM to the pid named in the file. This results in a graceful shutdown,
# where daemons get a chance to do orderly cleanup. To do a fast shutdown, you would send a SIGQUIT to the
# condor_master process, something like this:
#  /bin/kill -s SIGQUIT `cat condor_master2.pid`
# In either case, when the master receives the signal, it will immediately write a message to the log, then signal
# all of its children. When each child exits, the master will send a SIGKILL to any remaining descendants.
# Once all of the children exit, the master then exits.
function on_die {
    condor_signal=$1
    # Can receive SIGTERM SIGINT SIGQUIT, condor understands SIGTERM SIGQUIT. Send SIGQUIT for SIGQUIT, SIGTERM otherwise
    [[ "$condor_signal" != SIGQUIT ]] && condor_signal=SIGTERM
    condor_pid_tokill=$condor_pid
    [[ -z "$condor_pid_tokill" ]] && condor_pid_tokill=`cat $PWD/condor_master2.pid 2> /dev/null`
    echo "Condor startup received $1 signal ... shutting down condor processes (forwarding $condor_signal to $condor_pid_tokill)"
    [[ -n "$condor_pid_tokill" ]] && kill -s $condor_signal $condor_pid_tokill
    # $CONDOR_DIR/sbin/condor_master -k $PWD/condor_master2.pid
    ON_DIE=1
}

function ignore_signal {
    echo "Condor startup received SIGHUP signal, ignoring..."
}

metrics=""

# put in place a reasonable default
GLIDEIN_CPUS=1

# first of all, clean up any CONDOR variable
condor_vars=`env |awk '/^_[Cc][Oo][Nn][Dd][Oo][Rr]_/{split($1,a,"=");print a[1]}'`
for v in $condor_vars; do
    unset $v
done
echo "Removed condor variables $condor_vars" 1>&2

# Condor 7.5.6 and above will use the system's gsi-authz.conf.  We don't want that.
export GSI_AUTHZ_CONF=/dev/null
# Specifically for the cloud:  If we want Condor to run as a specific user on the VM,
# set GLIDEIN_Condor_IDS in the environment.
if [ -n "$GLIDEIN_Condor_IDS" ]; then
    export _CONDOR_CONDOR_IDS=$GLIDEIN_Condor_IDS
    echo "Created _CONDOR_CONDOR_IDS variable based on GLIDEIN_Condor_User" 1>&2
fi

# pstr = variable representing an appendix
pstr='"'

config_file="$1"

error_gen="`grep '^ERROR_GEN_PATH ' "$config_file" | cut -d ' ' -f 2-`"

glidein_startup_pid="`grep -i "^GLIDEIN_STARTUP_PID " "$config_file" | cut -d ' ' -f 2-`"
# DO NOT USE PID FOR DAEMON NAMES
# If site's batch system is HTCondor and USE_PID_NAMESPACES is set pid's
# it does not play well with HTCondor daemon name creation
# $RANDOM is in range(0, 32K). Add extra safeguards
let "random_name_str=($RANDOM+1000)*($RANDOM+2000)"

# find out whether user wants to run job or run test
debug_mode="`grep -i "^DEBUG_MODE " "$config_file" | cut -d ' ' -f 2-`"

print_debug=0
check_only=0
if [ "$debug_mode" -ne 0 ]; then
    print_debug=1
    if [ "$debug_mode" -eq 2 ]; then
        check_only=1
    fi
fi

adv_only=`grep -i "^GLIDEIN_ADVERTISE_ONLY " "$config_file" | cut -d ' ' -f 2-`

if [ "$adv_only" -eq 1 ]; then
    adv_destination=`grep -i "^GLIDEIN_ADVERTISE_DESTINATION " "$config_file" | cut -d ' ' -f 2-`
    if [ -z "${adv_destination}" ]; then
        adv_destination=VO
    fi

    # no point in printing out debug info about config
    print_debug=0
    if [ "$adv_destination" = "VO" ]; then
        echo "Advertising failure to the VO collector"  1>&2
    else
        echo "Advertising failure to the Factory collector"  1>&2
    fi
fi

if [ "$print_debug" -ne 0 ]; then
    echo "-------- $config_file in condor_startup.sh ----------" 1>&2
    cat $config_file 1>&2
    echo "-----------------------------------------------------" 1>&2
fi

main_stage_dir="`grep -i "^GLIDEIN_WORK_DIR " "$config_file" | cut -d ' ' -f 2-`"

description_file="`grep -i "^DESCRIPTION_FILE " "$config_file" | cut -d ' ' -f 2-`"

in_condor_config="${main_stage_dir}/`grep -i '^condor_config ' "${main_stage_dir}/${description_file}" | cut -s -f 2-`"

export CONDOR_CONFIG="${PWD}/condor_config"

cp "$in_condor_config" "$CONDOR_CONFIG"

echo "# ---- start of condor_startup generated part ----" >> $CONDOR_CONFIG

wrapper_list="`grep -i "^WRAPPER_LIST " "$config_file" | cut -d ' ' -f 2-`"

#
# Create the job wrapper
#
# TODO: should it skip the wrapper if WRAPPER_LIST is empty?
condor_job_wrapper="condor_job_wrapper.sh"
cat > "$condor_job_wrapper" <<EOF
#!/bin/bash

# This script is started just before the user job
# It is referenced by the USER_JOB_WRAPPER

EOF

for fname in `cat "$wrapper_list"`;
do
    cat "$fname" >> "$condor_job_wrapper"
done


echo "USER_JOB_WRAPPER = \$(LOCAL_DIR)/$condor_job_wrapper" >> "$CONDOR_CONFIG"


# glidein_variables = list of additional variables startd is to publish
glidein_variables=""

# job_env = environment to pass to the job
# Make sure we do not leak LD_LIBRARY_PATH to the job incorrectly
job_env="LD_LIBRARY_PATH=$LD_LIBRARY_PATH"


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

    var_val=`grep "^$var_name " $config_file | awk '{if (NF>1) ind=length($1)+1; v=substr($0, ind); print substr(v, index(v, $2))}'`
    if [ -z "$var_val" ]; then
        if [ "$var_req" == "Y" ]; then
            # needed var, exit with error
            #echo "Cannot extract $var_name from '$config_file'" 1>&2
            STR="Cannot extract $var_name from '$config_file'"
            "$error_gen" -error "condor_startup.sh" "Config" "$STR" "MissingAttribute" "$var_name"
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

        condor_env_entry="$var_user=$var_val"
        condor_env_entry=`echo "$condor_env_entry" | awk "{gsub(/\"/,\"\\\\\"\\\\\"\"); print}"`
        condor_env_entry=`echo "$condor_env_entry" | awk "{gsub(/'/,\"''\"); print}"`
        if [ -z "$job_env" ]; then
           job_env="'$condor_env_entry'"
        else
           job_env="$job_env '$condor_env_entry'"
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

    logname=$1
    shift
    # Use ls to allow fpath to include wild cards
    files_to_zip="`ls -1 "$@" 2>/dev/null`"
    
    if [ "$files_to_zip" != "" ]; then
        echo "$logname" 1>&2
        echo "======== gzip | uuencode =============" 1>&2
        gzip --stdout $files_to_zip | b64uuencode 1>&2
        echo
    fi
}


function fix_param () {
    # Fix a parameter list with positional and dictionary parameters
    # 1. parameters, comma separated, parameter or name=value, positional parameters must come before all dictionary ones
    # 2. parameter names (all), comma separated, in the correct order (no extra comma at beginning or end)
    # return on stdout the expanded list, comma separated
    # exit code: 0=ok 1=error (echo on stderr error conditions)
    # e.g. fix_param 11,q4=44,q3=33 q1,q2,q3,q4   ->   11,,33,44

    if [[ -z "$2" || ! "$1" == *=* ]]; then
        echo "$1"
        return
    fi
    local varnames
    local varnames_len
    local PARLIST
    IFS=',' read -ra PARLIST <<< "$1"
    varnames_len="${2//[^,]/},"
    if [ ${#PARLIST[@]} -gt ${#varnames_len} ]; then
        echo "Parameter list ($1) longer than possible parameters ($2). Aborting." 1>&2
        return 1
    fi
    varnames=",$2,"
    # prepare reverse index
    for i in "${!my_array[@]}"; do
        if [[ "${my_array[$i]}" = "${value}" ]]; then
            echo "${i}";
        fi
    done
    local dict_start=
    local res_ctr=0
    local r1
    local r2
    local RESLIST
    declare -a RESLIST
    for i in "${PARLIST[@]}"; do
        if [[ "$i" == *=* ]]; then
            dict_start=yes
            # find name position
            r1=${varnames%,${i%%=*},*}
            r2=${r1//[^,]/}
            RESLIST[${#r2}]=${i#*=}
        else
            if [ -n "$dict_start" ]; then
                echo "Positional parameter after dictionary in ($1). Aborting." 1>&2
                return 1
            fi
            RESLIST[res_ctr]=$i
        fi
        let res_ctr+=1
    done
    res="${RESLIST[0]}"
    let res_ctr=${#varnames_len}-1
    for i in $(seq 1 1 $res_ctr 2>/dev/null); do
        res="$res,${RESLIST[$i]}"
    done
    echo $res
}


function unit_division {
    # Divide the number and preserve the unit (integer division)
    # 1 dividend (integer w/ unit), 2 divisor (integer)
    # Dividend can be a fraction w/o units: .N (N is divided by the divisor), N/M (M is multiplied by the divisor)
    local number_only
    local res_num
    if [[ "$1" =~ ^\.[0-9]+$ ]]; then
        let res_num=${1:1}/$2
        res=".$res_num"
    elif [[ "$1" =~ ^[0-9]+\/[0-9]+$ ]]; then
        number_only=${1#*/}
        let res_num=$number_only*$2
        res="${1%/*}/$res_num"
    else
        number_only=${1%%[!0-9]*}
        if [ -n "$number_only" ]; then
            local number_only=${1%%[!0-9]*}
            let res_num=$number_only/$2
        else
            echo "Invalid format for $1. Skipping division by $2, returning $1." 1>&2
        fi
        res="$res_num${1:${#number_only}}"
    fi
    echo $res
}


function find_gpus_num {
    # use condor tools to find the available GPUs
    if [ ! -f "$CONDOR_DIR/libexec/condor_gpu_discovery" ]; then
        echo "WARNING: condor_gpu_discovery not found" 1>&2
        return 1
    fi
    local tmp1
    tmp1="`"$CONDOR_DIR"/libexec/condor_gpu_discovery`"
    local ec=$?
    if [ $ec -ne 0 ]; then
        echo "WARNING: condor_gpu_discovery failed (exit code: $ec)" 1>&2
        return $ec
    fi 
    local tmp="`echo "$tmp1" | grep "^DetectedGPUs="`"
    if [ "${tmp:13}" = 0 ]; then
        echo "No GPUs found with condor_gpu_discovery, setting them to 0" 1>&2
        echo 0
        return
    fi
    set -- $tmp
    echo "condor_gpu_discovery found $# GPUs: $tmp" 1>&2
    echo $#
}


# interpret the variables
rm -f condor_vars.lst.tmp
touch condor_vars.lst.tmp
for vid in GLIDECLIENT_GROUP_CONDOR_VARS_FILE GLIDECLIENT_CONDOR_VARS_FILE ENTRY_CONDOR_VARS_FILE CONDOR_VARS_FILE
do
    condor_vars="`grep -i "^$vid " "$config_file" | cut -d ' ' -f 2-`"
    if [ -n "$condor_vars" ]; then
        grep -v "^#" "$condor_vars" >> condor_vars.lst.tmp
    fi
done

while read line
do
    set_var $line
done < condor_vars.lst.tmp


cat >> "$condor_job_wrapper" <<EOF

# Condor job wrappers must replace its own image
exec "$GLIDEIN_WRAPPER_EXEC"
EOF
chmod a+x "$condor_job_wrapper"


now=`date +%s`
# If not an integer reset to 0 (a string could cause errors [#7899])
[ "$X509_EXPIRE" -eq "$X509_EXPIRE" ] 2>/dev/null || X509_EXPIRE=0

#add some safety margin
let "x509_duration=$X509_EXPIRE - $now - 300"

# Get relevant attributes from glidein_config if they exist
# if they do not, check condor config from vars population above
max_walltime=`grep -i "^GLIDEIN_Max_Walltime " "$config_file" | cut -d ' ' -f 2-`
job_maxtime=`grep -i "^GLIDEIN_Job_Max_Time " "$config_file" | cut -d ' ' -f 2-`
graceful_shutdown=`grep -i "^GLIDEIN_Graceful_Shutdown " "$config_file" | cut -d ' ' -f 2-`
# randomize the retire time, to smooth starts and terminations
retire_spread=`grep -i "^GLIDEIN_Retire_Time_Spread " "$config_file" | cut -d ' ' -f 2-`
expose_x509=`grep -i "^GLIDEIN_Expose_X509 " "$config_file" | cut -d ' ' -f 2-`

if [ -z "$expose_x509" ]; then
    expose_x509=`grep -i "^GLIDEIN_Expose_X509=" "$CONDOR_CONFIG" | awk -F"=" '{print $2}'`
    if [ -z "$expose_x509" ]; then
        expose_x509="false"
    fi
fi
expose_x509=`echo $expose_x509 | tr '[:upper:]' '[:lower:]'`

if [ -z "$graceful_shutdown" ]; then
    graceful_shutdown=`grep -i "^GLIDEIN_Graceful_Shutdown=" "$CONDOR_CONFIG" | awk -F"=" '{print $2}'`
    if [ -z "$graceful_shutdown" ]; then
        echo "WARNING: graceful shutdown not defined in vars or glidein_config, using 120!" 1>&2
        graceful_shutdown=120
    fi
fi
if [ -z "$job_maxtime" ]; then
    job_maxtime=`grep -i "^GLIDEIN_Job_Max_Time=" "$CONDOR_CONFIG" | awk -F"=" '{print $2}'`
    if [ -z "$job_maxtime" ]; then
        echo "WARNING: job max time not defined in vars or glidein_config, using 192600!" 1>&2
        job_maxtime=192600
    fi
fi

# At this point, we need to define two times:
#  die_time = time that glidein will enter graceful shutdown
#  retire_time = time that glidein will stop accepting jobs

# DAEMON_SHUTDOWN is only updated when the classad is sent to the Collector
# Since update interval is randomized, hardcode a grace period here to 
# make sure max_walltime is respected
update_interval=370

#Minimum amount retire time can be
min_glidein=600

# Take into account GLIDEIN_Max_Walltime
# GLIDEIN_Max_Walltime = Max allowed time for the glidein.
#   If you specify this variable, then Condor startup scripts will calculate the 
#   GLIDEIN_Retire_Time for the glidein as 
#    (GLIDEIN_MAX_Walltime - GLIDEIN_Job_Max_Time)
#   If GLIDEIN_Retire_Time is also specified, 
#   it will be ignored and only the calculated value is used. 
if [ -z "$max_walltime" ]; then
    retire_time=`grep -i "^GLIDEIN_Retire_Time " "$config_file" | cut -d ' ' -f 2-`
    if [ -z "$retire_time" ]; then
        retire_time=21600
        echo "used default retire time, $retire_time" 1>&2
    else
        echo "used param defined retire time, $retire_time" 1>&2
    fi
    let "die_time=$retire_time + $job_maxtime"
else
    echo "max wall time, $max_walltime" 1>&2

    if [ -z "$retire_spread" ]; then
        # Make sure that the default spread is enough so that we
        # dont drop below min_glidein (ie 600 seconds)
        let "default_spread=($min_glidein * 11) / 100"
    else
        let "default_spread=$retire_spread"
    fi

    # Make sure retire time is not set to less than 300 plus default spread
    # (since job max default is set to 36hours, this can happen)
    # total_grace=max total time to end glidein after DAEMON_SHUTDOWN occurs
    let "total_grace= $graceful_shutdown + $default_spread + $update_interval"
    let "total_job_allotment= $total_grace + $job_maxtime+$min_glidein"
    if [ "$total_job_allotment" -gt "$max_walltime" ]; then
        let "job_maxtime= $max_walltime - $total_grace - $min_glidein"
        if [ "$job_maxtime" -lt "0" ]; then
            let "job_maxtime=0"
        fi
        echo "WARNING: job max time is bigger than max_walltime, lowering it.  " 1>&2
    fi
    echo "job max time, $job_maxtime" 1>&2
  
    let "die_time=$max_walltime - $update_interval - $graceful_shutdown"
    let "retire_time=$die_time - $job_maxtime"
    GLIDEIN_Retire_Time=$retire_time
    echo "calculated retire time, $retire_time" 1>&2
fi

# make sure the glidein goes away before the proxy expires
if [ "$die_time" -gt "$x509_duration" ]; then
    ignore_x509=`grep -i "^GLIDEIN_Ignore_X509_Duration " $config_file | awk '{print $2}' | tr '[:upper:]' '[:lower:]'`
    if [ "$x509_duration" -lt 900 ]; then
        echo "Remaining proxy duration is less than 15min. Shortening the Glidein lifetime."
        ignore_x509=false
    fi
    if [ "x$ignore_x509" == "xfalse" ]; then
        # Subtract both die time and retire time by the difference
        let "reduce_time=$die_time-$x509_duration"
        let "die_time=$x509_duration"
        let "retire_time=$retire_time - $reduce_time"
        echo "Proxy not long lived enough ($x509_duration s left), shortened retire time to $retire_time" 1>&2
    else
        echo "GLIDEIN_Ignore_X509_Duration is true (default). Ignoring glidein die time ($retire_time s) longer than remaining proxy duration ($x509_duration s)" 1>&2
    fi
fi


if [ -z "$retire_spread" ]; then
    let "retire_spread=$retire_time / 10"
    echo "using default retire spread, $retire_spread" 1>&2
else
    echo "used param retire spead, $retire_spread" 1>&2
fi


let "random100=$RANDOM%100"
let "retire_time=$retire_time - $retire_spread * $random100 / 100"
let "die_time=$die_time - $retire_spread * $random100 / 100"

# but protect from going too low
if [ "$retire_time" -lt "$min_glidein" ]; then
    echo "Retire time after spread too low ($retire_time), remove spread" 1>&2
    # With the various calculations going on now with walltime
    # Safer to add spread rather than to revert to previous value
    let "retire_time=$retire_time + $retire_spread * $random100 / 100"
    let "die_time=$die_time + $retire_spread * $random100 / 100"
fi
if [ "$retire_time" -lt "$min_glidein" ] && [ "$adv_only" -ne "1" ]; then  
    #echo "Retire time still too low ($retire_time), aborting" 1>&2
    STR="Retire time still too low ($retire_time), aborting"
    "$error_gen" -error "condor_startup.sh" "Config" "$STR" "retire_time" "$retire_time" "min_retire_time" "$min_glidein"
    exit 1
fi
echo "Retire time set to $retire_time" 1>&2
echo "Die time set to $die_time" 1>&2

let "glidein_toretire=$now + $retire_time"
let "glidein_todie=$now + $die_time"

# minimize re-authentications, by asking for a session lenght to be the same as proxy lifetime, if possible
let "session_duration=$x509_duration"

# if in test mode, don't ever start any jobs
START_JOBS="TRUE"
if [ "$check_only" == "1" ]; then
    START_JOBS="FALSE"
    # need to know which startd to fetch against
    STARTD_NAME=glidein_${glidein_startup_pid}_${random_name_str}
fi

#Add release and distribution information
LSB_RELEASE="UNKNOWN"
LSB_DISTRIBUTOR_ID="UNKNOWN"
LSB_DESCRIPTION="UNKNOWN"
command -v lsb_release >/dev/null
if test $? = 0; then
    LSB_RELEASE=`lsb_release -rs | sed 's/"//g'`
    LSB_DISTRIBUTOR_ID=`lsb_release -is | sed 's/"//g'`
    LSB_DESCRIPTION=`lsb_release -ds | sed 's/"//g'`
fi


cat >> "$CONDOR_CONFIG" <<EOF
# ---- start of condor_startup fixed part ----
LSB_DISTRIBUTOR_ID = "$LSB_DISTRIBUTOR_ID"
LSB_RELEASE = "$LSB_RELEASE"
LSB_DESCRIPTION = "$LSB_DESCRIPTION"

SEC_DEFAULT_SESSION_DURATION = $session_duration

LOCAL_DIR = $PWD

#GLIDEIN_EXPIRE = $glidein_expire
GLIDEIN_TORETIRE = $glidein_toretire
GLIDEIN_ToDie = $glidein_todie
GLIDEIN_START_TIME = $now

STARTER_JOB_ENVIRONMENT = "$job_env"
GLIDEIN_VARIABLES = $glidein_variables

MASTER_NAME = glidein_${glidein_startup_pid}_${random_name_str}
STARTD_NAME = glidein_${glidein_startup_pid}_${random_name_str}

#This can be used for locating the proper PID for monitoring
GLIDEIN_PARENT_PID = $$

START = $START_JOBS && (SiteWMS_WN_Draining =?= False)

#Use the default grace time unless the job has to be preempted. In that case set the value to 20 minutes.
PREEMPT_GRACE_TIME = ifthenelse( (SiteWMS_WN_Preempt =?= True), 1200, $PREEMPT_GRACE_TIME)

EOF
####################################
if [ $? -ne 0 ]; then
    #echo "Error customizing the condor_config" 1>&2
    STR="Error customizing the condor_config"
    "$error_gen" -error "condor_startup.sh" "WN_Resource" "$STR" "file" "$CONDOR_CONFIG"
    exit 1
fi

monitor_mode=`grep -i "^MONITOR_MODE " "$config_file" | cut -d ' ' -f 2-`

if [ "$monitor_mode" == "MULTI" ]; then
    use_multi_monitor=1
else
    use_multi_monitor=0
fi

# get the periodic scripts configuration
condor_config_startd_cron_include="`grep -i "^GLIDEIN_condor_config_startd_cron_include " "$config_file" | cut -d ' ' -f 2-`"
if [ -n "$condor_config_startd_cron_include" ]; then
    echo "adding periodic scripts (startd_cron) configuration from: $condor_config_startd_cron_include" 1>&2
    echo "# ---- start of startd_cron part ----" >> "$CONDOR_CONFIG"
    cat "$condor_config_startd_cron_include" >> "$CONDOR_CONFIG"
fi

# get check_include file for testing
if [ "$check_only" == "1" ]; then
    condor_config_check_include="${main_stage_dir}/`grep -i '^condor_config_check_include ' ${main_stage_dir}/${description_file} | awk '{print $2}'`"
    echo "# ---- start of include part ----" >> "$CONDOR_CONFIG"
    cat "$condor_config_check_include" >> "$CONDOR_CONFIG"
    if [ $? -ne 0 ]; then
        #echo "Error appending check_include to condor_config" 1>&2
        STR="Error appending check_include to condor_config"
        "$error_gen" -error "condor_startup.sh" "WN_Resource" "$STR" "file" "$CONDOR_CONFIG" "infile" "$condor_config_check_include"
        exit 1
    fi
    # fake a few variables, to make the rest work
    use_multi_monitor=0
    GLIDEIN_Monitoring_Enabled=False
else
    # NO check_only, run the actual glidein and accept jobs
    if [ "$use_multi_monitor" -eq 1 ]; then
        condor_config_multi_include="${main_stage_dir}/`grep -i '^condor_config_multi_include ' ${main_stage_dir}/${description_file} | awk '{print $2}'`"
        echo "# ---- start of include part ----" >> "$CONDOR_CONFIG"
        cat "$condor_config_multi_include" >> "$CONDOR_CONFIG"
        if [ $? -ne 0 ]; then
            #echo "Error appending multi_include to condor_config" 1>&2
            STR="Error appending multi_include to condor_config"
            "$error_gen" -error "condor_startup.sh" "WN_Resource" "$STR" "file" "$CONDOR_CONFIG" "infile" "$condor_config_multi_include"
            exit 1
        fi
    else
        condor_config_main_include="${main_stage_dir}/`grep -i '^condor_config_main_include ' ${main_stage_dir}/${description_file} | awk '{print $2}'`"
        echo "# ---- start of include part ----" >> "$CONDOR_CONFIG"

        # using two different configs... one for monitor and one for main
        # don't create the monitoring configs and dirs if monitoring is disabled
        if [ "$GLIDEIN_Monitoring_Enabled" == "True" ]; then
            condor_config_monitor_include="${main_stage_dir}/`grep -i '^condor_config_monitor_include ' ${main_stage_dir}/${description_file} | awk '{print $2}'`"
            condor_config_monitor=${CONDOR_CONFIG}.monitor
            cp "$CONDOR_CONFIG" "$condor_config_monitor"
            if [ $? -ne 0 ]; then
                #echo "Error copying condor_config into condor_config.monitor" 1>&2
                STR="Error copying condor_config into condor_config.monitor"
                "$error_gen" -error "condor_startup.sh" "WN_Resource" "$STR" "infile" "$condor_config_monitor" "file" "$CONDOR_CONFIG"
                exit 1
            fi
            cat "$condor_config_monitor_include" >> "$condor_config_monitor"
            if [ $? -ne 0 ]; then
                #echo "Error appending monitor_include to condor_config.monitor" 1>&2
                STR="Error appending monitor_include to condor_config.monitor"
                "$error_gen" -error "condor_startup.sh" "WN_Resource" "$STR" "infile" "$condor_config_monitor" "file" "$condor_config_monitor_include"
                exit 1
            fi

            cat >> "$condor_config_monitor" <<EOF
# use a different name for monitor
MASTER_NAME = monitor_$$
STARTD_NAME = monitor_$$

# use plural names, since there may be more than one if multiple job VMs
Monitored_Names = "glidein_$$@\$(FULL_HOSTNAME)"
EOF
        fi  # end of [ "$GLIDEIN_Monitoring_Enabled" == "True" ], still in else from use_multi_monitor==1

        # Set number of CPUs (otherwise the physical number is used)
        echo "NUM_CPUS = \$(GLIDEIN_CPUS)" >> "$CONDOR_CONFIG"
        # set up the slots based on the slots_layout entry parameter
        slots_layout=`grep -i "^SLOTS_LAYOUT " "$config_file" | cut -d ' ' -f 2-`
        if [ "X$slots_layout" = "Xpartitionable" ]; then
            echo "NUM_SLOTS = 1" >> "$CONDOR_CONFIG"
            echo "SLOT_TYPE_1 = cpus=\$(GLIDEIN_CPUS)" >> "$CONDOR_CONFIG"
            echo "NUM_SLOTS_TYPE_1 = 1" >> "$CONDOR_CONFIG"
            echo "SLOT_TYPE_1_PARTITIONABLE = True" >> "$CONDOR_CONFIG"
            num_slots_for_shutdown_expr=1
        else
            # fixed slot
            echo "SLOT_TYPE_1 = cpus=1" >> "$CONDOR_CONFIG"
            echo "NUM_SLOTS_TYPE_1 = \$(GLIDEIN_CPUS)" >> "$CONDOR_CONFIG"
            num_slots_for_shutdown_expr=$GLIDEIN_CPUS
        fi


        # check for resource slots
        condor_config_resource_slots="`grep -i "^GLIDEIN_Resource_Slots " "$config_file" | cut -d ' ' -f 2-`"
        if [ -n "$condor_config_resource_slots" ]; then
            echo "adding resource slots configuration: $condor_config_resource_slots" 1>&2
            cat >> "$CONDOR_CONFIG" <<EOF
# ---- start of resource slots part ($condor_config_resource_slots) ----
NEW_RESOURCES_LIST =
EXTRA_SLOTS_NUM = 0
EXTRA_CPUS_NUM = 0
EXTRA_SLOTS_START = True
NUM_CPUS = \$(GLIDEIN_CPUS)+\$(EXTRA_SLOTS_NUM)+\$(EXTRA_CPUS_NUM)

# Slot 1 definition done before (fixed/partitionable)
#SLOT_TYPE_1_PARTITIONABLE = FALSE
#SLOT_TYPE_1 = cpus=1, ioslot=0
#NUM_SLOTS_TYPE_1 = \$(GLIDEIN_CPUS)
#
#SLOT_TYPE_1_PARTITIONABLE = TRUE
#SLOT_TYPE_1 = ioslot=0
#NUM_SLOTS_TYPE_1 = 1
EOF
            # resource processing: res_name[,res_num[,res_total_ram[,res_opt]]]{;res_name[,res_num[,res_total_ram[,res_opt]]]}*
            # res_opt: static, partitionable, main
            IFS=';' read -ra RESOURCES <<< "$condor_config_resource_slots"
            # Slot Type Counter - Leave slot type 2 for monitoring
            slott_ctr=3
            for i in "${RESOURCES[@]}"; do
                resource_params="`fix_param "$i" "name,number,memory,type,disk"`"
                IFS=',' read res_name res_num res_ram res_opt res_disk <<< "$resource_params"
                if [ -z "$res_name" ]; then
                    continue
                fi
                if [ -z "$res_num" ]; then
                    if [ "`echo "$res_name" | tr -s '[:upper:]' '[:lower:]'`" = "gpus" ]; then
                        # GPUs auto-discovery: https://htcondor-wiki.cs.wisc.edu/index.cgi/wiki?p=HowToManageGpus
                        res_num=`find_gpus_num`
                        ec=$?
                        if [ $ec -eq 0 ]; then
                            echo "GPU autodiscovery (condor_gpu_discovery) found $res_num GPUs" 1>&2
                            AUTO_GPU=True
                        else
                            echo "GPU autodiscovery (condor_gpu_discovery) failed, disabling auto discovery, assuming 0 GPUs." 1>&2
                            res_num=0
                        fi
                    else
                        res_num=1
                    fi
                fi
                if [ -z "$res_ram" ]; then
                    # Will be ignored if res_opt=main
                    let res_ram=128*${res_num}
                fi
                if [ -n "$AUTO_GPU" ]; then
                    cat >> "$CONDOR_CONFIG" <<EOF
# Declare GPUs resource, auto-discovered: ${i}
use feature : GPUs
use feature : GPUsMonitor
GPU_DISCOVERY_EXTRA = -extra
# Protect against no GPUs found
if defined MACHINE_RESOURCE_${res_name}
else
  MACHINE_RESOURCE_${res_name} = 0
endif
EOF
                else
                    cat >> "$CONDOR_CONFIG" <<EOF
# Declare resource: ${i}
MACHINE_RESOURCE_${res_name} = ${res_num}
EOF
                fi
                if [ "x$res_opt" == "xextra" ]; then
                    # Like main, but adds CPUs
                    res_opt=main
                    echo "EXTRA_CPUS_NUM = \$(EXTRA_CPUS_NUM)+\$(MACHINE_RESOURCE_${res_name})" >> "$CONDOR_CONFIG"
                fi
                if [ "x$res_opt" == "xmain" ]; then  # which is the default value? main or static?
                    res_opt=
                    # Resource allocated for only main slots (partitionable or static)
                    # Main slots are determined by CPUs. Let condor split the resource: if not enough some slot will have none
                    echo "SLOT_TYPE_1 = \$(SLOT_TYPE_1), ${res_name}=100%" >> "$CONDOR_CONFIG"
                    # Decided not to add type "mainextra" with resources added to main slot and CPUs incremented
                    # It can be obtained with more control by setting GLIDEIN_CPUS
                else
                    if [[ "$res_num" -eq 1 || "x$res_opt" == "xstatic" ]]; then
                        res_opt=static
                        res_ram="`unit_division "${res_ram}" ${res_num}`"
                        if [ -n "$res_disk" ]; then
                            res_disk="`unit_division "${res_disk}" ${res_num}`"
                        fi
                    else
                        res_opt=partitionable
                    fi
                fi
                if [ -z "$res_disk" ]; then
                    # Set default here. What to do if disk is not given? Empty string lets HTCondor handle it
                    res_disk_specification=''
                else
                    res_disk_specification=", disk=${res_disk}"
                fi
                if [ -n "$res_opt" ]; then
                    # no main, separate static or partitionable
                    cat >> "$CONDOR_CONFIG" <<EOF
EXTRA_SLOTS_NUM = \$(EXTRA_SLOTS_NUM)+\$(MACHINE_RESOURCE_${res_name})
EOF
                    if [ "x$res_opt" == "xpartitionable" ]; then
                        cat >> "$CONDOR_CONFIG" <<EOF
SLOT_TYPE_${slott_ctr} = cpus=\$(MACHINE_RESOURCE_${res_name}), ${res_name}=\$(MACHINE_RESOURCE_${res_name}), ram=${res_ram}${res_disk_specification}
SLOT_TYPE_${slott_ctr}_PARTITIONABLE = TRUE
NUM_SLOTS_TYPE_${slott_ctr} = 1
EOF
                    else
                        cat >> "$CONDOR_CONFIG" <<EOF
SLOT_TYPE_${slott_ctr} = cpus=1, ${res_name}=1, ram=${res_ram}${res_disk_specification}
SLOT_TYPE_${slott_ctr}_PARTITIONABLE = FALSE
NUM_SLOTS_TYPE_${slott_ctr} = \$(MACHINE_RESOURCE_${res_name})
EOF
                    fi
                    cat >> "$CONDOR_CONFIG" <<EOF
IS_SLOT_${res_name} = SlotTypeID==${slott_ctr}
EXTRA_SLOTS_START = ifThenElse((SlotTypeID==${slott_ctr}), TARGET.Request${res_name}>0, (\$(EXTRA_SLOTS_START)))
EOF
                    let slott_ctr+=1
                fi
                echo "NEW_RESOURCES_LIST = \$(NEW_RESOURCES_LIST) $res_name" >> "$CONDOR_CONFIG"

            done

            cat >> "$CONDOR_CONFIG" <<EOF
# Update machine_resource_names and start expression
if defined MACHINE_RESOURCE_NAMES
  MACHINE_RESOURCE_NAMES = $\(MACHINE_RESOURCE_NAMES) \$(NEW_RESOURCES_LIST)
endif
START = (\$(START)) && (\$(EXTRA_SLOTS_START))
EOF

        fi  # end of resource slot if

        # Set to shutdown if total idle exceeds max idle, or if the age
        # exceeds the retire time (and is idle) or is over the max walltime (todie)
        echo "STARTD_SLOT_ATTRS = State, Activity, TotalTimeUnclaimedIdle, TotalTimeClaimedBusy" >> "$CONDOR_CONFIG"
        echo "STARTD_SLOT_ATTRS = \$(STARTD_SLOT_ATTRS), SelfMonitorAge, JobStarts, ExpectedMachineGracefulDrainingCompletion" >> "$CONDOR_CONFIG"
        daemon_shutdown=""
        for I in `seq 1 $num_slots_for_shutdown_expr`; do
            cat >> "$CONDOR_CONFIG" <<EOF

DS${I}_TO_DIE = ((GLIDEIN_ToDie =!= UNDEFINED) && (CurrentTime > GLIDEIN_ToDie))

# The condition pre 8.2 is valid only for not partitionable slots
# Since the idle timer doesn't reset/stop when resources are reclaimed, 
# partitionable slots will get reaped sooner than non-partitionable.
DS${I}_NOT_PARTITIONABLE = ((PartitionableSlot =!= True) || (TotalSlots =?=1))
# The daemon shutdown expression for idle startds(glideins) depends on some conditions:
# If some jobs were sheduled on the startd (TAIL) or none at all (NOJOB)
# If using condor 8.2 or later (NEW) or previous versions (PRE82). JobStarts defined
# is used to discriminate
DS${I}_IS_HTCONDOR_NEW = (Slot${I}_JobStarts =!= UNDEFINED)
# No jobs started (using GLIDEIN_Max_Idle) 
DS${I}_IDLE_NOJOB_NEW = ((Slot${I}_JobStarts =!= UNDEFINED) && (Slot${I}_SelfMonitorAge =!= UNDEFINED) && (GLIDEIN_Max_Idle =!= UNDEFINED) && \\
                  (Slot${I}_JobStarts == 0) && \\
                  (Slot${I}_SelfMonitorAge > GLIDEIN_Max_Idle))
DS${I}_IDLE_NOJOB_PRE82 = ((Slot${I}_TotalTimeUnclaimedIdle =!= UNDEFINED) && (GLIDEIN_Max_Idle =!= UNDEFINED) && \\
        \$(DS${I}_NOT_PARTITIONABLE) && \\
        (Slot${I}_TotalTimeUnclaimedIdle > GLIDEIN_Max_Idle))
DS${I}_IDLE_NOJOB = ((GLIDEIN_Max_Idle =!= UNDEFINED) && \\
        ifThenElse(\$(DS${I}_IS_HTCONDOR_NEW), \$(DS${I}_IDLE_NOJOB_NEW), \$(DS${I}_IDLE_NOJOB_PRE82))) 
# Some jobs started (using GLIDEIN_Max_Tail)
DS${I}_IDLE_TAIL_NEW = ((Slot${I}_JobStarts =!= UNDEFINED) && (Slot${I}_ExpectedMachineGracefulDrainingCompletion =!= UNDEFINED) && (GLIDEIN_Max_Tail =!= UNDEFINED) && \\
        (Slot${I}_JobStarts > 0) && \\
        ((CurrentTime - Slot${I}_ExpectedMachineGracefulDrainingCompletion) > GLIDEIN_Max_Tail) )
DS${I}_IDLE_TAIL_PRE82 = ((Slot${I}_TotalTimeUnclaimedIdle =!= UNDEFINED) && (GLIDEIN_Max_Tail =!= UNDEFINED) && \\
        (Slot${I}_TotalTimeClaimedBusy =!= UNDEFINED) && \\
        \$(DS${I}_NOT_PARTITIONABLE) && \\
        (Slot${I}_TotalTimeUnclaimedIdle > GLIDEIN_Max_Tail))
DS${I}_IDLE_TAIL = ((GLIDEIN_Max_Tail =!= UNDEFINED) && \\
        ifThenElse(\$(DS${I}_IS_HTCONDOR_NEW), \$(DS${I}_IDLE_TAIL_NEW), \$(DS${I}_IDLE_TAIL_PRE82)))
DS${I}_IDLE_RETIRE = (\$(DS${I}_NOT_PARTITIONABLE) && (GLIDEIN_ToRetire =!= UNDEFINED) && \\
       (CurrentTime > GLIDEIN_ToRetire ))
DS${I}_IDLE = ( (Slot${I}_Activity == "Idle") && (Slot${I}_State =!= "Claimed") && \\
        (\$(DS${I}_IDLE_NOJOB) || \$(DS${I}_IDLE_TAIL) || \$(DS${I}_IDLE_RETIRE)) )

DS${I} = (\$(DS${I}_TO_DIE) || \\
          \$(DS${I}_IDLE))

# But don't enforce shutdowns for dynamic slots (aka "subslots")
DS${I} = (DynamicSlot =!= True) && (\$(DS${I}))

EOF
            if [ "X$daemon_shutdown" != "X" ]; then
                daemon_shutdown="$daemon_shutdown &&"
            fi
            daemon_shutdown="$daemon_shutdown \$(DS${I})"
        done
        echo "STARTD.DAEMON_SHUTDOWN = $daemon_shutdown" >> "$CONDOR_CONFIG"

        cat $condor_config_main_include >> "$CONDOR_CONFIG"
        if [ $? -ne 0 ]; then
            #echo "Error appending main_include to condor_config" 1>&2
            STR="Error appending main_include to condor_config"
            "$error_gen" -error "condor_startup.sh" "WN_Resource" "$STR" "file" "$CONDOR_CONFIG" "infile" "$condor_config_main_include"
            exit 1
        fi

        if [ "$GLIDEIN_Monitoring_Enabled" == "True" ]; then
            cat >> "$CONDOR_CONFIG" <<EOF

Monitoring_Name = "monitor_$$@\$(FULL_HOSTNAME)"
EOF

            # also needs to create "monitor" dir for log and execute dirs
            if [ -d monitor ] && [ -d monitor/log ] && [ -d monitor/execute ]; then
                echo "Monitoring dirs exist" 1>&2
            else
                mkdir monitor monitor/log monitor/execute 
                if [ $? -ne 0 ]; then
                    #echo "Error creating monitor dirs" 1>&2
                    STR="Error creating monitor dirs"
                    "$error_gen" -error "condor_startup.sh" "WN_Resource" "$STR" "directory" "$PWD/monitor_monitor/log_monitor/execute"
                    exit 1
                fi
            fi
        fi
    fi  # end else of [ "$use_multi_monitor" -eq 1 ]
fi  # end else of "get check_include file for testing" [ "$check_only" == "1" ]


if [ -d log ] && [ -d execute ]; then
  echo "log and execute dirs exist" 1>&2
else
  mkdir log execute 
  if [ $? -ne 0 ]; then
    #echo "Error creating condor dirs" 1>&2
    STR="Error creating monitor dirs"
    "$error_gen" -error "condor_startup.sh" "WN_Resource" "$STR" "directory" "$PWD/log_execute"
    exit 1
  fi
fi

####################################

if [ "$print_debug" -ne "0" ]; then
  echo "--- condor_config ---" 1>&2
  cat $CONDOR_CONFIG 1>&2
  echo "--- ============= ---" 1>&2
  env 1>&2
  echo "--- ============= ---" 1>&2
  echo 1>&2
  #env 1>&2
fi

#Set the LD_LIBRARY_PATH so condor uses dynamically linked libraries correctly
export LD_LIBRARY_PATH=$CONDOR_DIR/lib:$CONDOR_DIR/lib/condor:$LD_LIBRARY_PATH

#
# The config is complete at this point
#

if [ "$adv_only" -eq "1" ]; then
    adv_type=`grep -i "^GLIDEIN_ADVERTISE_TYPE " "$config_file" | cut -d ' ' -f 2-`

    chmod u+rx "${main_stage_dir}/advertise_failure.helper"
    "${main_stage_dir}/advertise_failure.helper" "$CONDOR_DIR/sbin/condor_advertise" "${adv_type}" "${adv_destination}"
    # short circuit... do not even try to start the Condor daemons below
    exit $?
fi


X509_BACKUP=$X509_USER_PROXY
if [ "$expose_x509" == "true" ]; then
    echo "Exposing X509_USER_PROXY $X509_USER_PROXY" 1>&2
else
    echo "Unsetting X509_USER_PROXY" 1>&2
    unset X509_USER_PROXY
fi

## start the monitoring condor master
if [ "$use_multi_monitor" -ne 1 ]; then
    # don't start if monitoring is disabled
    if [ "$GLIDEIN_Monitoring_Enabled" == "True" ]; then
      # start monitoring startd
      # use the appropriate configuration file
      tmp_condor_config=$CONDOR_CONFIG
      export CONDOR_CONFIG=$condor_config_monitor

      monitor_start_time=`date +%s`
      echo "Starting monitoring condor at `date` (`date +%s`)" 1>&2

      # set the worst case limit
      # should never hit it, but let's be safe and shutdown automatically at some point
      let "monretmins=( $retire_time + $GLIDEIN_Job_Max_Time ) / 60 - 1"
      $CONDOR_DIR/sbin/condor_master -f -r $monretmins -pidfile $PWD/monitor/condor_master.pid  >/dev/null 2>&1 </dev/null &
      ret=$?
      if [ "$ret" -ne 0 ]; then
      echo 'Failed to start monitoring condor... still going ahead' 1>&2
      fi

      # clean back
      export CONDOR_CONFIG=$tmp_condor_config

      monitor_starter_log='monitor/log/StarterLog'
    fi
      main_starter_log='log/StarterLog'
      main_condor_log='log/StartdLog'
else
    main_starter_log='log/StarterLog.vm2'
    monitor_starter_log='log/StarterLog.vm1'
fi

start_time=`date +%s`
echo "=== Condor starting `date` (`date +%s`) ==="
ON_DIE=0
condor_pid=
trap 'ignore_signal' SIGHUP
trap_with_arg on_die SIGTERM SIGINT SIGQUIT
#trap 'on_die' TERM
#trap 'on_die' INT

#### STARTS CONDOR ####
if [[ "$check_only" == "1" ]]; then
    echo "=== Condor started in test mode ==="
    $CONDOR_DIR/sbin/condor_master -pidfile $PWD/condor_master.pid
else
    $CONDOR_DIR/sbin/condor_master -f -pidfile $PWD/condor_master2.pid &
    condor_pid=$!
    # Wait for a few seconds to make sure the pid file is created,
    sleep 5 & wait $!
    # Wait more if the pid file was not created and the Glidein was not killed, see [#9639]
    # Waiting additional 200s. HTCondor performs a hostname resolution and, if it fails, it retries every 3 seconds,
    # 40 times, before continuing. This makes for 120 seconds.
    if [[ ! -e "$PWD/condor_master2.pid" ]] && [[ "$ON_DIE" -eq 0 ]]; then
        echo "=== Condor started in background but the pid file is still missing, waiting 200 sec more ==="
        sleep 200 & wait $!
    fi
    # then wait on it for completion
    if [[ -e "$PWD/condor_master2.pid" ]]; then
        [[ "$condor_pid" -ne `cat "$PWD/condor_master2.pid"` ]] && echo "Background PID $condor_pid is different from PID file content `cat "$PWD/condor_master2.pid"`"
        echo "=== Condor started in background, now waiting on process $condor_pid ==="
        wait $condor_pid
    else
        # If ON_DIE == 1, condor has already been killed by a signal
        if [[ "$ON_DIE" -eq 0 ]]; then
            echo "=== Condor was started but the PID file is still missing, killing process $condor_pid ==="
            kill -s SIGQUIT $condor_pid
        fi
    fi
fi
condor_ret=$?
condor_pid=

if [ ${condor_ret} -eq 99 ]; then
    echo "Normal DAEMON_SHUTDOWN encountered" 1>&2
    condor_ret=0
    metrics+=" AutoShutdown True"
else
    metrics+=" AutoShutdown False"
fi

end_time=`date +%s`
let elapsed_time=$end_time-$start_time
echo "=== Condor ended `date` (`date +%s`) after $elapsed_time ==="
echo

metrics+=" CondorDuration $elapsed_time"


## perform a condor_fetchlog against the condor_startd
##    if fetch fails, sleep for 'fetch_sleeptime' amount
##    of seconds, then try again.  Repeat until
##    'timeout' amount of time has been reached.
if [ "$check_only" -eq 1 ]; then

    HOST=`uname -n`

    # debug statement
    # echo "CONDOR_CONFIG ENV VAR= `env | grep CONDOR_CONFIG | awk '{split($0,a,"="); print a[2]}'`" 1>&2
    #echo "running condor_fetchlog with the following:" 1>&2
    #echo "\t$CONDOR_DIR/sbin/condor_fetchlog -startd $STARTD_NAME@$HOST STARTD" 1>&2

    fetch_sleeptime=30      # can be dynamically set
    fetch_timeout=500       # can be dynamically set
    fetch_curTime=0
    fetch_exit_code=1
    let fetch_attemptsLeft="$fetch_timeout / $fetch_sleeptime"
    while [ "$fetch_curTime" -lt "$fetch_timeout" ]; do
        sleep $fetch_sleeptime

        # grab user proxy so we can authenticate ourselves to run condor_fetchlog
        PROXY_FILE="`grep -i "^X509_USER_PROXY " "$config_file" | cut -d ' ' -f 2-`"

        let "fetch_curTime  += $fetch_sleeptime" 
        FETCH_RESULTS=`X509_USER_PROXY=$PROXY_FILE $CONDOR_DIR/sbin/condor_fetchlog -startd $STARTD_NAME@$HOST STARTD`
        fetch_exit_code=$?
        if [ $fetch_exit_code -eq 0 ]; then
            break
        fi
        echo "fetch exit code=$fetch_exit_code" 1>&2
        echo "fetch failed in this iteration...will try $fetch_attemptsLeft more times."  >&2
        let "fetch_attemptsLeft -= 1"
    done

    if [ $fetch_exit_code -ne 0 ]; then
        echo "Able to talk to startd? FALSE" 1>&1 1>&2
        echo "Failed to talk to startd $STARTD_NAME on host $HOST" >&2
        echo "Reason for failing: Condor_fetchlog took too long to talk to host" >&2
        echo "time spent trying to fetch : $fetch_curTime" >&2
    else
        echo "Able to talk to startd? TRUE" 1>&1 1>&2
        echo "Successfully talked to startd $STARTD_NAME on host $HOST" >&2
        echo "Fetch Results from condor_fetchlog: $FETCH_RESULTS" >&2
    fi

    ## KILL CONDOR
    KILL_RES=`$CONDOR_DIR/sbin/condor_master -k $PWD/condor_master.pid`
fi

# log dir is always different
# get the real name
log_dir='log'

echo "Total jobs/goodZ jobs/goodNZ jobs/badSignal jobs/badOther jobs below are normalized to 1 Core"
echo "=== Stats of main ==="
if [ -f "${main_starter_log}" ]; then
    echo "===NewFile===" > separator_log.txt
    listtoparse="separator_log.txt"
    slotlogs="`ls -1 ${main_starter_log} ${main_starter_log}.slot* 2>/dev/null`"
    for slotlog in $slotlogs
    do
        listtoparse="$listtoparse $slotlog separator_log.txt"
    done
    parsed_out=`cat $listtoparse | awk -v parallelism=${GLIDEIN_CPUS} -f "${main_stage_dir}/parse_starterlog.awk"`
    echo "$parsed_out"

    parsed_metrics=`echo "$parsed_out" | awk 'BEGIN{p=0;}/^Total /{if (p==1) {if ($2=="jobs") {t="Total";n=$3;m=$5;} else {t=$2;n=$4;m=$7;} print t "JobsNr " n " " t "JobsTime " m;}}/^====/{p=1;}'`
    # use echo to strip newlines
    metrics+=`echo " " $parsed_metrics`
fi
echo "=== End Stats of main ==="

if [ -f "${main_condor_log}" ]; then
    numactivations=`grep "Got activate_claim" "${main_condor_log}" 2>/dev/null | wc -l`
    echo "Total number of activations/claims: $numactivations"
fi

ls -l log 1>&2
echo
cond_print_log MasterLog log/MasterLog
cond_print_log StartdLog log/StartdLog
cond_print_log StarterLog ${main_starter_log}
slotlogs="`ls -1 ${main_starter_log}.slot* 2>/dev/null`"
for slotlog in $slotlogs
do
    slotname=`echo $slotlog | awk -F"${main_starter_log}." '{print $2}'`
    cond_print_log StarterLog.${slotname} $slotlog
done

if [ "$use_multi_monitor" -ne 1 ]; then
    if [ "$GLIDEIN_Monitoring_Enabled" == "True" ]; then
        cond_print_log MasterLog.monitor monitor/log/MasterLog
        cond_print_log StartdLog.monitor monitor/log/StartdLog
        cond_print_log StarterLog.monitor ${monitor_starter_log}
    fi
else
    cond_print_log StarterLog.monitor ${monitor_starter_log}
fi
cond_print_log StartdHistoryLog log/StartdHistoryLog

## kill the master (which will kill the startd)
if [ "$use_multi_monitor" -ne 1 ]; then
    # terminate monitoring startd
    if [ "$GLIDEIN_Monitoring_Enabled" == "True" ]; then
        # use the appropriate configuration file
        tmp_condor_config=$CONDOR_CONFIG
        export CONDOR_CONFIG=$condor_config_monitor

        monitor_start_time=`date +%s`
        echo "Terminating monitoring condor at `date` (`date +%s`)" 1>&2

        #### KILL CONDOR ####
        $CONDOR_DIR/sbin/condor_master -k $PWD/monitor/condor_master.pid
        ####

        ret=$?
        if [ "$ret" -ne 0 ]; then
            echo 'Failed to terminate monitoring condor... still going ahead' 1>&2
        fi

        # clean back
        export CONDOR_CONFIG=$tmp_condor_config
    fi
fi

if [ "$ON_DIE" -eq 1 ]; then

    #If we are explicitly killed, do not wait required time
    echo "Explicitly killed, exiting with return code 0 instead of $condor_ret";

    condor_ret=0
    metrics+=" CondorKilled True"
else
    metrics+=" CondorKilled False"
fi

##
##########################################################

if [ "$condor_ret" -eq "0" ]; then
    "$error_gen" -ok "condor_startup.sh" $metrics
else
    "$error_gen" -error "condor_startup.sh" "Unknown" "See Condor logs for details" $metrics
fi

exit $condor_ret
