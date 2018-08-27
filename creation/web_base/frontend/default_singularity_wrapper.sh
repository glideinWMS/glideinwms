#!/bin/bash
# 
EXITSLEEP=5m
GWMS_AUX_SUBDIR=.gwms_aux
GLIDEIN_THIS_SCRIPT=$0

################################################################################
#
# All code out here will run on the 1st invocation (whether Singularity is wanted or not)
# and also in the re-invocation within Singularity
# $HAS_SINGLARITY is used to discriminate if Singularity is desired (is 1) or not
# $GWMS_SINGULARITY_REEXEC is used to discriminate the re-execution (nothing outside, 1 inside)
#

# Source utility files, outside and inside Singularity
if [ -e singularity_lib.sh ]; then
    GWMS_AUX_DIR="./"
elif [ -e /srv/.gwms_aux/singularity_lib.sh ]; then
    # In Singularity
    GWMS_AUX_DIR="/srv/$GWMS_AUX_SUBDIR/"
else
    echo "ERROR: default_singularity_wrapper.sh: Unable to source singularity_lib.sh! File not found. Quitting" 1>&2
    exit 1
fi
source ${GWMS_AUX_DIR}singularity_lib.sh

function sleep_and_exit {
    # An error occurred. Sleep for holdtime and then exit 1
    #  1: Error message
    [ -n "$1" ] && warn_raw "ERROR: $1"
    sleep $EXITSLEEP
    exit 1
}

function exit_wrapper {
    # TODO: test if it is OK to run w/o Singularity?
    # An error occurred. Sleep for holdtime and then exit 1
    #  1: Error message
    #  2: Exit code (1 by default)
    #  3: sleep time (default: $EXITSLEEP
    [ -n "$1" ] && warn_raw "ERROR: $1"
    exit_code=$2
    [ -z "$exit_code" ] && exit_code=1
    # TODO: add so that condor understands that is a wrapper error and retries the job
    # See CMS wrpper
    sleep $EXITSLEEP
    exit $exit_code
}


if [ -z "$GWMS_SINGULARITY_REEXEC" ]; then

    ################################################################################
    #
    # Outside Singularity - Run this only on the 1st invocation
    #

    # Set up environment to know if Singularity is enabled and so we can execute Singularity
    setup_classad_variables

    # Check if singularity is disabled or enabled
    # This script could run when singularity is optional and not wanted
    # So should not fail but exec w/o running Singularity

#    ## Section removed, the bottom will setup and exec w/ and w/o singularity
#    if [ $HAS_SINGULARITY -eq 0 ]; then
#
#        ################################################################################
#        #
#        # Run w/o Singularity
#        # Assume that singularity_setup.sh removed inconsistencies
#        # $HAS_SINGULARITY False means it was optional and is OK to run without
#        # Run the real job and check for exec failure
#        #
#
#        info_dbg "Singularity disabled, running directly the user job via exec: $@"
#        #TODO: Run user scripts out_container
#        exec "$@"
#        error=$?
#        echo "Failed to exec($error): $@" > $_CONDOR_WRAPPER_ERROR_FILE
#        info "exec $@ failed: exit code $error"
#        exit $error
#    fi
  

    if [ "x$HAS_SINGULARITY" = "x1" -a "x$GWMS_SINGULARITY_PATH" != "x" ]; then
        #############################################################################
        #
        # Will run w/ Singularity - prepare for it
        # From here on the script assumes it has to run w/ Singularity
        #
        info_dbg "Decided to use singularity ($HAS_SINGULARITY, $GWMS_SINGULARITY_PATH). Proceeding w/ tests and setup."


        # TODO: check if doing the right thing when path became empty

        # TODO: move into function to allow run w/o Singularity if OK?

        # We make sure that every cvmfs repository that users specify in CVMFSReposList is available, otherwise this script exits with 1
        cvmfs_test_and_open "$CVMFS_REPOS_LIST" sleep_and_exit

        # If  image is not provided, load the default one
        # Custom URIs: http://singularity.lbl.gov/user-guide#supported-uris
        if [ -z "$GWMS_SINGULARITY_IMAGE" ]; then
            # No image requested by the job
            # Use OS matching to determine default; otherwise, set to the global default.
            # TODO: verify meaning of $GLIDEIN_REQUIRED_OS and $REQUIRED_OS, both lists?
            DESIRED_OS="`get_desired_platform "$GLIDEIN_REQUIRED_OS" "$REQUIRED_OS"`"
            GWMS_SINGULARITY_IMAGE="`singularity_get_image default,rhel7,rhel6 cvmfs`"

            # Default TODO: check  $OSG_SINGULARITY_IMAGE_DEFAULT --> default key
            #export OSG_SINGULARITY_IMAGE="$OSG_SINGULARITY_IMAGE_DEFAULT"

