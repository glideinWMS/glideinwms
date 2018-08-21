#!/bin/bash
#
# This script contains some utility functions for the singularity scripts
# The script will be available outside and inside Singularity
#
# This script advertises:
# HAS_SINGULARITY
# SINGULARITY_PATH
# GWMS_SINGULARITY_PATH
# SINGULARITY_VERSION
# GWMS_SINGULARITY_VERSION
# GLIDEIN_REQUIRED_OS - csv, Factory ops set it to tell which OS are allowed on the entry
# REQUIRED_OS - csv, Required OS, job submitters set it to say which OSes the job requires
# GLIDEIN_DEBUG_OUTPUT
#
# Note that HTCondor has these native attribute names:
# HasSingularity
# SingularityVersion
# Using the above names would interfere and modify HTCondor behavior
# NOTE: HAS_SINGULARITY and HasSingularity are different because of '_'


# All output is to stderr

# Functions are using:
# - $glidein_config
# - $GLIDEIN_DEBUG_OUTPUT
# - $GLIDEIN_THIS_SCRIPT

# Singularity mount points:
# src1:dst1,src2:dst2:ro,src3
# SINGULARITY_IMAGES_DICT
# Format checkers in python in reconfig
# Singularity images, could be URLs (docker://...)
# should platform be dash separated list (os-arch)? match is OK?
# plartorm:URL,DEFAULT:URL
# SINGULARITY_IMAGE_DEFAULT6 -> rhel6:
# SINGULARITY_IMAGE_DEFAULT7 -> rhel7:

# Mount points
# Once a mount point is used, following attempts to mount on it are not successful and trigger a warning message
# So the first time a mount point is the one used will determine what is mounted
# SINGULARITY_BINDPATH (left for the host environment) takes precedence (added before the command line options)
# Then come GLIDEIN_SINGULARITY_BINDPATH and last GLIDEIN_SINGULARITY_BINDPATH_DEFAULT are added to the command line
# The suggestion is for the Factory to guarantee defaults in GLIDEIN_SINGULARITY_BINDPATH_DEFAULT and let the Frontend
# set or override GLIDEIN_SINGULARITY_BINDPATH
# GWMS will not sanitize, check your user points
# GLIDEIN_SINGULARITY_BINDPATH
# GLIDEIN_SINGULARITY_BINDPATH_DEFAULT

# 0 = true
# 1 = false


error_gen=$(grep '^ERROR_GEN_PATH ' "$glidein_config" | awk '{print $2}')

# Output log levels:
# WARN used also for error, always to stderr
# INFO if GLIDEIN_QUIET is not set (default)
# DEBUG if GLIDEIN_DEBUG_OUTPUT is set (and GLIDEIN_QUIET is not set)
# GLIDEIN_THIS_SCRIPT should be set to $0 to log the file name

function info_stdout {
    [ -z "$GLIDEIN_QUIET" ] && echo $@
}

function info_raw {
    [ -z "$GLIDEIN_QUIET" ] && echo $@  1>&2
}

function info {
    [ -z "$GLIDEIN_QUIET" ] && echo "INFO " $@  1>&2
}

function info_dbg {
    if [ -n "$GLIDEIN_DEBUG_OUTPUT" ]; then
        local script_txt=''
        [ -n "$GLIDEIN_THIS_SCRIPT" ] && script_txt="(file: $GLIDEIN_THIS_SCRIPT)"
        info_raw "DEBUG $script_txt" $@
    fi
}

function warn {
    echo "WARN " $@  1>&2
}

function warn_raw {
    echo $@  1>&2
}

# Dictionaries are strings: key1:val1,key2:val2
# Comma is not allowed in keys or values, colon is not allowed in keys
# Associative dictionaries are OK in bash 4.1. Before then are not or not fully supported
# References (declare -n) are from 4.3.
# TEST: to test dict functions
# my_dict=" key 1:val1:opt1,key2:val2,key3:val3:opt3,key4,key5:,key6 :val6"
function get_dict_val {
    # Return to stdout the value of the fist key present in the dictionary
    # Return true (0) if a value is found and is not empty, 1 otherwise
    # Use a regex to extract the values
    # $1 dict name
    # $2 comma separated list of keys (key can contain a space if you quote it but not a comma)
    local IFS=,
    local key_list="$2"
    for key in $key_list; do
        res="$(expr ",${!1}," : ".*,$key:\([^,]*\),.*")"
        if [ -n "$res" ]; then
            echo "$res"
            return 0
        fi
    done
    return 1
}

function check_dict_key {
    # Return true (0) if the key is in the dict (the value could be empty)
    # $1 dict name
    # $2 key
    #re=*",${2}:"*  # bash <= 3.1 needs quoted regex, >=3.2 unquoted, variables are OK with both
    [[ ",${!1}," = *",${2}:"* ]] && return 0
    [[ ",${!1}," = *",${2},"* ]] && return 0  # could be empty val and no separatoe
    return 1
}

