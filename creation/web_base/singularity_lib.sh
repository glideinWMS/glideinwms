#!/bin/bash

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

#
# This script contains some utility functions for the singularity scripts
# The script will be available outside and inside Singularity
#
# Disabling "var is referenced but not assigned". The functions are imported by other scripts defining the variables:
# shellcheck disable=SC2154
#
# This script advertises:
# HAS_SINGULARITY
# SINGULARITY_PATH
# GWMS_SINGULARITY_PATH
# SINGULARITY_VERSION
# GWMS_SINGULARITY_VERSION
# GLIDEIN_DEBUG_OUTPUT
#
# Note that HTCondor has these native attribute names:
# HasSingularity
# SingularityVersion
# Using the above names would interfere and modify HTCondor behavior
# NOTE: HAS_SINGULARITY and HasSingularity are different because of '_'

# TODO: NOTEs for code and check these attrs are handled correctly
# GLIDEIN_SINGULARITY_BINDPATH, GLIDEIN_SINGULARITY_BINDPATH_DEFAULT
# GWMS_ in scripts GLIDEIN_ from attributes in config files and condor

# All output is to stderr

# Functions are using:
# - $glidein_config
# - $GLIDEIN_DEBUG_OUTPUT
# - $GWMS_THIS_SCRIPT

# Singularity images:
# SINGULARITY_IMAGES_DICT
# TODO: Format checkers could be added in python in reconfig
# Singularity images, could be URLs (File path, http://.., docker://.., ...)
# plat1:URL1,plat2:URL2,default:URLd
# No comma is allowed in platform IDs or URLs, no colon is allowed in platform IDs.
# A platform is an arbitrary string, could be the OS name, or a dash separated list (os-arch)
# GWMS will do an exact match with the requested or default ones (rhel7,rhel6,default).
# 'defult' is used for the default platform (no special meaning in reality)
# The legacy variables SINGULARITY_IMAGE_DEFAULT6, SINGULARITY_IMAGE_DEFAULT7 are mapped to rhel6, rhel7
# GLIDEIN_REQUIRED_OS (Factory - OS are allowed on the entry) and  REQUIRED_OS (Frontend or Job - OSes the job requires)
# are csv lists of platforms used to request a specific platform. 'any' is the default and means no preference.

# Mount points:
# GLIDEIN_SINGULARITY_BINDPATH
# GLIDEIN_SINGULARITY_BINDPATH_DEFAULT
# Once a mount point is used, following attempts to mount on it are not successful and trigger a warning message
# So the first time a mount point is the one used will determine what is mounted
# SINGULARITY_BINDPATH (left for the host environment) takes precedence (added before the command line options)
# Then come invocation overrides, GLIDEIN_SINGULARITY_BINDPATH, GLIDEIN_SINGULARITY_BINDPATH_DEFAULT and last
# system defaults (e.g. /cvmfs) are added to the command line
# The suggestion is for the Factory to guarantee defaults in GLIDEIN_SINGULARITY_BINDPATH_DEFAULT and let the Frontend
# set or override GLIDEIN_SINGULARITY_BINDPATH
# All lists have the format: src1:dst1,src2:dst2:ro,src3
# Bind w/ non existing sources are removed to prevent Singularity from failing
# GWMS will not do other checks, check your user mount points
# NOTE: if CVMFS_MOUNT_DIR is set, this is assumed to be the root of CVMFS instead of /cvmfs

# Invocation
# SINGULARITY_BIN path where the singularity binary is located. Can be specified by Factory and/or Frontend and
#   will be used before the other possible locations
# Additional options for the Singularity invocation
# GLIDEIN_SINGULARITY_OPTS - options after the exec command
# GLIDEIN_SINGULARITY_GLOBAL_OPTS - singularity options, like debug, silent/verbose, ...
# NOTE: GLIDEIN_SINGULARITY_OPTS and GLIDEIN_SINGULARITY_GLOBAL_OPTS must be expansion/flattening safe because
#       is passed as veriable and quoted strings inside it are not preserved
# Reference documentation for the command and env variables:
# https://sylabs.io/guides/3.3/user-guide/cli/singularity.html
# https://sylabs.io/guides/3.3/user-guide/appendix.html

# Overridden by OSG_SINGULARITY_BINARY (in environment at time of use)
OSG_SINGULARITY_BINARY_DEFAULT="/cvmfs/oasis.opensciencegrid.org/mis/singularity/bin/singularity"
[[ -n "$CVMFS_MOUNT_DIR" ]] && OSG_SINGULARITY_BINARY_DEFAULT="${CVMFS_MOUNT_DIR}/oasis.opensciencegrid.org/mis/singularity/bin/singularity"

# For shell, for HTCondor is the opposite
# 0 = true
# 1 = false

# TODO: Future extensions
# parametrize options:
# GLIDEIN_SINGULARITY_BINDPATH_CHECKS (exist, ...)
# GLIDEIN_SINGULARITY_IMAGE_CHECKS
# GLIDEIN_SINGULARITY_FEATURES
#

# By default Module and Spack are enabled (1=true), MODULE_USE can override this
GWMS_MODULE_USE_DEFAULT=1

# Output log levels:
# WARN used also for error, always to stderr
# INFO if GLIDEIN_QUIET is not set (default)
# DEBUG if GLIDEIN_DEBUG_OUTPUT is set (and GLIDEIN_QUIET is not set)
# GWMS_THIS_SCRIPT should be set to $0 to log the file name

# To increment each time the API changes
export GWMS_SINGULARITY_LIB_VERSION=2

GWMS_SCRIPT_LOG="$(dirname "$GWMS_THIS_SCRIPT")/.LOG_$(basename "$GWMS_THIS_SCRIPT").$$.txt"
# Change this to enable script log
SCRIPT_LOG=
[[ -n "$GLIDEIN_DEBUG_OUTPUT" ]] && SCRIPT_LOG="$GWMS_SCRIPT_LOG"

_DEFAULT_PATH=/usr/bin:/bin

info_stdout() {
    [[ -z "$GLIDEIN_QUIET" ]] && echo "$@"
    true  # Needed not to return false if the test if the test above is false
}

info_raw() {
    [[ -z "$GLIDEIN_QUIET" ]] && echo "$@"  1>&2
    [[ -n "$SCRIPT_LOG" ]] && echo "$@"  >> "$GWMS_SCRIPT_LOG"
    true  # Needed not to return false if the test if the test above is false
}

info() {
    info_raw "INFO " "$@"
}

info_dbg() {
    if [[ -n "$GLIDEIN_DEBUG_OUTPUT" ]]; then
        #local script_txt=''
        #[ -n "$GWMS_THIS_SCRIPT" ] && script_txt="(file: $GWMS_THIS_SCRIPT)"
        info_raw "DEBUG ${GWMS_THIS_SCRIPT:+"($GWMS_THIS_SCRIPT)"}" "$@"
    fi
}

warn_muted() {
    # These are warning messages (conditions that could cause errors) but are muted unless GLIDEIN_DEBUG_OUTPUT is set
    # because most of the times the Glideins work and the messages are confusing for users (OSG request)
    if [[ -n "$GLIDEIN_DEBUG_OUTPUT" ]]; then
        warn_raw "WARNING " "$@"
    fi
}

warn() {
    warn_raw "WARNING " "$@"
}

warn_raw() {
    echo "$@"  1>&2
    [[ -n "$SCRIPT_LOG" ]] && echo "$@"  >> "$GWMS_SCRIPT_LOG"
    true  # Needed not to return false if the test if the test above is false
}


######################################################
#
# Dictionary functions
# Dictionaries are strings: key1:val1,key2:val2
# Comma is not allowed in keys or values, colon is not allowed in keys
# Associative dictionaries are OK in bash 4.1. Before then are not or not fully supported
# References (declare -n) are from 4.3.
# TEST: to test dict functions
# my_dict=" key 1:val1:opt1,key2:val2,key3:val3:opt3,key4,key5:,key6 :val6"
#

dict_get_val() {
    # Return to stdout the value of the fist key present in the dictionary
    # Return true (0) if a value is found and is not empty, 1 otherwise
    # Use a regex to extract the values
    #  $1 dict name
    #  $2 comma separated list of keys (key can contain a space if you quote it but not a comma)
    local IFS=,
    local key_list="$2"
    local res
    for key in $key_list; do
        res="$(expr ",${!1}," : ".*,$key:\([^,]*\),.*")"
        if [[ -n "$res" ]]; then
            echo "$res"
            return 0
        fi
    done
    return 1
}

dict_check_key() {
    # Return true (0) if the key is in the dict (the value could be empty)
    # $1 dict name
    # $2 key
    #re=*",${2}:"*  # bash <= 3.1 needs quoted regex, >=3.2 unquoted, variables are OK with both
    [[ ",${!1}," = *",${2}:"* ]] && return 0
    [[ ",${!1}," = *",${2},"* ]] && return 0  # could be empty val and no separator
    return 1
}

dict_set_val() {
    # Echoes a new string including the new key:value. Return is 0 if the key was already there, 1 if new
    # $1 dict name
    # $2 key
    # $3 value (optional)
    # Assuming correct use, no check made, at least 2 arguments mandatory
    local my_dict=${!1}
    local key_found
    if [[ ",${my_dict}," = *",${2}:"* || ",${my_dict}," = *",${2},"* ]]; then
        my_dict=$(echo ",${my_dict}," | sed -E "s/,${2}(,|:[^,]*,)/,/;s/,+/,/g;s/^,//;s/,\$//")
        key_found=yes
    fi
    # [ -n "${my_dict}" ] && my_dict="${my_dict},"
    # [ -n "$3" ] && echo "${my_dict}$2:$3" || echo "${my_dict}$2"
    echo "${my_dict:+"${my_dict},"}$2${3:+":$3"}"
    [[ -n "${key_found}" ]] && return 0
    return 1
}

# function get_dict_items {} - not needed

# TEST: for iterators tests
# dit () { echo "TEST: <$1> <$2> <$3>"; }
# dict_items_iterator my_dict dit par1
# Make sure that par1 is passed, spaces are preserved, no-val keys are handled correctly and val options are preserved
dict_items_iterator() {
    # Split the dict string to list the items and apply the function
    # $1 dict
    # $2.. $n $2 is the function to apply to all items, $3..$n its parameters (optional), $(n+1) the key, $(n+2) the value
    local my_dict=${!1}
    shift
    local was_ifs=$IFS
    IFS=,
    local -a arr=($(echo "${my_dict}"))
    IFS=$was_ifs
    local val
    for i in "${arr[@]}"  # ${arr[*]} separates also by spaces
    do
        [[ "$i" = *\:* ]] && val="${i#*:}" || val=   # to protect against empty val and no :
        # function key value
        "$@" "${i%%:*}" "$val"
    done
}

dict_keys_iterator() {
    # Split the dict string to list the keys and apply the function
    # $1 dict
    # $2.. $n $2 is the function to apply to all keys, $3..$n its parameters (optional), $(n+1) will be the key
    local my_dict=${!1}
    shift
    local was_ifs=$IFS
    IFS=,
    local -a arr=($(echo "${my_dict}"))
    IFS=$was_ifs
    #echo "T:${arr[1]}"
    for i in "${arr[@]}"
    do
        "$@" "${i%%:*}"
    done
}

dict_get_keys() {
    # Returns a comma separated list of keys (there may be spaces if keys do have spaces)
    # Quote the return string and use  IFS=, to separate the keys, this way you'll preserve spaces
    # Returning the elements would flatten the array and cause problems w/ spaces
    # $1 dict
    local my_dict=${!1}
    local res
    res=$(echo "$my_dict," | sed 's/:[^,]*,/,/g; s/,\+/,/g')
    echo "${res%,}"
}


dict_get_first() {
    # Returns the first element of the dictionary (whole item, or key, or value)
    #  $1 dict
    #  $2 what to return: item, key, value (default: value)
    local my_dict=${!1}
    local what=${2:-value}
    local res="${my_dict%%,*}"
    if [[ -n "$res" ]]; then
        # to protect from empty dicts
        case $what in
        item)
            echo "$res"
            ;;
        value)
            [[ "$res" = *:* ]] && echo "${res#*:}"
            ;;
        key)
            echo "${res%%:*}"
            ;;
        esac
    fi
}


list_get_intersection() {
    # Return the intersection of two comma separated lists.
    # 'any' in any of the 2 lists, means that the other list is returned (is a wildcard)
    # If the Input lists are sorted in order of preference, the result is as well
    # In:
    #   1: comma separated list of values
    #   2: comma separated list of values
    # Out:
    #   intersection returned on stdout, 'any' is returned if both lists are 'any'
    #   Return 1 if the intersection is empty (or the calculation fails), 0 otherwise
    # Requires python2 or python3
    # This can be used to evaluate the desired OS (platform) that works for both Entry and VO,
    # intersection of GLIDEIN_REQUIRED_OS and REQUIRED_OS
    # Valid values: rhelNN, default
    local intersection
    [[ -z "$1"  ||  -z "$2" ]] && return 1
    if [[ "x$1" = "xany" ]]; then
        intersection="$2"
    else
        if [[ "x$2" = "xany" ]]; then
            intersection="$1"
        else
            local cmd
            # desired_os="$(python -c "print sorted(list(set('$2'.split(',')).intersection('$1'.split(','))))[0]" 2>/dev/null)"
            if cmd=$(command -v python2 2>/dev/null); then
                intersection="$($cmd -c "print ','.join(sorted(list(set('$2'.split(',')).intersection('$1'.split(',')))))" 2>/dev/null)"
            elif cmd=$(command -v python3 2>/dev/null); then
                intersection="$($cmd -c "print(','.join(sorted(list(set('$2'.split(',')).intersection('$1'.split(','))))))" 2>/dev/null)"
            else
                # no valid python found
                warn "Python (python2/python3) not found. Returning empty intersection"
                return 1
            fi
        fi
    fi
    [[ -z "$intersection" ]] && return 1
    echo "$intersection"
}


#######################################
#
# GWMS path functions
#
# TODO: to remove from here. These 3 variables and 3 functions are also in glidein_paths.source,
#  because used in glidien_startup.sh
#  This file should import from there
#  Make sure that are in sync in the mean time. Consider glidein_paths.source authoritative

# Directory structure inside .gwms_aux (or main glidein directory)
# bin, lib [python, python3, python2], exec [prejob, postjob, ...]
GWMS_SUBDIR_EXEC_PREJOB="exec/prejob"
GWMS_SUBDIR_EXEC_POSTJOB="exec/postjob"
GWMS_SUBDIR_EXEC_CLEANUP="exec/cleanup"

robust_realpath() {
    # Echo to stdout the real path even if realpath is not installed
    # 1. file path to find the real path of
    if ! realpath "$1" 2>/dev/null; then
        local first="$1"
        local last=
        if [[ ! -d "$1" ]]; then
            first="$(dirname "$first")"
            last="/$(basename "$1")"
        fi
        [[ -d "$first" ]] && first="$(cd "$first"; pwd -P)"
        echo "${first}${last}"
    fi
}

