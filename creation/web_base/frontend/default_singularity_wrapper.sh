#!/bin/bash
# 
EXITSLEEP=5
GWMS_AUX_SUBDIR=.gwms_aux

################################################################################
#
# All code out here will run on the 1st invocation and also in the re-invocation within singularity
# $GWMS_SINGULARITY_REEXEC is used to discriminate that (nothing outside, 1 inside)
#

# Source utility files
# TODO: Check that the path works both outside and within Singularity
if [ -e singularity_util.sh ]; then
    GWMS_AUX_DIR="./"
elif [ -e /srv/.gwms_aux/singularity_util.sh ]; then
    # In Singularity
    GWMS_AUX_DIR="/srv/$GWMS_AUX_SUBDIR/"
else
    echo "ERROR: default_singularity_wrapper.sh: Unable to source singularity_util.sh! File not found. Quitting" 1>&2
    exit 1
fi
source ${GWMS_AUX_DIR}singularity_util.sh

function sleep_and_exit {
    # An error occurred. Sleep for holdtime and then exit 1
    #  1: Error message
    [ -n "$1" ] && warn_raw "ERROR: $1"
    sleep $EXITSLEEP
    exit 1
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
    if [ $HAS_SINGULARITY -eq 0 ]; then

        ################################################################################
        #
        # Run w/o Singularity
        # Assume that singularity_setup.sh removed inconsistencies
        # $HAS_SINGULARITY False means it was optional and is OK to run without
        # Run the real job and check for exec failure
        #

        info_dbg "Singularity disabled, running directly the user job via exec: $@"
        #TODO: Run user scripts out_container
        exec "$@"
        error=$?
        echo "Failed to exec($error): $@" > $_CONDOR_WRAPPER_ERROR_FILE
        info "exec $@ failed: exit code $error"
        exit $error
    fi
  
    #############################################################################
    #
    # Will run w/ Singularity - prepare for it
    # From here on the script assumes it has to run w/ Singularity
    #
    info_dbg "Decided to use singularity ($HAS_SINGULARITY). Proceeding w/ tests and setup."
 
    # GWMS we do not allow users to set SingularityAutoLoad
    export GWMS_SINGULARITY_AUTOLOAD=1
    export GWMS_SINGULARITY_BIND_CVMFS=1

    if [ "x$HAS_SINGULARITY" = "x1" -a "x$GWMS_SINGULARITY_PATH" != "x" ]; then
        # $HAS_SINGULARITY is always 1 here (checked already for 0), GWMS_SINGULARITY_PATH not empty

        # We make sure that every cvmfs repository that users specify in CVMFSReposList is available, otherwise this script exits with 1
        cvmfs_test_and_open "$CVMFS_REPOS_LIST" sleep_and_exit

        # TODO: fix image selection, using functions - will do checks - verify w/ OSG/CMS scripts
        if [ -z "$GWMS_SINGULARITY_IMAGE" ]; then
            # Use OS matching to determine default; otherwise, set to the global default.
            if [ "x$GLIDEIN_REQUIRED_OS" = "xany" ]; then
                DESIRED_OS=$REQUIRED_OS
                if [ "x$DESIRED_OS" = "xany" ]; then
                    DESIRED_OS="rhel7"
                fi
            else
                DESIRED_OS=$(python -c "print sorted(list(set('$REQUIRED_OS'.split(',')).intersection('$GLIDEIN_REQUIRED_OS'.split(','))))[0]" 2>/dev/null)
            fi

            GWMS_SINGULARITY_IMAGE="`get_singularity_image default,rhel7,rhel6 cvmfs`"

#            if [ "x$DESIRED_OS" = "x" ]; then
#                if [ "x$SINGULARITY_IMAGE_DEFAULT6" != "x" ]; then
#                    GWMS_SINGULARITY_IMAGE="$SINGULARITY_IMAGE_DEFAULT6"
#                else
#                    GWMS_SINGULARITY_IMAGE="$SINGULARITY_IMAGE_DEFAULT7"
#                fi
#            elif [ "x$DESIRED_OS" = "xrhel6" ]; then
#                GWMS_SINGULARITY_IMAGE="$SINGULARITY_IMAGE_DEFAULT6"
#            else # For now, we just enumerate RHEL6 and RHEL7.
#                GWMS_SINGULARITY_IMAGE="$SINGULARITY_IMAGE_DEFAULT7"
#            fi
        fi

        # At this point, GWMS_SINGULARITY_IMAGE is still empty, something is wrong
        if [ "x$GWMS_SINGULARITY_IMAGE" = "x" ]; then 
           echo "Error: If you get this error when you did not specify desired OS, your VO does not support any default image" 1>&2
           echo "Error: If you get this error when you specified desired OS, your VO does not support that OS" 1>&2
           exit 1
        fi

    else #if [ "x$HAS_SINGULARITY" = "x1" -a "xSINGULARITY_PATH" != "x" ];
        # Since $HAS_SINGULARITY==1, then SINGULARITY_PATH is empty
        # TODO: do not understand this, image path in CVMFS if SINGULARITY_PATH is empty?
        if ! echo "$GWMS_SINGULARITY_IMAGE" | grep ^"/cvmfs" >/dev/null 2>&1; then
            echo "warning: $GWMS_SINGULARITY_IMAGE is not in /cvmfs area" 1>&2
            exit 1
        fi
    fi

    # for /cvmfs based directory images, expand the path without symlinks so that
    # the job can stay within the same image for the full duration
    if echo "$GWMS_SINGULARITY_IMAGE" | grep /cvmfs >/dev/null 2>&1; then
        if (cd $GWMS_SINGULARITY_IMAGE) >/dev/null 2>&1; then
            NEW_IMAGE_PATH="`(cd $GWMS_SINGULARITY_IMAGE && pwd -P) 2>/dev/null`"
            if [ -n "$NEW_IMAGE_PATH" ]; then
                export GWMS_SINGULARITY_IMAGE_HUMAN="$GWMS_SINGULARITY_IMAGE"
                GWMS_SINGULARITY_IMAGE="$NEW_IMAGE_PATH"
            fi
        fi
    fi
    # whether user-provided or default image, we make sure it exists
    if [ ! -e "$GWMS_SINGULARITY_IMAGE" ]; then
        echo "Error: $GWMS_SINGULARITY_IMAGE is not found" 1>&2
        exit 1
    fi


    GWMS_SINGULARITY_EXTRA_OPTS=""
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
    mkdir -p $GWMS_AUX_SUBDIR
    cp singularity_util.sh $GWMS_AUX_SUBDIR/

    # Remember what the outside pwd dir is so that we can rewrite env vars
    # pointing to omewhere inside that dir (for example, X509_USER_PROXY)
    if [ "x$_CONDOR_JOB_IWD" != "x" ]; then
        export GWMS_SINGULARITY_OUTSIDE_PWD="$_CONDOR_JOB_IWD"
    else
        export GWMS_SINGULARITY_OUTSIDE_PWD="$PWD"
    fi

    # build a new command line, with updated paths
    CMD=""
    for VAR in "$@"; do
        # two seds to make sure we catch variations of the iwd,
        # including symlinked ones
        VAR=`echo " $VAR" | sed -E "s;$PWD(.*);/srv\1;" | sed -E "s;.*/execute/dir_[0-9a-zA-Z]*(.*);/srv\1;"`
        CMD="$CMD $VAR"
    done

    info_dbg "about to invoke singularity pwd is $PWD" 
    export GWMS_SINGULARITY_REEXEC=1

    # quote all the path strings ($GWMS_SINGULARITY_PATH, ...) to deal with a path that contains whitespaces
    info_dbg  exec "$GWMS_SINGULARITY_PATH" exec \
            `get_singularity_exec_options_string "$GWMS_SINGULARITY_WRAPPER_BINDPATHS_DEFAULTS" "" "$GWMS_SINGULARITY_EXTRA_OPTS"` \
            "$GWMS_SINGULARITY_IMAGE"  "$JOB_WRAPPER_SINGULARITY" $CMD

    exec "$GWMS_SINGULARITY_PATH" exec \
            `get_singularity_exec_options_string "$GWMS_SINGULARITY_WRAPPER_BINDPATHS_DEFAULTS" "" "$GWMS_SINGULARITY_EXTRA_OPTS"` \
            "$GWMS_SINGULARITY_IMAGE" "$JOB_WRAPPER_SINGULARITY"  $CMD

    # Continues here only if singularity invocation failed
    error=$?
    echo "Failed to exec singularity ($error): exec \"$GWMS_SINGULARITY_PATH\" exec \
            `get_singularity_exec_options_string "$GWMS_SINGULARITY_WRAPPER_BINDPATHS_DEFAULTS" "" "$GWMS_SINGULARITY_EXTRA_OPTS"` \
            \"$GWMS_SINGULARITY_IMAGE\"  \"$JOB_WRAPPER_SINGULARITY\" $CMD" > $_CONDOR_WRAPPER_ERROR_FILE
    info "exec of singularity failed: exit code $error"
    exit $error

fi

################################################################################
#
# Same as else, $GWMS_SINGULARITY_REEXEC not empty
# We are now inside Singularity
#

# Fix up the env
# TODO: should the environment be printed after the changes? (setup_in_singularity)
info_dbg "running inside singularity env = "`printenv`

# Changing env variables (especially TMP and X509 related) to work w/ chrooted FS
setup_in_singularity

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