function set_dict_val {
    # Echoes a new string including the new key:value. Return is 0 if the key was already there, 1 if new
    # $1 dict name
    # $2 key
    # $3 value
    local my_dict=${!1}
    local key_found
    if [[ ",${my_dict}," = *",${2}:"* || ",${my_dict}," = *",${2},"* ]]; then
        my_dict="`echo ",${my_dict}," | sed -E "s/,${2}(,|:[^,]*,)/,/;s/,+/,/g;s/^,//;s/,\$//"`"
        key_found=yes
    fi
    [ -n "$3" ] && echo "${my_dict},$2:$3" || echo "${my_dict},$2"
    [ -n "${key_found}" ] && return 0
    return 1
}

# function get_dict_items {} - not needed
## TODO: problem if val is not there (only key)

# TEST: for iterators tests
# function dit { echo "TEST: <$1> <$2> <$3>"; }
# dict_items_iterator my_dict dit par1
# Make sure that par1 is passed, spaces are preserved, no-val keys are handled correctly and val options are preserved
function dict_items_iterator {
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

function dict_keys_iterator {
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

function get_dict_keys {
    # Returns a comma separated list of keys (there may be spaces if keys do have spaces)
    # Quote the return string and use  IFS=, to separate the keys, this way you'll preserve spaces
    # Returning the elements would flatten the array and cause problems w/ spaces
    # $1 dict
    local my_dict=${!1}
    local res="`echo "$my_dict," | sed 's/:[^,]*,/,/g; s/,\+/,/g'`"
    echo "${res%,}"
}


function get_prop_bool {
    # In:
    #  $1 the file (for example, $_CONDOR_JOB_AD or $_CONDOR_MACHINE_AD)
    #  $2 the key
    #  $3 default value (optional, must be 1->true or 0->false, 0 if unset)
    # For HTCondor consider True: true (case insensitive), any integer != 0
    #                       Anything else is False (0, false, undefined, ...)
    # Out:
    #  echo "1" for true, dafult for "0" undefined, for false/failure (bad invocation, no ClassAd file)
    #  return the opposite to allow shell truth values true,1->0 , false,0->1
    # NOTE Spaces are trimmed, so strings like "T RUE" are true

    local default=$3
    [ -z "$default" ] && default=0
    if [ $# -lt 2 ] || [ $# -gt 3 ]; then
        val=0
    elif [ "x$1" = "NONE" ]; then
        val=$default
    else
        # sed "s/[\"' \t\r\n]//g" not working on OS X, '\040\011\012\015' = ' '$'\t'$'\r'$'\n'
        val=`(grep -i "^$2 " $1 | cut -d= -f2 | tr -d '\040\011\012\015') 2>/dev/null`
        # Convert variations of true to 1
        re="^[0-9]+$"  # bash <= 3.1 needs quoted regex, >=3.2 unquoted, variables are OK with both
        if (echo "x$val" | grep -i true) >/dev/null 2>&1; then
            val=1
        elif [[ "$val" =~ $re ]]; then
            if [ $val -eq 0 ]; then
                val=0
            else
                val=1
            fi
        elif [ -z "$val" ]; then
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
    if [ "$val" = "1" ];  then
        return 0
    else
        return 1
    fi
}


function is_condor_true {
   # Assuming the input is numeric 0->False other->True
   if [ $1 -eq 0 ]; then
       false
   else
       true
   fi
}


function get_prop_str {
    # In:
    #  $1 the file (for example, $_CONDOR_JOB_AD or $_CONDOR_MACHINE_AD)
    #  $2 the key
    #  $3 default value (optional)
    # Out:
    #  echo the value (or the default if UNDEFINED) and return 0
    #  For no ClassAd file, echo the default and return 1
    #  For bad invocation, return 1
    if [ $# -lt 2 ] || [ $# -gt 3 ]; then
        return 1
    elif [ "x$1" = "NONE" ]; then
        echo $3
        return 1
    fi
    val=`(grep -i "^$2 " $1 | cut -d= -f2 | sed -e "s/^[\"' \t\n\r]//g" -e "s/[\"' \t\n\r]$//g" | sed -e "s/^[\"' \t\n\r]//g" ) 2>/dev/null`
    [ -z "$val" ] && val=$3
    echo $val
    return 0
}


# add_config_line and add_condor_vars_line are in add_config_line.source (ADD_CONFIG_LINE_SOURCE in $glidein_config)
if [ "$glidein_config" != "NONE" ] && [ "x$SOURCED_ADD_CONFIG_LINE" = "x" ]; then
    # import add_config_line and add_condor_vars_line functions used in advertise
    if [ "x$add_config_line_source" = "x" ]; then
        export add_config_line_source=`grep '^ADD_CONFIG_LINE_SOURCE ' $glidein_config | awk '{print $2}'`
        export       condor_vars_file=`grep -i "^CONDOR_VARS_FILE "    $glidein_config | awk '{print $2}'`
    fi

    info "Sourcing $add_config_line_source"
    source $add_config_line_source
    # make sure we don't source a second time inside the container
    export SOURCED_ADD_CONFIG_LINE=1
fi

function advertise {
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

    if [ "$glidein_config" != "NONE" ]; then
        add_config_line $key "$value"
        add_condor_vars_line $key "$atype" "-" "+" "Y" "Y" "+"
    fi

    if [ "$atype" = "S" ]; then
        echo "$key = \"$value\""
    else
        echo "$key = $value"
    fi
}


# TODO: parametrize options, handle mount points

function check_singularity_paths {
    # Chech if the mountpoints are valid
    # 1: checks, a list of e:exist,c:in cvmfs,v:check value instead of key
    # 2: src
    # 3: dst:options
    local failed=
    local to_check=$2
    if [ -z "$1" ]; then
        [ -n "$3" ] && echo -n "$2:$3," || echo -n "$2,"
        return
    fi
    [[ $1 = *v* ]] && to_check=$3
    [[ $1 = *e* ]] && [ ! -e $to_check ] && { info "Discarding path $to_check. File does not exist"; false; return; }
    [[ $1 = *c* ]] && [ ! $to_check = "/cvmfs"* ] && { info "Discarding path $to_check. Is not in CVMFS"; false; return; }
    [ -n "$3" ] && echo -n "$2:$3," || echo -n "$2,"
}


# TEST:
# get_singularity_binds "" /cvmfs /minos,/usr/games
function get_singularity_binds {
    # Return on stdout a string with multiple --bind options for whichever is not empty of:
    # $2,  GLIDEIN_SINGULARITY_BINDPATH, GLIDEIN_SINGULARITY_BINDPATH_DEFAULT, $2 (in that order)
    # Each of them must be a valid Sinsularity mount point string (comma separated, no spaces, src[:dst[:opt]] groups)
    # 1: parameters for the path checks (see check_singularity_paths for valid values)
    # 2: dafault binds (added at the end, not used if already mounted)
    # 3: override binds (added at the beginning, will override all binds specified in the variables)
    local retv=  # default controlled from outside ($2)
    local checks=$1

    info_dbg "Singularity binds: OVERRIDE:$3, BINDPATH:$GLIDEIN_SINGULARITY_BINDPATH, BINDPATH_DEFAULT:$GLIDEIN_SINGULARITY_BINDPATH_DEFAULT, DEFAULT:$2, CHECKS($checks)"
    [ -n "$3" ] && retv="${retv}$3,"
    [ -n "$GLIDEIN_SINGULARITY_BINDPATH" ] && retv="${retv}$GLIDEIN_SINGULARITY_BINDPATH,"
    [ -n "$GLIDEIN_SINGULARITY_BINDPATH_DEFAULT" ] && retv="${retv}$GLIDEIN_SINGULARITY_BINDPATH_DEFAULT,"
    [ -n "$2" ] && retv="${retv}$2"

    # TODO: validate mount points - if not existing Singularity will error (not running)
    retv="`dict_items_iterator retv check_singularity_paths "$checks"`"
    [ -n "${retv%,}" ] && echo "--bind ${retv%,}"
}


function get_singularity_exec_options_string {
   # Return on stdout the command to invoke Singularity exec
   # Change here for all invocations (both singularity_setup, wrapper). Custom options should go in the specific script
   # In:
   #  1 - Singularity bind defaults
   #  2 - Singularity bind overrides
   #  3 - Singularity extra options
   #  PWD
   # Out:
   #  string w/ command options on stdout

   local singularity_bind_defaults="$1"
   local singularity_bind_override="$2"
   local singularity_extra_opts="$3"
   # Get singularity binds from GLIDEIN_SINGULARITY_BINDPATH, GLIDEIN_SINGULARITY_BINDPATH_DEFAULT, add default /cvmfs,
   # add overrides, and remove non existing src (checks=e) - if src is not existing Singularity will error (not run)
   local singularity_bind_opts="`get_singularity_mountpoints e "$singularity_bind_defaults" "$singularity_bind_override"`"

   # TODO: verify it is protected for spaces in singularity_sin (if there), bind_paths and singularity_image (if here?)
   echo "exec --home $PWD:/srv --pwd /srv $singularity_bind_opts $singularity_extra_opts --contain --ipc --pid"
}


function test_singularity_exec {
   # Test Singularity by invoking it
   # In:
   #  1 - Singularity image, default GWMS_SINGULARITY_IMAGE_DEFAULT
   #  2 - Singularity path, default GWMS_SINGULARITY_PATH_DEFAULT
   #  3 - Singularity bind defaults
   #  4 - Singularity bind overrides
   #  5 - Singularity extra options
   #  PWD (used by get_singularity_exec_options_string)
   # Out:
   # Return:
   #  true - Singularity OK
   #  false - Singularity not working or empty bin/image

   local singularity_image="$1"
   local singularity_bin="$2"
   [ -z "$singularity_image" ] && singularity_image="$GWMS_SINGULARITY_IMAGE_DEFAULT"
   [ -z "$singularity_bin" ] && singularity_bin="$GWMS_SINGULARITY_PATH_DEFAULT"
   [ -z "$singularity_image" ] || [ -z "$singularity_bin" ] && { info "Singularity image or binary empty. Test failed "; false; return; }

   info_dbg "\"$singularity_bin\" `get_singularity_exec_options_string "$3" "$4" "$5"` \"$singularity_image\" \
             printenv | grep \"$singularity_bin\""

   if ("$singularity_bin" `get_singularity_exec_options_string "$3" "$4" "$5"` "$singularity_image" \
                               printenv | grep "$singularity_bin" 1>&2)
   then
       info "Singularity at $singularity_bin appears to work"
       true
   else
       info "Singularity at $singularity_bin failed "
       false
   fi
}


function locate_singularity {
    # Find Singularity path
    # In:
    #   1 - s_location, suggested Singularity directory, will be added first in PATH before searching for Singularity
    #   LMOD_CMD, optional if in the environment
    # Out (E - exported):
    #   E PATH - Singularity path may be added
    #   E GWMS_SINGULARITY_VERSION
    #   E GWMS_SINGULARITY_PATH - set if Singularity is found
    #   E HAS_SINGULARITY - set to True if Singularity is found
    #   singularity_in - place where singularity bin was found

    info "Checking for singularity..."
    #GWMS Entry must use SINGULARITY_BIN to specify the pathname of the singularity binary
    #GWMS, we quote $singularity_bin to deal with white spaces in the path
    local s_location="$1"
    if [ -n "$s_location" ]; then
        s_location_msg="at $s_location,"
        if [  -d "$s_location" ] && [ -x "${s_location}/singularity" ]; then
            export PATH="$s_location:$PATH"
        else
            if [ "x$s_location" = "xNONE" ]; then
                warn "SINGULARITY_BIN = NONE means that singularity is not supported!"
            else
                info "Suggested path $1 (SINGULARITY_BIN?) is not a directory or does not contain singularity!"
                info "will try to proceed with auto-discover but this misconfiguration may cause errors later!"
            fi
        fi
    fi

    HAS_SINGULARITY="False"
    if [ "x$s_location" != "xNONE" ]; then
        # should never end up here if NONE, locate_singularity should not have been invoked
        # 1. Look first in the path suggested
        GWMS_SINGULARITY_VERSION=$("$s_location"/singularity --version 2>/dev/null)
        if [ "x$GWMS_SINGULARITY_VERSION" != "x" ]; then
            HAS_SINGULARITY="True"
            GWMS_SINGULARITY_PATH="$s_location/singularity"
            # Add $LOCATION to $PATH
            # info " ... prepending $LOCATION to PATH"
            # export PATH="$LOCATION:$PATH"
            singularity_in="SINGULARITY_BIN"
        else
            # 2. Look in $PATH
            GWMS_SINGULARITY_VERSION=$(singularity --version 2>/dev/null)
            if [ "x$GWMS_SINGULARITY_VERSION" != "x" ]; then
                HAS_SINGULARITY="True"
                GWMS_SINGULARITY_PATH="$(which singularity 2>/dev/null)"
                singularity_in="PATH"
            else
                # 3. Invoke module
                # some sites requires us to do a module load first - not sure if we always want to do that
                GWMS_SINGULARITY_VERSION=$(module load singularity >/dev/null 2>&1; singularity --version 2>/dev/null)
                if [ "x$GWMS_SINGULARITY_VERSION" != "x" ]; then
                    HAS_SINGULARITY="True"
                    GWMS_SINGULARITY_PATH=$(module load singularity >/dev/null 2>&1; which singularity)
                    singularity_in="module"
                elif [[ "x$LMOD_CMD" == x/cvmfs/* ]]; then
                    warn "Singularity not found in module. OSG OASIS module from module-init.sh used. May override a system module."
                fi
            fi
        fi
    fi
    # Execution test '&& test_singularity_exec' left to later
    if [ "$HAS_SINGULARITY" = "True" ]; then
        # one last check - make sure we could determine the path to singularity
        if [ "x$GWMS_SINGULARITY_PATH" = "x" ]; then
            warn "Looks like we found Singularity, but were unable to determine the full path to the executable"
        else
            export HAS_SINGULARITY=$HAS_SINGULARITY
            export GWMS_SINGULARITY_PATH="$GWMS_SINGULARITY_PATH"
            export GWMS_SINGULARITY_VERSION=$GWMS_SINGULARITY_VERSION
            info "Singularity found at \"${GWMS_SINGULARITY_PATH}\" (using $singularity_in)"
            true
            return
        fi
    fi
    # No valid singularity found
    export HAS_SINGULARITY="False"
    export GWMS_SINGULARITY_PATH=""
    export GWMS_SINGULARITY_VERSION=""
    warn "Singularity not found$s_location_msg in PATH, and module"
    false
}


function get_desired_platform {
    # Return the desired OS that works for both Entry and VO
    # Input lists should be sorted in order of preference
    # In:
    #   1: GLIDEIN_REQUIRED_OS - comma separated list of OSes provided by the Entry
    #   2: REQUIRED_OS - comma separated list of OSes required by the VO
    # Out:
    #   DESIRED_OS
    # TODO: verify meaning of $GLIDEIN_REQUIRED_OS and $REQUIRED_OS, both lists?
    # TODO: change in real function w/ parameters and not global vars?
    # Return on stdout the desired platform/OS (first item in the intersection)
    # Valid values: rhel6, rhel7 (default),
    if [ "x$1" = "xany" ]; then
        DESIRED_OS=$2
        if [ "x$DESIRED_OS" = "xany" ]; then
            DESIRED_OS="el7"
        fi
    else
        DESIRED_OS=$(python -c "print sorted(list(set('$2'.split(',')).intersection('$1'.split(','))))[0]" 2>/dev/null)
    fi
    # Name corrections
    # TODO: corrections in list? el OR rhel?
    [ "x$DESIRED_OS" = "xel7" ] && DESIRED_OS=rhel7
    [ "x$DESIRED_OS" = "xel6" ] && DESIRED_OS=rhel6
    echo "$DESIRED_OS"

}


function get_singularity_image {
    # Return on stdout the Singularity image
    # Let caller decide what to do if there are problems
    # In:
    #  1: a comma separated list of platforms (OS) to choose the image (default: DESIRED_OS, [default,rhel7,rhel6])
    #  2: a comma separated list of restrictions (default: none)
    #     - cvmfs: image must be on CVMFS
    #  SINGULARITY_IMAGES_DICT
    #  SINGULARITY_IMAGE_DEFAULT (legacy)
    #  SINGULARITY_IMAGE_DEFAULT6 (legacy)
    #  SINGULARITY_IMAGE_DEFAULT7 (legacy)
    # Out:
    #  EC: 0: OK, 1: Empty/no image for the desired OS (or for any), 2: File not existing, 3: restriction not met (e.g. image not on cvmfs)
    # TODO: same default for desired OS and image pick

    local s_platform="$1"
    local singularity_image
    if [ -z "$s_platform" ]; then
        s_platform="$DESIRED_OS"
        [ -z "$s_platform" ] && s_platform="default,rhel7,rhel6"
    fi
    local s_restrictions="$2"

    # To support legacy variables SINGULARITY_IMAGE_DEFAULT, SINGULARITY_IMAGE_DEFAULT6, SINGULARITY_IMAGE_DEFAULT7
    # values are added to SINGULARITY_IMAGES_DICT
    # TODO: These override existing dict values (in the future we'll add && [ check_dict_key rhel6 ] to avoid this)
    [ -n "$SINGULARITY_IMAGE_DEFAULT6" ] && SINGULARITY_IMAGES_DICT="`set_dict_val SINGULARITY_IMAGES_DICT rhel6 "$SINGULARITY_IMAGE_DEFAULT6"`"
    [ -n "$SINGULARITY_IMAGE_DEFAULT7" ] && SINGULARITY_IMAGES_DICT="`set_dict_val SINGULARITY_IMAGES_DICT rhel7 "$SINGULARITY_IMAGE_DEFAULT7"`"
    [ -n "$SINGULARITY_IMAGE_DEFAULT" ] && SINGULARITY_IMAGES_DICT="`set_dict_val SINGULARITY_IMAGES_DICT default "$SINGULARITY_IMAGE_DEFAULT"`"

    singularity_image="`get_dict_val SINGULARITY_IMAGES_DICT "$s_platform"`"

    # At this point, GWMS_SINGULARITY_IMAGE is still empty, something is wrong
    if [ "x$singularity_image" = "x" ]; then
        warn_raw "ERROR: If you get this error when you did not specify a desired platform, your VO does not support any default Singularity image"
        warn_raw "ERROR: If you get this error when you specified desired platform, your VO does not support an image for your desired platform"
        return 1
    fi

    # Check all restrictions (at the moment cvmfs) and return 3 if failing
    if [[ ",${s_restrictions}," = *",cvmfs,"* ]] && ! echo "$singularity_image" | grep ^"/cvmfs" >/dev/null 2>&1; then
        warn "$singularity_image is not in /cvmfs area as requested"
        return 3
    fi

    # whether user-provided or default image, we make sure it exists
    if [ ! -e "$singularity_image" ]; then
        warn_raw "ERROR: $singularity_image file not found" 1>&2
        return 2
    fi

    echo "$singularity_image"
}

function sanitize_singularity_image {
    # for /cvmfs based directory images, expand the path without symlinks so that
    # the job can stay within the same image for the full duration
    # In:
    #  GWMS_SINGULARITY_IMAGE
    # Out:
    #  GWMS_SINGULARITY_IMAGE (modified if needed)
    #  GWMS_SINGULARITY_IMAGE_HUMAN (defined if GWMS_SINGULARITY_IMAGE needed to be changed)
    local new_image_path
    if echo "$GWMS_SINGULARITY_IMAGE" | grep ^"/cvmfs" >/dev/null 2>&1; then
        if (cd "$GWMS_SINGULARITY_IMAGE") >/dev/null 2>&1; then
            new_image_path="`(cd "$GWMS_SINGULARITY_IMAGE" && pwd -P) 2>/dev/null`"
            if [ "x$new_image_path" != "x" ]; then
                GWMS_SINGULARITY_IMAGE_HUMAN="$GWMS_SINGULARITY_IMAGE"
                GWMS_SINGULARITY_IMAGE="$new_image_path"
            fi
        fi
    fi

}


function create_host_lib_dir() {
    # this is a temporary solution until enough sites have newer versions
    # of Singularity. Idea for this solution comes from:
    # https://github.com/singularityware/singularity/blob/master/libexec/cli/action_argparser.sh#L123
    mkdir -p .host-libs
    NVLIBLIST=`mktemp ${TMPDIR:-/tmp}/.nvliblist.XXXXXXXX`
    cat >$NVLIBLIST <<EOF
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
        if [ -f "$TARGET" ]; then
            BASENAME=`basename $TARGET`
            # only keep the first one found
            if [ ! -e ".host-libs/$BASENAME" ]; then
                cp -L $TARGET .host-libs/
            fi
        fi
    done
    rm -f $NVLIBLIST
}


function setup_classad_variables {
    # Retrieve variables from Machine and Job ClassAds
    # Set up environment to know if Singularity is enabled and so we can execute Singularity
    # Out:
    #  export all of HAS_SINGULARITY, GWMS_SINGULARITY_PATH, GWMS_SINGULARITY_VERSION, GWMS_SINGULARITY_IMAGES_DICT,
    #    GLIDEIN_REQUIRED_OS, GLIDEIN_DEBUG_OUTPUT, REQUIRED_OS, GWMS_SINGULARITY_IMAGE, CVMFS_REPOS_LIST,
    #    GLIDEIN_DEBUG_OUTPUT (if not already set)

    if [ -z "$_CONDOR_JOB_AD" ]; then
        export _CONDOR_JOB_AD="NONE"
    fi
    if [ -z "$_CONDOR_MACHINE_AD" ]; then
        export _CONDOR_MACHINE_AD="NONE"
    fi

# TODO: remove this code snippet from setup_singularity.sh
## advertise HAS_SINGULARITY "True" "C"
#advertise SINGULARITY_PATH "$GWMS_SINGULARITY_PATH" "S"
#advertise GWMS_SINGULARITY_PATH "$GWMS_SINGULARITY_PATH" "S"
#advertise SINGULARITY_VERSION "$GWMS_SINGULARITY_VERSION" "S"
#advertise GWMS_SINGULARITY_VERSION "$GWMS_SINGULARITY_VERSION" "S"
## TODO: is GLIDEIN_REQUIRED_OS really "any" ?
#advertise GLIDEIN_REQUIRED_OS "any" "S"
#if [ "x$GLIDEIN_DEBUG_OUTPUT" != "x" ]; then
#    advertise GLIDEIN_DEBUG_OUTPUT "$GLIDEIN_DEBUG_OUTPUT" "S"

    ## from singularity_setup.sh executed earlier (Machine ClassAd)
    export HAS_SINGULARITY=$(get_prop_bool $_CONDOR_MACHINE_AD HAS_SINGULARITY)
    export GWMS_SINGULARITY_PATH=$(get_prop_str $_CONDOR_MACHINE_AD SINGULARITY_PATH)
    export GWMS_SINGULARITY_VERSION=$(get_prop_str $_CONDOR_MACHINE_AD SINGULARITY_VERSION)
    # Removed old GWMS_SINGULARITY_IMAGE_DEFAULT6 GWMS_SINGULARITY_IMAGE_DEFAULT7, now in _DICT
# TODO: send also the image used during test in setup? in case the VO does not care
#    export GWMS_SINGULARITY_IMAGE_DEFAULT=$(get_prop_str $_CONDOR_MACHINE_AD SINGULARITY_IMAGE_DEFAULT)
    export GWMS_SINGULARITY_IMAGES_DICT=$(get_prop_str $_CONDOR_MACHINE_AD SINGULARITY_IMAGES_DICT)
    export GLIDEIN_REQUIRED_OS=$(get_prop_str $_CONDOR_MACHINE_AD GLIDEIN_REQUIRED_OS)
    export GLIDEIN_DEBUG_OUTPUT=$(get_prop_str $_CONDOR_MACHINE_AD GLIDEIN_DEBUG_OUTPUT)

    ## from Job ClassAd
    export REQUIRED_OS=$(get_prop_str $_CONDOR_JOB_AD REQUIRED_OS)
    export GWMS_SINGULARITY_IMAGE=$(get_prop_str $_CONDOR_JOB_AD SingularityImage)
    export CVMFS_REPOS_LIST=$(get_prop_str $_CONDOR_JOB_AD CVMFSReposList)
    if [ "x$GLIDEIN_DEBUG_OUTPUT" = "x" ]; then
        export GLIDEIN_DEBUG_OUTPUT=$(get_prop_str $_CONDOR_JOB_AD GLIDEIN_DEBUG_OUTPUT)
    fi
}


function setup_in_singularity {
    # Setup some environment variables when the script is restarting in Singularity
    # In:
    #   $GWMS_SINGULARITY_OUTSIDE_PWD
    # Out:
    #   Changing env variables (especially TMP and X509 related) to work w/ chrooted FS
    unset TMP
    unset TEMP
    unset X509_CERT_DIR
    local val
    # Adapt for changes in filesystem space
    # TODO: no X509_USER_KEY? Check if it should be here
    for key in X509_USER_PROXY X509_USER_CERT _CONDOR_MACHINE_AD _CONDOR_JOB_AD \
               _CONDOR_SCRATCH_DIR _CONDOR_CHIRP_CONFIG _CONDOR_JOB_IWD ; do
        val="`echo "${!key}" | sed -E "s;$GWMS_SINGULARITY_OUTSIDE_PWD(.*);/srv\1;"`"
        eval $key="$val"
        info_dbg "changed $key => $val"
    done

    # If X509_USER_PROXY and friends are not set by the job, we might see the
    # glidein one - in that case, just unset the env var
    for key in X509_USER_PROXY X509_USER_CERT X509_USER_KEY ; do
        val="${!key}"
        if [ -n "$val" ]; then
            if [ ! -e "$val" ]; then
                eval unset $key >/dev/null 2>&1 || true
                info_dbg "unset $key. File not found."
            fi
        fi
    done

    # Override some OSG specific variables
    [ -n "$OSG_WN_TMP" ] && export OSG_WN_TMP=/tmp

    # Some java programs have seen problems with the timezone in our containers.
    # If not already set, provide a default TZ
    [ -z "$TZ" = "x" ] && export TZ="UTC"
}


function cvmfs_test_and_open {
    # Testing and opeining all CVMFS repos named in the comma separated list
    # In:
    #  1 - CVMFS repos names, comma separated
    #  2 - callback for failure (must me a single command or function name), exit 1 if none is provided or callback returns false
    info_dbg "Testing CVMFS Repos List = $1"
    holdfd=3
    local IFS=,  # "\t\t\""
    if [ -n "$1" ]; then
        # Test and keep open each CVMFS repo
        for x in "$1"; do
            if eval "exec $holdfd</cvmfs/\"$x\""; then
                echo "\"/cvmfs/$x\" exists and available"
                let "holdfd=holdfd+1"
            else
                echo "\"/cvmfs/$x\" NOT available"
                # [ -n "$2" ] && { $2 } || { echo 1; }
                [ -n "$2" ] && $2 || exit 1
            fi
        done
    fi
}





####main#####


if [ "$glidein_config" != "NONE" ] && [ "x$SOURCED_ADD_CONFIG_LINE" = "x" ]; then
    # import advertise and add_condor_vars_line functions
    if [ "x$add_config_line_source" = "x" ]; then
        export add_config_line_source=`grep '^ADD_CONFIG_LINE_SOURCE ' $glidein_config | awk '{print $2}'`
        export       condor_vars_file=`grep -i "^CONDOR_VARS_FILE "    $glidein_config | awk '{print $2}'`
    fi

    info "Sourcing $add_config_line_source"
    source $add_config_line_source
    # make sure we don't source a second time inside the container
    export SOURCED_ADD_CONFIG_LINE=1
fi


###########################################################
# check attributes from Frontend Group and Factory Entry set by admins

export GLIDEIN_DEBUG_OUTPUT=`grep '^GLIDEIN_DEBUG_OUTPUT ' $glidein_config | awk '{print $2}'`

#some hackery to deal with spaces in SINGULARITY_BIN
temp_singularity_bin=`grep '^SINGULARITY_BIN ' $glidein_config | awk '{$1=""; print $0}'`
singularity_bin=$(echo $temp_singularity_bin)
if [ -z "$singularity_bin" ]; then
    singularity_bin="NONE"
fi


# default image for this glidein
# if we take action here about the absence of SINGULARITY_IMAGE_DEFAULT
# this would remove the change of user-provides singularity image being used
# But some users might rely on the assumption that the Frontend VO would have default singularity images
# Thus, we enforce the use of vo_pre_singularity_setup.sh.
# Also more importantly, this script itself needs a default image in order to conduct a validation test below!
# we provide {cms,osg}_pre_singularity_setup.sh and generic_pre_singularity_setup.sh for a generic use
# So, if a VO wants to have their own _new_pre_singularity_setup.sh, they must copy and modify
# generic_pre_singularity_setup.sh and also must put their default singularity images 
# under /cvmfs/singularity.opensciencegrid.org
export GWMS_SINGULARITY_IMAGE_DEFAULT6=`grep '^SINGULARITY_IMAGE_DEFAULT6 ' $glidein_config | awk '{print $2}'`
export GWMS_SINGULARITY_IMAGE_DEFAULT7=`grep '^SINGULARITY_IMAGE_DEFAULT7 ' $glidein_config | awk '{print $2}'`
export GWMS_SINGULARITY_IMAGE_DEFAULT=''

# Look for singularity images and adapt if no valid one is found
if [ "x$GWMS_SINGULARITY_IMAGE_DEFAULT6" != "x" ] && [ "x$GWMS_SINGULARITY_IMAGE_DEFAULT7" = "x" ]; then
    GWMS_SINGULARITY_IMAGE_DEFAULT=$GWMS_SINGULARITY_IMAGE_DEFAULT6
elif [ "x$GWMS_SINGULARITY_IMAGE_DEFAULT6" = "x" ] && [ "x$GWMS_SINGULARITY_IMAGE_DEFAULT7" != "x" ]; then
    GWMS_SINGULARITY_IMAGE_DEFAULT=$GWMS_SINGULARITY_IMAGE_DEFAULT7
elif [ "x$GWMS_SINGULARITY_IMAGE_DEFAULT6" != "x" ] && [ "x$GWMS_SINGULARITY_IMAGE_DEFAULT7" != "x" ]; then
    GWMS_SINGULARITY_IMAGE_DEFAULT=$GWMS_SINGULARITY_IMAGE_DEFAULT7
elif [ "x$GWMS_SINGULARITY_IMAGE_DEFAULT6" = "x" ] && [  "x$GWMS_SINGULARITY_IMAGE_DEFAULT7" = "x" ]; then
    HAS_SINGULARITY="False"
    if [ "$use_singularity" = "REQUIRED" ] || [ "$require_singularity" = "True" ] ; then
        STR="SINGULARITY_IMAGE_DEFAULT was not set by vo_pre_singularity_setup.sh"
        "$error_gen" -error "singularity_setup.sh"  "WN_Resource" "$STR"
        exit 1
    elif [ "$use_singularity" = "OPTIONAL" ]; then
        warn "SINGULARITY_IMAGE_DEFAULT was not set by vo_pre_singularity_setup.sh"
        no_use_singularity_config
    fi
fi

export GWMS_SINGULARITY_IMAGE_DEFAULT
# for now, we will only advertise singularity on nodes which can access cvmfs
if [ ! -e "$GWMS_SINGULARITY_IMAGE_DEFAULT" ]; then
    HAS_SINGULARITY="False"
    if [ "$use_singularity" = "REQUIRED" ] || [ "$require_singularity" = "True" ] ; then
        STR="Default singularity image, $GWMS_SINGULARITY_IMAGE_DEFAULT, does not appear to exist"
        "$error_gen" -error "singularity_setup.sh"  "WN_Resource" "$STR"
        exit 1
    elif [ "$use_singularity" = "OPTIONAL" ]; then
        warn "$GWMS_SINGULARITY_IMAGE_DEFAULT does not exist."
        no_use_singularity_config
    fi
fi

# Look for binary and adapt if missing
locate_singularity "$singularity_bin"

if [ "x$HAS_SINGULARITY" = "xTrue" ]; then
    info "Singularity binary appears present and claims to be version $GWMS_SINGULARITY_VERSION"
else
    # Adapt to missing binary
    if [ "$use_singularity" = "REQUIRED" ] || [ "$require_singularity" = "True" ] ; then
        STR="Unable to find singularity in PATH=$PATH"
        "$error_gen" -error "singularity_setup.sh" "WN_Resource" "$STR"
        exit 1
    elif [ "$use_singularity" = "OPTIONAL" ]; then
        warn "Singularity binary does not exist."
        no_use_singularity_config
    fi
fi

# Test execution and adapt if failed
if [ "x$HAS_SINGULARITY" = "xTrue" ]; then
    if ! test_singularity_exec ; then
        HAS_SINGULARITY="False"
        if [ "$use_singularity" = "REQUIRED" ] || [ "$require_singularity" = "True" ] ; then
            STR="Simple singularity exec inside $GWMS_SINGULARITY_IMAGE_DEFAULT failed."
            "$error_gen" -error "singularity_setup.sh"  "WN_Resource" "$STR"
            exit 1
        elif [ "$use_singularity" = "OPTIONAL" ]; then
            warn "Simple singularity exec inside $GWMS_SINGULARITY_IMAGE_DEFAULT failed."
            no_use_singularity_config
        fi
    fi
fi

advertise HAS_SINGULARITY "True" "C"
advertise SINGULARITY_PATH "$GWMS_SINGULARITY_PATH" "S"
advertise GWMS_SINGULARITY_PATH "$GWMS_SINGULARITY_PATH" "S"
advertise SINGULARITY_VERSION "$GWMS_SINGULARITY_VERSION" "S"
advertise GWMS_SINGULARITY_VERSION "$GWMS_SINGULARITY_VERSION" "S"
advertise GLIDEIN_REQUIRED_OS "any" "S"
if [ "x$GLIDEIN_DEBUG_OUTPUT" != "x" ]; then
    advertise GLIDEIN_DEBUG_OUTPUT "$GLIDEIN_DEBUG_OUTPUT" "S"
fi
info "All done - time to do some real work!"

"$error_gen" -ok "singularity_setup.sh"  "use_singularity" "True"
exit 0