gwms_process_scripts() {
    # Process all the scripts in the directory, in lexicographic order
    #  ignore the files named .ignore files
    #  run all the executable files passing glidein_config ($3) as argument,
    #  source the remaining files if extension is .sh or .source
    # 1- directory scripts to process
    # 2- a modifier to search only in subdirectories (prejob)
    # 3- glidein_config (path of the file containing shared variables)
    local old_pwd my_pwd
    old_pwd=$(robust_realpath "$PWD")
    my_pwd=$(robust_realpath "$1")
    cfg_file=$(robust_realpath "$3")
    if [[ -n "$2" ]]; then
        case "$2" in
            prejob) my_pwd="${my_pwd}/$GWMS_SUBDIR_EXEC_PREJOB";;
            postjob) my_pwd="${my_pwd}/$GWMS_SUBDIR_EXEC_POSTJOB";;
            cleanup) my_pwd="${my_pwd}/$GWMS_SUBDIR_EXEC_CLEANUP";;
        esac
    fi
    if ! cd "$my_pwd"; then
        warn "Scripts directory ($my_pwd) not found. Skipping scripts processing."
        return
    fi
    for i in * ; do
        [[ -e "$i" ]] || continue  # protect against nullglob (no match)
        [[ "$i" != *.ignore ]] || continue
        if [[ -x "$i" ]]; then
            # run w/ some protection?
            "./$i" "$cfg_file"
            [[ $(pwd -P) != "$my_pwd" ]] && { cd "$my_pwd" || warn "Unable to return to scripts directory ($my_pwd)."; }
        elif [[ "$i" = *.sh || "$i" = *.source ]]; then
            . "$i"
            [[ $(pwd -P) != "$my_pwd" ]] && { cd "$my_pwd" || warn "Unable to return to scripts directory ($my_pwd)."; }
        fi
    done
    cd "$old_pwd" || warn "Unable to return old directory after scripts ($old_pwd)."
}

gwms_from_config() {
    # Retrieve a parameter from glidien_config ($glidien_config) and echo it to stdout
    #  If the $glidein_config variable is not defined assume the parameter is not defined
    # 1. - parameter to parse from glidein_config
    # 2. - default (when the value is not defined)
    # 3. - function to validate or process the parameter (get_prop_bool or same interface)
    #      The default, when used, is not processed by this function
    local ret=
    if [[ -n "$glidein_config" ]]; then
        #ret=$(grep "^$1 " "$glidein_config" | cut -d ' ' -f 2-)
        #ret=$(tac "$glidein_config" | grep -m1 "^$1 " | cut -d ' ' -f 2-)
        if ! ret=$(gconfig_get "$1" "$glidein_config" 2>/dev/null); then
            ret=$(tac "$glidein_config" | grep -m1 "^$1 " | cut -d ' ' -f 2-)
        fi
    fi
    if [[ -n "$ret" ]]; then
        if [[ -n "$3" ]]; then
            "$3" VALUE_PROVIDED "$ret" "$2"
            return
        fi
    else
        ret=$2
    fi
    echo "$ret"
}


#######################################
#
# GWMS aux functions
#

