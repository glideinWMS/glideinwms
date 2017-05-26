#!/bin/sh

glidein_config="$1"

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
        add_config_line      $key "$value"
        add_condor_vars_line $key "$atype" "-" "+" "Y" "Y" "+"
    fi

    if [ "$atype" = "S" ]; then
        echo "$key = \"$value\""
    else
        echo "$key = $value"
    fi
}

#HK> glidein_config has
#HK> ADD_CONFIG_LINE_SOURCE  /home/scratchgwms/glide_o9qhWF/add_config_line.source
#HK> add_config_line.source has
#function add_config_line {
#    egrep -q "^${*}$" $glidein_config
#    if [ $? -ne 0 ]; then
#        rm -f ${glidein_config}.old #just in case one was there
#        mv $glidein_config ${glidein_config}.old
#        if [ $? -ne 0 ]; then
#            warn "Error renaming $glidein_config into ${glidein_config}.old"
#            exit 1
#        fi
#        grep -v "^$1 " ${glidein_config}.old > $glidein_config
#        # NOTE that parameters are flattened, if there are spaces they are separated
#        echo "$@" >> $glidein_config
#        rm -f ${glidein_config}.old
#    fi
#}
#HK> when     source $add_config_line_source is executed, this script now has add_config_line function available























if [ "x$glidein_config" = "x" ]; then
    glidein_config="NONE"
    info "No arguments provided - assuming HTCondor startd cron mode"
else
    info "Arguments to the script: $@"
fi

info "This is a setup script for the CMS frontend."
info "In case of problems, contact CMS support at ggus.eu"
info "Running in directory $PWD"

if [ "$glidein_config" != "NONE" ]; then
    ###########################################################
    # import advertise and add_condor_vars_line functions
    # are we inside singularity?
    if [ "x$add_config_line_source" = "x" ]; then
        export add_config_line_source=`grep '^ADD_CONFIG_LINE_SOURCE ' $glidein_config | awk '{print $2}'`
        export condor_vars_file=`      grep -i "^CONDOR_VARS_FILE "    $glidein_config | awk '{print $2}'`
    fi

    source $add_config_line_source
fi




function no_use_singularity_config {
    echo "Not using singularity" 1>&2
    advertise HAS_SINGULARITY              "True"                          "C"
    "$error_gen" -ok "singularity_setup.sh" "use_singularity" "False"
    exit 0
}




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

            STR="Factory requires glidein to use singularity."
            "$error_gen" -error "singularity_setup.sh" "VO_Config" "$STR" "attribute" "GLIDEIN_Singularity_Use"
            exit 1
        fi
        no_use_singularity_config
        ;;
    OPTIONAL)
        if [ "$require_singularity_use" == "True" ]; then
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


echo 'if we are here, that means'


