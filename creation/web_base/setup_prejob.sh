#!/bin/bash
# bash source, adding the shebang only for shellcheck
# This script is meant to be sourced and not executed
# Setup script executed by the GlideinWMS job wrapper before all jobs whether they use Singularity or not

#############################
#
#  modules and env
#

# fix discrepancy for Squid proxy URLs
if [[ -z "$GLIDEIN_Proxy_URL"  ||  "$GLIDEIN_Proxy_URL" = "None" ]]; then
    if [[ -n "$OSG_SQUID_LOCATION"  &&  "$OSG_SQUID_LOCATION" != "None" ]]; then
        export GLIDEIN_Proxy_URL="$OSG_SQUID_LOCATION"
    fi
fi

# load modules and spack, if available
# InitializeModulesEnv and MODULE_USE are 2 variables to enable the use of modules
[[ "$InitializeModulesEnv" = "1" ]] && MODULE_USE=1

if [[ "$MODULE_USE" = "1" ]]; then
    # Removed LMOD_BETA (/cvmfs/oasis.opensciencegrid.org/osg/sw/module-beta-init.sh), obsolete
    if [[ -e /cvmfs/oasis.opensciencegrid.org/osg/sw/module-init.sh  &&  -e /cvmfs/connect.opensciencegrid.org/modules/spack/share/spack/setup-env.sh ]]; then
        . /cvmfs/oasis.opensciencegrid.org/osg/sw/module-init.sh
    fi
    if ! module -v >/dev/null 2>&1; then
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
            MODULE_XROOTD_BASE="$(which xrdcp | sed -e 's,/bin/.*,,')"
            export MODULE_XROOTD_BASE
            export XRD_PLUGINCONFDIR="$MODULE_XROOTD_BASE/etc/xrootd/client.plugins.d"
        fi
    fi

}

# Check for PosixStashCache first
if [[ "$POSIXSTASHCACHE" = "1" ]]; then
    if setup_stashcp; then

        # Add the LD_PRELOAD hook
        export LD_PRELOAD="$MODULE_XROOTD_BASE/lib64/libXrdPosixPreload.so:$LD_PRELOAD"

        # Set proxy for virtual mount point
        # Format: cache.domain.edu/local_mount_point=/storage_path
        # E.g.: export XROOTD_VMP=data.ci-connect.net:/stash=/
        # Currently this points _ONLY_ to the OSG Connect source server
        XROOTD_VMP=$(stashcp --closest | cut -d'/' -f3):/stash=/
        export XROOTD_VMP
    fi
elif [[ "$STASHCACHE" = "1"  ||  "$STASHCACHE_WRITABLE" = "1" ]]; then
    setup_stashcp
    # No more extra path for $STASHCACHE_WRITABLE
    # [[ $? -eq 0 ]] && [[ "x$STASHCACHE_WRITABLE" = "x1" ]]export PATH="/cvmfs/oasis.opensciencegrid.org/osg/projects/stashcp/writeback:$PATH"
fi


################################
#
#  Load user specified modules
#
if [[ -n "$LoadModules" ]]; then
    if [[ "$MODULE_USE" != "1" ]]; then
        warn "Module unavailable. Unable to load desired modules: $LoadModules"
    else
        ModuleList=$(echo "$LoadModules" | sed 's/^LoadModules = //i;s/"//g')
        for Module in $ModuleList; do
            info_dbg "Loading module: $Module"
            module load "$Module"
        done
    fi
fi
