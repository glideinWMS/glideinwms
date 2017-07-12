#!/bin/bash
#
glidein_config="$1"

error_gen=`grep '^ERROR_GEN_PATH ' $glidein_config | awk '{print $2}'`

function error {
    echo "ERROR  " $@ 1>&2
}

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

if [ "x$GWMS_SINGULARITY_REEXEC" = "x" ]; then
    info "This is a setup script for the OSG-FLOCK frontend."
    info "In case of problems, contact Mats Rynge (rynge@isi.edu)"
    info "Running in directory $PWD"
else
    info "Now running inside a singularity container"
fi

if [ "x$glidein_config" = "x" ]; then
    glidein_config="NONE"
    info "No arguments provided - assuming HTCondor startd cron mode"
else
    info "Arguments to the script: $@"
fi




if [ "$glidein_config" != "NONE" -a "x$SOURCED_ADD_CONFIG_LINE" = "x" ]; then
    ###########################################################
    # import advertise and add_condor_vars_line functions
    if [ "x$add_config_line_source" = "x" ]; then
        export add_config_line_source=`grep '^ADD_CONFIG_LINE_SOURCE ' $glidein_config | awk '{print $2}'`
        export condor_vars_file=`grep -i "^CONDOR_VARS_FILE " $glidein_config | awk '{print $2}'`
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
#    add_config_line "SINGULARITY_IMAGE_EXPR" "False"
#    add_config_line "SINGULARITY_JOB" "False"
#    add_condor_vars_line "SINGULARITYIMAGE_EXPR" "C" "False" "+" "Y" "Y" "-"
#    add_condor_vars_line "SINGULARITY_JOB"       "C" "False" "+" "Y" "Y" "-"

    "$error_gen" -ok "singularity_setup.sh" "use_singularity" "False"
    exit 0
}

if [ "x$GWMS_SINGULARITY_REEXEC" = "x" ]; then

    singularity_bin=`grep '^SINGULARITY_BIN ' $glidein_config | awk '{print $2}'`
    if [ -z "$singularity_bin" ]; then
	singularity_bin="NONE"
    fi

# Does frontend wants to use singularity?
    use_singularity=`grep '^GLIDEIN_Singularity_Use ' $glidein_config | awk '{print $2}'`
    if [ -z "$use_singularity" ]; then
	echo "`date` GLIDEIN_Singularity_Use not configured. Defaulting it to OPTIONAL"
#	use_singularity="OPTIONAL"
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
	    #GWMS no_use_singularity_config alone might not be sufficient. 
            #GWMS If Group mistakenly use default_singularity_wrapper.sh with GLIDEIN_Glexec_Use=NEVER
	    #GWMS we need to set    advertise HAS_SINGULARITY "False" "C"
#            no_use_singularity_config
	    advertise HAS_SINGULARITY "False" "C"
	    "$error_gen" -ok "singularity_setup.sh" "use_singularity" "False"
	    exit 0
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
		    "$error_gen" -ok "singularity_setup.sh" "use_singularity" "False"
		    advertise HAS_SINGULARITY "False" "C"
		    exit 0
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


##################
# singularity
# advertise availability and version
# July 12 2017 Wednesday. 
# Basic principle is, setup script checks for singularity binary and availability of cvmfs by probing 
# the default singularity image in /cvmfs/singularity.
# this script does not make sure /cvmfs repositories are accessible.
# this script can NOT validate the user-specified singularity image, that's the job of wrapper script.
# the wrapper will only allow a user singularity image that is in /cvmfs if the user wants to use his own singularity image
# the wrapper will make sure that if the user does NOT specify his own singularity image, the default image is used. This is why this script
# must make sure the default image is available..
# advertise HAS_SINGULARITY "False" "C"  is very important if [ "$use_singularity" == "OPTIONAL" ]; 

if [ "x$GWMS_SINGULARITY_REEXEC" = "x" ]; then
    info "Checking for singularity..."

    # some known singularity locations
    for LOCATION in /usr/bin $singularity_bin; do
        if [ -e "$LOCATION" ]; then
            info " ... prepending $LOCATION to PATH"
            export PATH="$LOCATION:$PATH"
            break
        fi
    done
