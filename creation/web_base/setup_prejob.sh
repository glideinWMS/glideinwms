# bash source
# This script is meant to be sourced and not executed
# Setup script executed by the GlideinWMS job wrapper before all jobs whether they use Singularity or not

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
