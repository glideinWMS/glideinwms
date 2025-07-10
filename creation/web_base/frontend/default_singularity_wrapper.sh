#!/bin/sh

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

# shebang must be /bin/sh for Busybox compatibility
if [ -z "$BASH_VERSION" ]; then
    # If not running Bash and Bash is available, use it
    which bash > /dev/null 2>&1 && exec bash "$0" "$@"
else
    # If in Bash, disable POSIX mode
    # shellcheck disable=SC3040
    set +o posix || echo "WARN: running in POSIX mode"
fi
# Supposing Bash or Busybox ash/dash shell
# use let instead of (( )), use $(eval "echo \"\$${var##*[!0-9_a-z_A-Z]*}\"") instead of ${!var}
# and for assignment `eval "new_var=\$${var##*[!0-9_a-z_A-Z]*}"`
# [[ ]] is OK, variables manipulation OK (except {var/#st/new} and {var/%end/new})

# GlideinWMS singularity wrapper. Invoked by HTCondor as user_job_wrapper
# default_singularity_wrapper USER_JOB [job options and arguments]
EXITSLEEP=10m
GWMS_THIS_SCRIPT="$0"
GWMS_THIS_SCRIPT_DIR=$(dirname "$0")

# Directory in Singularity where auxiliary files are copied (e.g. singularity_lib.sh)
GWMS_AUX_SUBDIR=${GWMS_AUX_SUBDIR:-".gwms_aux"}
export GWMS_AUX_SUBDIR
# GWMS_BASE_SUBDIR (directory where the base glidein directory is mounted) not defiled in Singularity for the user jobs, only for setup scripts
# Directory to use for bin, lib, exec, ...
GWMS_SUBDIR=${GWMS_SUBDIR:-".gwms.d"}
export GWMS_SUBDIR

GWMS_VERSION_SINGULARITY_WRAPPER=20250709
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
[[ ",${GLIDEIN_DEBUG_OPTIONS}," = *,usertrace,* ]] && set -x
[[ ",${GLIDEIN_DEBUG_OPTIONS}," = *,nowait,* ]] && EXITSLEEP=2m # leave 2min to update classad

# When failing we need to tell HTCondor to put the job back in the queue by creating
# a file in the PATH pointed by $_CONDOR_WRAPPER_ERROR_FILE
# Make sure there is no leftover wrapper error file (if the file exists HTCondor assumes the wrapper failed)
# shellcheck disable=SC2015    # OK if the file is not there
[[ -n "$_CONDOR_WRAPPER_ERROR_FILE" ]] && rm -f "$_CONDOR_WRAPPER_ERROR_FILE" >/dev/null 2>&1 || true

exit_wrapper() {
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
    # The message is flattened (\n\r removed) when writing to HTCondor because it does not support multiline strings (see bug HTCONDOR-2305)
    if [[ -n "$_CONDOR_WRAPPER_ERROR_FILE" ]]; then
        warn "Wrapper script failed, creating condor log file: $_CONDOR_WRAPPER_ERROR_FILE"
        echo "Wrapper script $GWMS_THIS_SCRIPT failed ($exit_code): ${1//$'\r\n']/  /}" >>"$_CONDOR_WRAPPER_ERROR_FILE"
    else
        publish_fail="HTCondor error file"
    fi
    # If chirp (pychirp) is available set a job attribute
    if command -v condor_chirp >/dev/null 2>&1; then
        condor_chirp set_job_attr JobWrapperFailure "Wrapper script $GWMS_THIS_SCRIPT failed ($exit_code): ${1//$'\r\n']/  /}"
    else
        [[ -n "$publish_fail" ]] && publish_fail="${publish_fail} and "
        publish_fail="${publish_fail}condor_chirp"
    fi

    # TODO: also this?: touch ../../.stop-glidein.stamp >/dev/null 2>&1

    [[ -n "$publish_fail" ]] && warn "Failed to communicate ERROR with ${publish_fail}"

    #  TODO: Add termination stamp? see OSG
    #              touch ../../.stop-glidein.stamp >/dev/null 2>&1
    # Eventually the periodic validation of singularity will make the pilot
    # to stop matching new payloads
    # Prevent a black hole by sleeping EXITSLEEP (10) minutes before exiting. Sleep time can be changed on top of this file
    sleep "$sleep_time"
    exit "$exit_code"
}

