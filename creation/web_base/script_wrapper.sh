#!/bin/bash
#
# Project:
#   glideinWMS
#
# Description:
#   Helper script to wrap periodically executed scripts
#   This script will allow periodic script to be similar to the other script executed at startup
#   Adds error and output processing. Sets up the environment
#   Contrary to the startup, there may be multiple periodic script running at the same time.
#   Runs as startd_cron:  stdout is interpreted as classad
# 
# script_wrapper "$glidein_config" "$s_ffb_id" "$s_name" "$s_fname" 
#
# Attributes/files used:
#  ERROR_GEN_PATH
#  add_config_line.source
# Attributes returned:
#  GLIDEIN_PS_FAILED_LIST - list of scripts that failed at least once
#  GLIDEIN_PS_FAILING_LIST - list of scripts that failed last execution
#  GLIDEIN_PS_OK - True is no script failed its last execution (GLIDEIN_PS_FAILING_LIST is empty)
#  GLIDEIN_PS_FAILED_LAST - name ot the last script that failed execution
#  GLIDEIN_PS_FAILED_LAST_REASON - string describing the last failure
#  GLIDEIN_PS_LAST (w/ error_gen) - file path of the last script
#  prefix GLIDEIN_PS_ (w/ error_gen) - the wrapper returns the prefix used (GLIDEIN_PS_)

# find the real path even if realpath is not installed
# realpath file
function robust_realpath {
    if ! realpath "$1" 2>/dev/null; then 
        echo "$(cd "$(dirname "$1")"; pwd -P)/$(basename "$1")"
    fi
}

# input parameters sanityzed
glidein_config="`robust_realpath $1`"
s_id="$2"
# the name is used in the included functions
s_name=$3
s_fname="`robust_realpath $4`"


# find error reporting helper script 
error_gen=`grep '^ERROR_GEN_PATH ' $glidein_config | awk '{print $2}'`

if [ -z "$3" ]; then
    # no script passed, wrapper invoked by the initial test
    "$error_gen" -ok  "script_wrapper.sh" GLIDEIN_PS_LAST "script_wrapper.sh" "prefix" "GLIDEIN_PS_"
    exit 0
fi

verbose=
[ -n "$DEBUG" ] && verbose=yes

# write to stderr only if verbose is set
function vmessage {
    # echo `date` $@ 1>&2 
    [ -n "$verbose" ] && echo "# script_wrapper.sh `date`" $@ 1>&2
}


# temporary function until the correct one is sourced
function add_config_line {
    echo "$@" >> $glidein_config
}


# publish to startd classad and to the glidein_config file (key must have no spaces)
# publish key value
function publish {
    prefix=GLIDEIN_PS_
    echo "$1 = ${*:2}"
    add_config_line "${prefix}$*"
}


# Manage failure listst in glidein_config (GLIDEIN_PS_FAILED_LIST/GLIDEIN_PS_FAILING_LIST) and connected ads
# list_manage add|del name list_name 
function list_manage {
    # invoked locally, trust 3 parameters
    tmp_list=",`grep -i "^$3 " $glidein_config | awk '{print $2}'`,"
    if [[ "$1" == "del" && "$tmp_list" == *,$2,* ]]; then
        tmp_list="${tmp_list/,$2,/,}"
        add_config_line "$3" "`[[ "$tmp_list" =~ ,*([^,]|[^,].*[^,]),* ]]; echo -n "${BASH_REMATCH[1]}"`"
    elif [[ "$1" == "add" && ! "$tmp_list," == *,$2,* ]]; then
        tmp_list="$tmp_list,$2"
        add_config_line "$3" "`[[ "$tmp_list" =~ ,*([^,]|[^,].*[^,]),* ]]; echo -n "${BASH_REMATCH[1]}"`"
    fi
    if [ "$3" == GLIDEIN_PS_FAILING_LIST ]; then
        # publish test status
        if [[ "$tmp_list" =~ ,* ]]; then
            publish OK True
        else
            publish OK False
        fi
    fi
}


