#!/bin/bash
#
# This script advertises:
# HAS_SINGULARITY
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

error_gen=$(grep '^ERROR_GEN_PATH ' "$glidein_config" | awk '{print $2}')

function info {
    echo "INFO " $@  1>&2
}

GLIDEIN_THIS_SCRIPT=$0
function info_dbg {
    if [ "x$GLIDEIN_DEBUG_OUTPUT" != "x" ]; then
        info "DEBUG: file:"$GLIDEIN_THIS_SCRIPT $@
    fi
}


function warn {
    echo "WARN " $@  1>&2
}

function advertise {
    # atype is the type of the value as defined by GlideinWMS:
    #   I - integer
    #   S - quoted string
    #   C - unquoted string (i.e. Condor keyword or expression)
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

function no_use_singularity_config {

    info "Not using singularity" 1>&2
    advertise HAS_SINGULARITY "False" "C"
    "$error_gen" -ok "singularity_setup.sh" "use_singularity" "False"
    exit 0

}

function test_singularity_exec {

   #image="$GWMS_SINGULARITY_IMAGE_DEFAULT"
   info_dbg "$GWMS_SINGULARITY_PATH exec --home $PWD:/srv --bind /cvmfs \
             --pwd /srv --scratch /var/tmp --scratch /tmp \
             --contain --ipc --pid $image \
             echo Hello World | grep Hello World"

   if ("$GWMS_SINGULARITY_PATH" exec --home $PWD:/srv \
                                         --bind /cvmfs \
                                         --pwd /srv \
                                         --scratch /var/tmp \
                                         --scratch /tmp \
                                         --contain --ipc --pid \
                                         "$GWMS_SINGULARITY_IMAGE_DEFAULT" \
                                         printenv \
                                         | grep "$GWMS_SINGULARITY_PATH" 1>&2)  
   then
       info "Singularity at $GWMS_SINGULARITY_PATH appears to work"
       true
   else
       info "Singularity at $GWMS_SINGULARITY_PATH failed "
       false
   fi
}


function locate_singularity {
    info "Checking for singularity..."
    #GWMS Entry must use SINGULARITY_BIN to specify the pathname of the singularity binary
    #GWMS, we quote $singularity_bin to deal with white spaces in the path
    LOCATION=$1
    if [  -d "$LOCATION" ] && [ -x "$LOCATION/singularity" ]; then
        PATH="$LOCATION:$PATH"
    else
        warn "SINGULARITY_BIN = $1  in factory xml configuration is not a directory or does not contain singularity!"
        warn "will try to proceed with default value '/usr/bin' but this misconfiguration may cause errors later!"
    fi

    HAS_SINGULARITY="False"
    GWMS_SINGULARITY_VERSION=$("$LOCATION"/singularity --version 2>/dev/null)
    if [ "x$GWMS_SINGULARITY_VERSION" != "x" ]; then
        HAS_SINGULARITY="True"
        export GWMS_SINGULARITY_PATH="$LOCATION/singularity"
    else
        # some sites requires us to do a module load first - not sure if we always want to do that
        PATH="$LOCATION:$PATH"
        GWMS_SINGULARITY_VERSION=`module load singularity >/dev/null 2>&1; singularity --version 2>/dev/null`
        if [ "x$GWMS_SINGULARITY_VERSION" != "x" ]; then
            HAS_SINGULARITY="True"
            GWMS_SINGULARITY_PATH=`module load singularity >/dev/null 2>&1; which singularity`
        fi
    fi
    if [ "$HAS_SINGULARITY" = "True" ] && test_singularity_exec; then
        info " ... prepending $LOCATION to PATH"
        export PATH=$LOCATION:$PATH
        export HAS_SINGULARITY=$HAS_SINGULARITY
        export GWMS_SINGULARITY_PATH="$LOCATION/singularity"
        export GWMS_SINGULARITY_VERSION=$GWMS_SINGULARITY_VERSION
        true
     else
        export HAS_SINGULARITY=$HAS_SINGULARITY
        export GWMS_SINGULARITY_PATH=""
        export GWMS_SINGULARITY_VERSION=""
        warn "Singularity not found at $LOCATION"
        false
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

# Does frontend want to use singularity?
use_singularity=`grep '^GLIDEIN_Singularity_Use ' $glidein_config | awk '{print $2}'`
if [ -z "$use_singularity" ]; then
    echo "`date` GLIDEIN_Singularity_Use not configured. Defaulting it to DISABLE_GWMS"
    # GWMS, when Group does not specify GLIDEIN_Singularity_Use, it should default to DISABLE_GWMS (2018-03-19 discussion)
    use_singularity="DISABLE_GWMS"
fi

# Does entry require glidein to use singularity?
require_singularity=`grep '^GLIDEIN_SINGULARITY_REQUIRE ' $glidein_config | awk '{print $2}'`
if [ -z "$require_singularity" ]; then
    echo "`date` GLIDEIN_SINGULARITY_REQUIRE not configured. Defaulting it to False"
    require_singularity="False"
fi

echo "`date` Factory requires glidein to use singularity: $require_singularity"
echo "`date` VO's desire to use singularity:              $use_singularity"
echo "`date` Entry configured with singularity:           $singularity_bin"

case "$use_singularity" in
    DISABLE_GWMS)
        "$error_gen" -ok "singularity_setup.sh"  "use_singularity" "Undefined"
        exit 0
        ;;
    NEVER)
        echo "`date` VO does not want to use singularity"
        if [ "$require_singularity" = "True" ]; then
            STR="Factory requires glidein to use singularity."
            "$error_gen" -error "singularity_setup.sh" "VO_Config" "$STR" "attribute" "GLIDEIN_Singularity_Use"
            exit 1
        fi
        # If Group mistakenly use default_singularity_wrapper.sh with GLIDEIN_Glexec_Use=NEVER
        # we need to set    advertise HAS_SINGULARITY "False" "C"
        no_use_singularity_config
        ;;
    OPTIONAL) #GWMS Even in OPTIONAL case, FE will have to specify the wrapper script
        if [ "$require_singularity" = "True" ]; then
            if [ "$singularity_bin" = "NONE" ]; then
               STR="Factory requires glidein to use singularity but singularity_bin is NONE."
               "$error_gen" -error "singularity_setup.sh" "VO_Config" "$STR" "attribute" "SINGULARITY_BIN" "attribute" "GLIDEIN_Singularity_Use"
                exit 1
            fi
        else
            if [ "$singularity_bin" = "NONE" ]; then
                echo "`date` VO has set the use singularity to OPTIONAL but site is not configured with singularity"
                no_use_singularity_config
            fi
        fi
        # OK to continue w/ Singularity
        ;;
    REQUIRED)
        if [ "$singularity_bin" = "NONE" ]; then
            STR="VO mandates the use of singularity but the site is not configured with singularity information"
            "$error_gen" -error "singularity_setup.sh" "VO_Config" "$STR" "attribute" "SINGULARITY_BIN" "attribute" "GLIDEIN_Singularity_Use"
            exit 1
        fi
        # OK to continue w/ Singularity
        ;;
    *)
        STR="GLIDEIN_Singularity_Use in VO Frontend configured to be $use_singularity.\nAccepted values are 'NEVER' or 'OPTIONAL' or 'REQUIRED'."
        STR1=`echo -e "$STR"`
        "$error_gen" -error "singularity_setup.sh" "VO_Config" "$STR1" "attribute" "GLIDEIN_Singularity_Use"
        exit 1
        ;;
    esac


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
if ! locate_singularity $singularity_bin ; then
   locate_singularity '/usr/bin'
fi

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

