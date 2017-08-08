#!/bin/bash
#
glidein_config="$1"

error_gen=`grep '^ERROR_GEN_PATH ' $glidein_config | awk '{print $2}'`

function info {
    echo "INFO  " $@ 1>&2
}

function warn {
    echo "WARN  " $@ 1>&2
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

if [ "$glidein_config" != "NONE" -a "x$SOURCED_ADD_CONFIG_LINE" = "x" ]; then
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
function no_use_singularity_config {
    echo "Not using singularity" 1>&2
    advertise HAS_SINGULARITY "False" "C"
    "$error_gen" -ok "singularity_setup.sh" "use_singularity" "False"
    exit 0
}

TEMP_CONDITION=1
if [ "x$TEMP_CONDITION" = "x1" ]; then
#GWMS direct use of singularity_bin before I started using echo (as below) failed..
    temp_singularity_bin=`grep '^SINGULARITY_BIN ' $glidein_config | awk '{$1=""; print $0}'`
# GWMS use awk differently here to deal with cases where the pathname contains whitespaces..
#   singularity_bin=`grep '^SINGULARITY_BIN ' $glidein_config | awk '{print $2}'`
    singularity_bin=$(echo $temp_singularity_bin)
    if [ -z "$singularity_bin" ]; then
	singularity_bin="NONE"
    fi

# Does frontend wants to use singularity?
    use_singularity=`grep '^GLIDEIN_Singularity_Use ' $glidein_config | awk '{print $2}'`
    if [ -z "$use_singularity" ]; then
	echo "`date` GLIDEIN_Singularity_Use not configured. Defaulting it to OPTIONAL"
# GWMS, when Group does not specify GLIDEIN_Singularity_Use, it should default to NEVER
	use_singularity="NEVER"
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
	NEVER)
            echo "`date` VO does not want to use singularity"
            if [ "$require_singularity" == "True" ]; then
		STR="Factory requires glidein to use singularity."
		"$error_gen" -error "singularity_setup.sh" "VO_Config" "$STR" "attribute" "GLIDEIN_Singularity_Use"
		exit 1
            fi
            #GWMS If Group mistakenly use default_singularity_wrapper.sh with GLIDEIN_Glexec_Use=NEVER
	    #GWMS we need to set    advertise HAS_SINGULARITY "False" "C"
            no_use_singularity_config
            ;;
	OPTIONAL) #GWMS Even in OPTIONAL case, FE will have to specify the wrapper script
            if [ "$require_singularity" == "True" ]; then
		if [ "$singularity_bin" == "NONE" ]; then
                    STR="Factory requires glidein to use singularity but singularity_bin is NONE."
		    "$error_gen" -error "singularity_setup.sh" "VO_Config" "$STR" "attribute" "SINGULARITY_BIN" "attribute" "GLIDEIN_Singularity_Use"
                    exit 1
		fi
            else
		if [ "$singularity_bin" == "NONE" ]; then
                    echo "`date` VO has set the use singularity to OPTIONAL but site is not configured with singularity"
		    no_use_singularity_config
		fi
            fi
            ;;
	REQUIRED)
            if [ "$singularity_bin" == "NONE" ]; then
		STR="VO mandates the use of singularity but the site is not configured with singularity information"
		"$error_gen" -error "singularity_setup.sh" "VO_Config" "$STR" "attribute" "SINGULARITY_BIN" "attribute" "GLIDEIN_Singularity_Use"
		exit 1
            fi
            ;;
	*)
            STR="USE_SINGULARITY in VO Frontend configured to be $use_singularity.\nAccepted values are 'NEVER' or 'OPTIONAL' or 'REQUIRED'."
            STR1=`echo -e "$STR"`
            "$error_gen" -error "singularity_setup.sh" "VO_Config" "$STR1" "attribute" "GLIDEIN_Singularity_Use"
            exit 1
            ;;
    esac
fi