# moved below, for all images, including user provided
#            # also some extra debugging and make sure CVMFS has not fallen over
#            if ! ls -l "$GWMS_SINGULARITY_IMAGE/" >/dev/null; then
#                echo "warning: unable to access $OSG_SINGULARITY_IMAGE" 1>&2
#                echo "         $OSG_SITE_NAME" `hostname -f` 1>&2
#                touch ../../.stop-glidein.stamp >/dev/null 2>&1
#                sleep 10m
#            fi
        fi

        # At this point, GWMS_SINGULARITY_IMAGE is still empty, something is wrong
        if [ -z "$GWMS_SINGULARITY_IMAGE" ]; then
            msg="\
ERROR   If you get this error when you did not specify desired OS, your VO does not support any default image
        If you get this error when you specified desired OS, your VO does not support that OS"
            exit_wrapper "$msg" 1
        fi

        # Whether user-provided or default image, we make sure it exists and make sure CVMFS has not fallen over
        # TODO: better -e or ls?
        #if ! ls -l "$GWMS_SINGULARITY_IMAGE/" >/dev/null; then
        # will both work for non expanded images?
        if [ ! -e "$GWMS_SINGULARITY_IMAGE" ]; then
            EXITSLEEP=10m
            msg="\
ERROR   Unable to access the Singularity image: $GWMS_SINGULARITY_IMAGE
        Site and node: $OSG_SITE_NAME `hostname -f`"
            # TODO: also this?: touch ../../.stop-glidein.stamp >/dev/null 2>&1
            exit_wrapper "$msg" 1
        fi


        # TODO: does it need really to exit if not in CVMFS?
        #if ! echo "$GWMS_SINGULARITY_IMAGE" | grep ^"/cvmfs" >/dev/null 2>&1; then
        #    exit_wrapper "ERROR: $GWMS_SINGULARITY_IMAGE is not in /cvmfs area. Exiting" 1
        #fi

        # Put a human readable version of the image in the env before
        # expanding it - useful for monitoring
        export GWMS_SINGULARITY_IMAGE_HUMAN="$GWMS_SINGULARITY_IMAGE"

        # for /cvmfs based directory images, expand the path without symlinks so that
        # the job can stay within the same image for the full duration
        if echo "$GWMS_SINGULARITY_IMAGE" | grep /cvmfs >/dev/null 2>&1; then
            # Make sure CVMFS is mounted in Singularity
            export GWMS_SINGULARITY_BIND_CVMFS=1
            if (cd "$GWMS_SINGULARITY_IMAGE") >/dev/null 2>&1; then
                NEW_IMAGE_PATH="`(cd $OSG_SINGULARITY_IMAGE && pwd -P) 2>/dev/null`"
                if [ "x$NEW_IMAGE_PATH" != "x" ]; then
                    GWMS_SINGULARITY_IMAGE="$NEW_IMAGE_PATH"
                fi
            fi
        fi

        # Singularity image is OK, continue w/ other init

        # set up the env to make sure Singularity uses the glidein dir for exported /tmp, /var/tmp
        if [ "x$GLIDEIN_Tmp_Dir" != "x" -a -e "$GLIDEIN_Tmp_Dir" ]; then
            export SINGULARITY_WORKDIR="$GLIDEIN_Tmp_Dir/singularity-work.$$"
        fi

        GWMS_SINGULARITY_EXTRA_OPTS=""

        GWMS_SINGULARITY_EXTRA_OPTS="$GLIDEIN_SINGULARITY_OPTS"

        # Binding different mounts (they will be removed if not existent on the host)
        # OSG: checks also in image, may not work if not expanded
        #  if [ -e $MNTPOINT/. -a -e $OSG_SINGULARITY_IMAGE/$MNTPOINT ]; then
        GWMS_SINGULARITY_WRAPPER_BINDPATHS_DEFAULTS="/hadoop,/hdfs,/lizard,/mnt/hadoop,/mnt/hdfs"

        # cvmfs access inside container (default, but optional)
        if [ "x$GWMS_SINGULARITY_BIND_CVMFS" = "x1" ]; then
            GWMS_SINGULARITY_WRAPPER_BINDPATHS_DEFAULTS="`dict_set_val /cvmfs`"
        fi
                
        # GPUs - bind outside GPU library directory to inside /host-libs
        if [ $OSG_MACHINE_GPUS -gt 0 ]; then
            if [ "x$OSG_SINGULARITY_BIND_GPU_LIBS" = "x1" ]; then
                HOST_LIBS=""
                if [ -e "/usr/lib64/nvidia" ]; then
                    HOST_LIBS=/usr/lib64/nvidia
                elif create_host_lib_dir; then
                    HOST_LIBS=$PWD/.host-libs
                fi
                if [ "x$HOST_LIBS" != "x" ]; then
                    OSG_SINGULARITY_EXTRA_OPTS="$OSG_SINGULARITY_EXTRA_OPTS --bind $HOST_LIBS:/host-libs"
                fi
                if [ -e /etc/OpenCL/vendors ]; then
                    OSG_SINGULARITY_EXTRA_OPTS="$OSG_SINGULARITY_EXTRA_OPTS --bind /etc/OpenCL/vendors:/etc/OpenCL/vendors"
                fi
            fi
        else
            # if not using gpus, we can limit the image more
            OSG_SINGULARITY_EXTRA_OPTS="$OSG_SINGULARITY_EXTRA_OPTS --contain"
        fi

        # We want to bind $PWD to /srv within the container - however, in order
        # to do that, we have to make sure everything we need is in $PWD, most
        # notably the user-job-wrapper.sh (this script!)
        cp $0 .osgvo-user-job-wrapper.sh

        # Remember what the outside pwd dir is so that we can rewrite env vars
        # pointing to omewhere inside that dir (for example, X509_USER_PROXY)
        if [ "x$_CONDOR_JOB_IWD" != "x" ]; then
            export OSG_SINGULARITY_OUTSIDE_PWD="$_CONDOR_JOB_IWD"
        else
            export OSG_SINGULARITY_OUTSIDE_PWD="$PWD"
        fi

        # build a new command line, with updated paths
        CMD=()
        for VAR in "$@"; do
            # Two seds to make sure we catch variations of the iwd,
            # including symlinked ones. The leading space is to prevent
            # echo to interpret dashes.
            VAR=`echo " $VAR" | sed -E "s;$PWD(.*);/srv\1;" | sed -E "s;.*/execute/dir_[0-9a-zA-Z]*(.*);/srv\1;" | sed -E "s;^ ;;"`
            CMD+=("$VAR")
        done

        export OSG_SINGULARITY_REEXEC=1
        exec $OSG_SINGULARITY_PATH exec $OSG_SINGULARITY_EXTRA_OPTS \
                                   --home $PWD:/srv \
                                   --pwd /srv \
                                   --ipc --pid \
                                   "$OSG_SINGULARITY_IMAGE" \
                                   /srv/.osgvo-user-job-wrapper.sh \
                                   "${CMD[@]}"
    fi
