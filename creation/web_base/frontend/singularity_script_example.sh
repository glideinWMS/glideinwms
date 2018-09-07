#!/bin/bash
# 
EXITSLEEP=5
# Change the variable to control the exit code returned
EXIT_CODE=0
# Change this possibly to a unique name
GWMS_THIS_SCRIPT=singularity_script_example
GWMS_THIS_SCRIPT_DIR="`dirname "$0"`"
GWMS_AUX_SUBDIR=.gwms_aux


##############################################
#
# Check below for the
# ADD HERE ....
# sections to add your code that you want to run inside Singularity, outside, or both times
#


################################################################################
#
# All code out here will run on the 1st invocation (whether Singularity is wanted or not)
# and also in the re-invocation within Singularity
# $HAS_SINGLARITY is used to discriminate if Singularity is desired (is 1) or not
# $GWMS_SINGULARITY_REEXEC is used to discriminate the re-execution (nothing outside, 1 inside)
#



function exit_script {
    # An error occurred. Communicate to HTCondor and avoid black hole (sleep for hold time) and then exit 1
    #  1: Error message
    #  2: Exit code (1 by default)
    #  3: sleep time (default: $EXITSLEEP)
    [ -n "$1" ] && warn_raw "ERROR: $1"
    local exit_code=${2:-1}
    # Publish the error so that HTCondor understands that is a wrapper error and retries the job
    if [ -n "$_CONDOR_WRAPPER_ERROR_FILE" ]; then
        warn "Example script failed, creating condor log file: $_CONDOR_WRAPPER_ERROR_FILE"
    fi
    sleep $EXITSLEEP
    exit $exit_code
}

# In case singularity_lib cannot be imported
function warn_raw {
    echo "$@" 1>&2
}

[ -z "$glidein_config" ] && [ -e "$GWMS_THIS_SCRIPT_DIR/../glidein_config" ] &&
    glidein_config="$GWMS_THIS_SCRIPT_DIR/../glidein_config"

# error_gen defined in singularity_lib.sh
[ -e "$glidein_config" ] && error_gen=$(grep '^ERROR_GEN_PATH ' "$glidein_config" | awk '{print $2}')


# Source utility files, outside and inside Singularity
# condor_job_wrapper is in the base directory, singularity_lib.sh in main
# and copied to RUNDIR/$GWMS_AUX_SUBDIR (RUNDIR becomes /srv in Singularity)
if [ -e "$GWMS_THIS_SCRIPT_DIR/singularity_lib.sh" ]; then
    GWMS_AUX_DIR="$GWMS_THIS_SCRIPT_DIR/"
elif [ -e /srv/$GWMS_AUX_SUBDIR/singularity_lib.sh ]; then
    # In Singularity
    GWMS_AUX_DIR="/srv/$GWMS_AUX_SUBDIR/"
else
    echo "ERROR: $GWMS_THIS_SCRIPT: Unable to source singularity_lib.sh! File not found. Quitting" 1>&2
    warn=warn_raw
    exit_script "Wrapper script $GWMS_THIS_SCRIPT failed: Unable to source singularity_lib.sh" 1
fi
source ${GWMS_AUX_DIR}singularity_lib.sh

info_dbg "GWMS singularity wrapper starting, `date`. Imported singularity_util.sh. glidein_config ($glidein_config). $GWMS_THIS_SCRIPT, in `pwd`: `ls -al`"

function exit_or_fallback {
    # An error in Singularity occurred. Fallback to no Singularity if preferred or fail if required
    # If this function returns, then is OK to fall-back to no Singularity (otherwise it will exit)
    # OSG is continuing after sleep, no fall-back, no exit
    # In
    #  1: Error message
    #  2: Exit code (1 by default)
    #  3: sleep time (default: $EXITSLEEP)
    #  $GWMS_SINGULARITY_STATUS
    if [ "x$GWMS_SINGULARITY_STATUS" = "xPREFERRED" ]; then
        # Fall back to no Singularity
        export HAS_SINGULARITY=0
        export GWMS_SINGULARITY_PATH=
        export GWMS_SINGULARITY_REEXEC=
        [ -n "$1" ] && warn "$1"
        warn "An error in Singularity occurred, but can fall-back to no Singularity ($GWMS_SINGULARITY_STATUS). Continuing"
    else
        exit_script "${@}"
    fi
}