if [ "x$TEMP_CONDITION" = "x1" ]; then
    info "Checking for singularity..."
    #GWMS Entry must use SINGULARITY_BIN to specify the pathname of the singularity binary
    #GWMS, we quote $singularity_bin to deal with white spaces in the path
    LOCATION="$singularity_bin"
    if [ -e "$LOCATION" ]; then
        info " ... prepending $LOCATION to PATH"
        export PATH="$LOCATION:$PATH"
    fi

    HAS_SINGULARITY="False"
    export GWMS_SINGULARITY_VERSION=`singularity --version 2>/dev/null`
    if [ "x$GWMS_SINGULARITY_VERSION" != "x" ]; then
        HAS_SINGULARITY="True"
        export GWMS_SINGULARITY_PATH=`which singularity`
    else
        # some sites requires us to do a module load first - not sure if we always want to do that
        export GWMS_SINGULARITY_VERSION=`module load singularity >/dev/null 2>&1; singularity --version 2>/dev/null`
        if [ "x$GWMS_SINGULARITY_VERSION" != "x" ]; then
            HAS_SINGULARITY="True"
            export GWMS_SINGULARITY_PATH=`module load singularity >/dev/null 2>&1; which singularity`
        else
	    if [ "$use_singularity" == "OPTIONAL" ]; then
		warn "Singularity binary does not exist."
		no_use_singularity_config
	    elif [ "$use_singularity" == "REQUIRED" ]; then
		STR="Unable to find singularity in PATH=$PATH"
		"$error_gen" -error "singularity_setup.sh" "WN_Resource" "$STR"
		exit 1
	    fi
        fi
    fi
    if [ "x$HAS_SINGULARITY" = "xTrue" ]; then
        info "Singularity binary appears present and claims to be version $GWMS_SINGULARITY_VERSION"
    fi

    # default image for this glidein
    export GWMS_SINGULARITY_IMAGE_DEFAULT=`grep '^SINGULARITY_IMAGE_DEFAULT6 ' $glidein_config | awk '{print $2}'`

    # for now, we will only advertise singularity on nodes which can access cvmfs
    if [ ! -e "$GWMS_SINGULARITY_IMAGE_DEFAULT" ]; then
        HAS_SINGULARITY="False" #GWMS I don't think we need this any longer..
	if [ "$use_singularity" == "OPTIONAL" ]; then
	    warn "$GWMS_SINGULARITY_IMAGE_DEFAULT doex not exist."
            no_use_singularity_config
	elif [ "$use_singularity" == "REQUIRED" ]; then
	    STR="Default singularity image, $GWMS_SINGULARITY_IMAGE_DEFAULT, does not appear to exist"
	    "$error_gen" -error "singularity_setup.sh"  "WN_Resource" "$STR"
	    exit 1
	fi
    fi

    if [ "x$HAS_SINGULARITY" = "xTrue" ]; then
        info "$GWMS_SINGULARITY_PATH exec --home $PWD:/srv --bind /cvmfs --pwd /srv --scratch /var/tmp --scratch /tmp --containall $GWMS_SINGULARITY_IMAGE_DEFAULT echo Hello World | grep Hello World"
        if ! ("$GWMS_SINGULARITY_PATH" exec --home $PWD:/srv \
                                         --bind /cvmfs \
                                         --pwd /srv \
                                         --scratch /var/tmp \
                                         --scratch /tmp \
                                         --containall \
                                         "$GWMS_SINGULARITY_IMAGE_DEFAULT" \
                                         echo "Hello World" \
                                         | grep "Hello World") 1>&2 \
        ; then
            HAS_SINGULARITY="False"
	    if [ "$use_singularity" == "OPTIONAL" ]; then
		warn "Simple singularity exec inside $GWMS_SINGULARITY_IMAGE_DEFAULT failed."
		no_use_singularity_config
	    elif [ "$use_singularity" == "REQUIRED" ]; then
		STR="Simple singularity exec inside $GWMS_SINGULARITY_IMAGE_DEFAULT failed."
		"$error_gen" -error "singularity_setup.sh"  "WN_Resource" "$STR"
		exit 1
	    fi
        fi
    fi

    advertise HAS_SINGULARITY "True" "C"
    advertise SINGULARITY_PATH "$GWMS_SINGULARITY_PATH" "S"

fi

info "All done - time to do some real work!"

"error_gen" -ok "singularity_setup.sh"  "use_singularity" "True"
exit 0

