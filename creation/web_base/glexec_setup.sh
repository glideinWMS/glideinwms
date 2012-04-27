#!/bin/bash

#
# Project:
#   glideinWMS
#
# File Version:
#
# Description:
#   This script will setup the gLExec parameters
#

# Configuration in case GLEXEC should not be used
function no_use_glexec_config {
    echo "Not using glexec" 1>&2
    # still explicitly disable it in the config
    add_config_line "GLEXEC_STARTER" "False"
    add_config_line "GLEXEC_JOB" "False"
    add_condor_vars_line "GLEXEC_STARTER" "C" "False" "+" "Y" "Y" "-"
    add_condor_vars_line "GLEXEC_JOB"     "C" "False" "+" "Y" "Y" "-"

    "$error_gen" -ok "glexec_setup.sh" "Glexec" "glexec"
    exit 0
}

function test_glexec {
    tst=`env GLEXEC_CLIENT_CERT="$X509_USER_PROXY" "$glexec_bin"  "$ALTSH" -c "id && echo \"Hello World\""`
    res=$?
    if [ $res -ne 0 ]; then
        #echo "glexec test failed, nonzero value $res" 1>&2
        #echo "result: $tst" 1>&2
        STR="			glexec test failed, nonzero value $res\n"
        STR=$STR"			result: $tst"
        echo -e $STR > string
        "$error_gen" -error "glexec_setup.sh" "WN_Resource" "command" "$glexec_bin"
        exit 1
    else
        tst2=`echo "$tst" |tail -1`
        if [ "$tst2" == "Hello World" ]; then
            echo "glexec verified to work" 1>&2
        else
            #echo "glexec broken!" 1>&2
            #echo "Expected 'Hello World', got '$tst2'" 1>&2
            STR="			glexec broken!\n"
            STR=$STR"			Expected 'Hello World', got '$tst2'"
            echo -e $STR > string
            "$error_gen" -error "glexec_setup.sh" "WN_Resource" "command" "$glexec_bin"
            exit 1
        fi
    fi
}

function test_glexec2 {
    cat > glexec_test2.sh << EOF
#!/bin/sh
id && echo "Hello World"
EOF
    chmod a+x glexec_test2.sh

    tst=`env GLEXEC_CLIENT_CERT="$X509_USER_PROXY" "$glexec_bin"  "$PWD/glexec_test2.sh"`

    res=$?
    if [ $res -ne 0 ]; then
        #echo "glexec test2 failed, nonzero value $res" 1>&2
        #echo "result: $tst" 1>&2
        STR="			glexec test2 failed, nonzero value $res\n"
        STR=$STR"			result: $tst"
        echo -e $STR > string
        "$error_gen" -error "glexec_setup.sh" "WN_Resource" "command" "$glexec_bin"
        exit 1
    else
        tst2=`echo "$tst" |tail -1`
        if [ "$tst2" == "Hello World" ]; then
            echo "glexec verified to work (test2)" 1>&2
        else
            #echo "glexec broken (test2)!" 1>&2
            #echo "Expected 'Hello World', got '$tst2'" 1>&2
            STR="			glexec broken (test2)!\n"
            STR=$STR"			Expected 'Hello World', got '$tst2'"
            echo -e $STR > string
            "$error_gen" -error "glexec_setup.sh" "WN_Resource" "command" "$glexec_bin"
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
        ;;
    REQUIRED)
        if [ "$glexec_bin" == "NONE" ]; then
            #echo "`date` VO mandates the use of glexec but the site is not configured with glexec information."
            STR="			`date` VO mandates the use of glexec but the site is not configured with glexec information"
            echo -e $STR > string
            "$error_gen" -error "glexec_setup.sh" "VO_Config" "attribute" "GLEXEC_BIN" "attribute" "GLIDEIN_Glexec_Use"
            exit 1
        fi
        ;;
    *)
        #echo "`date` USE_GLEXEC in VO Frontend configured to be $use_glexec. Accepted values are 'NEVER' or 'OPTIONAL' or 'REQUIRED'."
        STR="			`date` USE_GLEXEC in VO Frontend configured to be $use_glexec. Accepted values are 'NEVER' or 'OPTIONAL' or 'REQUIRED'."
        echo -e $STR > string
        "$error_gen" -error "glexec_setup.sh" "VO_Config" "attribute" "GLIDEIN_Glexec_Use"
        exit 1
        ;;
esac 

# We should use the copy of the proxy created by setup_x509.sh
x509_user_proxy=`grep "^X509_USER_PROXY " $glidein_config | awk '{print $2}'`
if [ -f "$x509_user_proxy" ]; then
    export X509_USER_PROXY=$x509_user_proxy
else
    # should never happen, but let's be safe
    echo "`date` X509_USER_PROXY not defined in config file."
    exit 1
fi