function prepare_and_invoke_singularity {
    # Code moved into a function to allow early return in case of failure
    # In:
    #   SINGULARITY_IMAGES_DICT: dictionary w/ Singularity images
    #   $SINGULARITY_IMAGE_RESTRICTIONS: constraints on the Singularity image

    # If  image is not provided, load the default one
    # Custom URIs: http://singularity.lbl.gov/user-guide#supported-uris
    if [ -z "$GWMS_SINGULARITY_IMAGE" ]; then
        # No image requested by the job
        # Use OS matching to determine default; otherwise, set to the global default.
        DESIRED_OS="`list_get_intersection "${GLIDEIN_REQUIRED_OS:-any}" "${REQUIRED_OS:-any}"`"
        if [ -z "$DESIRED_OS" ]; then
            msg="ERROR   VO (or job) REQUIRED_OS and Entry GLIDEIN_REQUIRED_OS have no intersection. Cannot select a Singularity image."
            exit_or_fallback "$msg" 1
            return
        fi
        if [ "x$DESIRED_OS" = xany ]; then
            # Prefer the platforms default,rhel7,rhel6, otherwise pick the first one available
            GWMS_SINGULARITY_IMAGE="`singularity_get_image default,rhel7,rhel6 ${SINGULARITY_IMAGE_RESTRICTIONS:+$SINGULARITY_IMAGE_RESTRICTIONS,}any`"
        else
            GWMS_SINGULARITY_IMAGE="`singularity_get_image "$DESIRED_OS" $SINGULARITY_IMAGE_RESTRICTIONS`"
        fi
    fi

    # At this point, GWMS_SINGULARITY_IMAGE is still empty, something is wrong
    if [ -z "$GWMS_SINGULARITY_IMAGE" ]; then
        msg="\
ERROR   If you get this error when you did not specify required OS, your VO does not support any valid default Singularity image
        If you get this error when you specified required OS, your VO does not support any valid image for that OS"
        exit_or_fallback "$msg" 1
        return
    fi

    # Whether user-provided or default image, we make sure it exists and make sure CVMFS has not fallen over
    if [ ! -e "$GWMS_SINGULARITY_IMAGE" ]; then
        msg="\
ERROR   Unable to access the Singularity image: $GWMS_SINGULARITY_IMAGE
        Site and node: $OSG_SITE_NAME `hostname -f`"
        exit_or_fallback "$msg" 1
        return
    fi

    # Put a human readable version of the image in the env before
    # expanding it - useful for monitoring
    export GWMS_SINGULARITY_IMAGE_HUMAN="$GWMS_SINGULARITY_IMAGE"

    # for /cvmfs based directory images, expand the path without symlinks so that
    # the job can stay within the same image for the full duration
    if echo "$GWMS_SINGULARITY_IMAGE" | grep /cvmfs >/dev/null 2>&1; then
        # Make sure CVMFS is mounted in Singularity
        export GWMS_SINGULARITY_BIND_CVMFS=1
        if (cd "$GWMS_SINGULARITY_IMAGE") >/dev/null 2>&1; then
            # This will fail for images that are not expanded in CVMFS, just ignore the failure
            NEW_IMAGE_PATH="`(cd "$GWMS_SINGULARITY_IMAGE" && pwd -P) 2>/dev/null`"
            if [ "x$NEW_IMAGE_PATH" != "x" ]; then
                GWMS_SINGULARITY_IMAGE="$NEW_IMAGE_PATH"
            fi
        fi
    fi

    info_dbg "using image $GWMS_SINGULARITY_IMAGE_HUMAN ($GWMS_SINGULARITY_IMAGE)"
    # Singularity image is OK, continue w/ other init

    # set up the env to make sure Singularity uses the glidein dir for exported /tmp, /var/tmp
    if [ "x$GLIDEIN_Tmp_Dir" != "x" -a -e "$GLIDEIN_Tmp_Dir" ]; then
        export SINGULARITY_WORKDIR="$GLIDEIN_Tmp_Dir/singularity-work.$$"
    fi

    GWMS_SINGULARITY_EXTRA_OPTS="$GLIDEIN_SINGULARITY_OPTS"

    # Binding different mounts (they will be removed if not existent on the host)
    # OSG: checks also in image, may not work if not expanded. And Singularity will not fail if missing, only give a warning
    #  if [ -e $MNTPOINT/. -a -e $OSG_SINGULARITY_IMAGE/$MNTPOINT ]; then
    GWMS_SINGULARITY_WRAPPER_BINDPATHS_DEFAULTS="/hadoop,/hdfs,/lizard,/mnt/hadoop,/mnt/hdfs"

    # CVMFS access inside container (default, but optional)
    if [ "x$GWMS_SINGULARITY_BIND_CVMFS" = "x1" ]; then
        GWMS_SINGULARITY_WRAPPER_BINDPATHS_DEFAULTS="`dict_set_val GWMS_SINGULARITY_WRAPPER_BINDPATHS_DEFAULTS /cvmfs`"
    fi

    # GPUs - bind outside GPU library directory to inside /host-libs
    if [ $OSG_MACHINE_GPUS -gt 0 ]; then
        if [ "x$OSG_SINGULARITY_BIND_GPU_LIBS" = "x1" ]; then
            HOST_LIBS=""
            if [ -e "/usr/lib64/nvidia" ]; then
                HOST_LIBS=/usr/lib64/nvidia
            elif create_host_lib_dir; then
                HOST_LIBS="$PWD/.host-libs"
            fi
            if [ "x$HOST_LIBS" != "x" ]; then
                GWMS_SINGULARITY_WRAPPER_BINDPATHS_DEFAULTS="`dict_set_val GWMS_SINGULARITY_WRAPPER_BINDPATHS_DEFAULTS "$HOST_LIBS" /host-libs`"
            fi
            if [ -e /etc/OpenCL/vendors ]; then
                GWMS_SINGULARITY_WRAPPER_BINDPATHS_DEFAULTS="`dict_set_val GWMS_SINGULARITY_WRAPPER_BINDPATHS_DEFAULTS /etc/OpenCL/vendors /etc/OpenCL/vendors`"
            fi
        fi
    else
        # if not using gpus, we can limit the image more
        GWMS_SINGULARITY_EXTRA_OPTS="$GWMS_SINGULARITY_EXTRA_OPTS --contain"
    fi
    info_dbg "bind-path default (cvmfs:$GWMS_SINGULARITY_BIND_CVMFS, hostlib:`[ -n "$HOST_LIBS" ] && echo 1`, ocl:`[ -e /etc/OpenCL/vendors ] && echo 1`): $GWMS_SINGULARITY_WRAPPER_BINDPATHS_DEFAULTS"

    # We want to bind $PWD to /srv within the container - however, in order
    # to do that, we have to make sure everything we need is in $PWD, most
    # notably the user-job-wrapper.sh (this script!) and singularity_util.sh (in $GWMS_AUX_SUBDIR)
    cp "$GWMS_THIS_SCRIPT" .gwms-user-job-wrapper.sh
    export JOB_WRAPPER_SINGULARITY="/srv/.gwms-user-job-wrapper.sh"
    mkdir -p "$GWMS_AUX_SUBDIR"
    cp "${GWMS_AUX_DIR}singularity_lib.sh" "$GWMS_AUX_SUBDIR/"

    # Remember what the outside pwd dir is so that we can rewrite env vars
    # pointing to somewhere inside that dir (for example, X509_USER_PROXY)
    if [ "x$_CONDOR_JOB_IWD" != "x" ]; then
        export GWMS_SINGULARITY_OUTSIDE_PWD="$_CONDOR_JOB_IWD"
    else
        export GWMS_SINGULARITY_OUTSIDE_PWD="$PWD"
    fi

    # Build a new command line, with updated paths. Returns an array in GWMS_RETURN
    singularity_update_path /srv "$@"

    # Get Singularity binds, uses also GLIDEIN_SINGULARITY_BINDPATH, GLIDEIN_SINGULARITY_BINDPATH_DEFAULT
    # remove binds w/ non existing src (e)
    singularity_binds="`singularity_get_binds e "$GWMS_SINGULARITY_WRAPPER_BINDPATHS_DEFAULTS"`"
    # Run and log the Singularity command.
    info_dbg "about to invoke singularity, pwd is $PWD"
    export GWMS_SINGULARITY_REEXEC=1
    singularity_exec "$GWMS_SINGULARITY_PATH" "$GWMS_SINGULARITY_IMAGE" "$singularity_binds" \
            "$GWMS_SINGULARITY_EXTRA_OPTS" "exec" "$JOB_WRAPPER_SINGULARITY"  "${GWMS_RETURN[@]}"

    # Continuing here only if exec of singularity failed
    GWMS_SINGULARITY_REEXEC=0
    exit_or_fallback "exec of singularity failed" $?
}


