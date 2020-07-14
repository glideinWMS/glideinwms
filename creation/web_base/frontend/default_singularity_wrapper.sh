#!/bin/bash
# GlideinWMS singularity wrapper. Invoked by HTCondor as user_job_wrapper
# default_singularity_wrapper USER_JOB [job options and arguments]
EXITSLEEP=10m
GWMS_AUX_SUBDIR=.gwms_aux
GWMS_THIS_SCRIPT="$0"
GWMS_THIS_SCRIPT_DIR="`dirname "$0"`"
GWMS_VERSION_SINGULARITY_WRAPPER=20200413
# Updated using OSG wrapper #5d8b3fa9b258ea0e6640727405f20829d2c5d4b9
# https://github.com/opensciencegrid/osg-flock/blob/master/job-wrappers/user-job-wrapper.sh
# Link to the CMS wrapper
# https://gitlab.cern.ch/CMSSI/CMSglideinWMSValidation/-/blob/master/singularity_wrapper.sh

################################################################################
#
# All code out here will run on the 1st invocation (whether Singularity is wanted or not)
# and also in the re-invocation within Singularity
# $HAS_SINGLARITY is used to discriminate if Singularity is desired (is 1) or not
# $GWMS_SINGULARITY_REEXEC is used to discriminate the re-execution (nothing outside, 1 inside)
#

# To avoid GWMS debug and info messages in the job stdout/err (unless userjob option is set)
[[ ! ",${GLIDEIN_DEBUG_OPTIONS}," = *,userjob,* ]] && GLIDEIN_QUIET=True
[[ ! ",${GLIDEIN_DEBUG_OPTIONS}," = *,nowait,* ]] && EXITSLEEP=2m  # leave 2min to update classad

# When failing we need to tell HTCondor to put the job back in the queue by creating
# a file in the PATH pointed by $_CONDOR_WRAPPER_ERROR_FILE
# Make sure there is no leftover wrapper error file (if the file exists HTCondor assumes the wrapper failed)
[[ -n "$_CONDOR_WRAPPER_ERROR_FILE" ]] && rm -f "$_CONDOR_WRAPPER_ERROR_FILE" >/dev/null 2>&1 || true


exit_wrapper () {
    # An error occurred. Communicate to HTCondor and avoid black hole (sleep for hold time) and then exit 1
    #  1: Error message
    #  2: Exit code (1 by default)
    #  3: sleep time (default: $EXITSLEEP)
    # The error is published to stderr, if available to $_CONDOR_WRAPPER_ERROR_FILE,
    # if chirp available sets JobWrapperFailure
    [[ -n "$1" ]] && warn_raw "ERROR: $1"
    local exit_code=${2:-1}
    local sleep_time=${3:-$EXITSLEEP}
    local publish_fail
    # Publish the error so that HTCondor understands that is a wrapper error and retries the job
    if [[ -n "$_CONDOR_WRAPPER_ERROR_FILE" ]]; then
        warn "Wrapper script failed, creating condor log file: $_CONDOR_WRAPPER_ERROR_FILE"
        echo "Wrapper script $GWMS_THIS_SCRIPT failed ($exit_code): $1" >> $_CONDOR_WRAPPER_ERROR_FILE
    else
        publish_fail="HTCondor error file"
    fi
    # also chirp
    if [[ -e ../../main/condor/libexec/condor_chirp ]]; then
        ../../main/condor/libexec/condor_chirp set_job_attr JobWrapperFailure "Wrapper script $GWMS_THIS_SCRIPT failed ($exit_code): $1"
    else
        [[ -n "$publish_fail" ]] && publish_fail="${publish_fail} and "
        publish_fail="${publish_fail}condor_chirp"
    fi

    [[ -n "$publish_fail" ]] && warn "Failed to communicate ERROR with ${publish_fail}"

    #  TODO: Add termination stamp? see OSG
    #              touch ../../.stop-glidein.stamp >/dev/null 2>&1
    # Eventually the periodic validation of singularity will make the pilot
    # to stop matching new payloads
    # Prevent a black hole by sleeping EXITSLEEP (10) minutes before exiting. Sleep time can be changed on top of this file
    sleep $sleep_time
    exit $exit_code
}

# In case singularity_lib cannot be imported
warn_raw () {
    echo "$@" 1>&2
}

# Ensure all jobs have PATH set
# bash can set a default PATH - make sure it is exported
export PATH=$PATH
[[ -z "$PATH" ]] && export PATH="/usr/local/bin:/usr/bin:/bin"