###############

if true; then
pass
    else  #if [ "x$HAS_SINGULARITY" = "x1" -a "xSINGULARITY_PATH" != "x" ];
        # Since $HAS_SINGULARITY==1, then SINGULARITY_PATH is empty
        # TODO: do not understand this, image path in CVMFS if SINGULARITY_PATH is empty?
        pass
    fi




    GWMS_SINGULARITY_EXTRA_OPTS="$GLIDEIN_SINGULARITY_OPTS"
    GWMS_SINGULARITY_WRAPPER_BINDPATHS_DEFAULTS=""
    # cvmfs access inside container (default, but optional)
    if [ "x$GWMS_SINGULARITY_BIND_CVMFS" = "x1" ]; then
        GWMS_SINGULARITY_WRAPPER_BINDPATHS_DEFAULTS="/cvmfs"
    fi

    # We want to bind $PWD to /srv within the container - however, in order
    # to do that, we have to make sure everything we need is in $PWD, most
    # notably the user-job-wrapper.sh (this script!) and singularity_util.sh (in $GWMS_AUX_SUBDIR)
    cp $0 .gwms-user-job-wrapper.sh
    export JOB_WRAPPER_SINGULARITY="/srv/.gwms-user-job-wrapper.sh"
    mkdir -p "$GWMS_AUX_SUBDIR"
    cp singularity_util.sh "$GWMS_AUX_SUBDIR/"

    # Remember what the outside pwd dir is so that we can rewrite env vars
    # pointing to somewhere inside that dir (for example, X509_USER_PROXY)
    if [ "x$_CONDOR_JOB_IWD" != "x" ]; then
        export GWMS_SINGULARITY_OUTSIDE_PWD="$_CONDOR_JOB_IWD"
    else
        export GWMS_SINGULARITY_OUTSIDE_PWD="$PWD"
    fi

    # Build a new command line, with updated paths. Returns an array in GWMS_RETURN
    singularity_update_path /srv "$@"

    info_dbg "about to invoke singularity pwd is $PWD" 
    export GWMS_SINGULARITY_REEXEC=1

    # Get Singularity binds, uses also GLIDEIN_SINGULARITY_BINDPATH, GLIDEIN_SINGULARITY_BINDPATH_DEFAULT
    singularity_binds="`singularity_get_binds e "$GWMS_SINGULARITY_WRAPPER_BINDPATHS_DEFAULTS"`"
    # Run and log the Singularity command.
    singularity_exec "$GWMS_SINGULARITY_PATH" "$GWMS_SINGULARITY_IMAGE" "$singularity_binds" \
            "$GWMS_SINGULARITY_EXTRA_OPTS" "exec" "$JOB_WRAPPER_SINGULARITY"  "${GWMS_RETURN[@]}"
    # Continuing here only if singularity invocation failed
    exit $?

fi

################################################################################
#
# Same as else, $GWMS_SINGULARITY_REEXEC not empty
# We are now inside Singularity
#

# Fix up the env
# TODO: should the environment be printed after the changes? (singularity_setup_inside)
info_dbg "running inside singularity env = "`printenv`

# Changing env variables (especially TMP and X509 related) to work w/ chrooted FS
singularity_setup_inside

# Set modules and env

# Prepend HTCondor libexec dir so that we can call chirp
if [ -e ../../main/condor/libexec ]; then
    DER="`(cd ../../main/condor/libexec; pwd)`"
    export PATH="$DER:$PATH"
fi

rm -f .gwms-user-job-wrapper.sh >/dev/null 2>&1 || true

#############################################################################
#
#  Run the real job
#
exec "$@"
error=$?
echo "Failed to exec within Singularity ($error): $@" > $_CONDOR_WRAPPER_ERROR_FILE
info "exec $@ failed in Singularity: exit code $error"
exit $error

