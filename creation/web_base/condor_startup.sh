#!/bin/bash

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

# Description:
#   This script starts the condor daemons. Expects a config file (glidien_config) as a parameter

trap_with_arg() {
    local sig func="$1" ; shift
    for sig ; do
        # shellcheck disable=SC2064  # Variables evaluated at setup
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
on_die() {
    # Can receive SIGTERM SIGINT SIGQUIT as $1, condor understands SIGTERM (graceful) SIGQUIT (fast). Send SIGQUIT for SIGQUIT, SIGTERM otherwise
    # condor_signal=$1
    # [[ "$condor_signal" != SIGQUIT ]] && condor_signal=SIGTERM
    # The HTCondor team suggested to send always SIGQUIT to speedup the shutdown and avoid leftover files
    condor_signal=SIGQUIT
    condor_pid_tokill=$condor_pid
    [[ -z "$condor_pid_tokill" ]] && condor_pid_tokill=$(cat "$PWD"/condor_master2.pid 2> /dev/null)
    echo "Condor startup received $1 signal ... shutting down condor processes (forwarding $condor_signal to $condor_pid_tokill)"
    [[ -n "$condor_pid_tokill" ]] && kill -s $condor_signal $condor_pid_tokill
    # "$CONDOR_DIR"/sbin/condor_master -k $PWD/condor_master2.pid
    ON_DIE=1
}

ignore_signal() {
    echo "Condor startup received SIGHUP signal, ignoring..."
}

metrics=""

# put in place a reasonable default
GLIDEIN_CPUS=1

# first of all, clean up any CONDOR variable
condor_vars=$(env |awk '/^_[Cc][Oo][Nn][Dd][Oo][Rr]_/{split($1,a,"=");print a[1]}')
for v in $condor_vars; do
    unset $v
done
echo "Removed condor variables $condor_vars" 1>&2
# removing CONDOR_INHERIT. See https://github.com/glideinWMS/glideinwms/issues/274
unset CONDOR_INHERIT

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

# Aux scripts: import gconfig functions and define error_gen
# most grep here are case insensitive (grep -i ... )
add_config_line_source=$(grep -m1 '^ADD_CONFIG_LINE_SOURCE ' "$config_file" | cut -d ' ' -f 2-)
# shellcheck source=add_config_line.source
. "$add_config_line_source"
error_gen=$(gconfig_get ERROR_GEN_PATH "$config_file")

# Read the knobs coming from the frontend configuration for blackhole detection (GLIDEIN_BLACKHOLE_NUMJOBS and GLIDEIN_BLACKHOLE_RATE)
glidein_blackhole_numjobs=$(gconfig_get GLIDEIN_BLACKHOLE_NUMJOBS "$config_file")
glidein_blackhole_rate=$(gconfig_get GLIDEIN_BLACKHOLE_RATE "$config_file")
if [[ -z "$glidein_blackhole_rate" || "$glidein_blackhole_rate" =~ ^0(\.0*)?$ ]]; then
    use_blackhole_prevention=false
else
    use_blackhole_prevention=true
fi

glidein_startup_pid=$(gconfig_get GLIDEIN_STARTUP_PID "$config_file")
# DO NOT USE PID FOR DAEMON NAMES
# If site's batch system is HTCondor and USE_PID_NAMESPACES is set pid's
# it does not play well with HTCondor daemon name creation
# $RANDOM is in range(0, 32K). Add extra safeguards
let "random_name_str=($RANDOM+1000)*($RANDOM+2000)"

# find out whether user wants to run job or run test
debug_mode=$(gconfig_get DEBUG_MODE "$config_file")

print_debug=0
check_only=0
if [ "$debug_mode" -ne 0 ]; then
    print_debug=1
    if [ "$debug_mode" -eq 2 ]; then
        check_only=1
    fi
fi

adv_only=$(gconfig_get GLIDEIN_ADVERTISE_ONLY "$config_file")

if [[ "$adv_only" -eq 1 ]]; then
    adv_destination=$(gconfig_get GLIDEIN_ADVERTISE_DESTINATION "$config_file")
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

if [[ "$print_debug" -ne 0 ]]; then
    echo "-------- $config_file in condor_startup.sh ----------" 1>&2
    cat "$config_file" 1>&2
    echo "-----------------------------------------------------" 1>&2
fi

main_stage_dir=$(gconfig_get GLIDEIN_WORK_DIR "$config_file")

description_file=$(gconfig_get DESCRIPTION_FILE "$config_file")

in_condor_config="${main_stage_dir}/$(grep -i '^condor_config ' "${main_stage_dir}/${description_file}" | cut -s -f 2-)"

export CONDOR_CONFIG="${PWD}/condor_config"

cp "$in_condor_config" "$CONDOR_CONFIG"

echo "# ---- start of condor_startup generated part ----" >> "$CONDOR_CONFIG"

wrapper_list=$(gconfig_get WRAPPER_LIST "$config_file")

#
# Create the job wrapper
#
# TODO: should it skip the wrapper if WRAPPER_LIST is empty?
condor_job_wrapper="condor_job_wrapper.sh"
cat > "$condor_job_wrapper" <<EOF
#!/bin/sh

# This script is started just before the user job
# It is referenced by the USER_JOB_WRAPPER
# /bin/sh is used for Busybox compatibility (small images)
if [ -n "$BASH_VERSION" ]; then
    # If in Bash, disable POSIX mode
    # shellcheck disable=SC3040
    set +o posix || echo "WARN: running in POSIX mode"
fi

EOF

for fname in $(cat "$wrapper_list");
do
    cat "$fname" >> "$condor_job_wrapper"
done


echo "USER_JOB_WRAPPER = \$(LOCAL_DIR)/$condor_job_wrapper" >> "$CONDOR_CONFIG"


# glidein_variables = list of additional variables startd is to publish
glidein_variables=""

CONDOR_REQUIRED_VAR_X509=",X509_USER_PROXY,X509_EXPIRE,X509_CERT_DIR,X509_CONDORMAP,"
is_var_required() {
    # Some condor variables have conditional/complex requirements
    # This functions returns true/0 if the variable is required, false/1 otherwise
    # e.g. X509_... variables are required only if there is no token support
    # 1. variable_name
    if [[ "$CONDOR_REQUIRED_VAR_X509" = *,$1,* ]]; then
        # If an IDTOKEN is available X509 variables are not required
        if [[ !  -e "$GLIDEIN_CONDOR_TOKEN" ]]; then
            true
            return
        fi
    fi
    false
}

set_var() {
    # Set a variable defined in condor_vars.lst file reading the value from glidein_config
    # condor_vars.lst format: var_name var_type var_default var_condor var_required var_exportcondor var_user
    local var_name=$1
    local var_type=$2
    local var_def=$3
    local var_condor=$4
    local var_req=$5
    local var_exportcondor=$6
    local var_user=$7

    if [[ -z "$var_name" ]]; then
        # empty line
        return 0
    fi
    # was: var_val=`grep "^$var_name " $config_file | awk '{if (NF>1) ind=length($1)+1; v=substr($0, ind); print substr(v, index(v, $2))}'`
    # this new version is not left-trimming, counting on a single space as separator
    var_val=$(gconfig_get "$var_name" "$config_file")
    if [[ -z "$var_val" ]]; then
        if [[ "$var_req" == "Y" ]] || is_var_required "$var_name"; then
            # needed var, exit with error
            #echo "Cannot extract $var_name from '$config_file'" 1>&2
            STR="Cannot extract $var_name from '$config_file'"
            "$error_gen" -error "condor_startup.sh" "Config" "$STR" "MissingAttribute" "$var_name"
            exit 1
        elif [[ "$var_def" == "-" ]]; then
            # no default, do not set
            return 0
        else
            eval var_val="$var_def"
        fi
    fi

    if [[ "$var_condor" == "+" ]]; then
        var_condor=$var_name
    fi
    if [[ "$var_type" == "S" ]]; then
        var_val_str="${pstr}${var_val}${pstr}"
    else
        var_val_str="$var_val"
    fi

    # insert into condor_config
    echo "$var_condor=$var_val_str" >> "$CONDOR_CONFIG"

    if [[ "$var_exportcondor" == "Y" ]]; then
        # register var_condor for export
        if [ -z "$glidein_variables" ]; then
           glidein_variables="$var_condor"
        else
           glidein_variables="$glidein_variables,$var_condor"
        fi
    fi

    if [[ "$var_user" != "-" ]]; then
        # - means do not export
        if [[ "$var_user" == "+" ]]; then
            var_user=$var_name
        elif [[ "$var_user" == "@" ]]; then
            var_user=$var_condor
        fi

        condor_env_entry="$var_user=$var_val"
        condor_env_entry=$(echo "$condor_env_entry" | awk '{gsub(/"/,"\"\""); print}')
        condor_env_entry=$(echo "$condor_env_entry" | awk "{gsub(/'/,\"''\"); print}")
        if [[ -z "$job_env" ]]; then
           job_env="'$condor_env_entry'"
        else
           job_env="$job_env '$condor_env_entry'"
        fi
    fi

    # define it for future use
    eval "$var_name='$var_val'"
    return 0
}

# TODO: import from b64uuencode.source instead of redefining
#       check about maxsize 45 (60 per line) vs 57 (76 x line), both OK, <80

get_python() {
    local py_command
    if command -v python3 > /dev/null 2>&1; then
        py_command="python3"
    elif command -v python > /dev/null 2>&1; then
        py_command="python"
    elif command -v python2 > /dev/null 2>&1; then
        py_command="python2"
    elif command -v gwms-python > /dev/null 2>&1; then
        py_command="gwms-python"
    else
        return 1
    fi
    echo "$py_command"
}

python_b64uuencode() {
    echo "begin-base64 644 -"
    if py_command=$(get_python); then
        $py_command -c 'from __future__ import print_function; import binascii,sys;
fdb=getattr(sys.stdin, "buffer", sys.stdin);buf=fdb.read();size=len(buf);idx=0
while size>57:
 print(binascii.b2a_base64(buf[idx:idx+57]).decode(), end="");
 idx+=57;
 size-=57;
print(binascii.b2a_base64(buf[idx:]).decode(), end="")'
    else
        echo "ERROR_FAILED_ENCODING"
    fi
    echo "===="
}

base64_b64uuencode() {
    echo "begin-base64 644 -"
    base64 -
    echo "===="
}

# not all WNs have all the tools installed
b64uuencode() {
    if which uuencode >/dev/null 2>&1; then
        uuencode -m -
    elif which base64 >/dev/null 2>&1; then
        base64_b64uuencode
    else
        python_b64uuencode
    fi
}

cond_print_log() {
    # $1 = fname
    # $2 = fpath

    logname=$1
    shift
    # Use ls to allow fpath to include wild cards
    files_to_zip=$(ls -1 "$@" 2>/dev/null)

    if [[ "$files_to_zip" != "" ]]; then
        echo "$logname" 1>&2
        echo "======== gzip | uuencode =============" 1>&2
        gzip --stdout $files_to_zip | b64uuencode 1>&2
        echo
    fi
}


fix_param() {
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
            if [[ -n "$dict_start" ]]; then
                echo "Positional parameter after dictionary in ($1). Aborting." 1>&2
                return 1
            fi
            RESLIST[res_ctr]=$i
        fi
        ((res_ctr+=1))
    done
    res="${RESLIST[0]}"
    ((res_ctr=${#varnames_len}-1))
    for i in $(seq 1 1 "$res_ctr" 2>/dev/null); do
        res="$res,${RESLIST[$i]}"
    done
    echo "$res"
}


unit_division() {
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
    echo "$res"
}


find_gpus_num() {
    # use condor tools to find the available GPUs
    if [[ ! -f "$CONDOR_DIR/libexec/condor_gpu_discovery" ]]; then
        echo "WARNING: condor_gpu_discovery not found" 1>&2
        return 1
    fi
    local tmp tmp1
    tmp1=$( "$CONDOR_DIR"/libexec/condor_gpu_discovery )
    local ec=$?
    if [[ $ec -ne 0 ]]; then
        echo "WARNING: condor_gpu_discovery failed (exit code: $ec)" 1>&2
        return $ec
    fi
    tmp=$( echo "$tmp1" | grep "^DetectedGPUs=" )
    if [[ "${tmp:13}" = 0 ]]; then
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
    condor_vars=$(gconfig_get "$vid" "$config_file")
    if [[ -n "$condor_vars" ]]; then
        grep -v "^#" "$condor_vars" >> condor_vars.lst.tmp
    fi
done

GLIDEIN_CONDOR_TOKEN=$(gconfig_get GLIDEIN_CONDOR_TOKEN "$config_file")
while read line
do
    set_var $line
done < condor_vars.lst.tmp

# The exec command GLIDEIN_WRAPPER_EXEC is and must be already quoted (e.g. "\\\"\\\$@\\\"")
# This allows to modify the wrapper parameters list
cat >> "$condor_job_wrapper" <<EOF

# Condor job wrappers must replace its own image
exec $GLIDEIN_WRAPPER_EXEC
EOF
chmod a+x "$condor_job_wrapper"

now=$(date +%s)
# If not an integer reset to 0 (a string could cause errors [#7899])
[ "$X509_EXPIRE" -eq "$X509_EXPIRE" ] 2>/dev/null || X509_EXPIRE=0

[ "$X509_EXPIRE" -eq 0 ] && [ -e "$GLIDEIN_CONDOR_TOKEN" ] && let "X509_EXPIRE=$now + 86400"

#add some safety margin
((x509_duration= X509_EXPIRE - now - 300))

# Get relevant attributes from glidein_config if they exist
# if they do not, check condor config from vars population above
max_walltime=$(gconfig_get GLIDEIN_Max_Walltime "$config_file")
job_maxtime=$(gconfig_get GLIDEIN_Job_Max_Time "$config_file")
graceful_shutdown=$(gconfig_get GLIDEIN_Graceful_Shutdown "$config_file")
# randomize the retire time, to smooth starts and terminations
retire_spread=$(gconfig_get GLIDEIN_Retire_Time_Spread "$config_file")
expose_x509=$(gconfig_get GLIDEIN_Expose_X509 "$config_file")

if [[ -z "$expose_x509" ]]; then
    # parsing condor_config - not glidein_config
    expose_x509=$(grep -i "^GLIDEIN_Expose_X509=" "$CONDOR_CONFIG" | awk -F"=" '{print $2}')
    if [[ -z "$expose_x509" ]]; then
        expose_x509="false"
    fi
fi
expose_x509=$(echo $expose_x509 | tr '[:upper:]' '[:lower:]')

if [[ -z "$graceful_shutdown" ]]; then
    # parsing condor_config - not glidein_config
    graceful_shutdown=$(grep -i "^GLIDEIN_Graceful_Shutdown=" "$CONDOR_CONFIG" | awk -F"=" '{print $2}')
    if [[ -z "$graceful_shutdown" ]]; then
        echo "WARNING: graceful shutdown not defined in vars or glidein_config, using 120!" 1>&2
        graceful_shutdown=120
    fi
fi
if [[ -z "$job_maxtime" ]]; then
    # parsing condor_config
    job_maxtime=$(grep -i "^GLIDEIN_Job_Max_Time=" "$CONDOR_CONFIG" | awk -F"=" '{print $2}')
    if [[ -z "$job_maxtime" ]]; then
        echo "WARNING: job max time not defined in vars or glidein_config, using 192600!" 1>&2
        job_maxtime=192600
    fi
fi

# import logging utility functions
logging_utils_source=$(gconfig_get LOGGING_UTILS_SOURCE "${config_file}")
# shellcheck source=logging_utils.source
. "${logging_utils_source}"
glog_setup "${config_file}"

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
if [[ -z "$max_walltime" ]]; then
    retire_time=$(gconfig_get GLIDEIN_Retire_Time "$config_file")
    if [[ -z "$retire_time" ]]; then
        retire_time=21600
        echo "used default retire time, $retire_time" 1>&2
    else
        echo "used param defined retire time, $retire_time" 1>&2
    fi
    ((die_time = retire_time + job_maxtime))
else
    echo "max wall time, $max_walltime" 1>&2

    if [[ -z "$retire_spread" ]]; then
        # Make sure that the default spread is enough so that we
        # dont drop below min_glidein (ie 600 seconds)
        ((default_spread = (min_glidein * 11) / 100))
    else
        ((default_spread = retire_spread))
    fi

    # Make sure retire time is not set to less than 300 plus default spread
    # (since job max default is set to 36hours, this can happen)
    # total_grace=max total time to end glidein after DAEMON_SHUTDOWN occurs
    ((total_grace= graceful_shutdown + default_spread + update_interval))
    ((total_job_allotment= total_grace + job_maxtime + min_glidein))
    if [[ "$total_job_allotment" -gt "$max_walltime" ]]; then
        ((job_maxtime= max_walltime - total_grace - min_glidein))
        if [[ "$job_maxtime" -lt "0" ]]; then
            ((job_maxtime=0))
        fi
        echo "WARNING: job max time is bigger than max_walltime, lowering it.  " 1>&2
    fi
    echo "job max time, $job_maxtime" 1>&2

    ((die_time= max_walltime - update_interval - graceful_shutdown))
    ((retire_time= die_time - job_maxtime))
    GLIDEIN_Retire_Time=$retire_time
    echo "calculated retire time, $retire_time" 1>&2
fi

# make sure the glidein goes away before the proxy expires
if [[ "$die_time" -gt "$x509_duration" ]]; then
    ignore_x509=$(gconfig_get GLIDEIN_Ignore_X509_Duration "$config_file" | tr '[:upper:]' '[:lower:]')
    if [[ "$x509_duration" -lt 900 ]]; then
        echo "Remaining proxy duration is less than 15min. Shortening the Glidein lifetime."
        ignore_x509=false
    fi
    if [[ "x$ignore_x509" == "xfalse" ]]; then
        # Subtract both die time and retire time by the difference
        ((reduce_time= die_time - x509_duration))
        ((die_time= x509_duration))
        ((retire_time= retire_time - reduce_time))
        echo "Proxy not long lived enough ($x509_duration s left), shortened retire time to $retire_time" 1>&2
    else
        echo "GLIDEIN_Ignore_X509_Duration is true (default). Ignoring glidein die time ($retire_time s) longer than remaining proxy duration ($x509_duration s)" 1>&2
    fi
fi


if [[ -z "$retire_spread" ]]; then
    ((retire_spread= retire_time / 10))
    echo "using default retire spread, $retire_spread" 1>&2
else
    echo "used param retire spread, $retire_spread" 1>&2
fi


((random100=RANDOM%100))
((retire_time= retire_time - retire_spread * random100 / 100))
((die_time= die_time - retire_spread * random100 / 100))

# but protect from going too low
if [[ "$retire_time" -lt "$min_glidein" ]]; then
    echo "Retire time after spread too low ($retire_time), remove spread" 1>&2
    # With the various calculations going on now with walltime
    # Safer to add spread rather than to revert to previous value
    ((retire_time= retire_time + retire_spread * random100 / 100))
    ((die_time= die_time + retire_spread * random100 / 100))
fi
if [[ "$retire_time" -lt "$min_glidein" ]] && [ "$adv_only" -ne "1" ]; then
    #echo "Retire time still too low ($retire_time), aborting" 1>&2
    STR="Retire time still too low ($retire_time), aborting"
    "$error_gen" -error "condor_startup.sh" "Config" "$STR" "retire_time" "$retire_time" "min_retire_time" "$min_glidein"
    exit 1
fi
echo "Retire time set to $retire_time" 1>&2
echo "Die time set to $die_time" 1>&2

((glidein_toretire= now + retire_time))
((glidein_todie= now + die_time))

# minimize re-authentications, by asking for a session length to be the same as proxy lifetime, if possible
((session_duration=x509_duration))

# if in test mode, don't ever start any jobs
START_JOBS="TRUE"
if [[ "$check_only" == "1" ]]; then
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
    LSB_RELEASE=$(lsb_release -rs | sed 's/"//g')
    LSB_DISTRIBUTOR_ID=$(lsb_release -is | sed 's/"//g')
    LSB_DESCRIPTION=$(lsb_release -ds | sed 's/"//g')
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

monitor_mode=$(gconfig_get MONITOR_MODE "$config_file")

if [[ "$monitor_mode" == "MULTI" ]]; then
    use_multi_monitor=1
else
    use_multi_monitor=0
fi

# get the periodic scripts configuration
condor_config_startd_cron_include=$(gconfig_get GLIDEIN_condor_config_startd_cron_include "$config_file")
if [[ -n "$condor_config_startd_cron_include" ]]; then
    echo "adding periodic scripts (startd_cron) configuration from: $condor_config_startd_cron_include" 1>&2
    echo "# ---- start of startd_cron part ----" >> "$CONDOR_CONFIG"
    cat "$condor_config_startd_cron_include" >> "$CONDOR_CONFIG"
fi

# get check_include file for testing
if [[ "$check_only" == "1" ]]; then
    condor_config_check_include="${main_stage_dir}/`grep -i '^condor_config_check_include ' ${main_stage_dir}/${description_file} | awk '{print $2}'`"
    echo "# ---- start of include part ----" >> "$CONDOR_CONFIG"
    if ! cat "$condor_config_check_include" >> "$CONDOR_CONFIG"; then
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
    if [[ "$use_multi_monitor" -eq 1 ]]; then
        condor_config_multi_include="${main_stage_dir}/`grep -i '^condor_config_multi_include ' ${main_stage_dir}/${description_file} | awk '{print $2}'`"
        echo "# ---- start of include part ----" >> "$CONDOR_CONFIG"
        if ! cat "$condor_config_multi_include" >> "$CONDOR_CONFIG"; then
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
        if [[ "$GLIDEIN_Monitoring_Enabled" == "True" ]]; then
            condor_config_monitor_include="${main_stage_dir}/`grep -i '^condor_config_monitor_include ' ${main_stage_dir}/${description_file} | awk '{print $2}'`"
            condor_config_monitor=${CONDOR_CONFIG}.monitor
            if ! cp "$CONDOR_CONFIG" "$condor_config_monitor"; then
                #echo "Error copying condor_config into condor_config.monitor" 1>&2
                STR="Error copying condor_config into condor_config.monitor"
                "$error_gen" -error "condor_startup.sh" "WN_Resource" "$STR" "infile" "$condor_config_monitor" "file" "$CONDOR_CONFIG"
                exit 1
            fi
            if ! cat "$condor_config_monitor_include" >> "$condor_config_monitor"; then
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
        # glidein_disk empty is the same as auto, used in the slot_type definitions
        glidein_disk=$(gconfig_get GLIDEIN_DISK "$config_file")
        # set up the slots based on the slots_layout entry parameter
        slots_layout=$(gconfig_get SLOTS_LAYOUT "$config_file")
        if [[ "X$slots_layout" = "Xpartitionable" ]]; then
            echo "NUM_SLOTS = 1" >> "$CONDOR_CONFIG"
            echo "SLOT_TYPE_1 = cpus=\$(GLIDEIN_CPUS) ${glidein_disk:+disk=${glidein_disk}}" >> "$CONDOR_CONFIG"
            echo "NUM_SLOTS_TYPE_1 = 1" >> "$CONDOR_CONFIG"
            echo "SLOT_TYPE_1_PARTITIONABLE = True" >> "$CONDOR_CONFIG"
            num_slots_for_shutdown_expr=1
            # Blackhole calculation based on the parent startd stats (child slots will have the same stats).
            if $use_blackhole_prevention; then
                cat >> "$CONDOR_CONFIG" <<EOF
BLACKHOLE_TRIGGERED_P = (RecentJobBusyTimeAvg < (1.0/$glidein_blackhole_rate)) && (RecentJobBusyTimeCount >= $glidein_blackhole_numjobs)
GLIDEIN_BLACKHOLE = ifThenElse(isUndefined(\$(BLACKHOLE_TRIGGERED_P)), False, \$(BLACKHOLE_TRIGGERED_P))
EOF
            fi
        else
            # fixed slot
            [[ -n "$glidein_disk" ]] && glidein_disk=$(unit_division $glidein_disk $GLIDEIN_CPUS)
            echo "SLOT_TYPE_1 = cpus=1 ${glidein_disk:+disk=${glidein_disk}}" >> "$CONDOR_CONFIG"
            echo "NUM_SLOTS_TYPE_1 = \$(GLIDEIN_CPUS)" >> "$CONDOR_CONFIG"
            num_slots_for_shutdown_expr=$GLIDEIN_CPUS
            #Blackhole calculation based on the startd stats for fixed slots
            if $use_blackhole_prevention; then
                for I in `seq 1 $num_slots_for_shutdown_expr`; do
                    cat >> "$CONDOR_CONFIG" <<EOF
BLACKHOLE_TRIGGERED_${I} = (RecentJobBusyTimeAvg < (1.0/$glidein_blackhole_rate)) && (RecentJobBusyTimeCount >= $glidein_blackhole_numjobs)
GLIDEIN_BLACKHOLE = ifThenElse(isUndefined(\$(BLACKHOLE_TRIGGERED_${I})), False, \$(BLACKHOLE_TRIGGERED_${I}))
EOF
                done
            fi
        fi
        if $use_blackhole_prevention; then
            cat >> "$CONDOR_CONFIG" <<EOF
#Stats that make detection of black-hole slots
STARTD.STATISTICS_TO_PUBLISH_LIST = \$(STATISTICS_TO_PUBLISH_LIST) JobBusyTime JobDuration
GLIDEIN_BLACKHOLE_NUMJOBS = $glidein_blackhole_numjobs
GLIDEIN_BLACKHOLE_RATE = $glidein_blackhole_rate
STARTD_LATCH_EXPRS = GLIDEIN_BLACKHOLE
STARTD_ATTRS = \$(STARTD_ATTRS), GLIDEIN_BLACKHOLE, GLIDEIN_BLACKHOLE_NUMJOBS, GLIDEIN_BLACKHOLE_RATE
START = (\$(START)) && (\$(GLIDEIN_BLACKHOLE) =?= False)
EOF
        fi

        # check for resource slots
        # resource_name GPUs has special meaning, enables GPUs (including monitoring and autodetection if desired)
        condor_config_resource_slots=$(gconfig_get GLIDEIN_Resource_Slots "$config_file")
        if [[ -z "$condor_config_resource_slots" ]]; then
            # GPUs should be set to 0 if not desired, otherwise HTCondor will enable them
            echo "MACHINE_RESOURCE_GPUs = 0" >> "$CONDOR_CONFIG"
        else
            cc_resource_slots_has_gpus=0
            echo "adding resource slots configuration: $condor_config_resource_slots" 1>&2
            cat >> "$CONDOR_CONFIG" <<EOF
# ---- start of resource slots part ($condor_config_resource_slots) ----
NEW_RESOURCES_LIST =
EXTRA_SLOTS_NUM = 0
EXTRA_CPUS_NUM = 0
EXTRA_MEMORY_MB = 0
EXTRA_SLOTS_START = True
NUM_CPUS = \$(GLIDEIN_CPUS)+\$(EXTRA_SLOTS_NUM)+\$(EXTRA_CPUS_NUM)
MEMORY = \$(GLIDEIN_MaxMemMBs)+\$(EXTRA_MEMORY_MB)

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
            # Extra memory to add for all the staticextra slots
            cc_resource_slots_mem_add=0
            for i in "${RESOURCES[@]}"; do
                resource_params=$(fix_param "$i" "name,number,memory,type,disk")
                IFS=',' read res_name res_num res_ram res_opt res_disk <<< "$resource_params"
                if [[ -z "$res_name" ]]; then
                    continue
                fi
                GPU_USE=
                GPU_AUTO=
                [[ "$(echo "$res_name" | tr -s '[:upper:]' '[:lower:]')" = "gpus" ]] && GPU_USE=True
                if [[ "$GPU_USE" == "True" ]]; then
                    (( cc_resource_slots_has_gpus++ ))
                fi
                if [[ -z "$res_num" ]]; then
                    # GPUs can be auto-discovered, other resources default to 1
                    if [[ -n "$GPU_USE" ]]; then
                        # GPUs auto-discovery: https://htcondor-wiki.cs.wisc.edu/index.cgi/wiki?p=HowToManageGpus
                        res_num=$(find_gpus_num)
                        ec=$?
                        if [ $ec -eq 0 ]; then
                            echo "GPU autodiscovery (condor_gpu_discovery) found $res_num GPUs" 1>&2
                            GPU_AUTO=True
                        else
                            echo "GPU autodiscovery (condor_gpu_discovery) failed, disabling auto discovery, assuming 0 GPUs." 1>&2
                            res_num=0
                        fi
                    else
                        res_num=1
                    fi
                fi
                if [[ -z "$res_ram" ]]; then
                    # Will be ignored if res_opt=main
                    ((res_ram= 128*res_num))
                fi
                if [[ -n "$GPU_AUTO" ]]; then
                    cat >> "$CONDOR_CONFIG" <<EOF
# Declare GPUs resource, auto-discovered: ${i}
use feature : GPUs
# GPUsMonitor is automatically included in newer HTCondor
use feature : GPUsMonitor
GPU_DISCOVERY_EXTRA = -extra
# Protect against no GPUs found
if defined MACHINE_RESOURCE_${res_name}
else
  MACHINE_RESOURCE_${res_name} = 0
endif
EOF
                elif [[ -n "$GPU_USE" ]]; then
                    cat >> "$CONDOR_CONFIG" <<EOF
# Declare GPU resource, forcing ${res_num}: ${i}
use feature : GPUs
# GPUsMonitor is automatically included in newer HTCondor
use feature : GPUsMonitor
GPU_DISCOVERY_EXTRA = -extra
MACHINE_RESOURCE_${res_name} = ${res_num}
EOF
                else
                    cat >> "$CONDOR_CONFIG" <<EOF
# Declare resource: ${i}
MACHINE_RESOURCE_${res_name} = ${res_num}
EOF
                fi
                if [[ "$res_opt" == "extra" ]]; then
                    # Like main, but adds CPUs
                    res_opt=main
                    echo "EXTRA_CPUS_NUM = \$(EXTRA_CPUS_NUM)+\$(MACHINE_RESOURCE_${res_name})" >> "$CONDOR_CONFIG"
                fi
                if [[ "$res_opt" == "main" ]]; then  # which is the default value? main or static?
                    res_opt=
                    # Resource allocated for only main slots (partitionable or static)
                    # Main slots are determined by CPUs. Let condor split the resource: if not enough some slot will have none
                    echo "SLOT_TYPE_1 = \$(SLOT_TYPE_1), ${res_name}=100%" >> "$CONDOR_CONFIG"
                    # Decided not to add type "mainextra" with resources added to main slot and CPUs incremented
                    # It can be obtained with more control by setting GLIDEIN_CPUS
                else
                    if [[ "$res_num" -eq 1 || "$res_opt" == "static" || "$res_opt" == "staticextra" ]]; then
                        if [[ "$res_opt" == "partitionable" ]]; then
                            res_opt=static
                        fi
                        res_ram=$(unit_division "${res_ram}" ${res_num})
                        if [[ -n "$res_disk" ]]; then
                            res_disk=$(unit_division "${res_disk}" ${res_num})
                        fi
                    else
                        res_opt=partitionable
                    fi
                fi
                if [[ -z "$res_disk" ]]; then
                    # Set default here. What to do if disk is not given? Empty string lets HTCondor handle it
                    res_disk_specification=''
                else
                    res_disk_specification=", disk=${res_disk}"
                fi
                if [[ -n "$res_opt" ]]; then
                    # no main, separate static or partitionable
                    cat >> "$CONDOR_CONFIG" <<EOF
EXTRA_SLOTS_NUM = \$(EXTRA_SLOTS_NUM)+\$(MACHINE_RESOURCE_${res_name})
EOF
                    if [[ "$res_opt" == "partitionable" ]]; then
                        cat >> "$CONDOR_CONFIG" <<EOF
SLOT_TYPE_${slott_ctr} = cpus=\$(MACHINE_RESOURCE_${res_name}), ${res_name}=\$(MACHINE_RESOURCE_${res_name}), ram=${res_ram}${res_disk_specification}
SLOT_TYPE_${slott_ctr}_PARTITIONABLE = TRUE
NUM_SLOTS_TYPE_${slott_ctr} = 1
EOF
                    else
                        if [[ "$res_opt" == "staticextra" ]]; then
                            ((cc_resource_slots_mem_add=cc_resource_slots_mem_add+res_ram))
                        fi
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
                    ((slott_ctr+=1))
                fi
                echo "NEW_RESOURCES_LIST = \$(NEW_RESOURCES_LIST) $res_name" >> "$CONDOR_CONFIG"

            done  # end per-resource loop

            # Epilogue RAM
            if [[ "$cc_resource_slots_mem_add" -ne 0 ]]; then
                echo "EXTRA_MEMORY_MB = ${cc_resource_slots_mem_add}" >> "$CONDOR_CONFIG"
            fi

            # Epilogue GPUs handling
            if [[ "$cc_resource_slots_has_gpus" -eq 0 ]]; then
                echo "MACHINE_RESOURCE_GPUs = 0" >> "$CONDOR_CONFIG"
            elif [[ "$cc_resource_slots_has_gpus" -gt 1 ]]; then
                echo "WARNING: More than one GPU resource defined in GLIDEIN_Resource_Slots" 1>&2
            fi

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
# If some jobs were scheduled on the startd (TAIL) or none at all (NOJOB)
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
            if [[ -n "$daemon_shutdown" ]]; then
                daemon_shutdown="$daemon_shutdown &&"
            fi
            daemon_shutdown="$daemon_shutdown \$(DS${I})"
        done
        echo "STARTD.DAEMON_SHUTDOWN = $daemon_shutdown" >> "$CONDOR_CONFIG"

        if ! cat "$condor_config_main_include" >> "$CONDOR_CONFIG"; then
            #echo "Error appending main_include to condor_config" 1>&2
            STR="Error appending main_include to condor_config"
            "$error_gen" -error "condor_startup.sh" "WN_Resource" "$STR" "file" "$CONDOR_CONFIG" "infile" "$condor_config_main_include"
            exit 1
        fi

        if [[ "$GLIDEIN_Monitoring_Enabled" == "True" ]]; then
            cat >> "$CONDOR_CONFIG" <<EOF

Monitoring_Name = "monitor_$$@\$(FULL_HOSTNAME)"
EOF

            # also needs to create "monitor" dir for log and execute dirs
            if [ -d monitor ] && [ -d monitor/log ] && [ -d monitor/execute ]; then
                echo "Monitoring dirs exist" 1>&2
            else
                if ! mkdir monitor monitor/log monitor/execute; then
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
  if ! mkdir log execute ; then
    #echo "Error creating condor dirs" 1>&2
    STR="Error creating monitor dirs"
    "$error_gen" -error "condor_startup.sh" "WN_Resource" "$STR" "directory" "$PWD/log_execute"
    exit 1
  fi
fi

####################################

if [[ "$print_debug" -ne "0" ]]; then
  echo "--- condor_config ---" 1>&2
  cat $CONDOR_CONFIG 1>&2
  echo "--- ============= ---" 1>&2
  env 1>&2
  echo "--- ============= ---" 1>&2
  echo 1>&2
  #env 1>&2
fi

#
# The config is complete at this point
#

if [[ "$adv_only" -eq "1" ]]; then
    adv_type=$(gconfig_get GLIDEIN_ADVERTISE_TYPE "$config_file")

    chmod u+rx "${main_stage_dir}/advertise_failure.helper"
    "${main_stage_dir}/advertise_failure.helper" "$CONDOR_DIR/sbin/condor_advertise" "${adv_type}" "${adv_destination}"
    # short circuit... do not even try to start the Condor daemons below
    exit $?
fi


X509_BACKUP=$X509_USER_PROXY
if [[ "$expose_x509" == "true" ]]; then
    echo "Exposing X509_USER_PROXY $X509_USER_PROXY" 1>&2
else
    echo "Unsetting X509_USER_PROXY" 1>&2
    unset X509_USER_PROXY
fi

## start the monitoring condor master
if [[ "$use_multi_monitor" -ne 1 ]]; then
    # don't start if monitoring is disabled
    if [[ "$GLIDEIN_Monitoring_Enabled" == "True" ]]; then
        # start monitoring startd
        # use the appropriate configuration file
        tmp_condor_config=$CONDOR_CONFIG
        export CONDOR_CONFIG=$condor_config_monitor

        monitor_start_time=$(date +%s)
        echo "Starting monitoring condor at $(date -d "@$monitor_start_time") ($monitor_start_time)" 1>&2

        # set the worst case limit
        # should never hit it, but let's be safe and shutdown automatically at some point
        ((monretmins= ( retire_time + GLIDEIN_Job_Max_Time ) / 60 - 1))
        "$CONDOR_DIR"/sbin/condor_master -f -r $monretmins -pidfile "$PWD"/monitor/condor_master.pid  >/dev/null 2>&1 </dev/null &
        ret=$?
        if [[ "$ret" -ne 0 ]]; then
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

start_time=$(date +%s)
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
    "$CONDOR_DIR"/sbin/condor_master -pidfile "$PWD"/condor_master.pid
else
    "$CONDOR_DIR"/sbin/condor_master -f -pidfile "$PWD"/condor_master2.pid &
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
        [[ "$condor_pid" -ne $(cat "$PWD/condor_master2.pid") ]] && echo "Background PID $condor_pid is different from PID file content `cat "$PWD/condor_master2.pid"`"
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

if [[ ${condor_ret} -eq 99 ]]; then
    echo "Normal DAEMON_SHUTDOWN encountered" 1>&2
    condor_ret=0
    metrics+=" AutoShutdown True"
else
    metrics+=" AutoShutdown False"
fi

end_time=$(date +%s)
((elapsed_time= end_time - start_time))
echo "=== Condor ended `date` (`date +%s`) after $elapsed_time ==="
echo

metrics+=" CondorDuration $elapsed_time"


## perform a condor_fetchlog against the condor_startd
##    if fetch fails, sleep for 'fetch_sleeptime' amount
##    of seconds, then try again.  Repeat until
##    'timeout' amount of time has been reached.
if [[ "$check_only" -eq 1 ]]; then

    HOST=$(uname -n)

    # debug statement
    # echo "CONDOR_CONFIG ENV VAR= `env | grep CONDOR_CONFIG | awk '{split($0,a,"="); print a[2]}'`" 1>&2
    #echo "running condor_fetchlog with the following:" 1>&2
    #echo "\t$CONDOR_DIR/sbin/condor_fetchlog -startd $STARTD_NAME@$HOST STARTD" 1>&2

    fetch_sleeptime=30      # can be dynamically set
    fetch_timeout=500       # can be dynamically set
    fetch_curTime=0
    fetch_exit_code=1
    let fetch_attemptsLeft="$fetch_timeout / $fetch_sleeptime"
    while [[ "$fetch_curTime" -lt "$fetch_timeout" ]]; do
        sleep $fetch_sleeptime

        # grab user proxy so we can authenticate ourselves to run condor_fetchlog
        PROXY_FILE=$(gconfig_get X509_USER_PROXY "$config_file")

        ((fetch_curTime  += fetch_sleeptime))
        FETCH_RESULTS=`X509_USER_PROXY=$PROXY_FILE $CONDOR_DIR/sbin/condor_fetchlog -startd $STARTD_NAME@$HOST STARTD`
        fetch_exit_code=$?
        if [[ $fetch_exit_code -eq 0 ]]; then
            break
        fi
        echo "fetch exit code=$fetch_exit_code" 1>&2
        echo "fetch failed in this iteration...will try $fetch_attemptsLeft more times."  >&2
        ((fetch_attemptsLeft -= 1))
    done

    if [[ $fetch_exit_code -ne 0 ]]; then
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
    KILL_RES=$("$CONDOR_DIR"/sbin/condor_master -k "$PWD"/condor_master.pid)
fi

# log dir is always different
# get the real name
log_dir='log'

echo "Total jobs/goodZ jobs/goodNZ jobs/badSignal jobs/badOther jobs below are normalized to 1 Core"
echo "=== Stats of main ==="
# the following if block has been tested with condor version 24.0.2, where 'log/StarterLog' no longer exists and has changed to 'log/StarterLog.testing' (as confirmed by Cole Bollig of HTCondor team)
slotlogs=$(ls -1 ${main_starter_log} ${main_starter_log}.slot* 2>/dev/null)
if [[ -n "$slotlogs" ]]; then
    echo "===NewFile===" > separator_log.txt
    listtoparse="separator_log.txt"
    for slotlog in $slotlogs
    do
        listtoparse="$listtoparse $slotlog separator_log.txt"
    done
    parsed_out=$(cat $listtoparse | awk -v parallelism=${GLIDEIN_CPUS} -f "${main_stage_dir}/parse_starterlog.awk")
    echo "$parsed_out"

    parsed_metrics=$(echo "$parsed_out" | awk 'BEGIN{p=0;}/^\(Normalized\) Total /{if (p==1) {if ($3=="jobs") {t="Total";n=$4;m=$6;} else {t=$3;n=$5;m=$8;} print t "JobsNr " n " " t "JobsTime " m}}/^====/{p=1;}')
    # use echo to strip newlines
    metrics+=$(echo " " $parsed_metrics)
else
    # when all of 'log/StarterLog' or 'log/StarterLog.slot*' files are missing; report it and continue
    echo "One/more HTCondor starter logs missing; skipping calculation of metrics" 1>&2
    echo "Proceeding with rest of the condor shutdown process..." 1>&2
fi
echo "=== End Stats of main ==="

if [[ -f "${main_condor_log}" ]]; then
    numactivations=$(grep -c "Got activate_claim" "${main_condor_log}" 2>/dev/null)
    echo "Total number of activations/claims: $numactivations"
fi

ls -l log 1>&2
echo
cond_print_log MasterLog log/MasterLog
cond_print_log StartdLog log/StartdLog
cond_print_log StarterLog ${main_starter_log}
slotlogs=$(ls -1 ${main_starter_log}.slot* 2>/dev/null)
for slotlog in $slotlogs
do
    slotname=$(echo $slotlog | awk -F"${main_starter_log}." '{print $2}')
    cond_print_log "StarterLog.${slotname}" "$slotlog"
done

if [[ "$use_multi_monitor" -ne 1 ]]; then
    if [[ "$GLIDEIN_Monitoring_Enabled" == "True" ]]; then
        cond_print_log MasterLog.monitor monitor/log/MasterLog
        cond_print_log StartdLog.monitor monitor/log/StartdLog
        cond_print_log StarterLog.monitor "${monitor_starter_log}"
    fi
else
    cond_print_log StarterLog.monitor "${monitor_starter_log}"
fi
cond_print_log StartdHistoryLog log/StartdHistoryLog


append_glidein_log=true   # TODO: this should be a configurable option
if [[ $append_glidein_log = true ]]; then
    if logfile_path=$(glog_get_logfile_path_relative); then
        cond_print_log "GlideinLog" "${logfile_path}"
    fi
fi

## kill the master (which will kill the startd)
if [[ "$use_multi_monitor" -ne 1 ]]; then
    # terminate monitoring startd
    if [[ "$GLIDEIN_Monitoring_Enabled" == "True" ]]; then
        # use the appropriate configuration file
        tmp_condor_config=$CONDOR_CONFIG
        export CONDOR_CONFIG=$condor_config_monitor

        monitor_end_time=$(date +%s)
        # This will not work on mac osx/darwin/bsd
        echo "Terminating monitoring condor at $(date -d "@$monitor_end_time") ($monitor_end_time)" 1>&2

        #### KILL CONDOR ####
        "$CONDOR_DIR"/sbin/condor_master -k "$PWD"/monitor/condor_master.pid
        ####

        ret=$?
        if [[ "$ret" -ne 0 ]]; then
            echo 'Failed to terminate monitoring condor... still going ahead' 1>&2
        fi

        # clean back
        export CONDOR_CONFIG=$tmp_condor_config
    fi
fi

if [[ "$ON_DIE" -eq 1 ]]; then

    #If we are explicitly killed, do not wait required time
    echo "Explicitly killed, exiting with return code 0 instead of $condor_ret";

    condor_ret=0
    metrics+=" CondorKilled True"
else
    metrics+=" CondorKilled False"
fi

##########################################################

# $metrics is purposefully not quoted
if [[ "$condor_ret" -eq "0" ]]; then
    "$error_gen" -ok "condor_startup.sh" $metrics
else
    "$error_gen" -error "condor_startup.sh" "Unknown" "See Condor logs for details" $metrics
fi

exit $condor_ret