# In case singularity_lib cannot be imported
warn_raw() {
    echo "$@" 1>&2
}

# Ensure all jobs have PATH set
# bash can set a default PATH - make sure it is exported
export PATH=$PATH
[[ -z "$PATH" ]] && export PATH="/usr/local/bin:/usr/bin:/bin"

[[ -z "$glidein_config" ]] && [[ -e "$GWMS_THIS_SCRIPT_DIR/glidein_config" ]] &&
    glidein_config="$GWMS_THIS_SCRIPT_DIR/glidein_config"

# Source utility files, outside and inside Singularity
# condor_job_wrapper is in the base directory, singularity_lib.sh in main
# and copied to RUNDIR/$GWMS_AUX_SUBDIR (RUNDIR becomes /srv in Singularity)
if [[ -e "$GWMS_THIS_SCRIPT_DIR/main/singularity_lib.sh" ]]; then
    GWMS_AUX_DIR="$GWMS_THIS_SCRIPT_DIR/main"
elif [[ -e /srv/$GWMS_AUX_SUBDIR/singularity_lib.sh ]]; then
    # In Singularity
    GWMS_AUX_DIR="/srv/$GWMS_AUX_SUBDIR"
else
    echo "ERROR: $GWMS_THIS_SCRIPT: Unable to source singularity_lib.sh! File not found. Quitting" 1>&2
    warn=warn_raw
    exit_wrapper "Wrapper script $GWMS_THIS_SCRIPT failed: Unable to source singularity_lib.sh" 1
fi
if [[ -z "$GWMS_SINGULARITY_REEXEC" ]] || [[ -n "$BASH_VERSION" ]]; then
    # shellcheck source=../singularity_lib.sh
    . "${GWMS_AUX_DIR}"/singularity_lib.sh
    GWMS_SHELL_MODE="Bash"
else
    # Inside Apptainer and no Bash:  source and skip parts incompatible with Busybox, to be compatible w/ all containers
    # Lines ending in "# START bash" and "END bash" delimit Bash only sections
    eval "$(sed '/.*# START bash$/,/.*# END bash$/d' "${GWMS_AUX_DIR}"/singularity_lib.sh)"
    GWMS_SHELL_MODE="Busybox-compatibility"
fi
[[ ":$SHELLOPTS:" != *:posix:* ]] || GWMS_SHELL_MODE="$GWMS_SHELL_MODE/POSIX"
# These singularity_lib.sh functions must be Busybox compatible (are used inside the container)
# - info_dbg
# - setup_classad_variables
# - cvmfs_test_and_open
# - singularity_setup_inside
# - gwms_process_scripts

# Directory to use for bin, lib, exec, ... full path
if [[ -n "$GWMS_DIR" && -e "$GWMS_DIR/bin" ]]; then
    # already set, keep it
    true
elif [[ -e $GWMS_THIS_SCRIPT_DIR/$GWMS_SUBDIR/bin ]]; then
    GWMS_DIR=$GWMS_THIS_SCRIPT_DIR/$GWMS_SUBDIR
elif [[ -e /srv/$GWMS_SUBDIR/bin ]]; then
    GWMS_DIR=/srv/$GWMS_SUBDIR
elif [[ -e /srv/$(dirname "$GWMS_AUX_DIR")/$GWMS_SUBDIR/bin ]]; then
    GWMS_DIR=/srv/$(dirname "$GWMS_AUX_DIR")/$GWMS_SUBDIR/bin
else
    echo "ERROR: $GWMS_THIS_SCRIPT: Unable to find GWMS_DIR! File not found. Quitting" 1>&2
    exit_wrapper "Wrapper script $GWMS_THIS_SCRIPT failed: Unable to find GWMS_DIR" 1
