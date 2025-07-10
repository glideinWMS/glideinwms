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

#
EXITSLEEP=5
# Change the variable to control the exit code returned
EXIT_CODE=0
# Change this possibly to a unique name
GWMS_THIS_SCRIPT=singularity_script_example
GWMS_THIS_SCRIPT_DIR=$(dirname "$0")
GWMS_AUX_SUBDIR=${GWMS_AUX_SUBDIR:-".gwms_aux"}
export GWMS_AUX_SUBDIR
GWMS_SUBDIR=${GWMS_SUBDIR:-".gwms.d"}
export GWMS_SUBDIR

GWMS_VERSION_SINGULARITY_WRAPPER=ex20250709


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



exit_script() {
    # An error occurred. Communicate to HTCondor and avoid black hole (sleep for hold time) and then exit 1
    #  1: Error message
    #  2: Exit code (1 by default)
    #  3: sleep time (default: $EXITSLEEP)
    [[ -n "$1" ]] && warn_raw "ERROR: $1"
    local exit_code=${2:-1}
    # Publish the error so that HTCondor understands that is a wrapper error and retries the job
    if [[ -n "$_CONDOR_WRAPPER_ERROR_FILE" ]]; then
        warn "Example script failed, creating condor log file: $_CONDOR_WRAPPER_ERROR_FILE"
    fi
    sleep $EXITSLEEP
    exit $exit_code
}

# In case singularity_lib cannot be imported
warn_raw() {
    echo "$@" 1>&2
}

[[ -z "$glidein_config" ]] && [[ -e "$GWMS_THIS_SCRIPT_DIR/../glidein_config" ]] &&
    glidein_config="$GWMS_THIS_SCRIPT_DIR/../glidein_config"

# error_gen defined in singularity_lib.sh
[[ -e "$glidein_config" ]] && error_gen=$(grep '^ERROR_GEN_PATH ' "$glidein_config" | cut -d ' ' -f 2-)


# Source utility files, outside and inside Singularity
# condor_job_wrapper is in the base directory, singularity_lib.sh in main
# and copied to RUNDIR/$GWMS_AUX_SUBDIR (RUNDIR becomes /srv in Singularity)
if [[ -e "$GWMS_THIS_SCRIPT_DIR/singularity_lib.sh" ]]; then
    GWMS_AUX_DIR="$GWMS_THIS_SCRIPT_DIR/"
elif [[ -e /srv/$GWMS_AUX_SUBDIR/singularity_lib.sh ]]; then
    # In Singularity
    GWMS_AUX_DIR="/srv/$GWMS_AUX_SUBDIR/"
else
    echo "ERROR: $GWMS_THIS_SCRIPT: Unable to source singularity_lib.sh! File not found. Quitting" 1>&2
    warn=warn_raw
    exit_script "Wrapper script $GWMS_THIS_SCRIPT failed: Unable to source singularity_lib.sh" 1
fi
if [[ -z "$GWMS_SINGULARITY_REEXEC" ]] || [[ -n "$BASH_VERSION" ]]; then
    # shellcheck source=./singularity_lib.sh
    . "${GWMS_AUX_DIR}"/singularity_lib.sh
    GWMS_SHELL_MODE="Bash"
else
    # Inside Apptainer and no Bash:  source and skip parts incompatible with Busybox, to be compatible w/ all containers
    # Lines ending in "# START bash" and "END bash" delimit Bash only sections
    eval "$(sed '/.*# START bash$/,/.*# END bash$/d' "${GWMS_AUX_DIR}"/singularity_lib.sh)"
    GWMS_SHELL_MODE="Busybox-compatibility"
fi
[[ ":$SHELLOPTS:" != *:posix:* ]] || GWMS_SHELL_MODE="$GWMS_SHELL_MODE/POSIX"

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
info_dbg "GWMS singularity example ($GWMS_VERSION_SINGULARITY_WRAPPER) starting, $(date). Imported singularity_lib.sh ($GWMS_SHELL_MODE). glidein_config ($glidein_config)."
info_dbg "$GWMS_THIS_SCRIPT, in $(pwd), list: $(ls -al)"

#################### main ###################


################################################################################
#
# Outside and Inside Singularity - This is before any setup
#


if [[ -z "$GWMS_SINGULARITY_REEXEC" ]]; then

    ################################################################################
    #
    # Outside Singularity - Run this only on the 1st invocation
    #

    info_dbg "GWMS singularity example, first invocation"

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


    if [[ "$HAS_SINGULARITY" = "1" && -n "$GWMS_SINGULARITY_PATH" ]]; then
        #############################################################################
        #
        # Will run w/ Singularity - prepare for it
        # From here on the script assumes it has to run w/ Singularity
        #
        info_dbg "Decided to use singularity ($HAS_SINGULARITY, $GWMS_SINGULARITY_PATH). Proceeding w/ tests and setup."

        # We make sure that every cvmfs repository that users specify in CVMFSReposList is available, otherwise this script exits with 1
        cvmfs_test_and_open "$CVMFS_REPOS_LIST" exit_script

        singularity_prepare_and_invoke "${@}"

        # If we arrive here, then something failed in Singularity but is OK to continue w/o

    else  #if [[ "$HAS_SINGULARITY" = "1" && -n "$GWMS_SINGULARITY_PATH" ]];
        # First execution, no Singularity.
        info_dbg "GWMS singularity example, first invocation, not using singularity ($HAS_SINGULARITY, $GWMS_SINGULARITY_PATH)"

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
    info_dbg "GWMS singularity example, running inside singularity env = "`printenv`

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

info_dbg "GWMS singularity example, final setup."

gwms_process_scripts "$GWMS_DIR" prejob

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