[[ -z "$glidein_config" ]] && [[ -e "$GWMS_THIS_SCRIPT_DIR/glidein_config" ]] &&
    glidein_config="$GWMS_THIS_SCRIPT_DIR/glidein_config"

# error_gen defined also in singularity_lib.sh
[[ -e "$glidein_config" ]] && error_gen="$(grep '^ERROR_GEN_PATH ' "$glidein_config" | cut -d ' ' -f 2-)"


# Source utility files, outside and inside Singularity
# condor_job_wrapper is in the base directory, singularity_lib.sh in main
# and copied to RUNDIR/$GWMS_AUX_SUBDIR (RUNDIR becomes /srv in Singularity)
if [[ -e "$GWMS_THIS_SCRIPT_DIR/main/singularity_lib.sh" ]]; then
    GWMS_AUX_DIR="$GWMS_THIS_SCRIPT_DIR/main/"
elif [[ -e /srv/$GWMS_AUX_SUBDIR/singularity_lib.sh ]]; then
    # In Singularity
    GWMS_AUX_DIR="/srv/$GWMS_AUX_SUBDIR/"
else
    echo "ERROR: $GWMS_THIS_SCRIPT: Unable to source singularity_lib.sh! File not found. Quitting" 1>&2
    warn=warn_raw
    exit_wrapper "Wrapper script $GWMS_THIS_SCRIPT failed: Unable to source singularity_lib.sh" 1
fi
source ${GWMS_AUX_DIR}singularity_lib.sh

# Calculating full version number, including md5 sums form the wrapper and singularity_lib
GWMS_VERSION_SINGULARITY_WRAPPER="$GWMS_VERSION_SINGULARITY_WRAPPER_$(md5sum "$GWMS_THIS_SCRIPT" 2>/dev/null | cut -d ' ' -f1)_$(md5sum "${GWMS_AUX_DIR}singularity_lib.sh" 2>/dev/null | cut -d ' ' -f1)"
info_dbg "GWMS singularity wrapper ($GWMS_VERSION_SINGULARITY_WRAPPER_) starting, `date`. Imported singularity_lib.sh. glidein_config ($glidein_config)."
info_dbg "$GWMS_THIS_SCRIPT, in `pwd`, list: `ls -al`"

exit_or_fallback () {
    # An error in Singularity occurred. Fallback to no Singularity if preferred or fail if required
    # If this function returns, then is OK to fall-back to no Singularity (otherwise it will exit)
    # OSG is continuing after sleep, no fall-back, no exit
    # In
    #  1: Error message
    #  2: Exit code (1 by default)
    #  3: sleep time (default: $EXITSLEEP)
    #  $GWMS_SINGULARITY_STATUS
    if [[ "x$GWMS_SINGULARITY_STATUS" = "xPREFERRED" ]]; then
        # Fall back to no Singularity
        export HAS_SINGULARITY=0
        export GWMS_SINGULARITY_PATH=
        export GWMS_SINGULARITY_REEXEC=
        [[ -n "$1" ]] && warn "$1"
        warn "An error in Singularity occurred, but can fall-back to no Singularity ($GWMS_SINGULARITY_STATUS). Continuing"
    else
        exit_wrapper "${@}"
    fi
}


