#!/bin/bash
# 
EXITSLEEP=10m
GWMS_AUX_SUBDIR=.gwms_aux
GWMS_THIS_SCRIPT="$0"
GWMS_THIS_SCRIPT_DIR="`dirname "$0"`"

################################################################################
#
# All code out here will run on the 1st invocation (whether Singularity is wanted or not)
# and also in the re-invocation within Singularity
# $HAS_SINGLARITY is used to discriminate if Singularity is desired (is 1) or not
# $GWMS_SINGULARITY_REEXEC is used to discriminate the re-execution (nothing outside, 1 inside)
#


# When failing we need to tell HTCondor to put the job back in the queue by creating
# a file in the PATH pointed by $_CONDOR_WRAPPER_ERROR_FILE
# Make sure there is no leftover wrapper error file (if the file exists HTCondor assumes the wrapper failed)
[ -n "$_CONDOR_WRAPPER_ERROR_FILE" ] && rm -f "$_CONDOR_WRAPPER_ERROR_FILE" >/dev/null 2>&1 || true


function exit_wrapper {
    # An error occurred. Communicate to HTCondor and avoid black hole (sleep for hold time) and then exit 1
    #  1: Error message
    #  2: Exit code (1 by default)
    #  3: sleep time (default: $EXITSLEEP)
    [ -n "$1" ] && warn_raw "ERROR: $1"
    local exit_code=${2:-1}
    # Publish the error so that HTCondor understands that is a wrapper error and retries the job
    if [ -n "$_CONDOR_WRAPPER_ERROR_FILE" ]; then
        warn "Wrapper script failed, creating condor log file: $_CONDOR_WRAPPER_ERROR_FILE"
        echo "Wrapper script $GWMS_THIS_SCRIPT failed ($exit_code): $1" >> $_CONDOR_WRAPPER_ERROR_FILE
    fi
    #  TODO: Add termination stamp? see OSG
    #              touch ../../.stop-glidein.stamp >/dev/null 2>&1
    # Eventually the periodic validation of singularity will make the pilot
    # to stop matching new payloads
    # Prevent a black hole by sleeping EXITSLEEP (10) minutes before exiting. Sleep time can be changed on top of this file
    sleep $EXITSLEEP
    exit $exit_code
}

# In case singularity_lib cannot be imported
function warn_raw {
    echo "$@" 1>&2
}

[ -z "$glidein_config" ] && [ -e "$GWMS_THIS_SCRIPT_DIR/glidein_config" ] &&
    glidein_config="$GWMS_THIS_SCRIPT_DIR/glidein_config"

# error_gen defined in singularity_lib.sh
[ -e "$glidein_config" ] && error_gen=$(grep '^ERROR_GEN_PATH ' "$glidein_config" | awk '{print $2}')


# Source utility files, outside and inside Singularity
# condor_job_wrapper is in the base directory, singularity_lib.sh in main
# and copied to RUNDIR/$GWMS_AUX_SUBDIR (RUNDIR becomes /srv in Singularity)
if [ -e "$GWMS_THIS_SCRIPT_DIR/main/singularity_lib.sh" ]; then
    GWMS_AUX_DIR="$GWMS_THIS_SCRIPT_DIR/main/"
elif [ -e /srv/$GWMS_AUX_SUBDIR/singularity_lib.sh ]; then
    # In Singularity
    GWMS_AUX_DIR="/srv/$GWMS_AUX_SUBDIR/"
else
    echo "ERROR: $GWMS_THIS_SCRIPT: Unable to source singularity_lib.sh! File not found. Quitting" 1>&2
    warn=warn_raw
    exit_wrapper "Wrapper script $GWMS_THIS_SCRIPT failed: Unable to source singularity_lib.sh" 1
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
        exit_wrapper "${@}"
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
        #  # Correct some legacy names? What if they are used in the dictionary?
        #  REQUIRED_OS="`echo ",$REQUIRED_OS," | sed "s/,el7,/,rhel7,/;s/,el6,/,rhel6,/;s/,+/,/g;s/^,//;s/,$//"`"
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

    # TODO: Custom images are not subject to SINGULARITY_IMAGE_RESTRICTIONS in OSG and CMS scripts. Should add a check here?
    #if ! echo "$GWMS_SINGULARITY_IMAGE" | grep ^"/cvmfs" >/dev/null 2>&1; then
    #    exit_wrapper "ERROR: $GWMS_SINGULARITY_IMAGE is not in /cvmfs area. Exiting" 1
    #fi

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

