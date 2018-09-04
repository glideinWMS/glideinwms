#!/bin/bash
#
# This script tests for singularity variables (bin, image, ...) and does a test run of Singularity
# It is not re-invoking itself (it is running all in the glidein environment, not in Singularity)
# This script advertises:
# HAS_SINGULARITY
# GWMS_SINGULARITY_STATUS
# SINGULARITY_PATH
# GWMS_SINGULARITY_PATH
# SINGULARITY_VERSION
# GWMS_SINGULARITY_VERSION
# GLIDEIN_REQUIRED_OS
# GLIDEIN_DEBUG_OUTPUT
#
# Note that HTCondor has these native attribute names:
# HasSingularity
# SingularityVersion
# Using the above names would interfere and modify HTCondor behavior
# NOTE: HAS_SINGULARITY and HasSingularity are different because of '_'


glidein_config="$1"

GWMS_THIS_SCRIPT="$0"
GWMS_THIS_SCRIPT_DIR="`dirname "$0"`"

echo "`date` Starting singularity_setup.sh. Importing singularity_util.sh."

# defined in singularity_lib.sh
[ -e "$glidein_config" ] && error_gen=$(grep '^ERROR_GEN_PATH ' "$glidein_config" | awk '{print $2}')

# Source utility files, outside and inside Singularity
if [ -e "$GWMS_THIS_SCRIPT_DIR"/singularity_lib.sh ]; then
    source "$GWMS_THIS_SCRIPT_DIR"/singularity_lib.sh
else
    echo "ERROR: singularity_setup.sh: Unable to source '$GWMS_THIS_SCRIPT_DIR/singularity_lib.sh'! File not found. Quitting" 1>&2
    [ -n "$error_gen" ] && "$error_gen" -error "singularity_setup.sh"
    exit 1
fi


function no_use_singularity_config {
    info_stdout "`date` Not using singularity ($gwms_singularity_status)"
    advertise HAS_SINGULARITY "False" "C"
    "$error_gen" -ok "singularity_setup.sh" "use_singularity" "False"
    exit 0
}

function no_singularity_fail_or_exit {
    # No singularity, fail if required, exit 0 after advertising if not
    # In
    #  1: gwms_singularity_status
    #  2: output message
    #  3: variable (default: WN_Resource)
    local var_name="${3:-WN_Resource}"
    if [ "$1" = "REQUIRED" ]; then
        info_stdout "`date` Incompatible Singularity requirements ($2). Failing Glidein"
        "$error_gen" -error "singularity_setup.sh" "$var_name" "$2"
        exit 1
    elif [ "$1" = "PREFERRED" ]; then
        warn "$2"
        no_use_singularity_config
    else
        warn "Unexpected gwms_singularity_status $1 in fail_or_exit (no REQUIRED or PREFERRED)"
    fi
}