get_prop_bool() {
    # In:
    #  $1 the file (for example, $_CONDOR_JOB_AD or $_CONDOR_MACHINE_AD) special keywords: NONE, VALUE_PROVIDED
    #  $2 the key
    #  $3 default value (optional, must be 1->true or 0->false, 0 if unset)
    # For HTCondor consider True: true (case insensitive), any integer != 0
    #                       Anything else is False (0, false, undefined, ...)
    #                       This is the default behavior (default=0)
    # Out:
    #  echo "1" for true, "$default" for empty value/undefined, "0" for false/failure (bad invocation, no ClassAd file)
    #  return the opposite to allow shell truth values true,1->0 , false,0->1
    # NOTE Spaces are trimmed, so strings like "T RUE" are true
    # TODO: replace grep w/ case insensitive comparison, currently any string containng 'true' case insensitive is
    #       considered true, e.g. trueval, NotTrue, ...

    local default=${3:-0}
    local val
    if [[ $# -lt 2 || $# -gt 3 ]]; then
        val=0
    elif [[ "x$1" = "xNONE" ]]; then
        val=$default
    else
        if [[ "x$1" = "xVALUE_PROVIDED" ]]; then
            val=$2
        else
            # sed "s/[\"' \t\r\n]//g" not working on OS X, '\040\011\012\015' = ' '$'\t'$'\r'$'\n'
            val=$( (grep -i "^$2 " "$1" | cut -d= -f2 | tr -d '\040\011\012\015') 2>/dev/null )
        fi
        # Convert variations of true to 1
        re="^[0-9]+$"  # bash <= 3.1 needs quoted regex, >=3.2 unquoted, variables are OK with both
        if (echo "x$val" | grep -i true) >/dev/null 2>&1; then
            val=1
        elif [[ "$val" =~ $re ]]; then
            if [[ $val -eq 0 ]]; then
                val=0
            else
                val=1
            fi
        elif [[ -z "$val" ]]; then
            val=$default
        elif (echo "x$val" | grep -i undefined) >/dev/null 2>&1; then
            val=$default
        else
            val=0
        fi
    fi
    # From here on val=0/1
    echo $val
    # return value accordingly, but backwards (in shell true -> 0, false -> 1)
    if [[ "$val" = "1" ]];  then
        return 0
    else
        return 1
    fi
}


is_condor_true() {
   # Assuming the input is numeric 0->False other->True
   if [[ $1 -eq 0 ]]; then
       false
   else
       true
   fi
}


get_prop_str() {
    # In:
    #  $1 the file (for example, $_CONDOR_JOB_AD or $_CONDOR_MACHINE_AD)
    #  $2 the key
    #  $3 default value (optional)
    # Out:
    #  echo the value (or the default if UNDEFINED) and return 0
    #  For no ClassAd file or file not readable, echo the default and return 1
    #  For bad invocation, return 1
    if [[ $# -lt 2  ||  $# -gt 3 ]]; then
        return 1
    elif [[ "$1" = "NONE" ]]; then
        echo "$3"
        return 1
    elif [[ "$1" = "VALUE_PROVIDED" ]]; then
        val=$2
    else
        if [[ ! -r "$1" ]]; then
            echo "$3"
            return 1
        fi
        val=$( (grep -i "^$2 " "$1" | cut -d= -f2 | sed -e "s/^[\"' \t\n\r]//g" -e "s/[\"' \t\n\r]$//g" | sed -e "s/^[\"' \t\n\r]//g" ) 2>/dev/null )
    fi
    if [[ -z "$val" || "$val" =~ [Uu][Nn][Dd][Ee][Ff][Ii][Nn][Ee][Dd] ]]; then
        val="$3"
    fi
    echo "$val"
    return 0
}

# $glidein_config from the file importing this
# add_config_line and add_condor_vars_line are in add_config_line.source (ADD_CONFIG_LINE_SOURCE in $glidein_config)
if [[ -e "$glidein_config" ]]; then    # was: [ -n "$glidein_config" ] && [ "$glidein_config" != "NONE" ]
    if [[ -z "$SOURCED_ADD_CONFIG_LINE" ]]; then
        # import add_config_line and add_condor_vars_line functions used in advertise
        if [[ -z "$add_config_line_source" ]]; then
            add_config_line_source=$(grep -m1 '^ADD_CONFIG_LINE_SOURCE ' "$glidein_config" | cut -d ' ' -f 2-)
            export add_config_line_source
        fi
        if [[ -e "$add_config_line_source" ]]; then
            info "Sourcing add config line: $add_config_line_source"
            # shellcheck source=./add_config_line.source
            . "$add_config_line_source"
            # make sure we don't source a second time inside the container
            export SOURCED_ADD_CONFIG_LINE=1
        else
            warn "glidein_config defined but add_config_line ($add_config_line_source) not available. Some functions like advertise will be limited." || true
        fi
    fi
    export condor_vars_file
    if [[ $(type -t gconfig_get) = function ]]; then
        condor_vars_file=$(gconfig_get CONDOR_VARS_FILE "$glidein_config")
        error_gen=$(gconfig_get ERROR_GEN_PATH "$glidein_config")
    else
        # Trying to get these defined even if add_config_line is unavailable (using grep instead ot tac, OK if no duplicate)
        condor_vars_file=$(grep -m1 '^CONDOR_VARS_FILE ' "$glidein_config" | cut -d ' ' -f 2-)
        error_gen=$(grep -m1 '^ERROR_GEN_PATH ' "$glidein_config" | cut -d ' ' -f 2-)
    fi
else
    # glidein_config not available
    warn_muted "glidein_config not defined ($glidein_config) in singularity_lib.sh. Some functions like advertise and error_gen will be limited." || true
    [[ -z "$error_gen" ]] && error_gen=warn
    glidein_config=NONE
fi


# TODO: gconfig_add is safe also for periodic scripts. advertise_safe seems not used.
#  Should it be removed leaving only advertise?
advertise() {
    # Add the attribute to glidein_config (if not NONE) and return the string for the HTC ClassAd
    # In:
    #  1 - key
    #  2 - value
    #  3 - type, atype is the type of the value as defined by GlideinWMS:
    #    I - integer
    #    S - quoted string
    #    C - unquoted string (i.e. Condor keyword or expression)
    # Out:
    #  string for ClassAd
    #  Added lines to glidein_config and condor_vars.lst
    key="$1"
    value="$2"
    atype="$3"

    if [[ "$glidein_config" != "NONE" ]]; then
        gconfig_add "$key" "$value"
        add_condor_vars_line "$key" "$atype" "-" "+" "Y" "Y" "+"
    fi

    if [[ "$atype" = "S" ]]; then
        echo "$key = \"$value\""
    else
        echo "$key = $value"
    fi
}

advertise_safe() {
    # Add the attribute to glidein_config (if not NONE) and return the string for the HTC ClassAd
    # Thos should be used in periodic scripts or wrappers, because it uses add_config_line_safe
    # In:
    #  1 - key
    #  2 - value
    #  3 - type, atype is the type of the value as defined by GlideinWMS:
    #    I - integer
    #    S - quoted string
    #    C - unquoted string (i.e. Condor keyword or expression)
    # Out:
    #  string for ClassAd
    #  Added lines to glidein_config and condor_vars.lst
    local key="$1"
    local value="$2"
    local atype="$3"

    if [[ "$glidein_config" != "NONE" ]]; then
        gconfig_add_safe "$key" "$value"
        add_condor_vars_line "$key" "$atype" "-" "+" "Y" "Y" "+"
    fi

    if [[ "$atype" = "S" ]]; then
        echo "$key = \"$value\""
    else
        echo "$key = $value"
    fi
}


# The following four functions (htc_...) are based mostly on Carl Edquist's code to parse the HTCondor file
htc_setmatch() {
  local __=("$@")
  set -- "${BASH_REMATCH[@]}"
  shift
  eval "${__[@]}"
}

htc_rematch() {
  [[ $1 =~ $2 ]] || return 1
  shift 2
  htc_setmatch "$@"
}


htc_get_vars_from_env_str() {
  local str_arr condor_var_string=""
  # TODO: used \" instead of '"' - check w/ Carl if changes are ok, ask about quoting
  env_str=${env_str#\"}
  env_str=${env_str%\"}
  # Strip out escaped whitespace
  while htc_rematch "$env_str" "(.*)'([[:space:]]+)'(.*)" env_str='$1$3'
  do :; done

  # Now, split the string on whitespace
  read -ra str_arr <<<"${env_str}"

  # Finally, parse each element of the array.
  # They should each be name=value assignments,
  # and we only need to grab the name
  vname_regex="(^[_a-zA-Z][_a-zA-Z0-9]*)(=)[.]*"
  for assign in "${str_arr[@]}"; do
      if [[ "$assign" =~ $vname_regex ]]; then
	  condor_var_string="$condor_var_string ${BASH_REMATCH[1]}"
      fi
  done
  echo "$condor_var_string"
}


htc_parse_env_file() {
    shopt -s nocasematch
    while read -r attr eq env_str; do
	if [[ "$attr" = Environment && "$eq" = '=' ]]; then
	    htc_get_vars_from_env_str
	    break
	fi
    done < "$1"
    shopt -u nocasematch
}


env_clear_one() {
    # Clear the environment variable and print a info message
    # In
    #  1 - name of the variable to clear, e.g. LD_LIBRARY_PATH
    local varname="GWMS_OLDENV_$1"
    if [[ -n "${!1}" ]]; then
        info "GWMS Singularity wrapper: $1 is set to ${!1} outside Singularity. This will not be propagated to inside the container instance."
        export "${varname}"="${!1}"
        case $1 in
            PATH) PATH=$_DEFAULT_PATH ;;
               *) unset "$1" ;;
        esac
    fi
}


env_process_options() {
    # The options string is a list of any of the following:
    #   clearall - clear all from the environment (at your own risk)
    #   condorset - _CONDOR_ env variables AND variables set in the job ClassAd (Environment). Implied gwmsset
    #   osgset - set of OSG variables (get it from OSG wrapper). Implied gwmsset
    #   gwmsset - set of GWMS utilities variables
    #   clear - same as: clearall,gwmsset,osgset,condorset
    #   clearpaths - clear only PATH,LD_LIBRARY_PATH,PYTHONPATH (default)
    #   keepall - clear no variable, incompatible w/ any clear... option
    # Inconsistencies should be checked by configuration validation
    # In
    #  1 - environment options
    # Out
    #  stdout - normalized environment options
    local retval
    if [[ -z "$1" ]]; then
        retval=clearpath
    else
        # Verify consistency and normalize
        [[ ",${1}," = *",clear"* && ",${1}," = *",keepall,"* ]] &&
            warn "Inconsistent container environment options: keepall will be ignored because a clear option is present"
        retval=${1}
        [[ ",${retval}," = *",clear,"* ]] && retval="${retval},clearall,gwmsset,osgset,condorset"
        [[ ",${retval}," = *",osgset,"* && ! ",${retval}," = *",condorset,"* ]] && retval="${retval},condorset"
        [[ ",${retval}," = *",osgset,"* && ! ",${retval}," = *",gwmsset,"* ]] && retval="${retval},gwmsset"
        [[ ",${retval}," = *",condorset,"* && ! ",${retval}," = *",gwmsset,"* ]] && retval="${retval},gwmsset"
    fi
    echo "$retval"
}


env_clear() {
    # If requested in the env options, clear the PATH vasiables and add the singularity option
    # In
    #  1 - list of environment options (see env_process_options)
    #  2 - singularity options (GWMS_SINGULARITY_EXTRA_OPTS)
    # Out
    #  stdout - modified singularity option (w/ cleanenv option added if needed)
    local env_options
    env_options=",$(env_process_options "$1"),"
    local singularity_opts="$2"
    if [[ "${env_options}" = *",clearall,"* ]]; then
        # add cleanenv option to singularity
        singularity_opts="$singularity_opts --cleanenv"
        info "Instructing Singularity to clean the environment as requested"
    fi
    if [[ "${env_options}" = *",clearall,"* || "${env_options}" = *",clearpaths,"* ]]; then
        # clear the ...PATH variables
        # PATH should be cleared also by Singularity, but the behavior is inconsistent across versions
        for i in PATH LD_LIBRARY_PATH PYTHONPATH ; do
            env_clear_one ${i}
        done
    fi
    echo "${singularity_opts}"
}


env_gets_cleared() {
    # True if Singularity is set to clear the environment
    [[ " ${1} " = *" --cleanenv "* ]]
}


env_preserve() {
    # If we are cleaning the environment, then we also need to "protect" (by exporting)
    # variables that will be transformed into certain critical variables
    # inside the container.
    # Note, we don't deal with PATH, which requires
    # some care, as a user could conceivably set not just
    # SINGULARITYENV_PATH, but also either of SINGULARITYENV_PREPEND_PATH
    # or SINGULARITYENV_APPEND_PATH.
    #
    # The list of variables below that are transformed should be any variable
    # that is exported during the first execution of this script (above), or
    # which is inspected or manipulated during the second execution of this
    # script.  Maybe also others...
    #
    # Note on future proofing: if additional variables are exported above
    # or referenced during the second execution of this script, they will
    # also need to be added to this list.  I don't know an elegant way
    # to automate that process.
    #
    # CVMFS_MOUNT_DIR is important outside singularity, but CVMFS is assumed
    # to be mounted always as /cvmfs inside, so no need to preserve the variable

    # In
    #  1 - list of environment options (see env_process_options)

    # Variables used in the "inside Singularity" and "Setup for job execution" of the singularity_wrapper
    # Other important GWMS variables
    local envvars_gwmsset="GWMS_SINGULARITY_REEXEC \
    GLIDEIN_Proxy_URL \
    MODULE_USE \
    InitializeModulesEnv \
    XRD_PLUGINCONFDIR \
    POSIXSTASHCACHE \
    STASHCACHE \
    STASHCACHE_WRITABLE \
    LoadModules \
    GWMS_AUX_SUBDIR \
    GWMS_BASE_SUBDIR \
    GWMS_SUBDIR \
    GWMS_DIR"

    local envvars_osgset="OSG_SINGULARITY_REEXEC \
    _CHIRP_DELAYED_UPDATE_PREFIX \
    APPTAINER_WORKDIR \
    CONDOR_PARENT_ID \
    GLIDEIN_ResourceName \
    GLIDEIN_Site \
    HAS_SINGULARITY \
    http_proxy \
    InitializeModulesEnv \
    LIGO_DATAFIND_SERVER \
    OSG_MACHINE_GPUS \
    OSG_SINGULARITY_AUTOLOAD \
    OSG_SINGULARITY_BIND_CVMFS \
    OSG_SINGULARITY_CLEAN_ENV \
    OSG_SINGULARITY_IMAGE \
    OSG_SINGULARITY_IMAGE_DEFAULT \
    OSG_SINGULARITY_IMAGE_HUMAN \
    OSG_SINGULARITY_OUTSIDE_PWD \
    OSG_SINGULARITY_PATH \
    OSG_SITE_NAME \
    OSGVO_PROJECT_NAME \
    OSGVO_SUBMITTER \
    OSG_WN_TMP \
    POSIXSTASHCACHE \
    SINGULARITY_WORKDIR \
    STASHCACHE \
    STASHCACHE_WRITABLE \
    TZ \
    X509_USER_CERT \
    X509_USER_KEY \
    X509_USER_PROXY"

    local env_options
    env_options=",$(env_process_options "$1"),"
    local env_preserve=
    local all_condor_set_envvars varname newname envvars_condorset=""
    # ist of Singularity/Apptainer protected variables
    local singenv_condor_set_envvars="" singenv_regex="^SINGULARITYENV_" apptenv_regex="^APPTAINERENV_"
    # Protect GWMS variables all the time the environment is cleared
    env_preserve="$env_preserve $envvars_gwmsset"
#    if [[ "${env_options}" = *",gwmsset,"* ]]; then
#        # protect the variables in GWMS set
#        env_preserve="$env_preserve $envvars_gwmsset"
#    fi
    if [[ "${env_options}" = *",osgset,"* ]]; then
        # protect the variables in OSG set
        env_preserve="$env_preserve $envvars_osgset"
    fi
    if [[ "${env_options}" = *",condorset,"* ]]; then
        # protect the variables in HTCondor set

        # Determine all the _CONDOR_* variable names
        env_preserve="$env_preserve $(env -0 | tr '\n' '\\n' | tr '\0' '\n' | tr '=' ' ' | awk '{print $1;}' | grep ^_CONDOR_ | tr '\n' ' ')"
        # Determine all the environment variables from the job ClassAd
        if [[ -e "$_CONDOR_JOB_AD" ]]; then
            all_condor_set_envvars=$(htc_parse_env_file "$_CONDOR_JOB_AD")
            for varname in ${all_condor_set_envvars}; do
                if [[ "$varname" =~ ${singenv_regex} ]]; then
                    singenv_condor_set_envvars="$singenv_condor_set_envvars $varname"
                elif [[ "$varname" =~ ${apptenv_regex} ]]; then
                    singenv_condor_set_envvars="$singenv_condor_set_envvars $varname"
                else
                    envvars_condorset="$envvars_condorset $varname"
                fi
            done
            # If the user set variables of the form SINGULARITYENV_VARNAME,
            # then warn them and unset those variables
            if [ -n "${singenv_condor_set_envvars}" ]; then
                warn "The following variables beginning with 'SINGULARITYENV_' or 'APPTAINERENV_' were set " \
                     "in the HTCondor submission file and will not be propagated: ${singenv_condor_set_envvars}"
                for varname in ${singenv_condor_set_envvars}; do
                    unset "$varname"
                done
            fi
        fi
    fi
    # should it do something for keepall?

    # Add to the list to preserve to Singularity
    # TODO: revise this once Singularity supports env-file (3.6)
    info_dbg "Protecting the following variables by setting SINGULARITYENV_/APPTAINERENV_ variables: $env_preserve"
    for varname in ${env_preserve}; do
        # If any of the variables above are unset, we don't want to
        # accidentally propagate that into the container as set but empty.
        # Note the test below could be simplified in bash 4.2+ using -v, but not
        # sure what we can assume.
        if [[ -n "${!varname+x}" ]]; then
            newname="SINGULARITYENV_${varname}"
            newname_appt="APPTAINERENV_${varname}"
            # If there's already a variable of the form APPTAINERENV_varname or SINGULARITYENV_varname set,
            # then do nothing. No check on consistency if both are set, or setting the Apptainer one if not set.
            # Unsure if this should  be removed if setting up
            # the condor-specified environment inside the container is implemented.
            if [[ -z "${!newname_appt+x}" && -z "${!newname+x}" ]]; then
                export "$newname_appt"="${!varname}"
                export "$newname"="${!varname}"
            fi
        fi
    done

}


env_restore() {
    # Restore the environment if the Singularity invocation fails
    # Nothing to do for the env cleared by Singularity, we are outside of it.
    # The PATH... variables may need to be restored.
    #
    # In Singularity there is nothing to do.
    # The PATH... variables are not desirable. Using SINGULARITYENV_ Singularity will do the rest
    #
    # In
    #  1 - list of environment options (see env_process_options)
    local env_options varname
    env_options=",$(env_process_options "$1"),"
    if [[ "${env_options}" = *",clearall,"* || "${env_options}" = *",clearpaths,"* ]]; then
        # clear the ...PATH variables
        # PATH should be cleared also by Singularity, but the behavior is inconsistent across versions
        info "Restoring the cleared PATH, LD_LIBRARY_PATH, PYTHONPATH"
        for i in PATH LD_LIBRARY_PATH PYTHONPATH ; do
            varname="GWMS_OLDENV_$i"
            export ${i}="${!varname}"
        done
    fi
}


get_all_platforms() {
    # Return all supported platforms (all Singularity platforms)
    # In
    #  SINGULARITY_IMAGES_DICT
    # Out
    #  csv list of platforms - assuming that all the keys in the Images dictionary are platform names,
    #                          excluding "default"
    # Note: singularity_get_platform - will give the platform of Singularity's current image
    return "$(echo ",$(dict_get_keys SINGULARITY_IMAGES_DICT)," | sed "s/,default,/,/g;s/,$//")"
}


#################################
#
# CVMFS functions
#
# CVMFS_MOUNT_DIR - alternative mount point for CVMFS if set and not empty (path w/o trailing slash "/")

cvmfs_test_and_open() {
    # Testing and opening all CVMFS repos named in the comma separated list. Call-back or exit if failing
    # In:
    #  1 - CVMFS repos names, comma separated
    #  2 - callback for failure (must be a single command or function name), exit 1 if none is provided or callback returns false
    # Using:
    #  CVMFS_MOUNT_DIR
    info_dbg "Testing CVMFS Repos List = $1"
    holdfd=3
    local cvmfs_mount=/cvmfs
    [[ -n "$CVMFS_MOUNT_DIR" ]] && cvmfs_mount="${CVMFS_MOUNT_DIR%/}"
    local IFS=,  # "\t\t\""
    if [[ -n "$1" ]]; then
        # Test and keep open each CVMFS repo
        for x in $1; do  # Spaces in file name are OK, separator is comma
            if eval "exec ${holdfd}<${cvmfs_mount}/\"$x\""; then
                echo "\"${cvmfs_mount}/$x\" exists and available"
                let "holdfd=holdfd+1"
            else
                echo "\"${cvmfs_mount}/$x\" NOT available"
                # [ -n "$2" ] && { $2 } || { echo 1; }
                [[ -n "$2" ]] && $2 || exit 1
            fi
        done
    fi
}


cvmfs_path_in_cvmfs_literal() {
    # True (0) if the image path is in CVMFS, i.e. is /cvmfs or starts with /cvmfs/
    # TODO: What if cvmfs cannot be mounted there (non root, ...) and is mounted e.g. in /srv/cvmfs ?
    #  Should check for "/cvmfs" in path (not only at the beginning, could this be confusing
    #  moving to a function to change easily the heuristic
    # In:
    #  1 - path to check
    [[ "$1" = /cvmfs  ||  "$1" = /cvmfs/* ]]
}


cvmfs_path_in_cvmfs() {
    # True (0) if the image path is in CVMFS, whichever the actual mount point is,
    # - the path is /cvmfs or starts with /cvmfs/ (could be symbolic)
    # - the path is $CVMFS_MOUNT_DIR or starts with $CVMFS_MOUNT_DIR/ and CVMFS_MOUNT_DIR is set
    # In:
    #  1 - path to check
    if [[ "$1" = /cvmfs  ||  "$1" = /cvmfs/* ]]; then
        true
    elif [[ -n "$CVMFS_MOUNT_DIR" ]]; then
        local cvmfs_mount="${CVMFS_MOUNT_DIR%/}"
        [[ "$1" = "$cvmfs_mount"  ||  "$1" = "$cvmfs_mount"/* ]]
    else
        false
    fi
}


cvmfs_resolve_path() {
    # Return a CVMFS path translating /cvmfs in the actual CVMFS mount point
    # In:
    #  1 - path to translate
    #  CVMFS_MOUNT_DIR - CVMFS mount point when different form /cvmfs
    # Out:
    #  stdout: translated path
    if [[ -n "$CVMFS_MOUNT_DIR" ]]; then
        if [[ "$1" = "/cvmfs/"* || "$1" = "/cvmfs" ]]; then
            echo "${CVMFS_MOUNT_DIR%/}${1#/cvmfs}"
            return
        fi
    fi
    echo "$1"
}


####################################
#
# Singularity functions
#

singularity_check_paths() {
    # Check if the mount-points are valid. Return true and echo the mount-point if all tests are satisfied,
    # return false otherwise.
    # List of valid checks (other letters will be ignored):
    #  e: exist
    #  c: in cvmfs
    #  v: check value instead of key (does not apply to d)
    #  d: the value (destination) exist
    # 1: checks, a list of the tests to perform e,c,v or d (see above for meaning)
    # 2: src
    # 3: dst:options
    # both src and dst are assumed to be "resolved" path w/ symbolic /cvmfs translated if CVMFS_MOUNT_DIR is set
    if [[ -z "$1" ]]; then
        # Same as  [ -n "$3" ] && echo -n "$2:$3," || echo -n "$2,"
        echo -n "$2${3:+":$3"},"
        return
    fi
    local to_check="$2"
    local val_no_opt="${3%:*}"  # singularity binds are "src:dst:options", keep only 'dst'
    [[ -z "$val_no_opt" ]] && val_no_opt="$2"
    [[ $1 = *v* ]] && to_check="$val_no_opt"
    [[ -z "$to_check" ]] && { info "Cannot check empty key/value ('$to_check'). Discarding it"; false; return; }
    [[ $1 = *e*  &&  ! -e "$to_check" ]] && { info "Discarding path '$to_check'. File does not exist"; false; return; }
    [[ $1 = *c* ]] && ! cvmfs_path_in_cvmfs "$to_check" && { info "Discarding path '$to_check'. Is not in CVMFS"; false; return; }
    [[ $1 = *d*  &&  ! -e "$val_no_opt" ]] && { info "Discarding value path '$val_no_opt'. File does not exist"; false; return; }
    # Same as [ -n "$3" ] && echo -n "$2:$3," || echo -n "$2,"
    echo -n "$2${3:+":$3"},"
}


# TOTEST:
# singularity_get_binds "" /cvmfs /minos,/usr/games
singularity_get_binds() {
    # Return on stdout a string with multiple --bind options for whichever is not empty of:
    # $3 (overrides), GLIDEIN_SINGULARITY_BINDPATH, GLIDEIN_SINGULARITY_BINDPATH_DEFAULT, $2 (defaults), in that order
    # Each of them must be a valid Singularity mount point string (comma separated, no spaces, src[:dst[:opt]] groups)
    # And remove all binds not satisfying the checks
    # (e.g. non existing src (checks=e) - if src is not existing Singularity will error, i.e. not run)
    # In:
    #  1: parameters for the path checks (see singularity_check_paths for valid values)
    #  2: default binds (added at the end, not used if already mounted)
    #  3: override binds (added at the beginning, will override all binds specified in the variables)
    # E.g. singularity_get_binds e "$singularity_bind_defaults" "$singularity_bind_override"
    local retv=  # default controlled from outside ($2)
    local checks=$1

    # Get singularity binds from GLIDEIN_SINGULARITY_BINDPATH, GLIDEIN_SINGULARITY_BINDPATH_DEFAULT,
    # invoker adds default /cvmfs (via $2),
    # add overrides, and remove non existing src (checks=e) - if src is not existing Singularity will error (not run)

    info_dbg "Singularity binds: OVERRIDE:$3, BINDPATH:$GLIDEIN_SINGULARITY_BINDPATH, BINDPATH_DEFAULT:$GLIDEIN_SINGULARITY_BINDPATH_DEFAULT, DEFAULT:$2, CHECKS($checks)"
    [[ -n "$3" ]] && retv="${retv}$3,"
    [[ -n "$GLIDEIN_SINGULARITY_BINDPATH" ]] && retv="${retv}$GLIDEIN_SINGULARITY_BINDPATH,"
    [[ -n "$GLIDEIN_SINGULARITY_BINDPATH_DEFAULT" ]] && retv="${retv}$GLIDEIN_SINGULARITY_BINDPATH_DEFAULT,"
    [[ -n "$2" ]] && retv="${retv}$2"

    # Check all mount points
    retv=$(dict_items_iterator retv singularity_check_paths "$checks")
    [[ -n "${retv%,}" ]] && echo "${retv%,}"
}


singularity_make_outside_pwd_list() {
    # 1 GWMS_SINGULARITY_OUTSIDE_PWD_LIST
    # 2..N list of paths to add to GWMS_SINGULARITY_OUTSIDE_PWD_LIST
    #   to be added must be new and have same real path (if GWMS_SINGULARITY_OUTSIDE_PWD_LIST is prefixed by ":",
    #   only the new values are considered for the real path comparison)
    # Out: new value for GWMS_SINGULARITY_OUTSIDE_PWD_LIST
    # NOTE: this will not work inside Singularity where some path do not exist and cannot be resolved correctly by
    #   robust_realpath
    local path_list="$1"
    shift
    local first="${path_list%%:*}"
    for i in "$@"; do
        [[ -z "$i" ]] && continue
        [[ -z "$first" ]] && first="$i"
        if [[ -z "$path_list" ]]; then
            path_list="$i"
        else
            if [[ ":${path_list}:" != *":${i}:"* ]]; then
                [[ $(robust_realpath "$first") == $(robust_realpath "$i") ]] && path_list="${path_list}:$i"
            fi
        fi
    done
    echo "${path_list#:}"
}


singularity_update_path() {
    # Replace all outside paths in the command line referring GWMS_SINGULARITY_OUTSIDE_PWD (working directory)
    # or a path in GWMS_SINGULARITY_OUTSIDE_PWD_LIST (paths linked or bind mounted to the working directory)
    # so that they can work inside.
    # "*/execute/dir_[0-9a-zA-Z]*" directories trigger a warning if remaining
    # In:
    #  1 - PWD inside path (path of current PWD once singularity is invoked)
    #  2..N Arguments to correct
    #  GWMS_SINGULARITY_OUTSIDE_PWD_LIST, GWMS_SINGULARITY_OUTSIDE_PWD (or PWD if not defined)
    # Out:
    #  nothing in stdout
    #  GWMS_RETURN - Array variable w/ the commands
    GWMS_RETURN=()
    local outside_pwd="${GWMS_SINGULARITY_OUTSIDE_PWD:-$PWD}"
    local outside_pwd_list
    outside_pwd_list="$(singularity_make_outside_pwd_list "${GWMS_SINGULARITY_OUTSIDE_PWD_LIST}" \
        "${outside_pwd}" "$(robust_realpath "${outside_pwd}")" \
        "${GWMS_THIS_SCRIPT_DIR}" "${_CONDOR_JOB_IWD}")"
    export GWMS_SINGULARITY_OUTSIDE_PWD_LIST="${outside_pwd_list}"
    local inside_pwd=$1
    shift
    info_dbg "Outside paths $GWMS_SINGULARITY_OUTSIDE_PWD_LIST => $inside_pwd in Singularity"
    local arg arg2 old_ifs out_path arg_found
    for arg in "$@"; do
        arg_found=false
        arg2=
        old_ifs="$IFS"
        IFS=:
        for out_path in $outside_pwd_list; do
            # the case is checking "/" ensuring that partial matches are discarded
            case "$arg" in
                "$out_path") arg="${inside_pwd}"; arg_found=true;;
                "$out_path"/*) arg="${arg/#$out_path/$inside_pwd}"; arg_found=true;;
                /*) [[ -z "$arg2" ]] && arg2="$(robust_realpath "${arg}")"
                    case "$arg2" in
                        "$out_path") arg="${inside_pwd}"; arg_found=true;;
                        "$out_path"/*) arg="${arg2/#$out_path/$inside_pwd}"; arg_found=true;;
                    esac
            esac
            # Warn about possible error conditions
            [[ "${arg}" == *"${out_path}"* ]] && info_dbg "Outside path (${outside_pwd}) still in argument ($arg), the path is a partial match or the conversion to run in Singularity may be incorrect"
            $arg_found && break
        done
        IFS="$old_ifs"
        # Warn about possible error conditions
        [[ "${arg}" == */execute/dir_* ]] && info_dbg "String '/execute/dir_' in argument path ($arg), path is a partial match or the conversion to run in Singularity may be incorrect"
        GWMS_RETURN+=("${arg}")
    done
}


singularity_exec() {
    # Return on stdout the command to invoke Singularity exec
    # Change here for all invocations (both singularity_setup, wrapper). Custom options should go in the specific script
    # In:
    #  1 - singularity bin
    #  2 - Singularity image path (constraints checked outside)
    #  3 - Singularity binds (constraints checked outside)
    #  4 - Singularity extra options (NOTE: this is not quoted, so spaces will be interpreted as separators)
    #  5 - Singularity global options, before the exec command (NOTE: this is not quoted, so spaces will be interpreted as separators)
    #  6 - Execution options: exec (exec singularity)
    #  7 and more - Command to be executed and its options
    #  PWD
    # Out:
    # Return:
    #  string w/ command options on stdout
    # Uses:
    #  SINGULARITY_DISABLE_PID_NAMESPACES

    local singularity_bin="$1"
    local singularity_image="$2"
    local singularity_binds="$3"
    # Keeping --contain. Should not interfere w/ GPUs
    local singularity_opts="--ipc --contain $4"  # extra options added at the end (still before binds)
    # add --pid if not disabled in config
    [[ $(gwms_from_config SINGULARITY_DISABLE_PID_NAMESPACES) = 1 ]] || singularity_opts+=" --pid"
    local singularity_global_opts="$5"
    local execution_opt="$6"
    [[ -z "$singularity_image"  ||  -z "$singularity_bin" ]] && { warn "Singularity image or binary empty. Failing to run Singularity "; false; return; }
    # TODO: to remove in the future (keeping only the else branch). This is for compatibility with default_singularity_wrapper.sh pre 3.4.6
    if [[ "X$singularity_global_opts" = Xexec ]]; then
        warn "default_singularity_wrapper.sh pre 3.4.6 running with 3.4.6 Factory scripts. Continuing in compatibility mode."
        singularity_global_opts=
        execution_opt="exec"
        shift 5
    else
        shift 6
    fi
    # the remaining parameters are the command and parameters invoked by singularity
    [[ -z "$1"  &&  $# -ne 0 ]] && { warn "Singularity invoked with an empty command. Failing."; false; return; }

    # Make sure that ALL invocation strings and debug printout are same/consistent
    # Quote all the path strings ($PWD, $singularity_bin, ...) to deal with a path that contains whitespaces
    # CMS is not using "--home $PWD:/srv", OSG is
    # New OSG: --bind $PWD:/srv --no-home (no --home \"$PWD\":/srv --pwd)
    # TODO: --home or --no-home ? See email from Dave and Mats
    # Dave: In versions 3.x through 3.2.1-1 where --home was being ignored on sites that set "mount home = no"
    # in singularity.conf. This was fixed in 3.2.1-1.1.

    info_dbg  "$execution_opt \"$singularity_bin\" $singularity_global_opts exec --home \"$PWD\":/srv --pwd /srv " \
            "$singularity_opts ${singularity_binds:+"--bind" "\"$singularity_binds\""} " \
            "\"$singularity_image\"" "${@}" "[ $# arguments ]"
    local error
    if [[ ",${execution_opt}," = *,exec,* ]]; then
        exec "$singularity_bin" ${singularity_global_opts} exec --home "$PWD":/srv --pwd /srv \
            ${singularity_opts} ${singularity_binds:+"--bind" "$singularity_binds"} \
            "$singularity_image" "${@}"
        error=$?
        [[ -n "$_CONDOR_WRAPPER_ERROR_FILE" ]] && echo "Failed to exec singularity ($error): exec \"$singularity_bin\" $singularity_global_opts exec --home \"$PWD\":/srv --pwd /srv " \
            "$singularity_opts ${singularity_binds:+"--bind" "\"$singularity_binds\""} " \
            "\"$singularity_image\"" "${@}" >> $_CONDOR_WRAPPER_ERROR_FILE
        warn "exec of singularity failed: exit code $error"
        return ${error}
    else
        "$singularity_bin" ${singularity_global_opts} exec --home "$PWD":/srv --pwd /srv \
            ${singularity_opts} ${singularity_binds:+"--bind" "$singularity_binds"} \
            "$singularity_image" "${@}"
        return $?
    fi
    # Code should never get here
    warn "ERROR Inconsistency in Singularity invocation functions. Failing"
    [[ -n "$_CONDOR_WRAPPER_ERROR_FILE" ]] && echo "ERROR: Inconsistency in GWMS Singularity invocation. Failing." >> $_CONDOR_WRAPPER_ERROR_FILE
    exit 1
}


singularity_exec_simple() {
    # Return on stdout the command to invoke Singularity exec
    # Change here for all invocations (both singularity_setup, wrapper). Custom options should go in the specific script
    # In:
    #  1 - singularity bin
    #  2 - Singularity image path
    #  3 ... - Command to execute and its arguments
    #  PWD, GLIDEIN_SINGULARITY_BINDPATH, GLIDEIN_SINGULARITY_BINDPATH_DEFAULT, GLIDEIN_SINGULARITY_OPTS, GLIDEIN_SINGULARITY_GLOBAL_OPTS
    # NOTE: GLIDEIN_SINGULARITY_OPTS and GLIDEIN_SINGULARITY_GLOBAL_OPTS must be expansion/flattening safe (see above)

    # Get singularity binds from GLIDEIN_SINGULARITY_BINDPATH, GLIDEIN_SINGULARITY_BINDPATH_DEFAULT, add default /cvmfs,
    # and remove non existing src (checks=e) - if src is not existing Singularity will error (not run)
    local singularity_binds
    local cvmfs_bind="/cvmfs"
    [[ -n "$CVMFS_MOUNT_DIR" ]] && cvmfs_bind="${CVMFS_MOUNT_DIR}:/cvmfs"
    singularity_binds=$(singularity_get_binds e "${cvmfs_bind},/etc/hosts,/etc/localtime")
    local singularity_bin="$1"
    local singularity_image="$2"
    shift 2
    local error exit_code
    { error=$(singularity_exec "$singularity_bin" "$singularity_image" "$singularity_binds" \
            "$GLIDEIN_SINGULARITY_OPTS" "$GLIDEIN_SINGULARITY_GLOBAL_OPTS" "" "${@}" 2>&1 >&3 3>&-); } 3>&1
    exit_code=$?
    echo "$error" >&2
    if [[ $exit_code -eq 0 ]] && echo "$error" | grep -q "^FATAL:"; then
        warn "singularity/apptainer exited w/ 0 but seems to have a FATAL error reported in stderr"
    fi
    return "$exit_code"
}


singularity_test_exec() {
    # Test Singularity by invoking it with the standard environment (binds, options)
    # In:
    #  1 - Singularity image, default GWMS_SINGULARITY_IMAGE_DEFAULT
    #  2 - Singularity path, default GWMS_SINGULARITY_PATH_DEFAULT
    #  PWD (used by singularity_exec to bind it)
    #  GLIDEIN_DEBUG_OUTPUT - to increase verbosity
    # Out:
    #  unprivileged
    #  privileged
    #  fakeroot
    #  EMPTY if no singularity
    # Return:
    #  true - Singularity OK
    #  false - Test failing. Singularity not working or empty bin/image
    # E.g. if ! singularity_test_exec "$GWMS_SINGULARITY_IMAGE" "$GWMS_SINGULARITY_PATH" ; then
    local singularity_image="${1:-$GWMS_SINGULARITY_IMAGE_DEFAULT}"
    local singularity_bin="${2:-$GWMS_SINGULARITY_PATH_DEFAULT}"
    [[ -z "$singularity_image"  ||  -z "$singularity_bin" ]] &&
            { info "Singularity image or binary empty. Test failed "; false; return; }
    # If verbose, make also Singularity verbose
    [[ -n "$GLIDEIN_DEBUG_OUTPUT" ]] && export GLIDEIN_SINGULARITY_GLOBAL_OPTS="-vvv -d $GLIDEIN_SINGULARITY_GLOBAL_OPTS"
    # singularity v2.x outputs escape codes always to stdout (bug), they need to be filtered out:
    #   sed -r -e 's/\x1b\[[0-9;]*m?//g' -e 's/\x1b[()][A-Z0-9]//g'
    # singularity always creates a user map /proc/self/uid_map with lines (D.Dykstra):
    #   n1  n2  [n3]
    # Looking at the first line:
    # if n2 is 0 then it runs in privileged mode
    # if n1 is not 0, the it runs unprivileged as that user
    # if n1 is 0 but n2 not then it runs in fake-root mode (a special unprivileged mode in v3.3)
    local map_format_regex="^,[0-9]+,[0-9]+,"
    local check_singularity singularity_ec
    if [[ -e /proc/self/uid_map ]]; then
        check_singularity="$(singularity_exec_simple "$singularity_bin" "$singularity_image" cat /proc/self/uid_map |
                sed -r -e 's/\x1b\[[0-9;]*m?//g' -e 's/\x1b[()][A-Z0-9]//g' | head -n1 | tr -s '[:blank:]' ',';
                echo "sing_ec:${PIPESTATUS[0]}")"
    else
        # On older kernels there is no /proc/self/uid_map, only privileged singularity can run
        check_singularity="$(singularity_exec_simple "$singularity_bin" "$singularity_image" env | grep SINGULARITY_CONTAINER |
                sed -r -e 's/\x1b\[[0-9;]*m?//g' -e 's/\x1b[()][A-Z0-9]//g'; echo "sing_ec:${PIPESTATUS[0]}")"
    fi
    singularity_ec=${check_singularity##*sing_ec:}
    check_singularity="${check_singularity%sing_ec:*}"
    # Removing newline (not there if no output). Extra comma needed for if branch output, not disturbing for else
    check_singularity="${check_singularity%$'\n'},"
    if [[ $singularity_ec -eq 0  && "$check_singularity" =~ $map_format_regex ]]; then
        # singularity ran correctly
        local singularity_mode=unprivileged
        # same test used also in singularity_check()
        if [[ "$check_singularity" = ,0,* ]]; then
            [[ "$check_singularity" = ,0,0,* ]] && singularity_mode=privileged || singularity_mode=fakeroot
        fi
        info "Singularity at '$singularity_bin' appears to work ($singularity_mode mode)"
        echo "$singularity_mode"
        # true - not needed echo returns true
    elif [[ $singularity_ec -eq 0  && "$check_singularity" = "SINGULARITY_CONTAINER="* ]]; then
        singularity_mode=privileged
        info "Singularity at '$singularity_bin' appears to work ($singularity_mode mode), user namespaces not available"
        echo "$singularity_mode"
        # true - not needed echo returns true
    else
        # test failed
        [[ "$check_singularity" = ',' ]] && info "Singularity at $singularity_bin failed (ec:$singularity_ec)" ||
            info "Singularity at '$singularity_bin' failed (ec:$singularity_ec) w/ unexpected output"
        false
    fi
}


singularity_get_platform() {
    # TODO: incomplete, add script to detect platform (needs to work in/out singularity)
    # Detect the platform (OS) inside of Singularity (invoking it with the standard environment: binds, options)
    # In:
    #  1 - Singularity image, default GWMS_SINGULARITY_IMAGE_DEFAULT
    #  2 - Singularity path, default GWMS_SINGULARITY_PATH_DEFAULT
    #  PWD (used by singularity_exec to bind it)
    # Out:
    # Return:
    #  true - Singularity OK
    #  false - Singularity not working or empty bin/image
    # E.g. if ! singularity_test_exec "$GWMS_SINGULARITY_IMAGE" "$GWMS_SINGULARITY_PATH" ; then
    local PLATFORM_DETECTION=""
    local singularity_image="$1"
    local singularity_bin="$2"
    [[ -e "$PLATFORM_DETECTION" ]] ||
            { info "File not found ($PLATFORM_DETECTION). Unable to detect platform "; false; return; }
    [[ -z "$singularity_image" ]] && singularity_image="$GWMS_SINGULARITY_IMAGE_DEFAULT"
    [[ -z "$singularity_bin" ]] && singularity_bin="$GWMS_SINGULARITY_PATH_DEFAULT"
    [[ -z "$singularity_image"  ||  -z "$singularity_bin" ]] &&
            { info "Singularity image or binary empty. Unable to run Singularity to detect platform "; false; return; }
    singularity_exec_simple "$singularity_bin" "$singularity_image" "$PLATFORM_DETECTION"
    return $?
}


singularity_test_bin() {
    # Test Singularity path, check the version and validate w/ the image (if an image is passed)
    # In:
    #   1 - type,path
    #   2 - s_image, if provided will be used to test Singularity (as additional test)
    #   3 - s_binary_name, container system binary (and module) name, "singularity" by default,
    #                      used to test for apptainer
    # Side effects:
    #  bread_crumbs - documents the tests for debugging purposes
    #     test:   -> test attempted, path not provided or 'singularity version' failed,
    #     test:T  -> singularity version succeeded, image for test not provided
    #     test:TF -> singularity version succeeded but image invocation failed
    #     test:TT -> both singularity version and image invocation succeeded
    # Out:
    #  return 0 - all attempted tests succeeded, 1 - a test failed
    #  stdout "_$step\n_$sin_type\n_$sin_version\n_$sin_version_full\n_$sin_path\n_@$bread_crumbs"
    #         ("$bread_crumbs" if failing)

    local step="${1%%,*}"
    local sin_path="${1#*,}"
    local sin_binary_name="${3:-singularity}"
    local sin_version
    local sin_full_version
    local sin_type
    local sin_image="$2"
    if [[ "$step" = module ]]; then
        local module_name="$sin_binary_name"
        [[ -n "$sin_path" ]] && module_name=$sin_path
        module load "$module_name" >/dev/null 2>&1
        # message on error?
        sin_path=$(which "$sin_binary_name")
        # should check also CVMFS_MOUNT_DIR beside /cvmfs but not adding complication just for the warning message
        [[ -z "$sin_path" && "$LMOD_CMD" = /cvmfs/* ]] &&
            warn "$sin_binary_name not found in module. OSG OASIS module from module-init.sh used. May override a system module."
    elif [[ "$step" = PATH ]]; then
        # find the full path
        [[ -n "$sin_path" ]] && sin_binary_name="$sin_path"
        sin_path=$(which "$sin_binary_name")
    fi
    if [[ -z "$sin_path" ]] && [[ "$step" = module || "$step" = PATH ]]; then
        info_dbg "which failed ($PATH). Trying command: command -v \"$sin_binary_name\""
        sin_path=$(command -v "$sin_binary_name")
    fi
    local bread_crumbs=" $step($sin_path):"
    sin_full_version=$("$sin_path" --version 2>/dev/null)
    if ! sin_version=$("$sin_path" version 2>/dev/null); then
        # The version command returns only the version number
        # singularity 2.6.1 does not have the version command, must use option
        # More recent singularity versions add a "singularity version " prefix to the version number
        # in "singularity --version" this is not the case with "singularity version"
        # Similarly, apptainer  --version has an "apptainer version " prefix
        sin_version=${sin_full_version#singularity version }
        sin_version=${sin_version#apptainer version }
    fi
    [[ -z "$sin_version" ]] && { echo "$bread_crumbs"; false; return; }
    if [[ -z "$sin_image" ]]; then
        sin_type=unknown
        bread_crumbs+="T"
    else
        if sin_type=$(singularity_test_exec "$sin_image" "$sin_path"); then
            bread_crumbs+="TT"
        else
            bread_crumbs+="TF($sin_version)"
            echo "$bread_crumbs"
            false
            return
        fi
    fi
    # \n is the separator, _ is to ensure that all lines are counted when parsing, @ used for bread_crumbs quick parse
    echo -e "_$step\n_$sin_type\n_$sin_version\n_$sin_full_version\n_$sin_path\n_@$bread_crumbs"
    # true; return
}


singularity_locate_bin() {
    # Find Singularity in search path, check the version and validate w/ the image (if an image is passed)
    # Will look in some places also for apptainer (and singularitypro)
    # This will search in order:
    # 1. Optional: Look first in the override path (GLIDEIN_SINGULARITY_BINARY_OVERRIDE)
    # 2. Look for 'singularity' and then 'apptainer' in the path suggested via $1 (SINGULARITY_BIN)
    #      (keywords: PATH -> go to step 3 - ie start w/ $PATH;
    #           OSG -> OSG location, and continue from step 3 if failed, this is the default)
    # 3. Look in $PATH for 'apptainer' and then 'singularity'
    # 4. Invoke module singularitypro
    # 5. Invoke module singularity
    # 6. Look in the default OSG location
    # In:
    #   1 - s_location, suggested Singularity directory, will be added first in PATH before searching for Singularity
    #            keywords OSG (default, same as '') and PATH (no suggestion start checking form PATH) are possible
    #   2 - s_image, if provided will be used to test Singularity (as additional test)
    #   OSG_SINGULARITY_BINARY, OSG_SINGULARITY_BINARY_DEFAULT, LMOD_CMD, optional if in the environment
    # Out (E - exported):
    #   E GWMS_SINGULARITY_MODE - unprivileged, privileged, fakeroot or unknown (no image to test)
    #   E GWMS_SINGULARITY_VERSION
    #   E GWMS_SINGULARITY_PATH - set if Singularity is found
    #   E HAS_SINGULARITY - set to True if Singularity is found
    #   singularity_in - place where singularity bin was found

    info "Checking for singularity..."
    #GWMS Entry must use SINGULARITY_BIN to specify the pathname of the singularity binary
    #GWMS, we quote $singularity_bin to deal with white spaces in the path
    local s_step s_location_msg s_location="${1:-OSG}"
    local s_image="$2"
    # bread_crumbs populated also in singularity_test_bin
    local bread_crumbs=""
    local test_out
    HAS_SINGULARITY=False
    local osg_singularity_binary="${OSG_SINGULARITY_BINARY:-${OSG_SINGULARITY_BINARY_DEFAULT}}"
    local singularity_binary_override="${GLIDEIN_SINGULARITY_BINARY_OVERRIDE}"

    if [[ -n "$singularity_binary_override" ]]; then
        # 1. Look first in the override path (GLIDEIN_SINGULARITY_BINARY_OVERRIDE)
        bread_crumbs+=" s_override_defined"
        if [[ ! -x "$singularity_binary_override" ]]; then
            # Try considering it a PATH
            local singularity_binary_override_bin
            if ! singularity_binary_override_bin=$(PATH="$singularity_binary_override" command -v singularity); then
                if singularity_binary_override_bin=$(PATH="$singularity_binary_override" command -v apptainer); then
                    info "Found 'apptainer' instead of 'singularity' in the override path, trying that"
                    bread_crumbs+="_path"
                    test_out=$(singularity_test_bin "s_override,${singularity_binary_override_bin}" "$s_image" apptainer) &&
                        HAS_SINGULARITY=True
                    bread_crumbs+="${test_out##*@}"
                else
                    info "Override path '$singularity_binary_override' (GLIDEIN_SINGULARITY_BINARY_OVERRIDE) is not a valid binary or a PATH containing singularity."
                    info "Will proceed with suggested path and auto-discover"
                fi
            else
                bread_crumbs+="_path"
                test_out=$(singularity_test_bin "s_override,${singularity_binary_override_bin}" "$s_image") &&
                    HAS_SINGULARITY=True
                bread_crumbs+="${test_out##*@}"
            fi
        else
            bread_crumbs+="_bin"
            test_out=$(singularity_test_bin "s_override,${singularity_binary_override}" "$s_image") &&
                HAS_SINGULARITY=True
            bread_crumbs+="${test_out##*@}"
        fi
    fi
    if [[ "$HAS_SINGULARITY" != True && -n "$s_location" && "$s_location" != PASS ]]; then
        s_location_msg=" at $s_location,"
        bread_crumbs+=" s_bin_defined"
        s_step=s_bin
        [[ "$s_location" == OSG ]] && { s_location="${osg_singularity_binary%/singularity}"; s_step=s_bin_OSG; }
        if [[ ! -d "$s_location"  ||  ! -x "${s_location}/singularity" ]]; then
            [[ "$s_location" = NONE ]] &&
                warn "SINGULARITY_BIN = NONE is no more a valid value, use GLIDEIN_SINGULARITY_REQUIRE to control the use of Singularity"
            info "Suggested path (SINGULARITY_BIN?) '$1' ($s_location) is not a directory or does not contain singularity."
            info "Will try to proceed with auto-discover but this mis-configuration may cause errors later"
        else
            # 2. Look in the path suggested, separate from $PATH (key OSG -> OSG_SINGULARITY_BINARY)
            test_out=$(singularity_test_bin "${s_step},${s_location}/singularity" "$s_image") &&
                HAS_SINGULARITY=True
            bread_crumbs+="${test_out##*@}"
        fi
    fi
    if [[ "$HAS_SINGULARITY" != True ]]; then
        # 3. Look in $PATH for apptainer
        # 4. Look in $PATH for singularity
        # 5. Invoke module singularitypro
        # 6. Invoke module singularity
        #    some sites requires us to do a module load first - not sure if we always want to do that
        # 7. Look in the default OSG location
        for attempt in "PATH,apptainer" "PATH,singularity" "module,singularitypro" "module,singularity" "OSG,${osg_singularity_binary}"; do
            if test_out=$(singularity_test_bin "$attempt" "$s_image"); then
                HAS_SINGULARITY=True
                break
            fi
            bread_crumbs+="${test_out##*@}"
        done
        bread_crumbs+="${test_out##*@}"
    fi
    # Execution test done w/ default image
    info_dbg "Has singularity $HAS_SINGULARITY. Tests: $bread_crumbs"
    if [[ "$HAS_SINGULARITY" = True ]]; then
        local test_results
        IFS=$'\n' read -rd '' -a test_results <<<"$test_out"
        # one last check - make sure we could determine the path to singularity
        if [[ -z "${test_results[3]#_}" ]]; then
            warn "Looks like we found Singularity, but were unable to determine the full path to the executable"
        else
            export HAS_SINGULARITY=${HAS_SINGULARITY}
            export GWMS_SINGULARITY_PATH="${test_results[4]#_}"
            export GWMS_SINGULARITY_VERSION="${test_results[2]#_}"
            export GWMS_SINGULARITY_MODE="${test_results[1]#_}"
            export GWMS_CONTAINERSW_PATH="${test_results[4]#_}"
            export GWMS_CONTAINERSW_VERSION="${test_results[2]#_}"
            export GWMS_CONTAINERSW_FULL_VERSION="${test_results[3]#_}"
            export GWMS_CONTAINERSW_MODE="${test_results[1]#_}"
            info "Singularity found at \"${GWMS_SINGULARITY_PATH}\" ($GWMS_SINGULARITY_MODE mode, using ${test_results[0]#_})"
            true
            return
        fi
    fi
    # No valid singularity found
    export HAS_SINGULARITY=False
    export GWMS_SINGULARITY_PATH=""
    export GWMS_SINGULARITY_VERSION=""
    export GWMS_SINGULARITY_MODE=""
    export GWMS_CONTAINERSW_PATH=""
    export GWMS_CONTAINERSW_VERSION=""
    export GWMS_CONTAINERSW_FULL_VERSION=""
    export GWMS_CONTAINERSW_MODE=""
    warn "Singularity not found$s_location_msg in OSG_SINGULARITY_BINARY[_DEFAULT], PATH and module"
    info_dbg "PATH(${PATH}), attempt results(${bread_crumbs})"
    false
}


singularity_get_image() {
    # Return on stdout the Singularity image
    # Let caller decide what to do if there are problems
    # In:
    #  1: a comma separated list of platforms (OS) to choose the image
    #  2: a comma separated list of restrictions (default: none)
    #     - cvmfs: image must be on CVMFS
    #     - any: any image is OK, $1 was just a preference (the first one in SINGULARITY_IMAGES_DICT is used if none of the preferred is available)
    #  SINGULARITY_IMAGES_DICT
    #  SINGULARITY_IMAGE_DEFAULT (legacy)
    #  SINGULARITY_IMAGE_DEFAULT6 (legacy)
    #  SINGULARITY_IMAGE_DEFAULT7 (legacy)
    # Out:
    #  Singularity image path/URL returned on stdout
    #  EC: 0: OK, 1: Empty/no image for the desired OS (or for any), 2: File not existing, 3: restriction not met (e.g. image not on cvmfs)

    local s_platform="$1"
    if [[ -z "$s_platform" ]]; then
        warn "No desired platform, unable to select a Singularity image"
        return 1
    fi
    local s_restrictions="$2"
    local singularity_image

    # To support legacy variables SINGULARITY_IMAGE_DEFAULT, SINGULARITY_IMAGE_DEFAULT6, SINGULARITY_IMAGE_DEFAULT7
    # values are added to SINGULARITY_IMAGES_DICT
    # TODO: These override existing dict values OK for legacy support (in the future we'll add && [ dict_check_key rhel6 ] to avoid this)
    [[ -n "$SINGULARITY_IMAGE_DEFAULT6" ]] && SINGULARITY_IMAGES_DICT=$(dict_set_val SINGULARITY_IMAGES_DICT rhel6 "$SINGULARITY_IMAGE_DEFAULT6")
    [[ -n "$SINGULARITY_IMAGE_DEFAULT7" ]] && SINGULARITY_IMAGES_DICT=$(dict_set_val SINGULARITY_IMAGES_DICT rhel7 "$SINGULARITY_IMAGE_DEFAULT7")
    [[ -n "$SINGULARITY_IMAGE_DEFAULT" ]] && SINGULARITY_IMAGES_DICT=$(dict_set_val SINGULARITY_IMAGES_DICT default "$SINGULARITY_IMAGE_DEFAULT")

    # [ -n "$s_platform" ] not needed, s_platform is never null here (verified above)
    # Try a match first, then check if there is "any" in the list
    singularity_image=$(dict_get_val SINGULARITY_IMAGES_DICT "$s_platform")
    if [[ -z "$singularity_image" && ",${s_platform}," = *",any,"* ]]; then
        # any means that any image is OK, take the 'default' one and if not there the   first one
        singularity_image=$(dict_get_val SINGULARITY_IMAGES_DICT default)
        [[ -z "$singularity_image" ]] && singularity_image=$(dict_get_first SINGULARITY_IMAGES_DICT)
    fi

    if [[ -n "$CVMFS_MOUNT_DIR" ]]; then
        # set things up here since the path needs to be bindmounted inside the container
        local mount_home=${CVMFS_MOUNT_DIR/\/dist\/cvmfs/}
        symlink_target=$(readlink $mount_home/dist/${singularity_image#/})
        symlink_target=${symlink_target#/}
        singularity_image=$mount_home/dist/$symlink_target
    fi

    # At this point, GWMS_SINGULARITY_IMAGE is still empty, something is wrong
    if [[ -z "$singularity_image" ]]; then
        [[ -z "$SINGULARITY_IMAGES_DICT" ]] && warn "No Singularity image available (SINGULARITY_IMAGES_DICT is empty)" ||
                warn "No Singularity image available for the required platforms ($s_platform)"
        return 1
    fi

    # Check all restrictions (at the moment cvmfs) and return 3 if failing
    if [[ ",${s_restrictions}," = *",cvmfs,"* ]] && ! cvmfs_path_in_cvmfs "$singularity_image"; then
        warn "$singularity_image is not in the /cvmfs area as requested"
        return 3
    fi

    # We make sure it exists
    if [[ ! -e "$singularity_image" ]]; then
        warn "ERROR: $singularity_image file not found" 1>&2
        return 2
    fi

    echo "$singularity_image"
}


create_host_lib_dir() {
    # this is a temporary solution until enough sites have newer versions
    # of Singularity. Idea for this solution comes from:
    # https://github.com/singularityware/singularity/blob/master/libexec/cli/action_argparser.sh#L123
    mkdir -p .host-libs
    local NVLIBLIST
    NVLIBLIST="$(mktemp "${TMPDIR:-/tmp}/.nvliblist.XXXXXXXX")"
    cat >"$NVLIBLIST" <<EOF
libcuda.so
libEGL_installertest.so
libEGL_nvidia.so
libEGL.so
libGLdispatch.so
libGLESv1_CM_nvidia.so
libGLESv1_CM.so
libGLESv2_nvidia.so
libGLESv2.so
libGL.so
libGLX_installertest.so
libGLX_nvidia.so
libglx.so
libGLX.so
libnvcuvid.so
libnvidia-cfg.so
libnvidia-compiler.so
libnvidia-eglcore.so
libnvidia-egl-wayland.so
libnvidia-encode.so
libnvidia-fatbinaryloader.so
libnvidia-fbc.so
libnvidia-glcore.so
libnvidia-glsi.so
libnvidia-gtk2.so
libnvidia-gtk3.so
libnvidia-ifr.so
libnvidia-ml.so
libnvidia-opencl.so
libnvidia-ptxjitcompiler.so
libnvidia-tls.so
libnvidia-wfb.so
libOpenCL.so
libOpenGL.so
libvdpau_nvidia.so
nvidia_drv.so
tls_test_.so
EOF
    for TARGET in $(ldconfig -p | grep -f "$NVLIBLIST"); do
        if [[ -f "$TARGET" ]]; then
            # only keep the first one found
            if [[ ! -e ".host-libs/$(basename "$TARGET")" ]]; then
                cp -L "$TARGET" .host-libs/
            fi
        fi
    done
    rm -f "$NVLIBLIST"
}


singularity_check() {
    # Check if it is invoked in Singularity and if Singularity is privileged mode ot not
    # Return true (0) if in Singularity false (1) otherwise
    # Echo to stdout a string with the status:
    # - EMPTY if not in singularity
    # - yes is SINGULARITY_CONTAINER or GWMS_SINGULARITY_REEXEC are defined
    # - likely if SINGULARITY_NAME is not defined but process 1 is shim-init or sinit
    # - appends _privileged to yes or likely if singularity is running in privileged mode
    # - appends _fakeroot  to yes or likely if singularity is running in unprivileged fake-root mode
    # - appends _nousernamespaces to yes or likely there is no user namespace info (singularity is running in privileged mode)
    # In Singularity SINGULARITY_NAME and SINGULARITY_CONTAINER are defined (in v=2.2.1 only SINGULARITY_CONTAINER)
    # In the default GWMS wrapper GWMS_SINGULARITY_REEXEC=1
    # The process 1 in singularity is called init-shim (v>=2.6), or sinit (v>=3.2), not init
    # If the parent is 1 and is not init could be also Docker or other containers, so the check was removed
    #   even if it could be also Singularity
    local in_singularity=
    [[ -n "$SINGULARITY_CONTAINER" ]] && in_singularity=yes
    [[ -z "$in_singularity" && -n "$GWMS_SINGULARITY_REEXEC" ]] && in_singularity=yes
    [[ -z "$in_singularity" && "$(ps -p1 -ocomm=)" = "shim-init" ]] && in_singularity=likely
    [[ -z "$in_singularity" && "$(ps -p1 -ocomm=)" = "sinit" ]] && in_singularity=likely
    # [[ "x$PPID" = x1 ]] && [[ "x`ps -p1 -ocomm=`" != "xinit" ]] && { true; return; }  This is true also in Docker
    [[ -z "$in_singularity" ]] && { false; return; }
    # It is in Singularity
    # Test for privileged singularity suggested by D.Dykstra
    # singularity exec -c -i -p ~/work/singularity/cvmfs-fuse3 cat /proc/self/uid_map 2>/dev/null|awk '{if ($2 == "0") print "privileged"; else print "unprivileged"; gotone=1;exit} END{if (gotone != 1) print "failed"}'
    if [[ -e /proc/self/uid_map ]]; then
        local check_privileged
        check_privileged="$(cat /proc/self/uid_map 2>/dev/null | head -n1 | tr -s '[:blank:]' ','),"
        if [[ "$check_privileged" = ,0,* ]]; then
            [[ "$check_privileged" = ,0,0,* ]] && in_singularity=${in_singularity}_privileged || in_singularity=${in_singularity}_fakeroot
        fi
    else
        in_singularity=${in_singularity}_nousernamespaces
    fi
    echo ${in_singularity}
    # echo will not fail, returning 0 (true)
}


singularity_is_inside() {
    # Return true (0) if in Singularity false (1) otherwise
    # Uses singularity_check(), return its exit code
    singularity_check > /dev/null
}


singularity_exit_or_fallback () {
    # An error in Singularity occurred. Fallback to no Singularity if preferred or fail if required
    # If this function returns, then is OK to fall-back to no Singularity (otherwise it will exit)
    # OSG is continuing after sleep, no fall-back, no exit
    # In
    #  1: Error message
    #  2: Exit code (1 by default)
    #  3: sleep time (default: $EXITSLEEP used in exit_wrapper, not here)
    #  $GWMS_SINGULARITY_STATUS
    #  exit_wrapper() - function handling cleanup and exit
    if [[ "x$GWMS_SINGULARITY_STATUS" = "xPREFERRED" && "x$GWMS_SINGULARITY_STATUS_EFFECTIVE" != "xREQUIRED"* ]]; then
        # Fall back to no Singularity
        export HAS_SINGULARITY=0
        export GWMS_SINGULARITY_PATH=
        export GWMS_SINGULARITY_REEXEC=
        [[ -n "$1" ]] && warn "$1"
        warn "An error in Singularity occurred, but can fall-back to no Singularity ($GWMS_SINGULARITY_STATUS). Continuing"
    else
        [[ "x$GWMS_SINGULARITY_STATUS" = "xPREFERRED" ]] && info_dbg "Singularity PREFERRED overridden to REQUIRED (${GWMS_SINGULARITY_STATUS_EFFECTIVE#*_})"
        if [[ "$(type -t exit_wrapper)" == 'function' ]]; then
            exit_wrapper "${@}"
        else
            # TODO: also this?: touch ../../.stop-glidein.stamp >/dev/null 2>&1
            [[ -n "$1" ]] && warn "exit_wrapper not defined, printing message and exiting: $1" ||
                warn "exit_wrapper not defined, exiting"
            exit ${2:-1}
        fi
    fi
}


singularity_verify_image() {
    # check that the image is actually available (w/ extra check only for /cvmfs ones)
    # Assumes that all images in CVMFS are expanded by default (if ok_compressed is not set)
    # In:
    #  1. singularity image ($GWMS_SINGULARITY_IMAGE)
    #  2. flag: ok_compressed - return 0 if the image exists, is in CVMFS, but the listing fails
    # Exit codes
    #  0 - all OK
    #  1 - image (file or directory) does not exist
    #  2 - image (directory) exists, is in CVMFS, but the listing fails
    local singularity_image=$1
    local ok_compressed=false
    [[ "$2" = "ok_compressed" ]] && ok_compressed=true

    # TODO: better -e or ls?
    #if ! ls -l "$GWMS_SINGULARITY_IMAGE/" >/dev/null; then
    #if [[ ! -e "$GWMS_SINGULARITY_IMAGE" ]]; then
    # will both work for non expanded images?
    [[ ! -e "$singularity_image" ]] && return 1
    if cvmfs_path_in_cvmfs "$singularity_image"; then
        if ! ls -l "$(cvmfs_resolve_path "$singularity_image")" >/dev/null; then
            if ok_compressed; then
                info_dbg "Listing failed for $singularity_image, probably a compressed image in CVMFS"
            else
                return 2
            fi
        fi
    fi
    # all OK, returning 0
    true
}


# TODO: VO tests should be before (if contributing to image choice, ...) and inside (if they need to know the image, ...)
# WAS: prepare_and_invoke_singularity () {
singularity_prepare_and_invoke() {
    # Code moved into a function to allow early return in case of failure
    # In case of failure: 1. it invokes singularity_exit_or_fallback which exits if Singularity is required
    #   2. it interrupts itself and returns anyway
    # The function returns in case the Singularity setup fails
    # In:
    #   SINGULARITY_IMAGES_DICT: dictionary w/ Singularity images
    #   $SINGULARITY_IMAGE_RESTRICTIONS: constraints on the Singularity image
    # Using:
    #   GWMS_SINGULARITY_IMAGE,
    #   or GWMS_SINGULARITY_IMAGE_RESTRICTIONS (SINGULARITY_IMAGES_DICT via singularity_get_image)
    #      DESIRED_OS, GLIDEIN_REQUIRED_OS, REQUIRED_OS
    #   $OSG_SITE_NAME (in monitoring)
    #   GWMS_THIS_SCRIPT
    #   $GLIDEIN_Tmp_Dir GWMS_SINGULARITY_EXTRA_OPTS
    #   GWMS_SINGULARITY_OUTSIDE_PWD_LIST GWMS_SINGULARITY_OUTSIDE_PWD GWMS_THIS_SCRIPT_DIR _CONDOR_JOB_IWD
    #   GWMS_BASE_SUBDIR - if defined will be bound to the glidein directory (will be accessible from singularity)
    # Out:
    #   GWMS_SINGULARITY_IMAGE GWMS_SINGULARITY_IMAGE_HUMAN GWMS_SINGULARITY_OUTSIDE_PWD_LIST SINGULARITY_WORKDIR GWMS_SINGULARITY_EXTRA_OPTS GWMS_SINGULARITY_REEXEC
    # If  image is not provided, load the default one
    # Custom URIs: http://singularity.lbl.gov/user-guide#supported-uris

    # Choose the singularity image
    if [[ -z "$GWMS_SINGULARITY_IMAGE" ]]; then
        # No image requested by the job
        # Use OS matching to determine default; otherwise, set to the global default.
        #  # Correct some legacy names? What if they are used in the dictionary?
        #  REQUIRED_OS="`echo ",$REQUIRED_OS," | sed "s/,el7,/,rhel7,/;s/,el6,/,rhel6,/;s/,+/,/g;s/^,//;s/,$//"`"
        DESIRED_OS=$(list_get_intersection "${GLIDEIN_REQUIRED_OS:-any}" "${REQUIRED_OS:-any}")
        if [[ -z "$DESIRED_OS" ]]; then
            msg="ERROR   VO (or job) REQUIRED_OS and Entry GLIDEIN_REQUIRED_OS have no intersection. Cannot select a Singularity image."
            singularity_exit_or_fallback "$msg" 1
            return
        fi
        if [[ "$DESIRED_OS" = any ]]; then
            # Prefer the platforms default,rhel7,rhel6,rhel8, otherwise pick the first one available
            GWMS_SINGULARITY_IMAGE=$(singularity_get_image default,rhel7,rhel6,rhel8 ${GWMS_SINGULARITY_IMAGE_RESTRICTIONS:+$GWMS_SINGULARITY_IMAGE_RESTRICTIONS,}any)
        else
            GWMS_SINGULARITY_IMAGE=$(singularity_get_image "$DESIRED_OS" $GWMS_SINGULARITY_IMAGE_RESTRICTIONS)
        fi
    fi

    # At this point, GWMS_SINGULARITY_IMAGE is still empty, something is wrong
    if [[ -z "$GWMS_SINGULARITY_IMAGE" ]]; then
        msg="\
ERROR   If you get this error when you did not specify required OS, your VO does not support any valid default Singularity image
        If you get this error when you specified required OS, your VO does not support any valid image for that OS"
        singularity_exit_or_fallback "$msg" 1
        return
    fi

    # TODO: Custom images are not subject to SINGULARITY_IMAGE_RESTRICTIONS in OSG and CMS scripts. Should add a check here?
    # Something like:
    # if ! cvmfs_path_in_cvmfs "$GWMS_SINGULARITY_IMAGE"; then OR
    # if [[ -z "$(singularity_check_paths "c"  "$GWMS_SINGULARITY_IMAGE")" ]]; then
    #     singularity_exit_or_fallback "User provided image not in CVMFS" 1
    # fi

    # Whether user-provided or default image, we make sure it exists and make sure CVMFS has not fallen over
    # images in CVMFS can also be compressed (former expansion requirement is inconsistent w/ following lines)
    if ! singularity_verify_image "$GWMS_SINGULARITY_IMAGE" ok_compressed; then
        msg="\
ERROR   Unable to access the Singularity image: $GWMS_SINGULARITY_IMAGE
        Site and node: $OSG_SITE_NAME $(hostname -f)"
        singularity_exit_or_fallback "$msg" 1 10m
        return
    fi

    # Put a human readable version of the image in the env before expanding it - useful for monitoring
    export GWMS_SINGULARITY_IMAGE_HUMAN="$GWMS_SINGULARITY_IMAGE"

    # for /cvmfs based directory images, expand the path without symlinks so that
    # the job can stay within the same image for the full duration
    if cvmfs_path_in_cvmfs "$GWMS_SINGULARITY_IMAGE"; then
        # Make sure CVMFS is mounted in Singularity
        export GWMS_SINGULARITY_BIND_CVMFS=1
        local translated_image_path
        translated_image_path=$(cvmfs_resolve_path "$GWMS_SINGULARITY_IMAGE")
        if (cd "$translated_image_path") >/dev/null 2>&1; then
            # This will fail for images that are not expanded in CVMFS, just ignore the failure
            local new_image_path
            new_image_path=$( (cd "$translated_image_path" && pwd -P) 2>/dev/null)
            if [[ -n "$new_image_path" ]]; then
                GWMS_SINGULARITY_IMAGE=$new_image_path
            fi
        fi
    fi

    info_dbg "using image $GWMS_SINGULARITY_IMAGE_HUMAN ($GWMS_SINGULARITY_IMAGE)"
    # Singularity image is OK, continue w/ other init

    # set up the env to make sure Singularity uses the glidein dir for exported /tmp, /var/tmp
    if [[ -n "$GLIDEIN_Tmp_Dir" && -e "$GLIDEIN_Tmp_Dir" ]]; then
        if mkdir "$GLIDEIN_Tmp_Dir/singularity-work.$$"; then
            export SINGULARITY_WORKDIR="$GLIDEIN_Tmp_Dir/singularity-work.$$"
            export APPTAINER_WORKDIR="$GLIDEIN_Tmp_Dir/singularity-work.$$"
        else
            warn "Unable to set SINGULARITY_WORKDIR/APPTAINER_WORKDIR to $GLIDEIN_Tmp_Dir/singularity-work.$$. Leaving it undefined."
        fi
    fi

    GWMS_SINGULARITY_EXTRA_OPTS="$GLIDEIN_SINGULARITY_OPTS"

    # Binding different mounts (they will be removed if not existent on the host)
    # This is a dictionary in string w/ singularity mount options ("src1[:dst1[:opt1]][,src2[:dst2[:opt2]]]*"
    # OSG: checks also in image, may not work if not expanded. And Singularity will not fail if missing, only give a warning
    #  if [ -e $MNTPOINT/. -a -e $OSG_SINGULARITY_IMAGE/$MNTPOINT ]; then
    GWMS_SINGULARITY_WRAPPER_BINDPATHS_DEFAULTS="/hadoop,/ceph,/hdfs,/lizard,/mnt/hadoop,/mnt/hdfs,/etc/hosts,/etc/localtime"

    # CVMFS access inside container (default, but optional)
    if [[ "$GWMS_SINGULARITY_BIND_CVMFS" = "1" ]]; then
        if [[ -n "$CVMFS_MOUNT_DIR" ]]; then
            GWMS_SINGULARITY_WRAPPER_BINDPATHS_DEFAULTS=$(dict_set_val GWMS_SINGULARITY_WRAPPER_BINDPATHS_DEFAULTS "${CVMFS_MOUNT_DIR}:/cvmfs")
        else
            GWMS_SINGULARITY_WRAPPER_BINDPATHS_DEFAULTS=$(dict_set_val GWMS_SINGULARITY_WRAPPER_BINDPATHS_DEFAULTS /cvmfs)
        fi
    fi

    # GPUs - bind outside OpenCL directory if available, and add --nv flag
    if [[ "$OSG_MACHINE_GPUS" -gt 0 || "$GPU_USE" = "1" ]]; then
        if [[ -e /etc/OpenCL/vendors ]]; then
            GWMS_SINGULARITY_WRAPPER_BINDPATHS_DEFAULTS=$(dict_set_val GWMS_SINGULARITY_WRAPPER_BINDPATHS_DEFAULTS /etc/OpenCL/vendors /etc/OpenCL/vendors)
        fi
        GWMS_SINGULARITY_EXTRA_OPTS="$GWMS_SINGULARITY_EXTRA_OPTS --nv"
    fi
    info_dbg "bind-path default (cvmfs:$GWMS_SINGULARITY_BIND_CVMFS, hostlib:$([ -n "$HOST_LIBS" ] && echo 1), ocl:$([ -e /etc/OpenCL/vendors ] && echo 1)): $GWMS_SINGULARITY_WRAPPER_BINDPATHS_DEFAULTS"

    # We want to bind $PWD to /srv within the container - however, in order
    # to do that, we have to make sure everything we need is in $PWD, most
    # notably $GWMS_DIR (bin, lib, ...), the user-job-wrapper.sh (this script!)
    # and singularity_lib.sh (in $GWMS_AUX_SUBDIR)
    #
    # If gwms dir is present, then copy it inside the container
    [[ -z "$GWMS_SUBDIR" ]] && {
        GWMS_SUBDIR=".gwms.d"
        warn "GWMS_SUBDIR was undefined, setting to '.gwms.d'"
    }
    local gwms_dir=${GWMS_DIR:-"../../$GWMS_SUBDIR"}
    if [[ -d "$gwms_dir" ]]; then
        if mkdir -p "$GWMS_SUBDIR" && cp -r "$gwms_dir"/* "$GWMS_SUBDIR/"; then
            # Should copy only lib and bin instead?
            # TODO: change the message when condor_chirp requires no more special treatment
            info_dbg "copied GlideinWMS utilities (bin and libs, including condor_chirp) inside the container ($(pwd)/$GWMS_SUBDIR)"
        else
            warn "Unable to copy GlideinWMS utilities inside the container (to $(pwd)/$GWMS_SUBDIR)"
        fi
    else
        warn "Unable to find GlideinWMS utilities ($gwms_dir from $(pwd))"
    fi
    # copy singularity_lib.sh (in $GWMS_AUX_SUBDIR)
    mkdir -p "$GWMS_AUX_SUBDIR"
    cp "${GWMS_AUX_DIR}/singularity_lib.sh" "$GWMS_AUX_SUBDIR/"
    # mount the original glidein directory (for setup scripts only, not jobs)
    if [[ -n "$GWMS_BASE_SUBDIR" ]]; then
        # Make the glidein directory visible in singularity
        mkdir -p "$GWMS_BASE_SUBDIR"
        GWMS_SINGULARITY_WRAPPER_BINDPATHS_OVERRIDE="${GWMS_SINGULARITY_WRAPPER_BINDPATHS_OVERRIDE:+${GWMS_SINGULARITY_WRAPPER_BINDPATHS_OVERRIDE},}$(dirname "${GWMS_THIS_SCRIPT_DIR}"):/srv/$GWMS_BASE_SUBDIR"
    fi
    # copy the wrapper.sh (this script!)
    if [[ "$GWMS_THIS_SCRIPT" == */main/singularity_wrapper.sh ]]; then
        export JOB_WRAPPER_SINGULARITY="/srv/$GWMS_BASE_SUBDIR/main/singularity_wrapper.sh"
    else
        cp "$GWMS_THIS_SCRIPT" .gwms-user-job-wrapper.sh
        export JOB_WRAPPER_SINGULARITY="/srv/.gwms-user-job-wrapper.sh"
    fi

    # Remember what the outside pwd dir is so that we can rewrite env vars
    # pointing to somewhere inside that dir (for example, X509_USER_PROXY)
    #if [[ -n "$_CONDOR_JOB_IWD" ]]; then
    #    export GWMS_SINGULARITY_OUTSIDE_PWD="$_CONDOR_JOB_IWD"
    #else
    #    export GWMS_SINGULARITY_OUTSIDE_PWD="$PWD"
    #fi
    # Should this be GWMS_THIS_SCRIPT_DIR?
    #   Problem at sites like MIT where the job is started in /condor/execute/.. hard link from
    #   /export/data1/condor/execute/...
    # Do not trust _CONDOR_JOB_IWD when it comes to finding pwd for the job - M.Rynge
    GWMS_SINGULARITY_OUTSIDE_PWD="$PWD"
    # Protect from jobs starting from linked or bind mounted directories
    for i in "$_CONDOR_JOB_IWD" "$GWMS_THIS_SCRIPT_DIR"; do
        if [[ "$i" != "$GWMS_SINGULARITY_OUTSIDE_PWD" ]]; then
            [[ "$(robust_realpath "$i")" == "$GWMS_SINGULARITY_OUTSIDE_PWD" ]] && GWMS_SINGULARITY_OUTSIDE_PWD="$i"
        fi
    done
    export GWMS_SINGULARITY_OUTSIDE_PWD="$GWMS_SINGULARITY_OUTSIDE_PWD"
    GWMS_SINGULARITY_OUTSIDE_PWD_LIST="$(singularity_make_outside_pwd_list \
        "${GWMS_SINGULARITY_OUTSIDE_PWD_LIST}" "${PWD}" "$(robust_realpath "${PWD}")" \
        "${GWMS_THIS_SCRIPT_DIR}" "${_CONDOR_JOB_IWD}")"
    export GWMS_SINGULARITY_OUTSIDE_PWD_LIST

    # Build a new command line, with updated paths. Returns an array in GWMS_RETURN
    singularity_update_path /srv "$@"

    # Get Singularity binds, uses also GLIDEIN_SINGULARITY_BINDPATH, GLIDEIN_SINGULARITY_BINDPATH_DEFAULT
    # remove binds w/ non existing src (e)
    local singularity_binds
    singularity_binds=$(singularity_get_binds e "$GWMS_SINGULARITY_WRAPPER_BINDPATHS_DEFAULTS" "$GWMS_SINGULARITY_WRAPPER_BINDPATHS_OVERRIDE")
    # Run and log the Singularity command.
    info_dbg "about to invoke singularity, pwd is $PWD"
    export GWMS_SINGULARITY_REEXEC=1

    # Always disabling outside LD_LIBRARY_PATH, PATH, PYTHONPATH and LD_PRELOAD to avoid problems w/ different OS
    # Singularity is supposed to handle this, but different versions behave differently
    # Restore them only if continuing after the exec of singularity failed (end of this function)
    local old_ld_library_path=
    if [[ -n "$LD_LIBRARY_PATH" ]]; then
        old_ld_library_path=$LD_LIBRARY_PATH
        info "GWMS Singularity wrapper: LD_LIBRARY_PATH is set to $LD_LIBRARY_PATH outside Singularity. This will not be propagated to inside the container instance." 1>&2
        unset LD_LIBRARY_PATH
    fi
    local old_path=
    if [[ -n "$PATH" ]]; then
        old_path=$PATH
        info "GWMS Singularity wrapper: PATH is set to $PATH outside Singularity. This will not be propagated to inside the container instance." 1>&2
        PATH=$_DEFAULT_PATH
    fi
    local old_pythonpath=
    if [[ -n "$PYTHONPATH" ]]; then
        old_pythonpath=$PYTHONPATH
        info "GWMS Singularity wrapper: PYTHONPATH is set to $PYTHONPATH outside Singularity. This will not be propagated to inside the container instance." 1>&2
        unset PYTHONPATH
    fi
    if [[ -n "$LD_PRELOAD" ]]; then
        old_ld_preload=$LD_PRELOAD
        info "GWMS Singularity wrapper: LD_PRELOAD is set to $LD_PRELOAD outside Singularity. This will not be propagated to inside the container instance." 1>&2
        unset LD_PRELOAD
    fi

    # Add --clearenv if requested
    GWMS_SINGULARITY_EXTRA_OPTS=$(env_clear "${GLIDEIN_CONTAINER_ENV}" "${GWMS_SINGULARITY_EXTRA_OPTS}")

    # If there is clearenv protect the variables (it may also have been added by the custom Singularity options)
    if env_gets_cleared "${GWMS_SINGULARITY_EXTRA_OPTS}"; then
        env_preserve "${GLIDEIN_CONTAINER_ENV}"
    fi

    # The new OSG wrapper is not exec-ing singularity to continue after and inspect if it ran correctly or not
    # This may be causing problems w/ signals (sig-term/quit) propagation - [#24306]
    if [[ -z "$GWMS_SINGULARITY_LIB_VERSION" ]]; then
        # GWMS 3.4.5 or lower, no GWMS_SINGULARITY_GLOBAL_OPTS, no GWMS_SINGULARITY_LIB_VERSION
        singularity_exec "$GWMS_SINGULARITY_PATH" "$GWMS_SINGULARITY_IMAGE" "$singularity_binds" \
            "$GWMS_SINGULARITY_EXTRA_OPTS" "exec" "$JOB_WRAPPER_SINGULARITY" \
            "${GWMS_RETURN[@]}"
    else
        singularity_exec "$GWMS_SINGULARITY_PATH" "$GWMS_SINGULARITY_IMAGE" "$singularity_binds" \
            "$GWMS_SINGULARITY_EXTRA_OPTS" "$GWMS_SINGULARITY_GLOBAL_OPTS" "exec" "$JOB_WRAPPER_SINGULARITY" \
            "${GWMS_RETURN[@]}"
    fi
    # Continuing here only if exec of singularity failed
    GWMS_SINGULARITY_REEXEC=0
    env_restore "${GLIDEIN_CONTAINER_ENV}"
    # Restoring paths that are always cleared before invoking Singularity,
    # may contain something used for error communication
    [[ -n "$old_path" ]] && PATH=$old_path
    [[ -n "$old_ld_library_path" ]] && LD_LIBRARY_PATH=$old_ld_library_path
    [[ -n "$old_pythonpath" ]] && PYTHONPATH=$old_pythonpath
    [[ -n "$old_ld_preload" ]] && LD_PRELOAD=$old_ld_preload
    # Exit or return to run w/o Singularity
    singularity_exit_or_fallback "exec of singularity failed" $?
}


setup_from_environment() {
    # Retrieve variables from the environment and glidein_config file
    # Set up environment to know if Singularity is enabled and so we can execute Singularity
    # Out:
    #  export all of HAS_SINGULARITY, GWMS_SINGULARITY_STATUS, GWMS_SINGULARITY_PATH, GWMS_SINGULARITY_VERSION, GWMS_SINGULARITY_IMAGES_DICT,
    #    GLIDEIN_REQUIRED_OS, GLIDEIN_DEBUG_OUTPUT, REQUIRED_OS, GWMS_SINGULARITY_IMAGE, CVMFS_REPOS_LIST,
    #    GWMS_CONTAINERSW_PATH, GWMS_CONTAINERSW_VERSION, GWMS_CONTAINERSW_FULL_VERSION,
    #    GLIDEIN_DEBUG_OUTPUT (if not already set)

    # For OSG - from Job ClassAd
    #export OSGVO_PROJECT_NAME=$(get_prop_str ${_CONDOR_JOB_AD} ProjectName)
    #export OSGVO_SUBMITTER=$(get_prop_str ${_CONDOR_JOB_AD} User)

    # from singularity_setup.sh executed earlier (Machine ClassAd)
    export HAS_SINGULARITY=${HAS_SINGULARITY:-$(gwms_from_config HAS_SINGULARITY 0 get_prop_bool)}
    export GWMS_SINGULARITY_STATUS=${GWMS_SINGULARITY_STATUS:-$(gwms_from_config GWMS_SINGULARITY_STATUS "" get_prop_str)}
    export GWMS_SINGULARITY_PATH=${GWMS_SINGULARITY_PATH:-$(gwms_from_config SINGULARITY_PATH)}
    export GWMS_SINGULARITY_VERSION=${GWMS_SINGULARITY_VERSION:-$(gwms_from_config SINGULARITY_VERSION)}
    export GWMS_CONTAINERSW_PATH=${GWMS_CONTAINERSW_PATH:-$(gwms_from_config CONTAINERSW_PATH)}
    export GWMS_CONTAINERSW_VERSION=${GWMS_CONTAINERSW_VERSION:-$(gwms_from_config CONTAINERSW_VERSION)}
    export GWMS_CONTAINERSW_FULL_VERSION=${GWMS_CONTAINERSW_FULL_VERSION:-$(gwms_from_config CONTAINERSW_FULL_VERSION)}
    # Removed old GWMS_SINGULARITY_IMAGE_DEFAULT6 GWMS_SINGULARITY_IMAGE_DEFAULT7, now in _DICT
    # TODO: send also the image used during test in setup? in case the VO does not care
    # export GWMS_SINGULARITY_IMAGE_DEFAULT=$(get_prop_str $_CONDOR_MACHINE_AD SINGULARITY_IMAGE_DEFAULT)
    export GWMS_SINGULARITY_IMAGES_DICT=${GWMS_SINGULARITY_IMAGES_DICT:-$(gwms_from_config SINGULARITY_IMAGES_DICT)}
    export SINGULARITY_IMAGES_DICT=${GWMS_SINGULARITY_IMAGES_DICT}
    export GWMS_SINGULARITY_IMAGE_RESTRICTIONS=${GWMS_SINGULARITY_IMAGE_RESTRICTIONS:-$(gwms_from_config SINGULARITY_IMAGE_RESTRICTIONS)}
    export OSG_MACHINE_GPUS=${OSG_MACHINE_GPUS:-$(gwms_from_config GPUs 0)}
    # Setting below 0 as default for GPU_USE, to distinguish when undefined in machine AD
    export GPU_USE=${GPU_USE:-$(gwms_from_config GPU_USE)}
    # http_proxy from OSG advertise script
    export http_proxy=${http_proxy:-$(gwms_from_config http_proxy)}
    [[ -z "$http_proxy" ]] && unset http_proxy
    export GLIDEIN_REQUIRED_OS=${GLIDEIN_REQUIRED_OS:-$(gwms_from_config GLIDEIN_REQUIRED_OS)}
    export GLIDEIN_DEBUG_OUTPUT=${GLIDEIN_DEBUG_OUTPUT:-$(gwms_from_config GLIDEIN_DEBUG_OUTPUT)}
    export MODULE_USE=${MODULE_USE:-$(gwms_from_config MODULE_USE ${GWMS_MODULE_USE_DEFAULT} get_prop_bool)}

    # from Job ClassAd
    # Setting to defaults because Job ClassAd not available at setup time. Commenting values w/o default specified
    #export REQUIRED_OS=$(get_prop_str ${_CONDOR_JOB_AD} REQUIRED_OS)
    #export GWMS_SINGULARITY_IMAGE=$(get_prop_str ${_CONDOR_JOB_AD} SingularityImage)
    export GWMS_SINGULARITY_AUTOLOAD=${HAS_SINGULARITY}
    export GWMS_SINGULARITY_BIND_CVMFS=1
    export GWMS_SINGULARITY_BIND_GPU_LIBS=1
    #export CVMFS_REPOS_LIST=$(get_prop_str ${_CONDOR_JOB_AD} CVMFSReposList)
    # StashCache
    export STASHCACHE=0
    export STASHCACHE_WRITABLE=0
    export POSIXSTASHCACHE=0

    # OSG Modules
    # For MODULE_USE, the Factory and Frontend (machine ad) set the default. Job can override
    # TODO: TO REMOVE. For now don't load modules for LIGO. Later they will have to set MODULE_USE=0/false in the frontend
    if (echo "X$GLIDEIN_Client" | grep ligo) >/dev/null 2>&1; then
        export MODULE_USE=0
        export InitializeModulesEnv=0
    else
        export InitializeModulesEnv=${MODULE_USE}
    fi
    #export LoadModules=$(get_prop_str ${_CONDOR_JOB_AD} LoadModules)   # List of modules to load

    # CHECKS
    # SingularityAutoLoad is deprecated, see https://opensciencegrid.atlassian.net/browse/SOFTWARE-2770
    # SingularityAutoload effects on HAS_SINGULARITY depending on GWMS_SINGULARITY_STATUS
    if [[ "x$GWMS_SINGULARITY_STATUS" = "xPREFERRED" ]]; then
        # both variables are defined (w/ defaults)
        if [[ "x$GWMS_SINGULARITY_AUTOLOAD" != x1  &&  "x$HAS_SINGULARITY" = x1 ]]; then
            #warn "Using +SingularityAutoLoad is no longer allowed. Ignoring."
            #export GWMS_SINGULARITY_AUTOLOAD=1
            info "Singularity available but not required, disabled by +SingularityAutoLoad=0."
            export HAS_SINGULARITY=0
        fi
    fi
    # TODO: Remove to allow this for toubleshooting purposes?
    if [[ "x$GWMS_SINGULARITY_AUTOLOAD" != "x$HAS_SINGULARITY" ]]; then
        warn "Using +SingularityAutoLoad is no longer allowed to change Singularity use. Ignoring."
        export GWMS_SINGULARITY_AUTOLOAD=${HAS_SINGULARITY}
    fi
}

setup_classad_variables() {
    # Retrieve variables from Machine and Job ClassAds
    # Set up environment to know if Singularity is enabled and so we can execute Singularity
    # Out:
    #  export all of HAS_SINGULARITY, GWMS_SINGULARITY_STATUS, GWMS_SINGULARITY_PATH, GWMS_SINGULARITY_VERSION, GWMS_SINGULARITY_IMAGES_DICT,
    #    GLIDEIN_REQUIRED_OS, GLIDEIN_DEBUG_OUTPUT, REQUIRED_OS, GWMS_SINGULARITY_IMAGE, CVMFS_REPOS_LIST,
    #    GLIDEIN_DEBUG_OUTPUT (if not already set)

    if [[ -z "$_CONDOR_JOB_AD" ]]; then
        export _CONDOR_JOB_AD="NONE"
    fi
    if [[ -z "$_CONDOR_MACHINE_AD" ]]; then
        export _CONDOR_MACHINE_AD="NONE"
    fi

    # For OSG - from Job ClassAd
    export OSGVO_PROJECT_NAME=$(get_prop_str ${_CONDOR_JOB_AD} ProjectName)
    export OSGVO_SUBMITTER=$(get_prop_str ${_CONDOR_JOB_AD} User)

    # from singularity_setup.sh executed earlier (Machine ClassAd)
    export HAS_SINGULARITY=$(get_prop_bool ${_CONDOR_MACHINE_AD} HAS_SINGULARITY 0)
    export GWMS_SINGULARITY_STATUS=$(get_prop_str ${_CONDOR_MACHINE_AD} GWMS_SINGULARITY_STATUS)
    export GWMS_SINGULARITY_PATH=$(get_prop_str ${_CONDOR_MACHINE_AD} SINGULARITY_PATH)
    export GWMS_SINGULARITY_VERSION=$(get_prop_str ${_CONDOR_MACHINE_AD} SINGULARITY_VERSION)
    export GWMS_CONTAINERSW_PATH=$(get_prop_str ${_CONDOR_MACHINE_AD} CONTAINERSW_PATH)
    export GWMS_CONTAINERSW_VERSION=$(get_prop_str ${_CONDOR_MACHINE_AD} CONTAINERSW_VERSION)
    export GWMS_CONTAINERSW_FULL_VERSION=$(get_prop_str ${_CONDOR_MACHINE_AD} CONTAINERSW_FULL_VERSION)
    # Removed old GWMS_SINGULARITY_IMAGE_DEFAULT6 GWMS_SINGULARITY_IMAGE_DEFAULT7, now in _DICT
    # TODO: send also the image used during test in setup? in case the VO does not care
    # export GWMS_SINGULARITY_IMAGE_DEFAULT=$(get_prop_str $_CONDOR_MACHINE_AD SINGULARITY_IMAGE_DEFAULT)
    export GWMS_SINGULARITY_IMAGES_DICT=$(get_prop_str ${_CONDOR_MACHINE_AD} SINGULARITY_IMAGES_DICT)
    export GWMS_SINGULARITY_IMAGE_RESTRICTIONS=$(get_prop_str ${_CONDOR_MACHINE_AD} SINGULARITY_IMAGE_RESTRICTIONS)
    export OSG_MACHINE_GPUS=$(get_prop_str ${_CONDOR_MACHINE_AD} GPUs 0)
    # Setting below 0 as default for GPU_USE, to distinguish when undefined in machine AD
    export GPU_USE=$(get_prop_str ${_CONDOR_MACHINE_AD} GPU_USE)
    # http_proxy from OSG advertise script
    export http_proxy=$(get_prop_str ${_CONDOR_MACHINE_AD} http_proxy)
    [[ -z "$http_proxy" ]] && unset http_proxy
    export GLIDEIN_REQUIRED_OS=$(get_prop_str ${_CONDOR_MACHINE_AD} GLIDEIN_REQUIRED_OS)
    export GLIDEIN_DEBUG_OUTPUT=$(get_prop_str ${_CONDOR_MACHINE_AD} GLIDEIN_DEBUG_OUTPUT)
    export MODULE_USE=$(get_prop_bool ${_CONDOR_MACHINE_AD} MODULE_USE ${GWMS_MODULE_USE_DEFAULT})

    # from Job ClassAd
    export REQUIRED_OS=$(get_prop_str ${_CONDOR_JOB_AD} REQUIRED_OS)
    export GWMS_SINGULARITY_IMAGE=$(get_prop_str ${_CONDOR_JOB_AD} SingularityImage)
    # Jobs with SingularityImage make Singularity REQUIRED
    [[ -n "$GWMS_SINGULARITY_IMAGE" ]] && export GWMS_SINGULARITY_STATUS_EFFECTIVE="REQUIRED_Singularity_image_in_job"
    # If not provided default to whatever is Singularity availability
    export GWMS_SINGULARITY_AUTOLOAD=$(get_prop_bool ${_CONDOR_JOB_AD} SingularityAutoLoad ${HAS_SINGULARITY})
    export GWMS_SINGULARITY_BIND_CVMFS=$(get_prop_bool ${_CONDOR_JOB_AD} SingularityBindCVMFS 1)
    export GWMS_SINGULARITY_BIND_GPU_LIBS=$(get_prop_bool ${_CONDOR_JOB_AD} SingularityBindGPULibs 1)
    export CVMFS_REPOS_LIST=$(get_prop_str ${_CONDOR_JOB_AD} CVMFSReposList)
    # StashCache
    export STASHCACHE=$(get_prop_bool ${_CONDOR_JOB_AD} WantsStashCache 0)
    export STASHCACHE_WRITABLE=$(get_prop_bool ${_CONDOR_JOB_AD} WantsStashCacheWritable 0)
    export POSIXSTASHCACHE=$(get_prop_bool ${_CONDOR_JOB_AD} WantsPosixStashCache 0)

    # OSG Modules
    # For MODULE_USE, the Factory and Frontend (machine ad) set the default. Job can override
    # TODO: TO REMOVE. For now don't load modules for LIGO. Later they will have to set MODULE_USE=0/false in the frontend
    if (echo "X$GLIDEIN_Client" | grep ligo) >/dev/null 2>&1; then
        export MODULE_USE=$(get_prop_bool ${_CONDOR_JOB_AD} MODULE_USE 0)
        export InitializeModulesEnv=$(get_prop_bool ${_CONDOR_JOB_AD} InitializeModulesEnv 0)
    else
        export MODULE_USE=$(get_prop_bool ${_CONDOR_JOB_AD} MODULE_USE ${MODULE_USE})
        export InitializeModulesEnv=$(get_prop_bool ${_CONDOR_JOB_AD} InitializeModulesEnv ${MODULE_USE})
    fi

    export LoadModules=$(get_prop_str ${_CONDOR_JOB_AD} LoadModules)   # List of modules to load

    # These attributes may have been defined in the machine AD above (takes precedence)
    [[ -z "$GLIDEIN_DEBUG_OUTPUT" ]] && export GLIDEIN_DEBUG_OUTPUT=$(get_prop_str ${_CONDOR_JOB_AD} GLIDEIN_DEBUG_OUTPUT)
    # Setting here default for GPU_USE, to distinguish when undefined in machine AD
    [[ -z "$GPU_USE" ]] && export GPU_USE=$(get_prop_str ${_CONDOR_JOB_AD} GPU_USE 0)

    # CHECKS
    # SingularityAutoLoad is deprecated, see https://opensciencegrid.atlassian.net/browse/SOFTWARE-2770
    # SingularityAutoload effects on HAS_SINGULARITY depending on GWMS_SINGULARITY_STATUS
    if [[ "x$GWMS_SINGULARITY_STATUS" = "xPREFERRED" ]]; then
        # both variables are defined (w/ defaults)
        if [[ "x$GWMS_SINGULARITY_AUTOLOAD" != x1  &&  "x$HAS_SINGULARITY" = x1 ]]; then
            #warn "Using +SingularityAutoLoad is no longer allowed. Ignoring."
            #export GWMS_SINGULARITY_AUTOLOAD=1
            info "Singularity available but not required, disabled by +SingularityAutoLoad=0."
            export HAS_SINGULARITY=0
        fi
    fi
    # TODO: Remove to allow this for toubleshooting purposes?
    if [[ "x$GWMS_SINGULARITY_AUTOLOAD" != "x$HAS_SINGULARITY" ]]; then
        warn "Using +SingularityAutoLoad is no longer allowed to change Singularity use. Ignoring."
        export GWMS_SINGULARITY_AUTOLOAD=${HAS_SINGULARITY}
    fi
}


singularity_setup_inside_env() {
    # 1. GWMS_SINGULARITY_OUTSIDE_PWD, $GWMS_SINGULARITY_OUTSIDE_PWD_LIST, outside run directory pre-Singularity
    local outside_pwd_list="$1"
    local key val old_val old_ifs
    # TODO: htcondor-provided condor_chirp has been replaced by "pychirp", should _CONDOR_CHIRP_CONFIG be removed?
    for key in X509_USER_PROXY X509_USER_CERT X509_USER_KEY \
               _CONDOR_CREDS _CONDOR_MACHINE_AD _CONDOR_EXECUTE _CONDOR_JOB_AD \
               _CONDOR_SCRATCH_DIR _CONDOR_CHIRP_CONFIG _CONDOR_JOB_IWD \
               OSG_WN_TMP ; do
        # double sed to avoid matching a directory starting w/ the same name (e.g. /my /mydir)
        # val="$(echo "${!key}" | sed -E "s,${GWMS_SINGULARITY_OUTSIDE_PWD}/(.*),/srv/\1,;s,${GWMS_SINGULARITY_OUTSIDE_PWD}$,/srv,")"
        old_val="${!key}"
        val="$old_val"
        old_ifs="$IFS"
        IFS=":"
        for out_path in $outside_pwd_list; do
            # double substitution to avoid matching a directory starting w/ the same name (e.g. /my /mydir)
            case "$val" in
                $out_path) val=/srv ;;
                $out_path/*) val="${old_val/#$out_path//srv}";;
                # Not worth checking "$(robust_realpath "${old_val}")": outside paths are not existing
            esac
            # Warn about possible error conditions
            [[ "${val}" == *"${out_path}"*  ]] &&
                info_dbg "Outside path (${out_path}) still in ${key} ($val), the conversion to run in Singularity may be incorrect" ||
                true
            # update and exit loop if the value changed
            if [[ "$val" != "$old_val" ]]; then
                eval export ${key}="${val}"
                info_dbg "changed $key: $old_val => $val"
                break
            fi
        done
        IFS="$old_ifs"
        # Warn about possible error conditions
        [[ "${val}" == */execute/dir_* ]] &&
            info_dbg "String '/execute/dir_' in ${key} ($val), the conversion to run in Singularity may be incorrect" ||
            true
    done
}