if [ "x$OSG_SINGULARITY_REEXEC" = "x" ]; then

    for LOCATION in \
	/usr/bin \ 
        /util/opt/singularity/2.2.1/gcc/4.4/bin \
        /util/opt/singularity/2.2/gcc/4.4/bin \
        /uufs/chpc.utah.edu/sys/installdir/singularity/std/bin \
    ; do
        if [ -e "$LOCATION" ]; then
            info " ... prepending $LOCATION to PATH"
            export PATH="$LOCATION:$PATH"
            break
        fi
    done

    HAS_SINGULARITY="False"
    export HK_SINGULARITY_VERSION=`singularity --version 2>/dev/null`
    if [ "x$HK_SINGULARITY_VERSION" != "x" ]; then
        HAS_SINGULARITY="True"
        export HK_SINGULARITY_PATH=`which singularity`
    fi

    # default image for this glidein
    export HK_SINGULARITY_IMAGE_DEFAULT="/cvmfs/singularity.opensciencegrid.org/bbockelm/cms:rhel6"

    # for now, we will only advertise singularity on nodes which can access cvmfs
    if [ ! -e "$HK_SINGULARITY_IMAGE_DEFAULT" ]; then
        HAS_SINGULARITY="False"
    fi

    # Make sure $HOME exists and isn't shared
    EXTRA_ARGS="--home $PWD:/srv"

    # Let's do a simple singularity test by echoing something inside, and then
    # grepping for it outside. This takes care of some errors which happen "late" in the execing, like:
    # ERROR  : Could not identify basedir for home directory path: /
    if [ "x$HAS_SINGULARITY" = "xTrue" ]; then
        info "$HK_SINGULARITY_PATH exec $EXTRA_ARGS --bind /cvmfs --bind $PWD:/srv --pwd /srv --scratch /var/tmp --scratch /tmp --containall $HK_SINGULARITY_IMAGE_DEFAULT echo Hello World | grep Hello World"
        if ! ($HK_SINGULARITY_PATH exec $EXTRA_ARGS \
                                         --bind /cvmfs \
                                         --bind $PWD:/srv \
                                         --pwd /srv \
                                         --scratch /var/tmp \
                                         --scratch /tmp \
                                         --containall \
                                         "$HK_SINGULARITY_IMAGE_DEFAULT" \
                                         echo "Hello World" \
                                         | grep "Hello World") 1>&2 \
        ; then
            # singularity simple exec failed - we are done
            info "Singularity simple exec failed.  Disabling support"
            HAS_SINGULARITY="False"
        fi
    fi




    # If we still think we have singularity, we should re-exec this script within the default
    # container so that we can advertise that environment
    if [ "x$HAS_SINGULARITY" = "xTrue" ]; then
        # We want to map the full glidein dir to /srv inside the container. 
        # This is so that we can rewrite env vars pointing to somewhere inside that dir (for example, X509_USER_PROXY)
        export SING_OUTSIDE_BASE_DIR=`echo "$PWD" | sed -E "s;(.*/glide_[a-zA-Z0-9]+).*;\1;"`

        # build a new command line, with updated paths
        CMD=""
        for VAR in $0 "$@"; do
            VAR=`echo " $VAR" | sed -E "s;.*/glide_[a-zA-Z0-9]+(.*);/srv\1;"`
            CMD="$CMD $VAR"
        done
    
        # Make sure $HOME isn't shared
        EXTRA_ARGS="--home $SING_OUTSIDE_BASE_DIR:/srv"


        # Update the location of the advertise script:
        add_config_line_source=`echo "$add_config_line_source" | sed -E "s;.*/glide_[a-zA-Z0-9]+(.*);/srv\1;"`
        condor_vars_file=`      echo "$condor_vars_file"       | sed -E "s;.*/glide_[a-zA-Z0-9]+(.*);/srv\1;"`

        # let "inside" script know we are re-execing
        export OSG_SINGULARITY_REEXEC=1
        info "$HK_SINGULARITY_PATH exec $EXTRA_ARGS --bind /cvmfs --bind $SING_OUTSIDE_BASE_DIR:/srv --pwd /srv --scratch /var/tmp --scratch /tmp --containall $HK_SINGULARITY_IMAGE_DEFAULT $CMD"
        if $HK_SINGULARITY_PATH exec $EXTRA_ARGS \
                                      --bind /cvmfs \
                                      --bind $SING_OUTSIDE_BASE_DIR:/srv \
                                      --pwd /srv \
                                      --scratch /var/tmp \
                                      --scratch /tmp \
                                      --containall \
                                      "$HK_SINGULARITY_IMAGE_DEFAULT" \
                                      $CMD \
        ; then
            # singularity worked - exit here as the rest script ran inside the container
            exit $?
        fi
    fi





    
    # if we get here, singularity is not available or not working
    advertise HAS_SINGULARITY "False" "C"
    exit 0
fi


info "Already running inside singularity"

# fix up the env
for key in X509_USER_PROXY    X509_USER_CERT    _CONDOR_MACHINE_AD     _CONDOR_JOB_AD  \
           _CONDOR_SCRATCH_DIR   _CONDOR_CHIRP_CONFIG    _CONDOR_JOB_IWD     add_config_line_source     condor_vars_file ; do
    eval val="\$$key"
    val=`echo "$val" | sed -E "s;$SING_OUTSIDE_BASE_DIR(.*);/srv\1;"`
    eval $key=$val
done
# Any further tests that require Singularity should go here.


# At this point, we're convinced Singularity works
advertise HAS_SINGULARITY              "True"                          "C"
advertise HK_SINGULARITY_VERSION       "$HK_SINGULARITY_VERSION"       "S"
advertise HK_SINGULARITY_PATH          "$HK_SINGULARITY_PATH"          "S"
advertise HK_SINGULARITY_IMAGE_DEFAULT "$HK_SINGULARITY_IMAGE_DEFAULT" "S"
advertise GLIDEIN_REQUIRED_OS           "any"                          "S"

# Disable glexec if we are going to use Singularity.
advertise GLEXEC_JOB "False" "C"
advertise GLEXEC_BIN "NONE" "C"