function combine_requirements {
    # Combine the requirements of Frontend and Factory
    # Return 0 if it can run, 1 if glidein should fail
    # Echo a value for the level  OR has_singularity decision
    # In
    #  1 - Frontend preference GLIDEIN_Singularity_Use (DISABLE_GWMS, NEVER, OPTIONAL, PREFERRED, REQUIRED)
    #  2 - Factory preference GLIDEIN_SINGULARITY_REQUIRE (NEVER, OPTIONAL, PREFERRED, REQUIRED, REQUIRED_GWMS)
    # Out
    #  stdout: VALUE,Explanation
    #   VALUE is one of:
    #    FAIL (inconsistent requirements, fail glidein), DISABLE (do not interfere), NEVER (do not use Singularity),
    #    PREFERRED (use Singularity only if available), REQUIRED (use Singularity or fail)
    #   Explanation is an optional string following the comma
    local req_frontend=$1
    local req_factory=$2
    local res_str

    local valid_list="NEVER,OPTIONAL,PREFERRED,REQUIRED,"
    if [ ",$valid_list,REQUIRED_GWMS," = *",$req_factory,"* ]; then
        STR="GLIDEIN_SINGULARITY_REQUIRE in Factory configured to be $req_factory.\nAccepted values are $valid_list,REQUIRED_GWMS."
        res_str=`echo -e "$STR"`
        echo "FAIL,$res_str"
        return 1
    fi
    if [ ",$valid_list,DISABLE_GWMS," = *",$req_frontend,"* ]; then
        STR="GLIDEIN_Singularity_Use in VO Frontend configured to be $req_frontend.\nAccepted values are $valid_list,DISABLE_GWMS."
        res_str=`echo -e "$STR"`
        echo "FAIL,$res_str"
        return 1
    fi
    local res=FAIL
    case "$req_frontend" in
        DISABLE_GWMS)
            if [ "$req_factory" = REQUIRED_GWMS ]; then
                res_str="Factory requires glidein to enforce Singularity. Disabling not accepted"
                echo "FAIL,$res_str"
                return 1
            fi
            res=DISABLE
            ;;
        NEVER)
            #echo "`date` VO does not want to use singularity"
            if [ "$req_factory" = REQUIRED ] || [ "$req_factory" = REQUIRED_GWMS ]; then
                res_str="Factory requires glidein to use Singularity. VO is against."
                echo "FAIL,$res_str"
                return 1
            fi
            # If Group mistakenly use default_singularity_wrapper.sh with GLIDEIN_Singularity_Use=NEVER
            # we need to set    advertise HAS_SINGULARITY "False" "C"
            res=NEVER
            ;;
        OPTIONAL)  #GWMS Even in OPTIONAL/PREFERRED case, FE will have to specify the wrapper script
            if [ "$req_factory" = NEVER ] || [ "$req_factory" = OPTIONAL ]; then
                res_str="`date` VO and Site prefer no Singularity (OPTIONAL/NEVER)"
                res=NEVER
            elif [ "$req_factory" = REQUIRED ] || [ "$req_factory" = REQUIRED_GWMS ]; then
                res_str="Factory requires glidein to use Singularity."
                res=REQUIRED
            else
                # Factory is PREFERRED
                res=PREFERRED
            fi
            ;;
        PREFERRED)  #GWMS Even in OPTIONAL/PREFERRED case, FE will have to specify the wrapper script
            if [ "$req_factory" = REQUIRED ] || [ "$req_factory" = REQUIRED_GWMS ]; then
                res_str="Factory requires glidein to use Singularity."
                res=REQUIRED
            elif [ "$req_factory" = NEVER ]; then
                res_str="`date` VO has set the use singularity to OPTIONAL but site is not configured with singularity"
                res=NEVER
            else
                res=PREFERRED
            fi
            ;;
        REQUIRED)
            if [ "$req_factory" = NEVER ]; then
                res_str="VO mandates the use of Singularity Site requires not to use it"
                #"$error_gen" -error "singularity_setup.sh" "VO_Config" "$STR" "attribute" "SINGULARITY_BIN" "attribute" "GLIDEIN_Singularity_Use"
                echo "FAIL,$res_str"
                return 1
            fi
            res_str="VO mandates the use of Singularity."
            res=REQUIRED
            ;;
    esac
    # Return RESULT value and explanation
    echo "$res,$res_str"
    return 0
}


####main#####


###########################################################
# check attributes from Frontend Group and Factory Entry set by admins

export GLIDEIN_DEBUG_OUTPUT=`grep '^GLIDEIN_DEBUG_OUTPUT ' $glidein_config | awk '{print $2}'`

# SINGULARITY_BIN is now undocumented (can still be used for compatibility or to force a path for Singularity)
# TODO: future review use of SINGULARITY_BIN, remove to end legacy support
# some hackery to deal with spaces in SINGULARITY_BIN
temp_singularity_bin="`grep '^SINGULARITY_BIN ' $glidein_config | awk '{$1=""; print $0}'`"
singularity_bin="$(echo $temp_singularity_bin)"

# only to suggest a path, but path is used otherwise
#if [ -z "$singularity_bin" ]; then
#    singularity_bin="NONE"
#fi