singularity_setup_inside() {
    # Setup some environment variables when the script is restarting in Singularity
    # In:
    #   $GWMS_SINGULARITY_OUTSIDE_PWD_LIST ($GWMS_SINGULARITY_OUTSIDE_PWD), $GWMS_SINGULARITY_IMAGE_HUMAN ($GWMS_SINGULARITY_IMAGE as fallback)
    # Out:
    #   Changing env variables (especially TMP and X509 related) to work w/ chrooted FS
    unset TMP
    unset TMPDIR
    unset TEMPDIR
    unset TEMP
    unset X509_CERT_DIR
    # Adapt for changes in filesystem space
    if [[ -n "${GWMS_SINGULARITY_OUTSIDE_PWD_LIST}" || -n "${GWMS_SINGULARITY_OUTSIDE_PWD}" ]]; then
        info_dbg "calling singularity_setup_inside_env w/ ${GWMS_SINGULARITY_OUTSIDE_PWD_LIST} (${GWMS_SINGULARITY_OUTSIDE_PWD})."
        singularity_setup_inside_env "${GWMS_SINGULARITY_OUTSIDE_PWD_LIST:-${GWMS_SINGULARITY_OUTSIDE_PWD}}"
    else
        warn "GWMS_SINGULARITY_OUTSIDE_PWD_LIST and GWMS_SINGULARITY_OUTSIDE_PWD not set, cannot remove possible outside path from env variables"
    fi

    # If CONDOR_CONFIG, X509_USER_PROXY and friends are not set by the job, we might see the
    # glidein one - in that case, just unset the env var
    local key val
    for key in CONDOR_CONFIG X509_USER_PROXY X509_USER_CERT X509_USER_KEY ; do
        val="${!key}"
        if [[ -n "$val" ]]; then
            if [[ ! -e "$val" ]]; then
                eval unset $key >/dev/null 2>&1 || true
                info_dbg "unset $key ($val). File not found."
            fi
        fi
    done

#    # From CMS - not really required, why clobber the environment? could be in the job
#    # If the CVMFS worker node client was used for the pilot, it remains visible
#    # inside the container.  However, if the outside is RHEL7 and inside is RHEL6
#    # (or vice versa), unusable binaries may be on the path.  Reload the UI.
#    # If the UI isn't present, then we just hope for the best!
#    # TODO: Run this only if the OSG WN had been setup?
#    val="$GWMS_SINGULARITY_IMAGE_HUMAN"
#    [[ -z "$val" ]] && val="$GWMS_SINGULARITY_IMAGE"
#    if [[ "x$val" = "x/cvmfs/singularity.opensciencegrid.org/bbockelm/cms:rhel6"  &&  -e "/cvmfs/oasis.opensciencegrid.org/osg-software/osg-wn-client/3.4/current/el6-x86_64/setup.sh" ]]; then
#        source /cvmfs/oasis.opensciencegrid.org/osg-software/osg-wn-client/3.4/current/el6-x86_64/setup.sh
#    elif [[ "x$val" = "x/cvmfs/singularity.opensciencegrid.org/bbockelm/cms:rhel7"  &&  -e "/cvmfs/oasis.opensciencegrid.org/osg-software/osg-wn-client/3.4/current/el7-x86_64/setup.sh" ]]; then
#        source /cvmfs/oasis.opensciencegrid.org/osg-software/osg-wn-client/3.4/current/el7-x86_64/setup.sh
#    fi

    # Override some OSG specific variables if defined
    [[ -n "$OSG_WN_TMP" ]] && export OSG_WN_TMP=/tmp

    # GlideinWMS utility files and libraries
    if [[ -e "$PWD/$GWMS_SUBDIR/bin" ]]; then
        # This includes the portable Python only condor_chirp
        export PATH="$PWD/$GWMS_SUBDIR/bin:$PATH"
        # export LD_LIBRARY_PATH="$PWD/$GWMS_SUBDIR/lib/lib:$LD_LIBRARY_PATH"
    fi

    # Some java programs have seen problems with the timezone in our containers.
    # If not already set, provide a default TZ
    [[ -z "$TZ" ]] && export TZ="UTC"

}
