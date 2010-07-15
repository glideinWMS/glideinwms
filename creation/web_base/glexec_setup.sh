#!/bin/bash

############################################################
#
# This script will setup the gLExec parameters
#
############################################################

# Configuration in case GLEXEC should not be used
function no_use_glexec_config {
    echo "Not using glexec"
    # still explicitly disable it in the config
    add_config_line "GLEXEC_STARTER" "False"
    add_config_line "GLEXEC_JOB" "False"
    add_condor_vars_line "GLEXEC_STARTER" "C" "False" "+" "Y" "Y" "-"
    add_condor_vars_line "GLEXEC_JOB"     "C" "False" "+" "Y" "Y" "-"
    exit 0
}

glidein_config=$1
tmp_fname=${glidein_config}.$$.tmp

condor_vars_file=`grep -i "^CONDOR_VARS_FILE " $glidein_config | awk '{print $2}'`

# import add_config_line and add_condor_vars_line functions
add_config_line_source=`grep '^ADD_CONFIG_LINE_SOURCE ' $glidein_config | awk '{print $2}'`
source $add_config_line_source

# Is site configured with glexec?
glexec_bin=`grep '^GLEXEC_BIN ' $glidein_config | awk '{print $2}'`
if [ -z "$glexec_bin" ]; then
    glexec_bin="NONE"
fi

# Does frontend wants to use glexec? 
use_glexec=`grep '^GLIDEIN_Glexec_Use ' $glidein_config | awk '{print $2}'`
if [ -z "$use_glexec" ]; then
    # Default to optional usage
    echo "`date` GLIDEIN_Glexec_Use not configured. Defaulting it to OPTIONAL"
    use_glexec="OPTIONAL"
fi

echo "`date` VO's desire to use glexec: $use_glexec"
echo "`date` Entry configured with glexec: $glexec_bin"

case "$use_glexec" in
    NEVER)
        echo "`date` VO does not want to use glexec"
        no_use_glexec_config
        ;;
    OPTIONAL)
        if [ "$glexec_bin" == "NONE" ]; then
            echo "`date` VO has set the use glexec to OPTIONAL but site is not configured with glexec"
            no_use_glexec_config
        fi
        # Default to secure mode using glexec
        break
        ;;
    REQUIRED)
        if [ "$glexec_bin" == "NONE" ]; then
            echo "`date` VO mandates the use of glexec but the site is not configured with glexec information."
            exit 1
        fi
        break
        ;;
    *)
        echo "`date` USE_GLEXEC in VO Frontend configured to be $use_glexec. Accepted values are 'NEVER' or 'OPTIONAL' or 'REQUIRED'."
        exit 1
        ;;
esac 

echo "`date` making configuration changes to use glexec"
# --------------------------------------------------
# create a local copy of the shell
# gLExec does not like symlinks and this way we are sure it is a file
cp -p /bin/sh ./sh
if [ $? -ne 0 ]; then
    echo "Failed to copy /bin/sh to . ($PWD)" 1>&2
    exit 1
fi
add_config_line "ALTERNATIVE_SHELL" "$PWD/sh" 
add_condor_vars_line "ALTERNATIVE_SHELL" "C" "-" "SH" "Y" "N" "-"

# --------------------------------------------------
# Set glidein working dir into the tmp dir
# This is needes since the user will be changed and 
# the tmo directory is world writtable
glide_tmp_dir=`grep '^TMP_DIR ' $glidein_config | awk '{print $2}'`
if [ -z "$glide_tmp_dir" ]; then
    echo "TMP_DIR not found!" 1>&2
    exit 1
fi
add_config_line "GLEXEC_USER_DIR" "$glide_tmp_dir"
add_condor_vars_line "GLEXEC_USER_DIR" "C" "-" "+" "Y" "N" "-"


# --------------------------------------------------
#
# Tell Condor to actually use gLExec
#
if [ "$glexec_bin" == "OSG" ]; then
    echo "GLEXEC_BIN was OSG, expand to '$OSG_GLEXEC_LOCATION'" 1>&2
    glexec_bin="$OSG_GLEXEC_LOCATION"
fi

# but first test it does exist

if [ -x "$glexec_bin" ]; then
    echo "Using gLExec binary '$glexec_bin'"
else
    echo "gLExec binary '$glexec_bin' not found!" 1>&2
    exit 1
fi


glexec_job=`grep '^GLEXEC_JOB ' $glidein_config | awk '{print $2}'`
if [ -z "$glexec_job" ]; then
    # default to the old mode
    glexec_job=False
fi

if [ "$glexec_job" == "True" ]; then
    add_config_line "GLEXEC_STARTER" "False"
    add_config_line "GLEXEC_JOB" "True"
    add_condor_vars_line "GLEXEC_STARTER" "C" "False" "+" "Y" "Y" "-"
    add_condor_vars_line "GLEXEC_JOB"     "C" "True"  "+" "Y" "Y" "-"
else
    add_config_line "GLEXEC_STARTER" "True"
    add_config_line "GLEXEC_JOB" "False"
    add_condor_vars_line "GLEXEC_STARTER" "C" "True"  "+" "Y" "Y" "-"
    add_condor_vars_line "GLEXEC_JOB"     "C" "False" "+" "Y" "Y" "-"
fi

add_config_line "GLEXEC_BIN" "$glexec_bin"

####################################################################
# Add requirement that only jobs with X509 attributes can start here
####################################################################

start_condition=`grep '^GLIDEIN_Entry_Start ' $glidein_config | awk '{print $2}'`
if [ -z "$start_condition" ]; then
    add_config_line "GLIDEIN_Entry_Start" "x509userproxysubject=!=UNDEFINED"
else
    add_config_line "GLIDEIN_Entry_Start" "(x509userproxysubject=!=UNDEFINED)&&($start_condition)"
fi

exit 0