# Does frontend want to use singularity?
use_singularity=`grep '^GLIDEIN_Singularity_Use ' $glidein_config | awk '{print $2}'`
if [ -z "$use_singularity" ]; then
    info_stdout "`date` GLIDEIN_Singularity_Use not configured. Defaulting to DISABLE_GWMS"
    # GWMS, when Group does not specify GLIDEIN_Singularity_Use, it should default to DISABLE_GWMS (2018-03-19 discussion)
    use_singularity="DISABLE_GWMS"
fi

# Does entry require glidein to use singularity?
require_singularity=`grep '^GLIDEIN_SINGULARITY_REQUIRE ' $glidein_config | awk '{print $2}'`
if [ -z "$require_singularity" ]; then
    info_stdout "`date` GLIDEIN_SINGULARITY_REQUIRE not configured. Defaulting to OPTIONAL"
    require_singularity="OPTIONAL"
fi

info_stdout "`date` Factory's desire to use Singularity: $require_singularity"
info_stdout "`date` VO's desire to use Singularity:      $use_singularity"
info_stdout "`date` Entry configured with Singularity:   $singularity_bin"

gwms_singularity="`combine_requirements $use_singularity $require_singularity`"
gwms_singularity_ec=$?
gwms_singularity_status="${gwms_singularity%%,*}"
gwms_singularity_str="${gwms_singularity#*,}"
info_dbg "Combining VO ($use_singularity) and entry ($require_singularity/$singularity_bin): $gwms_singularity_ec, $gwms_singularity_status, $gwms_singularity_str"
if [ $gwms_singularity_ec -ne 0 ] && [ "${gwms_singularity_status}" != FAIL ]; then
    gwms_singularity_str="Detected inconsistent ec=1/status ${gwms_singularity_status} (${gwms_singularity_str}). Forcing failure."
    gwms_singularity_status=FAIL
fi

case "${gwms_singularity_status}" in
    FAIL)
        "$error_gen" -error "singularity_setup.sh" "VO_Config" "${gwms_singularity_str}" "attribute" "GLIDEIN_Singularity_Use"
        exit 1
        ;;
    DISABLE)
        "$error_gen" -ok "singularity_setup.sh"  "use_singularity" "Undefined"
        exit 0
        ;;
    NEVER)
        # If Group use default_singularity_wrapper.sh with GLIDEIN_Glexec_Use and GLIDEIN_SINGULARITY_REQUIRE
        # resulting in NEVER, we need to set    advertise HAS_SINGULARITY "False" "C"
        no_use_singularity_config
        ;;
    PREFERRED|REQUIRED)  #GWMS Even in OPTIONAL case, FE will have to specify the wrapper script
        # OK to continue w/ Singularity
        ;;
esac

# Using Singularity. After this point $gwms_singularity_status is PREFERRED|REQUIRED, all other would have exit

# default image for this glidein
# if we take action here about the absence of SINGULARITY_IMAGE_DEFAULT
# this would remove the change of user-provides singularity image being used
# But some users might rely on the assumption that the Frontend VO would have default singularity images
# Thus, we enforce the use of vo_pre_singularity_setup.sh or attributes.
# Also more importantly, this script itself needs a default image in order to conduct a validation test below!
# we provide generic_pre_singularity_setup.sh for a generic use
# So, if a VO wants to have their own _new_pre_singularity_setup.sh, they must copy and modify
# generic_pre_singularity_setup.sh and also must put their default singularity images 
# under /cvmfs/singularity.opensciencegrid.org
SINGULARITY_IMAGES_DICT="`grep '^SINGULARITY_IMAGES_DICT ' $glidein_config | awk '{print $2}'`"
SINGULARITY_IMAGE_DEFAULT6="`grep '^SINGULARITY_IMAGE_DEFAULT6 ' $glidein_config | awk '{print $2}'`"
SINGULARITY_IMAGE_DEFAULT7="`grep '^SINGULARITY_IMAGE_DEFAULT7 ' $glidein_config | awk '{print $2}'`"
SINGULARITY_IMAGE_DEFAULT="`grep '^SINGULARITY_IMAGE_DEFAULT ' $glidein_config | awk '{print $2}'`"