fi
export GWMS_DIR

# Calculating full version number, including md5 sums form the wrapper and singularity_lib
GWMS_VERSION_SINGULARITY_WRAPPER="${GWMS_VERSION_SINGULARITY_WRAPPER}_$(md5sum "$GWMS_THIS_SCRIPT" 2>/dev/null | cut -d ' ' -f1)_$(md5sum "${GWMS_AUX_DIR}/singularity_lib.sh" 2>/dev/null | cut -d ' ' -f1)"
info_dbg "GWMS singularity wrapper ($GWMS_VERSION_SINGULARITY_WRAPPER) starting, $(date). Imported singularity_lib.sh ($GWMS_SHELL_MODE). glidein_config ($glidein_config)."
info_dbg "$GWMS_THIS_SCRIPT, in $(pwd), list: $(ls -al)"

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

    if [[ "$HAS_SINGULARITY" = "1" && -n "$GWMS_SINGULARITY_PATH" ]]; then
        #############################################################################
        #
        # Will run w/ Singularity - prepare for it
        # From here on the script assumes it has to run w/ Singularity
        #
        info_dbg "Decided to use singularity ($HAS_SINGULARITY, $GWMS_SINGULARITY_PATH). Proceeding w/ tests and setup."

        # We make sure that every cvmfs repository that users specify in CVMFSReposList is available,
        # otherwise this script exits with 1
        cvmfs_test_and_open "$CVMFS_REPOS_LIST" exit_wrapper

        # Removed local prepare_and_invoke_singularity in favor of singularity_lib.sh
        # function singularity_prepare_and_invoke (was: CodeRM1)
        singularity_prepare_and_invoke "${@}"

        # If we arrive here, then something failed in Singularity but is OK to continue w/o

    else #if [ "x$HAS_SINGULARITY" = "x1" -a "xSINGULARITY_PATH" != "x" ];
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
    # shellcheck disable=SC2015    # Warning desired if directory not there or cd fails
    [[ -d /srv ]] && cd /srv || warn "GWMS singularity wrapper, unable to cd in /srv"
    export HOME=/srv

    # Changing env variables (especially TMP and X509 related) to work w/ chrooted FS
    singularity_setup_inside
    info_dbg "GWMS singularity wrapper, running inside singularity env = $(printenv)"

fi

################################################################################
#
# Setup for job execution
# This section will be executed:
# - in Singularity (if $GWMS_SINGULARITY_REEXEC not empty)
# - if is OK to run w/o Singularity ( $HAS_SINGULARITY" not true OR $GWMS_SINGULARITY_PATH" empty )
# - if setup or exec of singularity failed (and it is possible to fall-back to no Singularity)
#

info_dbg "GWMS singularity wrapper, final setup."

# Removed local code in favor of gwms_process_scripts from singularity_lib.sh and setup_prejob.sh (CodeRM1)
gwms_process_scripts "$GWMS_DIR" prejob "$glidein_config"

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
# shellcheck disable=SC2015    # OK if the directory is not there
[[ "$GWMS_AUX_SUBDIR/" = /srv/* ]] && rm -rf "${GWMS_AUX_SUBDIR:?}/" >/dev/null 2>&1 || true
rm -f .gwms-user-job-wrapper.sh >/dev/null 2>&1 || true

##############################
#
#  Run the real job
#
info_dbg "current directory at execution ($(pwd)): $(ls -al)"
info_dbg "GWMS singularity wrapper, job exec: $*"
info_dbg "GWMS singularity wrapper, messages after this line are from the actual job ##################"
# shellcheck disable=SC2093    # exec is desired, following lines are only in case exec fails
exec "$@"
error=$?
# exec failed. Log, communicate to HTCondor, avoid black hole and exit
exit_wrapper "exec failed  (Singularity:$GWMS_SINGULARITY_REEXEC, exit code:$error): $*" $error
