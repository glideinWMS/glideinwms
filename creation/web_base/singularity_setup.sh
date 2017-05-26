#!/bin/bash

#
# Project:
#   glideinWMS
#
# File Version:
#
# Description:
#   This script will setup the htcondor parameters that enable the Singularity
#messi
SINGULARITY
singularity
# Configuration in case GLEXEC should not be used
function no_use_singularity_config {
    echo "Not using singularity" 1>&2
    add_config_line "SINGULARITY_IMAGE_EXPR" "False"
    add_config_line "SINGULARITY_JOB" "False"
    add_condor_vars_line "SINGULARITYIMAGE_EXPR" "C" "False" "+" "Y" "Y" "-"
    add_condor_vars_line "SINGULARITY_JOB"       "C" "False" "+" "Y" "Y" "-"

    "$error_gen" -ok "singularity_setup.sh" "use_singularity" "False"
    exit 0
}

function test_singularity {
  tst=`"$glexec_bin"  "$ALTSH" -c "id && echo \"Hello World\"" 2>glexec_test.err`
  res=$?
  if [ $res -ne 0 ]; then
    #echo "glexec test failed, nonzero value $res" 1>&2
    #echo "result: $tst" 1>&2
    STR="glexec test failed, nonzero value $res
result:
$tst
stderr:
`cat glexec_test.err`"
    "$error_gen" -error "glexec_setup.sh" "WN_Resource" "$STR" "command" "$glexec_bin"
    exit 1
  else
    tst2=`echo "$tst" |tail -1`
    if [ "$tst2" == "Hello World" ]; then
      echo "glexec verified to work" 1>&2
    else
      #echo "glexec broken!" 1>&2
      #echo "Expected 'Hello World', got '$tst2'" 1>&2
      STR="glexec broken\n"
      STR+="Expected 'Hello World', got '$tst2'"
      STR1=`echo -e "$STR"`
      "$error_gen" -error "glexec_setup.sh" "WN_Resource" "$STR1" "command" "$glexec_bin"
      exit 1
    fi
  fi
}

glidein_config=$1
tmp_fname=${glidein_config}.$$.tmp

error_gen=`grep '^ERROR_GEN_PATH ' $glidein_config | awk '{print $2}'`

condor_vars_file=`grep -i "^CONDOR_VARS_FILE " $glidein_config | awk '{print $2}'`

# import add_config_line and add_condor_vars_line functions
add_config_line_source=`grep '^ADD_CONFIG_LINE_SOURCE ' $glidein_config | awk '{print $2}'`
source $add_config_line_source

# Is site configured with glexec?
singularity_bin=`grep '^SINGULARITY_BIN ' $glidein_config | awk '{print $2}'`
if [ -z "$singularity_bin" ]; then
    singularity_bin="NONE"
fi

# Does frontend wants to use singularity?
use_singularity=`grep '^GLIDEIN_Singularity_Use ' $glidein_config | awk '{print $2}'`
if [ -z "$use_singularity" ]; then
    # Default to optional usage
    echo "`date` GLIDEIN_Singularity_Use not configured. Defaulting it to OPTIONAL"
    use_singularity="OPTIONAL"
fi

# Does entry require glidein to use singularity?
require_singularity_use=`grep '^GLIDEIN_REQUIRE_SINGULARITY_USE ' $glidein_config | awk '{print $2}'`
if [ -z "$require_singularity_use" ]; then
    # Default is False
    echo "`date` GLIDEIN_Require_Singularity_Use not configured. Defaulting it to False"
    require_singularity_use="False"
fi

echo "`date` Factory requires glidein to use singularity: $require_singularity_use"
echo "`date` VO's desire to use glexec: $use_singularity"
echo "`date` Entry configured with singularity: $singularity_bin"

case "$use_singularity" in
    NEVER)
        echo "`date` VO does not want to use singularity"
        if [ "$require_singularity_use" == "True" ]; then
            #echo "`date` Factory requires glidein to use glexec. Exiting."
	    STR="Factory requires glidein to use singularity."
	    "$error_gen" -error "singularity_setup.sh" "VO_Config" "$STR" "attribute" "GLIDEIN_Singularity_Use"
            exit 1
        fi
        no_use_singularity_config
        ;;
    OPTIONAL)
        if [ "$require_singularity_use" == "True" ]; then
            if [ "$singularity_bin" == "NONE" ]; then
                #echo "`date` Factory requires glidein to use glexec but glexec_bin is NONE. Exiting."
		STR="Factory requires glidein to use singularity but singularity_bin is NONE."
		"$error_gen" -error "singularity_setup.sh" "VO_Config" "$STR" "attribute" "SINGULARITY_BIN" "attribute" "GLIDEIN_Singularity_Use"
                exit 1
            fi
        else
            if [ "$SINGULARITY_bin" == "NONE" ]; then
                echo "`date` VO has set the use singularity to OPTIONAL but site is not configured with singularity"
                no_use_singularity_config
            fi
        fi
        # Default to secure mode using glexec
        ;;
    REQUIRED)
        if [ "$singularity_bin" == "NONE" ]; then
            #echo "`date` VO mandates the use of glexec but the site is not configured with glexec information."
            STR="VO mandates the use of singularity but the site is not configured with singularity information"
            "$error_gen" -error "singularity_setup.sh" "VO_Config" "$STR" "attribute" "SINGULARITY_BIN" "attribute" "GLIDEIN_Singularity_Use"
            exit 1
        fi
        ;;
    *)
        #echo "`date` USE_GLEXEC in VO Frontend configured to be $use_glexec. Accepted values are 'NEVER' or 'OPTIONAL' or 'REQUIRED'."
        STR="USE_SINGULARITY in VO Frontend configured to be $use_singularity.\nAccepted values are 'NEVER' or 'OPTIONAL' or 'REQUIRED'."
	STR1=`echo -e "$STR"`
        "$error_gen" -error "singularity_setup.sh" "VO_Config" "$STR1" "attribute" "GLIDEIN_Singularity_Use"
        exit 1
        ;;