if [ -z "$GWMS_SINGULARITY_REEXEC" ]; then

    ################################################################################
    #
    # Outside Singularity - Run this only on the 1st invocation
    #

    info_dbg "GWMS singularity wrapper, first invocation"

    # Set up environment to know if Singularity is enabled and so we can execute Singularity
    setup_classad_variables

    # Check if singularity is disabled or enabled
    # This script could run when singularity is optional and not wanted
    # So should not fail but exec w/o running Singularity

    if [ "x$HAS_SINGULARITY" = "x1" -a "x$GWMS_SINGULARITY_PATH" != "x" ]; then
        #############################################################################
        #
        # Will run w/ Singularity - prepare for it
        # From here on the script assumes it has to run w/ Singularity
        #
        info_dbg "Decided to use singularity ($HAS_SINGULARITY, $GWMS_SINGULARITY_PATH). Proceeding w/ tests and setup."

        # We make sure that every cvmfs repository that users specify in CVMFSReposList is available, otherwise this script exits with 1
        cvmfs_test_and_open "$CVMFS_REPOS_LIST" exit_wrapper

        prepare_and_invoke_singularity "$@"

        # If we arrive here, then something failed in Singularity but is OK to continue w/o

    else  #if [ "x$HAS_SINGULARITY" = "x1" -a "xSINGULARITY_PATH" != "x" ];
        # First execution, no Singularity.
        info_dbg "GWMS singularity wrapper, first invocation, not using singularity ($HAS_SINGULARITY, $GWMS_SINGULARITY_PATH)"
    fi

else
    ################################################################################
    #
    # $GWMS_SINGULARITY_REEXEC not empty
    # We are now inside Singularity
    #

    # Changing env variables (especially TMP and X509 related) to work w/ chrooted FS
    singularity_setup_inside
    info_dbg "GWMS singularity wrapper, running inside singularity env = "`printenv`



fi

################################################################################
#
# Setup for job execution
# This section will be executed:
# - in Singularity (if $GWMS_SINGULARITY_REEXEC not empty)
# - if is OK to run w/o Singularity ( $HAS_SINGULARITY" not true OR $GWMS_SINGULARITY_PATH" empty )
# - if setup or exec of singularity failed (it is possible to fall-back)
#

info_dbg "GWMS singularity wrapper, final setup."

#############################
#
#  modules and env
#

# TODO: not needed here? It is in singularity_setup_inside for when Singularity is invoked, and should be already in the PATH when it is not
# Checked - glidin_startup seems not to add condor to the path
# Add Glidein provided HTCondor back to the environment (so that we can call chirp) - same is in
# TODO: what if original and Singularity OS are incompatible? Should check and avoid adding condor back?
if [ -e ../../main/condor/libexec ]; then
    DER="`(cd ../../main/condor; pwd)`"
    export PATH="$DER/libexec:$PATH"
    # TODO: Check if LD_LIBRARY_PATH is needed or OK because of RUNPATH
    # export LD_LIBRARY_PATH="$DER/lib:$LD_LIBRARY_PATH"
fi

# fix discrepancy for Squid proxy URLs
if [ "x$GLIDEIN_Proxy_URL" = "x" -o "$GLIDEIN_Proxy_URL" = "None" ]; then
    if [ "x$OSG_SQUID_LOCATION" != "x" -a "$OSG_SQUID_LOCATION" != "None" ]; then
        export GLIDEIN_Proxy_URL="$OSG_SQUID_LOCATION"
    fi
fi