echo "`date` making configuration changes to use glexec"
# --------------------------------------------------
# gLExec does not like symlinks and this way we are sure it is a file
# Note: the -e test performs the same function as readlink -e and allows
#       for SL4/SL5 compatibility (readlink -e does not exist in SL4).
if [ ! -e /bin/sh ];then
    #echo "gLExec does not like symlinks. Failed to dereference /bin/sh" 1>&2
    STR="			gLExec does not like symlinks. Failed to dereference /bin/sh"
    echo -e $STR > string
    "$error_gen" -error "glexec_setup.sh" "WN_Resource" "command" "ln"
    exit 1
fi
export ALTSH="`readlink -f /bin/sh`"
add_config_line "ALTERNATIVE_SHELL" "$ALTSH" 
add_condor_vars_line "ALTERNATIVE_SHELL" "C" "-" "SH" "Y" "N" "-"

# --------------------------------------------------
# Set glidein working dir into the tmp dir
# This is needes since the user will be changed and 
# the tmo directory is world writtable
glide_tmp_dir=`grep '^TMP_DIR ' $glidein_config | awk '{print $2}'`
if [ -z "$glide_tmp_dir" ]; then
    #echo "TMP_DIR not found!" 1>&2
    STR="			TMP_DIR not found!"
    echo -e $STR > string
    "$error_gen" -error "glexec_setup.sh" "WN_Resource" "environment" "TMP_DIR"
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
elif [ "$glexec_bin" == "glite" ]; then
    echo "GLEXEC_BIN was glite, expand to '/opt/glite/sbin/glexec'" 1>&2
    glexec_bin=/opt/glite/sbin/glexec
elif [ "$glexec_bin" == "auto" ]; then
    if [ -n "$OSG_GLEXEC_LOCATION" ]; then
        if [ -f "$OSG_GLEXEC_LOCATION" ]; then
            echo "GLEXEC_BIN was auto, found OSG, expand to '$OSG_GLEXEC_LOCATION'" 1>&2
            glexec_bin="$OSG_GLEXEC_LOCATION"
        fi
    fi
    if [ "$glexec_bin" == "auto" ]; then
        if [ -f "/opt/glite/sbin/glexec" ]; then
            echo "GLEXEC_BIN was auto, found glite, expand to '/opt/glite/sbin/glexec'" 1>&2
            glexec_bin=/opt/glite/sbin/glexec
        fi
    fi
    if [ "$glexec_bin" == "auto" ]; then
        #echo "GLEXEC_BIN was auto, but could not find it!" 1>&2
        STR="			GLEXEC_BIN was auto, but could not find it!"
        echo -e $STR > string
        "$error_gen" -error "glexec_setup.sh" "Factory_Config" "attribute" "GLEXEC_BIN"
        exit 1
    fi
fi

# but first test it does exist and is executable

if [ -f "$glexec_bin" ]; then
    if [ -x "$glexec_bin" ]; then
        echo "Using gLExec binary '$glexec_bin'"
    else
        #echo "gLExec binary '$glexec_bin' is not executable!" 1>&2
        STR="			gLExec binary '$glexec_bin' is not executable!"
        echo -e $STR > string
        "$error_gen" -error "glexec_setup.sh" "WN_Resource" "file" "$glexec_bin"
        exit 1
    fi
else
    #echo "gLExec binary '$glexec_bin' not found!" 1>&2
    STR="			gLExec binary '$glexec_bin' not found!"
    echo -e $STR > string
    "$error_gen" -error "glexec_setup.sh" "WN_Resource" "file" "$glexec_bin"
    exit 1
fi


glexec_job=`grep '^GLEXEC_JOB ' $glidein_config | awk '{print $2}'`
if [ -z "$glexec_job" ]; then
    # default to the new mode
    glexec_job="True"
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

###################################################################
# From mkgltempdir
echo "Setting whole path permissions"

# Setup tmpdir permissions
opwd=$(pwd)
while [ $(pwd) != / ];do
    echo "Trying $(pwd): `ls -ld .`"
    chmod a+x . 2> /dev/null || break
    echo "Done $(pwd): `ls -ld .`"
    cd ..
done
cd $opwd

test_glexec
test_glexec2

####################################################################
# Add requirement that only jobs with X509 attributes can start here
# Also add requirement that voms proxies exist
####################################################################

start_condition=`grep '^GLIDEIN_Entry_Start ' $glidein_config | awk '{print $2}'`
if [ -z "$start_condition" ]; then
    add_config_line "GLIDEIN_Entry_Start" "(x509userproxysubject=!=UNDEFINED)&&((GLIDEIN_REQUIRE_VOMS=?=UNDEFINED)||(GLIDEIN_REQUIRE_VOMS=?=False)||(TARGET.x509userproxyfirstfqan=!=UNDEFINED))"
else
    add_config_line "GLIDEIN_Entry_Start" "(x509userproxysubject=!=UNDEFINED)&&((GLIDEIN_REQUIRE_VOMS=?=UNDEFINED)||(GLIDEIN_REQUIRE_VOMS=?=False)||(TARGET.x509userproxyfirstfqan=!=UNDEFINED))&&($start_condition)"
fi

"$error_gen" -ok "glexec_setup.sh" "Glexec" "glexec"

exit 0