# Advertise failure, cleanup and exit
# failed "message" [error_type [ec]]
#    error_type is one of: WN_Resource, Network, Config, VO_Config, Corruption, VO_Proxy
function failed {
    [ -n "$verbose" ] || echo "Script wrapper failure: $1" 1>&2
    if [ -n "$tmp_dir" -a -d "$tmp_dir" ]; then
        rm -r "$tmp_dir"
    fi
    publish "FAILED_LAST $s_name:$s_fname"
    publish "FAILED_LAST_REASON $1"
    list_manage add $s_name GLIDEIN_PS_FAILING_LIST
    list_manage add $s_name GLIDEIN_PS_FAILED_LIST
    #TODO: should publish the lists to the schedd classad?
    echo "-"
    exit_code=1
    [ -n "$3" ] && exit_code=$3
    if [ "x$2" == "xwrapper" ]; then
        "$error_gen" -error "script_wrapper.sh" Corruption "$1" GLIDEIN_PS_LAST "$s_fname"
        ${main_dir}/error_augment.sh  -process $exit_code "${s_id}/script_wrapper.sh" "$PWD" "script_wrapper.sh $glidein_config" "$START" "$END"
        ${main_dir}/error_augment.sh -concat
    fi
    # cleanup
    cd "$start_dir"
    [ -d "$tmp_dir" ] && rm -r "$tmp_dir"
    # exit
    [ -n "$3" ] && exit $3
    exit 1
}


### Script starts

vmessage "Executing $s_name: $s_fname $glidein_config $s_id" 

# start_dir should be the same as wrok_dir in glidein_startup.sh and GLIDEIN_WORK_DIR
start_dir="`pwd`"
main_dir="$start_dir/main"

# Check that the start directory is correct and files are there
for i in "$glidein_config" ./add_config_line.source; do
    [ -r "$i" ] || failed "Missing essential file: $i" wrapper
done
for i in  "$main_dir/error_augment.sh" "$s_fname"; do
    [ -x "$i" ] || failed "Missing essential executable: $i" wrapper
done

source ./add_config_line.source


### Setup: move to personal temp dir not to step over other programs
temp_base_dir="$start_dir"
tmp_dir="`mktemp -d --tmpdir="$temp_base_dir"`"
if [ $? -ne 0 ]; then
    failed "Failed to create temporary directory" wrapper
fi

cd "$tmp_dir"


### Run the program

${main_dir}/error_augment.sh -init
START=`date +%s`
"$s_fname" "$glidein_config" "$s_id"
ret=$?
END=`date +%s`
${main_dir}/error_augment.sh  -process $ret "$s_id/`basename "$s_fname"`" "$PWD" "$s_fname $glidein_config" "$START" "$END"  #generating test result document
${main_dir}/error_augment.sh -locked-concat
if [ $? -ne 0 ]; then 
    vmessage "=== Error: unable to save the log file for $s_fname (lock file from other script) ==="
fi 
if [ $ret -ne 0 ]; then
    # Failed 
    vmessage "=== Validation error in $s_fname ===" 
    [ -n "$verbose" ] || $(cat otrx_output.xml | awk 'BEGIN{fr=0;}/<[/]detail>/{fr=0;}{if (fr==1) print $0}/<detail>/{fr=1;}' 1>&2)
    # add also the the failed/failing lists
    failed "Error running '$s_fname'"
fi 

# Ran successfully (failed includes exit)
vmessage "=== Periodic script ran OK: $s_fname ===" 
list_manage del $s_name GLIDEIN_PS_FAILING_LIST
echo "-"

#"$error_gen" -ok  "script_wrapper.sh" GLIDEIN_PS_LAST "$s_fname"

### End cleanup
cd "$start_dir"
rm -r "$tmp_dir"