esac

echo "`date` making configuration changes to use singularity"

# --------------------------------------------------
singularity_target_dir=`grep '^SINGULARITY_TARGET_DIR' $glidein_config | awk '{print $2}'`
if [ -z "$singularity_target_dir" ]; then
    STR="TARGET_DIR not found!"
    "$error_gen" -error "singularity_setup.sh" "WN_Resource" "$STR" "environment" "TARGET_DIR"
    exit 1
fi
add_config_line "SINGULARITY_TARGET_DIR" "$singularity_target_dir"
add_condor_vars_line "SINGULARITY_TARGET_DIR" "C" "-" "+" "Y" "N" "-"


# --------------------------------------------------
#
# Tell Condor to actually use gLExec
#
if [ "$singularity_bin" == "OSG" ]; then

    echo "SINGULARITY_BIN was OSG, expand to '$OSG_SINGULARITY_LOCATION'" 1>&2
    glexec_bin="$OSG_SINGULARITY_LOCATION"

elif [ "$singularity_bin" == "auto" ]; then

    type="glite"

    if [ -n "$OSG_SINGULARITY_LOCATION" ]; then
        if [ -f "$OSG_SINGULARITY_LOCATION" ]; then
            singularity_bin="$OSG_SINGULARITY_LOCATION"
            type="OSG"
        elif [ -f "/usr/sbin/singularity" ]; then
            singularity_bin=/usr/sbin/singularity
            type="OSG RPM"
        fi
    fi

    if [ "$singularity_bin" == "auto" ]; then
        if [ -f "$SINGULARITY_LOCATION/sbin/singularity" ]; then
            singularity_bin="$SINGULARITY_LOCATION/sbin/singularity"
        elif [ -f "$SINGULARITY_LOCATION/sbin/singularity" ]; then
            singularity_bin="$SINGULARITY_LOCATION/sbin/singularity"
        fi
    fi

    if [ "$singularity_bin" == "auto" ]; then
       STR="SINGULARITY_BIN was auto, but could not find it."
       "$error_gen" -error "singularity_setup.sh" "WN_Resource" "$STR" "file" "singularity"
       exit 1
    else
        echo "GLEXEC_BIN was auto, found $type, expand to '$singularity_bin'" 1>&2
    fi

fi

# but first test it does exist and is executable

if [ -f "$singularity_bin" ]; then
    if [ -x "$singularity_bin" ]; then
        echo "Using singularity binary '$singularity_bin'"
    else
        STR="singularity binary '$singularity_bin' is not executable!"
        "$error_gen" -error "singularity_setup.sh" "WN_Resource" "$STR" "file" "$singularity_bin"
        exit 1
    fi
else
    STR="singularity binary '$singularity_bin' not found!"
    "$error_gen" -error "singularity_setup.sh" "WN_Resource" "$STR" "file" "$singularity_bin"
    exit 1
fi

singularity_job=`grep '^SINGULARITY_JOB ' $glidein_config | awk '{print $2}'`
if [ -z "$singularity_job" ]; then
    singularity_job="True"
fi

if [ "$singularity_job" == "True" ]; then
    add_config_line "SINGULARITY_IMAGE_EXPR" "False"
    add_config_line "SINGULARITY_JOB" "True"
    add_condor_vars_line "SINGULARITYIMAGE_EXPR" "C" "False" "+" "Y" "Y" "-"
    add_condor_vars_line "SINGULARITY_JOB"       "C" "True" "+" "Y" "Y" "-"
else
    add_config_line "SINGULARITY_IMAGE_EXPR" "True"
    add_config_line "SINGULARITY_JOB" "False"
    add_condor_vars_line "SINGULARITYIMAGE_EXPR" "C" "True" "+" "Y" "Y" "-"
    add_condor_vars_line "SINGULARITY_JOB"       "C" "False" "+" "Y" "Y" "-"
fi

add_config_line "SINGULARITY_BIN" "$singularity_bin"

###################################################################

test_singularity

####################################################################

"$error_gen" -ok "singularity_setup.sh"  "use_singularity" "True" "singularity_bin" "$singularity_bin" "singularity_user_dir" "$singularity_target_dir" "use_singularity_job" "$singularity_job"

exit 0