#################### main ###################


################################################################################
#
# Outside and Inside Singularity - This is before any setup
#


if [ -z "$GWMS_SINGULARITY_REEXEC" ]; then

    ################################################################################
    #
    # Outside Singularity - Run this only on the 1st invocation
    #

    info_dbg "GWMS singulartity example, first invocation"

    # Set up environment to know if Singularity is enabled and so we can execute Singularity
    setup_classad_variables

    # Check if singularity is disabled or enabled
    # This script could run when singularity is optional and not wanted
    # So should not fail but exec w/o running Singularity

    #################
    #
    # ADD HERE your code that you want to run only OUTSIDE Singularity
    #
    #################


    if [ "x$HAS_SINGULARITY" = "x1" -a "x$GWMS_SINGULARITY_PATH" != "x" ]; then
        #############################################################################
        #
        # Will run w/ Singularity - prepare for it
        # From here on the script assumes it has to run w/ Singularity
        #
        info_dbg "Decided to use singularity ($HAS_SINGULARITY, $GWMS_SINGULARITY_PATH). Proceeding w/ tests and setup."

        # We make sure that every cvmfs repository that users specify in CVMFSReposList is available, otherwise this script exits with 1
        cvmfs_test_and_open "$CVMFS_REPOS_LIST" exit_script

        prepare_and_invoke_singularity "$@"

        # If we arrive here, then something failed in Singularity but is OK to continue w/o

    else  #if [ "x$HAS_SINGULARITY" = "x1" -a "xSINGULARITY_PATH" != "x" ];
        # First execution, no Singularity.
        info_dbg "GWMS singulartity example, first invocation, not using singularity ($HAS_SINGULARITY, $GWMS_SINGULARITY_PATH)"

        #################
        #
        # ADD HERE your code that you want to run only OUTSIDE Singularity if Singularity is not used
        #
        #################


    fi

else
    ################################################################################
    #
    # $GWMS_SINGULARITY_REEXEC not empty
    # We are now inside Singularity
    #

    # Changing env variables (especially TMP and X509 related) to work w/ chrooted FS
    singularity_setup_inside
    info_dbg "GWMS singulartity example, running inside singularity env = "`printenv`

    #################
    #
    # ADD HERE your code that you want to run only INSIDE Singularity
    #
    #################


fi

################################################################################
#
# Setup for job execution
# This section will be executed:
# - in Singularity (if $GWMS_SINGULARITY_REEXEC not empty)
# - if is OK to run w/o Singularity ( $HAS_SINGULARITY" not true OR $GWMS_SINGULARITY_PATH" empty )
# - if setup or exec of singularity failed (it is possible to fall-back)
#

info_dbg "GWMS singulartity example, final setup."

#############
#
# ADD HERE some setup (condor, stashcache, ...), see default_singularity_wrapper.sh for examples
#
#############

##############################
#
#  Cleanup
#
rm -f .gwms-${SCRIPT_NAME} >/dev/null 2>&1 || true


##############################
#
# Run the real job
#
# ADD HERE below your code that you want to run INSIDE Singularity or if Singularity is not available
#
#################


exit $EXIT_CODE