# Select the singularity image:  singularity_get_image platforms restrictions
# Uses SINGULARITY_IMAGES_DICT and legacy SINGULARITY_IMAGE_DEFAULT, SINGULARITY_IMAGE_DEFAULT6, SINGULARITY_IMAGE_DEFAULT7
# TODO Should the image be on CVMFS or anywhere is OK?
info_stdout "`date` Looking for Singularity image for [default,rhel7,rhel6] located on CVMFS"
GWMS_SINGULARITY_IMAGE="`singularity_get_image default,rhel7,rhel6 cvmfs`"
ec=$?
if [ $ec -ne 0 ]; then
    out_str="ERROR selecting a Singularity image ($ec, $GWMS_SINGULARITY_IMAGE)"
    if [ $ec -eq 1 ]; then
        out_str="Singularity image for the default platforms (default,rhel7,rhel6) was not set (via attributes or vo_pre_singularity_setup.sh)"
    elif [ $ec -eq 2 ]; then
        out_str="Selected singularity image, $GWMS_SINGULARITY_IMAGE, does not exist"
    elif [ $ec -eq 3 ]; then
        out_str="Selected singularity image, $GWMS_SINGULARITY_IMAGE, is not in CVMFS as requested"
    fi
    no_singularity_fail_or_exit $gwms_singularity_status "$out_str"
fi

# Using Singularity and valid image found
export GWMS_SINGULARITY_IMAGE

info_stdout "`date` Searching and testing the singularity binary"

# Look for binary and adapt if missing
# Changes PATH (Singularity path may be added), GWMS_SINGULARITY_VERSION, GWMS_SINGULARITY_PATH, HAS_SINGULARITY, singularity_in
singularity_locate_bin "$singularity_bin"

if [ "x$HAS_SINGULARITY" = "xTrue" ]; then
    info "Singularity binary appears present and claims to be version $GWMS_SINGULARITY_VERSION"
else
    # Adapt to missing binary
    no_singularity_fail_or_exit $gwms_singularity_status "Unable to find singularity in PATH=$PATH"
fi

# Valid singularity binary found, "$HAS_SINGULARITY" = True (otherwise would have exited)
# Test execution and adapt if failed
if ! singularity_test_exec "$GWMS_SINGULARITY_IMAGE" "$GWMS_SINGULARITY_PATH" ; then
    # HAS_SINGULARITY="False"
    no_singularity_fail_or_exit $gwms_singularity_status "Simple singularity exec inside $GWMS_SINGULARITY_IMAGE failed."
fi

# All tests passed, Singularity works w/ the default image
advertise HAS_SINGULARITY "True" "C"
advertise GWMS_SINGULARITY_STATUS "$gwms_singularity_status" "S"
advertise SINGULARITY_PATH "$GWMS_SINGULARITY_PATH" "S"
advertise GWMS_SINGULARITY_PATH "$GWMS_SINGULARITY_PATH" "S"
advertise SINGULARITY_VERSION "$GWMS_SINGULARITY_VERSION" "S"
advertise GWMS_SINGULARITY_VERSION "$GWMS_SINGULARITY_VERSION" "S"
# The dict has changed after singularity_get_image to include values from legacy variables
advertise SINGULARITY_IMAGES_DICT "$SINGULARITY_IMAGES_DICT" "S"
# TODO: advertise also GWMS_SINGULARITY_IMAGE ?
# TODO: is GLIDEIN_REQUIRED_OS "any" published here, will it not override config setting?
advertise GLIDEIN_REQUIRED_OS "any" "S"
if [ "x$GLIDEIN_DEBUG_OUTPUT" != "x" ]; then
    advertise GLIDEIN_DEBUG_OUTPUT "$GLIDEIN_DEBUG_OUTPUT" "S"
fi
info_stdout "`date` Decided to use Singularity ($gwms_singularity_status)"

"$error_gen" -ok "singularity_setup.sh"  "use_singularity" "True"
exit 0