prepare_and_invoke_singularity () {
    # Code moved into a function to allow early return in case of failure
    # In:
    #   SINGULARITY_IMAGES_DICT: dictionary w/ Singularity images
    #   $SINGULARITY_IMAGE_RESTRICTIONS: constraints on the Singularity image

    # If  image is not provided, load the default one
    # Custom URIs: http://singularity.lbl.gov/user-guide#supported-uris
    if [[ -z "$GWMS_SINGULARITY_IMAGE" ]]; then
        # No image requested by the job
        # Use OS matching to determine default; otherwise, set to the global default.
        #  # Correct some legacy names? What if they are used in the dictionary?
        #  REQUIRED_OS="`echo ",$REQUIRED_OS," | sed "s/,el7,/,rhel7,/;s/,el6,/,rhel6,/;s/,+/,/g;s/^,//;s/,$//"`"
        DESIRED_OS="`list_get_intersection "${GLIDEIN_REQUIRED_OS:-any}" "${REQUIRED_OS:-any}"`"
        if [[ -z "$DESIRED_OS" ]]; then
            msg="ERROR   VO (or job) REQUIRED_OS and Entry GLIDEIN_REQUIRED_OS have no intersection. Cannot select a Singularity image."
            exit_or_fallback "$msg" 1
            return
        fi
        if [[ "x$DESIRED_OS" = xany ]]; then
            # Prefer the platforms default,rhel7,rhel6, otherwise pick the first one available
            GWMS_SINGULARITY_IMAGE="`singularity_get_image default,rhel7,rhel6 ${GWMS_SINGULARITY_IMAGE_RESTRICTIONS:+$GWMS_SINGULARITY_IMAGE_RESTRICTIONS,}any`"
        else
            GWMS_SINGULARITY_IMAGE="`singularity_get_image "$DESIRED_OS" $GWMS_SINGULARITY_IMAGE_RESTRICTIONS`"
        fi
    fi

    # At this point, GWMS_SINGULARITY_IMAGE is still empty, something is wrong
    if [[ -z "$GWMS_SINGULARITY_IMAGE" ]]; then
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
    #if [[ ! -e "$GWMS_SINGULARITY_IMAGE" ]]; then
    # will both work for non expanded images?

    # check that the image is actually available (but only for /cvmfs ones)
    if (echo "$GWMS_SINGULARITY_IMAGE" | grep '^/cvmfs') >/dev/null 2>&1; then
        if ! ls -l "$GWMS_SINGULARITY_IMAGE" >/dev/null; then
            EXITSLEEP=10m
            msg="\
ERROR   Unable to access the Singularity image: $GWMS_SINGULARITY_IMAGE
        Site and node: $OSG_SITE_NAME `hostname -f`"
            # TODO: also this?: touch ../../.stop-glidein.stamp >/dev/null 2>&1
            exit_or_fallback "$msg" 1
            return
        fi
    fi

    if [[ ! -e "$GWMS_SINGULARITY_IMAGE" ]]; then
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
            if [[ "x$NEW_IMAGE_PATH" != "x" ]]; then
                GWMS_SINGULARITY_IMAGE="$NEW_IMAGE_PATH"
            fi
        fi
    fi

    info_dbg "using image $GWMS_SINGULARITY_IMAGE_HUMAN ($GWMS_SINGULARITY_IMAGE)"
    # Singularity image is OK, continue w/ other init

    # If gwms dir is present, then copy it inside the container.
    if [[ -d ../../gwms ]]; then
        if mkdir -p gwms && cp -r ../../gwms/* gwms/; then
            # Should copy only lib and bin instead?
            # TODO: change the message when condor_chirp requires no more special treatment
            info_dbg "copied GlideinWMS utilities (bin and libs, including condor_chirp) inside the container ($(pwd)/gwms)"
        else
	    warn "Unable to copy GlideinWMS utilities inside the container (to $(pwd)/gwms)"
        fi
    else
        warn "Unable to find GlideinWMS utilities (../../gwms from $(pwd))"
    fi

    # TODO: this is no more needed once 'pychirp' in gwms is tried and tested
    # If condor_chirp is present, then copy it inside the container.
    # This is used in singularity_lib.sh/singularity_setup_inside()
    if [ -e ../../main/condor/libexec/condor_chirp ]; then
        mkdir -p condor/libexec
        cp ../../main/condor/libexec/condor_chirp condor/libexec/condor_chirp
        mkdir -p condor/lib
        cp -r ../../main/condor/lib condor/
        info_dbg "copied condor_chirp (binary and libs) inside the container ($(pwd)/condor)"
    fi

    # set up the env to make sure Singularity uses the glidein dir for exported /tmp, /var/tmp
    if [[ "x$GLIDEIN_Tmp_Dir" != "x"  &&  -e "$GLIDEIN_Tmp_Dir" ]]; then
        if mkdir "$GLIDEIN_Tmp_Dir/singularity-work.$$" ; then
            export SINGULARITY_WORKDIR="$GLIDEIN_Tmp_Dir/singularity-work.$$"
        else
            warn "Unable to set SINGULARITY_WORKDIR to $GLIDEIN_Tmp_Dir/singularity-work.$$. Leaving it undefined."
        fi
    fi

    GWMS_SINGULARITY_EXTRA_OPTS="$GLIDEIN_SINGULARITY_OPTS"

    # Binding different mounts (they will be removed if not existent on the host)
    # OSG: checks also in image, may not work if not expanded. And Singularity will not fail if missing, only give a warning
    #  if [ -e $MNTPOINT/. -a -e $OSG_SINGULARITY_IMAGE/$MNTPOINT ]; then
    GWMS_SINGULARITY_WRAPPER_BINDPATHS_DEFAULTS="/hadoop,/ceph,/hdfs,/lizard,/mnt/hadoop,/mnt/hdfs,/etc/hosts,/etc/localtime"

    # CVMFS access inside container (default, but optional)
    if [[ "x$GWMS_SINGULARITY_BIND_CVMFS" = "x1" ]]; then
        GWMS_SINGULARITY_WRAPPER_BINDPATHS_DEFAULTS="`dict_set_val GWMS_SINGULARITY_WRAPPER_BINDPATHS_DEFAULTS /cvmfs`"
    fi

    # GPUs - bind outside GPU library directory to inside /host-libs
    if [[ "$OSG_MACHINE_GPUS" -gt 0  ||  "x$GPU_USE" = "x1" ]]; then
        if [[ "x$OSG_SINGULARITY_BIND_GPU_LIBS" = "x1" ]]; then
            HOST_LIBS=""
            if [[ -e "/usr/lib64/nvidia" ]]; then
                HOST_LIBS=/usr/lib64/nvidia
            elif create_host_lib_dir; then
                HOST_LIBS="$PWD/.host-libs"
            fi
            if [[ "x$HOST_LIBS" != "x" ]]; then
                GWMS_SINGULARITY_WRAPPER_BINDPATHS_DEFAULTS="`dict_set_val GWMS_SINGULARITY_WRAPPER_BINDPATHS_DEFAULTS "$HOST_LIBS" /host-libs`"
            fi
            if [[ -e /etc/OpenCL/vendors ]]; then
                GWMS_SINGULARITY_WRAPPER_BINDPATHS_DEFAULTS="`dict_set_val GWMS_SINGULARITY_WRAPPER_BINDPATHS_DEFAULTS /etc/OpenCL/vendors /etc/OpenCL/vendors`"
            fi
        fi
        GWMS_SINGULARITY_EXTRA_OPTS="$GWMS_SINGULARITY_EXTRA_OPTS --nv"
    #else
        # if not using gpus, we can limit the image more
        # Already in default: GWMS_SINGULARITY_EXTRA_OPTS="$GWMS_SINGULARITY_EXTRA_OPTS --contain"
    fi
    info_dbg "bind-path default (cvmfs:$GWMS_SINGULARITY_BIND_CVMFS, hostlib:`[ -n "$HOST_LIBS" ] && echo 1`, ocl:`[ -e /etc/OpenCL/vendors ] && echo 1`): $GWMS_SINGULARITY_WRAPPER_BINDPATHS_DEFAULTS"

    # We want to bind $PWD to /srv within the container - however, in order
    # to do that, we have to make sure everything we need is in $PWD, most
    # notably the user-job-wrapper.sh (this script!) and singularity_lib.sh (in $GWMS_AUX_SUBDIR)
    cp "$GWMS_THIS_SCRIPT" .gwms-user-job-wrapper.sh
    export JOB_WRAPPER_SINGULARITY="/srv/.gwms-user-job-wrapper.sh"
    mkdir -p "$GWMS_AUX_SUBDIR"
    cp "${GWMS_AUX_DIR}singularity_lib.sh" "$GWMS_AUX_SUBDIR/"

    # Remember what the outside pwd dir is so that we can rewrite env vars
    # pointing to somewhere inside that dir (for example, X509_USER_PROXY)
    #if [[ -n "$_CONDOR_JOB_IWD" ]]; then
    #    export GWMS_SINGULARITY_OUTSIDE_PWD="$_CONDOR_JOB_IWD"
    #else
    #    export GWMS_SINGULARITY_OUTSIDE_PWD="$PWD"
    #fi
    # Do not trust _CONDOR_JOB_IWD when it comes to finding pwd for the job - M.Rynge
    export GWMS_SINGULARITY_OUTSIDE_PWD="$PWD"


    # Build a new command line, with updated paths. Returns an array in GWMS_RETURN
    singularity_update_path /srv "$@"

    # Get Singularity binds, uses also GLIDEIN_SINGULARITY_BINDPATH, GLIDEIN_SINGULARITY_BINDPATH_DEFAULT
    # remove binds w/ non existing src (e)
    singularity_binds="`singularity_get_binds e "$GWMS_SINGULARITY_WRAPPER_BINDPATHS_DEFAULTS"`"
    # Run and log the Singularity command.
    info_dbg "about to invoke singularity, pwd is $PWD"
    export GWMS_SINGULARITY_REEXEC=1

    # Disabling outside LD_LIBRARY_PATH and PATH to avoid problems w/ different OS
    # Singularity is supposed to handle this, but different versions behave differently
    if [[ -n "$LD_LIBRARY_PATH" ]]; then
        info "GWMS Singularity wrapper: LD_LIBRARY_PATH is set to $LD_LIBRARY_PATH outside Singularity. This will not be propagated to inside the container instance." 1>&2
        unset LD_LIBRARY_PATH
    fi
    OLD_PATH=
    if [[ -n "$PATH" ]]; then
        OLD_PATH="$PATH"
        info "GWMS Singularity wrapper: PATH is set to $PATH outside Singularity. This will not be propagated to inside the container instance." 1>&2
        unset PATH
    fi
    OLD_PYTHONPATH=
    if [[ -n "$PYTHONPATH" ]]; then
        OLD_PYTHONPATH="$PYTHONPATH"
        info "GWMS Singularity wrapper: PYTHONPATH is set to $PYTHONPATH outside Singularity. This will not be propagated to inside the container instance." 1>&2
        unset PYTHONPATH
    fi

    # Add --clearenv if requested
    GWMS_SINGULARITY_EXTRA_OPTS=$(env_clear "${GLIDEIN_CONTAINER_ENV}" "${GWMS_SINGULARITY_EXTRA_OPTS}")

    # If there is clearenv protect the variables (it may also have been added by the custom Singularity options)
    if env_gets_cleared "${GWMS_SINGULARITY_EXTRA_OPTS}" ; then
        env_preserve "${GLIDEIN_CONTAINER_ENV}"
    fi

    # The new OSG wrapper is not exec-ing singularity to continue after and inspect if it ran correctly or not
    # This may be causing problems w/ signals (sig-term/quit) propagation - [#24306]
    if [[ -z "$GWMS_SINGULARITY_LIB_VERSION" ]]; then
        # GWMS 3.4.5 or lower, no GWMS_SINGULARITY_GLOBAL_OPTS, no GWMS_SINGULARITY_LIB_VERSION
        singularity_exec "$GWMS_SINGULARITY_PATH" "$GWMS_SINGULARITY_IMAGE" "$singularity_binds" \
                 "$GWMS_SINGULARITY_EXTRA_OPTS" "exec" "$JOB_WRAPPER_SINGULARITY" \
                 "${GWMS_RETURN[@]}"
    else
        singularity_exec "$GWMS_SINGULARITY_PATH" "$GWMS_SINGULARITY_IMAGE" "$singularity_binds" \
                 "$GWMS_SINGULARITY_EXTRA_OPTS" "$GWMS_SINGULARITY_GLOBAL_OPTS" "exec" "$JOB_WRAPPER_SINGULARITY" \
                 "${GWMS_RETURN[@]}"
    fi
    # Continuing here only if exec of singularity failed
    GWMS_SINGULARITY_REEXEC=0
    env_restore "${GLIDEIN_CONTAINER_ENV}"
    [[ -n "$OLD_PATH" ]] && PATH="$OLD_PATH"
    exit_or_fallback "exec of singularity failed" $?
}


#################### main ###################

if [[ -z "$GWMS_SINGULARITY_REEXEC" ]]; then

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

    if [[ "x$HAS_SINGULARITY" = "x1"  &&  "x$GWMS_SINGULARITY_PATH" != "x" ]]; then
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

    # Need to start in /srv (Singularity's --pwd is not reliable)
    # /srv should always be there in Singularity, we set the option '--home \"$PWD\":/srv'
    # TODO: double check robustness, we allow users to override --home
    [[ -d /srv ]] && cd /srv
    export HOME=/srv

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
# - if setup or exec of singularity failed (and it is possible to fall-back)
#

info_dbg "GWMS singularity wrapper, final setup."

#############################
#
#  modules and env
#

# TODO: to remove for sure once 'pychirp' is tried and tested
# TODO: not needed here? It is in singularity_setup_inside for when Singularity is invoked, and should be already in the PATH when it is not
# Checked - glidin_startup seems not to add condor to the path
# Add Glidein provided HTCondor back to the environment (so that we can call chirp) - same is in
# TODO: what if original and Singularity OS are incompatible? Should check and avoid adding condor back?
if ! command -v condor_chirp > /dev/null 2>&1; then
    # condor_chirp not found, setting up form the condor library
    if [[ -e ../../main/condor/libexec ]]; then
        DER="`(cd ../../main/condor; pwd)`"
        export PATH="$DER/libexec:$PATH"
        # TODO: Check if LD_LIBRARY_PATH is needed or OK because of RUNPATH
        # export LD_LIBRARY_PATH="$DER/lib:$LD_LIBRARY_PATH"
    fi
fi

# fix discrepancy for Squid proxy URLs
if [[ "x$GLIDEIN_Proxy_URL" = "x"  ||  "$GLIDEIN_Proxy_URL" = "None" ]]; then
    if [[ "x$OSG_SQUID_LOCATION" != "x"  &&  "$OSG_SQUID_LOCATION" != "None" ]]; then
        export GLIDEIN_Proxy_URL="$OSG_SQUID_LOCATION"
    fi
fi

# load modules and spack, if available
# InitializeModulesEnv and MODULE_USE are 2 variables to enable the use of modules
[[ "x$InitializeModulesEnv" = "x1" ]] && MODULE_USE=1

if [[ "x$MODULE_USE" = "x1" ]]; then
    # Removed LMOD_BETA (/cvmfs/oasis.opensciencegrid.org/osg/sw/module-beta-init.sh), obsolete
    if [[ -e /cvmfs/oasis.opensciencegrid.org/osg/sw/module-init.sh  &&  -e /cvmfs/connect.opensciencegrid.org/modules/spack/share/spack/setup-env.sh ]]; then
        . /cvmfs/oasis.opensciencegrid.org/osg/sw/module-init.sh
    fi
    module -v >/dev/null 2>&1
    if [[ $? -ne 0 ]]; then
        # module setup did not work, ignore it for the rest of the script
        MODULE_USE=0
    fi
fi


#############################
#
#  Stash cache
#

setup_stashcp () {
    if [[ "x$MODULE_USE" != "x1" ]]; then
        warn "Module unavailable. Unable to setup Stash cache if not in the environment."
        return 1
    fi

    # if we do not have stashcp in the path, load stashcache and xrootd from modules
    if ! which stashcp >/dev/null 2>&1; then
        module load stashcache >/dev/null 2>&1 || module load stashcp >/dev/null 2>&1

        # The OSG wrapper (as of 5d8b3fa9b258ea0e6640727405f20829d2c5d4b9) removed this xrdcp setup
        # We need xrootd, which is available both in the OSG software stack
        # as well as modules - use the system one by default
        if ! which xrdcp >/dev/null 2>&1; then
            module load xrootd >/dev/null 2>&1
        fi

        # Determine XRootD plugin directory.
        # in lieu of a MODULE_<name>_BASE from lmod, this will do:
        if [ -n "$XRD_PLUGINCONFDIR" ]; then
            export MODULE_XROOTD_BASE="$(which xrdcp | sed -e 's,/bin/.*,,')"
            export XRD_PLUGINCONFDIR="$MODULE_XROOTD_BASE/etc/xrootd/client.plugins.d"
        fi
    fi

}

# Check for PosixStashCache first
if [[ "x$POSIXSTASHCACHE" = "x1" ]]; then
    setup_stashcp
    if [[ $? -eq 0 ]]; then

        # Add the LD_PRELOAD hook
        export LD_PRELOAD="$MODULE_XROOTD_BASE/lib64/libXrdPosixPreload.so:$LD_PRELOAD"

        # Set proxy for virtual mount point
        # Format: cache.domain.edu/local_mount_point=/storage_path
        # E.g.: export XROOTD_VMP=data.ci-connect.net:/stash=/
        # Currently this points _ONLY_ to the OSG Connect source server
        export XROOTD_VMP=$(stashcp --closest | cut -d'/' -f3):/stash=/
    fi
elif [[ "x$STASHCACHE" = "x1"  ||  "x$STASHCACHE_WRITABLE" = "x1" ]]; then
    setup_stashcp
    # No more extra path for $STASHCACHE_WRITABLE
    # [[ $? -eq 0 ]] && [[ "x$STASHCACHE_WRITABLE" = "x1" ]]export PATH="/cvmfs/oasis.opensciencegrid.org/osg/projects/stashcp/writeback:$PATH"
fi


################################
#
#  Load user specified modules
#
if [[ "X$LoadModules" != "X" ]]; then
    if [[ "x$MODULE_USE" != "x1" ]]; then
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
info_dbg "GWMS singularity wrapper, job exec: $*"
info_dbg "GWMS singularity wrapper, messages after this line are from the actual job ##################"
exec "$@"
error=$?
# exec failed. Log, communicate to HTCondor, avoid black hole and exit
exit_wrapper "exec failed  (Singularity:$GWMS_SINGULARITY_REEXEC, exit code:$error): $*" $error