#GWMS this use of HAS_SINGULARITY="True" or "False" is simply local to this script.
#GWMS and different from as HAS_SINGULARITY as in advertise HAS_SINGULARITY "False" "C"
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
		"$error_gen" -ok "singularity_setup.sh" "use_singularity" "False"
		advertise HAS_SINGULARITY "False" "C"
		exit 0 #GWMS wrapper will make sure to run outside singularity
	    elif [ "$use_singularity" == "REQUIRED" ]; then
		STR="Unable to find singularity in PATH=$PATH"
		"$error_gen" -error "singularity_setup.sh" "WN_Resource" "$STR"
		exit 1 #GWMS no need to proceed
	    fi
        fi
    fi
    if [ "x$HAS_SINGULARITY" = "xTrue" ]; then
        info "Singularity binary appears present and claims to be version $GWMS_SINGULARITY_VERSION"
    fi

    # default image for this glidein
    export GWMS_SINGULARITY_IMAGE_DEFAULT="/cvmfs/singularity.opensciencegrid.org/opensciencegrid/osgvo:el6"

    # for now, we will only advertise singularity on nodes which can access cvmfs
    if [ ! -e "$GWMS_SINGULARITY_IMAGE_DEFAULT" ]; then
        HAS_SINGULARITY="False" #GWMS I don't think we need this any longer..
	if [ "$use_singularity" == "OPTIONAL" ]; then
	    "$error_gen" -ok "singularity_setup.sh" "use_singularity" "False"
	    advertise HAS_SINGULARITY "False" "C"		
	    exit 0 #GWMS wrapper will make sure to run outside singularity
	elif [ "$use_singularity" == "REQUIRED" ]; then
	    STR="Default singularity image, $GWMS_SINGULARITY_IMAGE_DEFAULT, does not appear to exist"
	    "$error_gen" -error "singularity_setup.sh"  "WN_Resource" "$STR"
	    exit 1 #GWMS no need to proceed
	fi
    fi

    # Let's do a simple singularity test by echoing something inside, and then
    # grepping for it outside. This takes care of some errors which happen "late"
    # in the execing, like:
    # ERROR  : Could not identify basedir for home directory path: /
    if [ "x$HAS_SINGULARITY" = "xTrue" ]; then
        info "$GWMS_SINGULARITY_PATH exec --home $PWD:/srv --bind /cvmfs --pwd /srv --scratch /var/tmp --scratch /tmp --containall $GWMS_SINGULARITY_IMAGE_DEFAULT echo Hello World | grep Hello World"
        if ! ($GWMS_SINGULARITY_PATH exec --home $PWD:/srv \
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
		"$error_gen" -ok "singularity_setup.sh" "use_singularity" "False"
		advertise HAS_SINGULARITY "False" "C"
		exit 0 #GWMS wrapper will make sure to run outside singularity
	    elif [ "$use_singularity" == "REQUIRED" ]; then
            # singularity simple exec failed - we are done
		STR="Simple singularity exec inside $GWMS_SINGULARITY_IMAGE_DEFAULT failed."
		"$error_gen" -error "singularity_setup.sh"  "WN_Resource" "$STR"
		exit 1 #GWMS no need to proceed
	    fi
        fi
    fi

    # If we still think we have singularity, we should re-exec this script within the default
    # container so that we can advertise that environment
    if [ "x$HAS_SINGULARITY" = "xTrue" ]; then
        # We want to map the full glidein dir to /srv inside the container. This is so 
        # that we can rewrite env vars pointing to somewhere inside that dir (for
        # example, X509_USER_PROXY)
        export SING_OUTSIDE_BASE_DIR=`echo "$PWD" | sed -E "s;(.*/glide_[a-zA-Z0-9]+).*;\1;"`

        # Make a copy of the user proxy - sometimes this lives outside the glidein dir
        if [ "x$X509_USER_PROXY" != "x" -a -e "$X509_USER_PROXY" ]; then
            info "Making a copy of the provided X509_USER_PROXY=$X509_USER_PROXY"
            cp $X509_USER_PROXY $SING_OUTSIDE_BASE_DIR/x509-pilot-proxy
            export X509_USER_PROXY=/srv/x509-pilot-proxy
        fi

        # build a new command line, with updated paths
        CMD=""
        for VAR in $0 "$@"; do
            VAR=`echo " $VAR" | sed -E "s;.*/glide_[a-zA-Z0-9]+(.*);/srv\1;"`
            CMD="$CMD $VAR"
        done

        # let "inside" script know we are re-execing
        export GWMS_SINGULARITY_REEXEC=1
        info "$GWMS_SINGULARITY_PATH exec --home $SING_OUTSIDE_BASE_DIR:/srv --bind /cvmfs --pwd /srv --scratch /var/tmp --scratch /tmp --containall $GWMS_SINGULARITY_IMAGE_DEFAULT $CMD"
        if $GWMS_SINGULARITY_PATH exec --home $SING_OUTSIDE_BASE_DIR:/srv \
                                      --bind /cvmfs \
                                      --pwd /srv \
                                      --scratch /var/tmp \
                                      --scratch /tmp \
                                      --containall \
                                      "$GWMS_SINGULARITY_IMAGE_DEFAULT" \
                                      $CMD \
        ; then
            # singularity worked - exit here as the rest script ran inside the container
            exit $?
        fi
    fi
    
    # if we get here, singularity is not available or not working
#    advertise HAS_SINGULARITY "False" "C"
    if [ "$use_singularity" == "OPTIONAL" ]; then
	warn "for some unknown reasons, singularity is not available"
	"$error_gen" -ok "singularity_setup.sh" "use_singularity" "False"
	advertise HAS_SINGULARITY "False" "C"
	exit 0 #HK> wrapper will make sure to run outside singularity
    elif [ "$use_singularity" == "REQUIRED" ]; then
	STR="for some unknown reasons, singularity is not available"
	"$error_gen" -error "singularity_setup.sh"  "WN_Resource" "$STR"
	exit 1 #HK> no need to proceed
    fi

else
#GWMS original place
    # fix up the env
    for key in X509_USER_PROXY X509_USER_CERT _CONDOR_MACHINE_AD _CONDOR_JOB_AD \
               _CONDOR_SCRATCH_DIR _CONDOR_CHIRP_CONFIG _CONDOR_JOB_IWD \
               add_config_line_source condor_vars_file ; do
        eval val="\$$key"
        val=`echo "$val" | sed -E "s;$SING_OUTSIDE_BASE_DIR(.*);/srv\1;"`
        eval $key=$val
    done
        
    export add_config_line_source=`echo "$add_config_line_source" | sed -E "s;.*/glide_[a-zA-Z0-9]+(.*);/srv\1;"`
    export       condor_vars_file=`echo "$condor_vars_file"       | sed -E "s;.*/glide_[a-zA-Z0-9]+(.*);/srv\1;"`
    info "Updated glidein config to paths inside the container: add_config_line_source=$add_config_line_source condor_vars_file=$condor_vars_file"

#GWMS I had to copy the following 3 lines from up there to here, otherwise the advertise lines below will error 
#GWMS because  with the source command here,   the function  add_config_line is not defined
    info "Sourcing $add_config_line_source"
    source $add_config_line_source
    # make sure we don't source a second time inside the container
    export SOURCED_ADD_CONFIG_LINE=1


#GWMS moved from the original place shown above..
    # delay the advertisement until here to make sure singularity actually works
    advertise HAS_SINGULARITY "True" "C"
    advertise GWMS_SINGULARITY_PATH "$GWMS_SINGULARITY_PATH" "S"
    advertise GWMS_SINGULARITY_IMAGE_DEFAULT "$GWMS_SINGULARITY_IMAGE_DEFAULT" "S"
#GWMS not used anywhere, thus no need to advertize to default_singularity_wrapper.sh
#    advertise GWMS_SINGULARITY_VERSION "$GWMS_SINGULARITY_VERSION" "S"
fi

##################
# mostly done - update START validation expressions and warnings attribute

##################
info "All done - time to do some real work!"