# load modules, if available
#MODULE_USE
[ "x$LMOD_BETA" = "x1" ] && MODULE_USE=1
if [ "x$MODULE_USE" = "x1" ]; then
    if [ "x$LMOD_BETA" = "x1" ]; then
        # used for testing the new el6/el7 modules
        if [ -e /cvmfs/oasis.opensciencegrid.org/osg/sw/module-beta-init.sh ]; then
            . /cvmfs/oasis.opensciencegrid.org/osg/sw/module-beta-init.sh
        fi
    elif [ -e /cvmfs/oasis.opensciencegrid.org/osg/sw/module-init.sh ]; then
        . /cvmfs/oasis.opensciencegrid.org/osg/sw/module-init.sh
    fi
    module -v >/dev/null 2>&1
    if [ $? -ne 0 ]; then
        MODULE_USE=0
    fi
fi

#############################
#
#  Stash cache
#

function setup_stashcp {
    if [ "x$MODULE_USE" != "x1" ]; then
        warn "Module unavailable. Unable to setup Stash cache."
        return 1
    fi

    module load stashcp

    # we need xrootd, which is available both in the OSG software stack
    # as well as modules - use the system one by default
    if ! which xrdcp >/dev/null 2>&1; then
      module load xrootd
    fi

    # Determine XRootD plugin directory.
    # in lieu of a MODULE_<name>_BASE from lmod, this will do:
    export MODULE_XROOTD_BASE="$(which xrdcp | sed -e 's,/bin/.*,,')"
    export XRD_PLUGINCONFDIR="$MODULE_XROOTD_BASE/etc/xrootd/client.plugins.d"

}

# Check for PosixStashCache first
if [ "x$POSIXSTASHCACHE" = "x1" ]; then
    setup_stashcp
    if [ $? -eq 0 ]; then

        # Add the LD_PRELOAD hook
        export LD_PRELOAD="$MODULE_XROOTD_BASE/lib64/libXrdPosixPreload.so:$LD_PRELOAD"

        # Set proxy for virtual mount point
        # Format: cache.domain.edu/local_mount_point=/storage_path
        # E.g.: export XROOTD_VMP=data.ci-connect.net:/stash=/
        # Currently this points _ONLY_ to the OSG Connect source server
        export XROOTD_VMP=$(stashcp --closest | cut -d'/' -f3):/stash=/
    fi
elif [ "x$STASHCACHE" = "x1" ]; then
    setup_stashcp
fi

if [ "x$STASHCACHE_WRITABLE" = "x1" ]; then
    setup_stashcp
    if [ $? -eq 0 ]; then
        export PATH="/cvmfs/oasis.opensciencegrid.org/osg/projects/stashcp/writeback:$PATH"
    fi
fi


################################
#
#  Load user specified modules
#
if [ "X$LoadModules" != "X" ]; then
    if [ "x$MODULE_USE" != "x1" ]; then
        warn "Module unavailable. Unable to load desired modules: $LoadModules"
    else
        ModuleList=`echo $LoadModules | sed 's/^LoadModules = //i;s/"//g'`
        for Module in $ModuleList; do
            info_dbg "Loading module: $Module"
            module load $Module
        done
    fi
fi

# TODO: This is OSG specific. Should there be something similar in GWMS?
###############################
#
#  Trace callback
#
#
#if [ ! -e .trace-callback ]; then
#    (wget -nv -O .trace-callback http://osg-vo.isi.edu/osg/agent/trace-callback && chmod 755 .trace-callback) >/dev/null 2>&1 || /bin/true
#fi
#./.trace-callback start >/dev/null 2>&1 || /bin/true
#rm -f .trace-callback >/dev/null 2>&1 || true

##############################
#
#  Cleanup
#
# Aux dir in the future mounted read only. Remove the directory if in Singularity
# TODO: should always auxdir be copied and removed? Should be left for the job?
[[ "$GWMS_AUX_SUBDIR/" == /srv/* ]] && rm -rf "$GWMS_AUX_SUBDIR/" >/dev/null 2>&1 || true
rm -f .gwms-user-job-wrapper.sh >/dev/null 2>&1 || true

##############################
#
#  Run the real job
#
info_dbg "current directory at execution (`pwd`): `ls -al`"
info_dbg "GWMS singularity wrapper, job exec: $@"
info_dbg "GWMS singularity wrapper, messages after this line are from the actual job ##################"
exec "$@"
error=$?
# exec failed. Log, communicate to HTCondor, avoid black hole and exit
exit_wrapper "exec failed  (Singularity:$GWMS_SINGULARITY_REEXEC, exit code:$error): $@" $error
