#!/bin/bash


function getPropBool
{
    # $1 the file (for example, $_CONDOR_JOB_AD or $_CONDOR_MACHINE_AD)
    # $2 the key
    # echo "1" for true, "0" for false/unspecified
    # return 0 for true, 1 for false/unspecified
    val=`(grep -i "^$2 " $1 | cut -d= -f2 | sed "s/[\"' \t\n\r]//g") 2>/dev/null`
    # convert variations of true to 1
    if (echo "x$val" | grep -i true) >/dev/null 2>&1; then
        val="1"
    fi
    if [ "x$val" = "x" ]; then
        val="0"
    fi
    echo $val
    # return value accordingly, but backwards (true=>0, false=>1)
    if [ "$val" = "1" ];  then
        return 0
    else
        return 1
    fi
}


function getPropStr
{
    # $1 the file (for example, $_CONDOR_JOB_AD or $_CONDOR_MACHINE_AD)
    # $2 the key
    # echo the value
    val=`(grep -i "^$2 " $1 | cut -d= -f2 | sed "s/[\"' \t\n\r]//g") 2>/dev/null`
    echo $val
}


if [ "x$SINGULARITY_REEXEC" = "x" ]; then
    
    if [ "x$_CONDOR_JOB_AD" = "x" ]; then
        export _CONDOR_JOB_AD="NONE"
    fi
    if [ "x$_CONDOR_MACHINE_AD" = "x" ]; then
        export _CONDOR_MACHINE_AD="NONE"
    fi

    # "save" some setting from the condor ads - we need these even if we get re-execed
    # inside singularity in which the paths in those env vars are wrong
    # Seems like arrays do not survive the singularity transformation, so set them
    # explicity

    export HAS_SINGULARITY=$(getPropBool $_CONDOR_MACHINE_AD HAS_SINGULARITY)
    export OSG_SINGULARITY_PATH=$(getPropStr $_CONDOR_MACHINE_AD OSG_SINGULARITY_PATH)
    export OSG_SINGULARITY_IMAGE_DEFAULT=$(getPropStr $_CONDOR_MACHINE_AD OSG_SINGULARITY_IMAGE_DEFAULT)
    export OSG_SINGULARITY_IMAGE=$(getPropStr $_CONDOR_JOB_AD SingularityImage)
    export OSG_SINGULARITY_AUTOLOAD=$(getPropStr $_CONDOR_JOB_AD SingularityAutoLoad)
    if [ "x$OSG_SINGULARITY_AUTOLOAD" = "x" ]; then
        # default for autoload is true
        export OSG_SINGULARITY_AUTOLOAD=1
    else
        export OSG_SINGULARITY_AUTOLOAD=$(getPropBool $_CONDOR_JOB_AD SingularityAutoLoad)
    fi
    export OSG_SINGULARITY_BIND_CVMFS=$(getPropBool $_CONDOR_JOB_AD SingularityBindCVMFS)

    export STASHCACHE=$(getPropBool $_CONDOR_JOB_AD WantsStashCache)

    export POSIXSTASHCACHE=$(getPropBool $_CONDOR_JOB_AD WantsPosixStashCache)

    export LoadModules=$(getPropStr $_CONDOR_JOB_AD LoadModules)

    export LMOD_BETA=$(getPropBool $_CONDOR_JOB_AD LMOD_BETA)

    export CVMFS_REPOS_LIST=$(getPropStr $_CONDOR_JOB_AD CVMFSReposList)
    echo "HK Warning: CVMFS Repos List = $CVMFS_REPOS_LIST" 1>&2
    export OSG_SINGULARITY_AUTOLOAD=1

    #############################################################################
    #
    #  Singularity
    #
    if [ "x$HAS_SINGULARITY" = "x1" -a "x$OSG_SINGULARITY_AUTOLOAD" = "x1" -a "x$OSG_SINGULARITY_PATH" != "x" ]; then

        holdfd=3
	exitcondition=false
        if [ "x$CVMFS_REPOS_LIST" != "x" ]; then
            for x in $(echo $CVMFS_REPOS_LIST | sed 's/,/ /g'); do
                if ls "/cvmfs/$x" > /dev/null 2>&1; then
                    echo "/cvmfs/$x exists and available"
                    eval "exec $holdfd</cvmfs/$x"
                    let "holdfd=holdfd+1"
                else
                    echo "/cvmfs/$x NOT available"
                    exitcondition=true
                fi
            done

	    tempoutput=`lsof | grep cvmfs | grep -v cvmfs2`
            echo $tempoutput
        fi

        # If  image is not provided, load the default one
        # Custom URIs: http://singularity.lbl.gov/user-guide#supported-uris
        if [ "x$OSG_SINGULARITY_IMAGE" = "x" ]; then
            # Default
            export OSG_SINGULARITY_IMAGE="$OSG_SINGULARITY_IMAGE_DEFAULT"
            export OSG_SINGULARITY_BIND_CVMFS=1

            # also some extra debugging and make sure CVMFS has not fallen over
            if ! ls -l "$OSG_SINGULARITY_IMAGE/" >/dev/null; then
                echo "warning: unable to access $OSG_SINGULARITY_IMAGE" 1>&2
                echo "$OSG_SITE_NAME" `hostname -f` 1>&2
                touch ../../.stop-glidein.stamp >/dev/null 2>&1
                sleep 10m
            fi
        fi

        # for /cvmfs based directory images, expand the path without symlinks so that
        # the job can stay within the same image for the full duration
        if echo "$OSG_SINGULARITY_IMAGE" | grep /cvmfs >/dev/null 2>&1; then
            if (cd $OSG_SINGULARITY_IMAGE) >/dev/null 2>&1; then
                NEW_IMAGE_PATH=`(cd $OSG_SINGULARITY_IMAGE && pwd -P) 2>/dev/null`
                if [ "x$NEW_IMAGE_PATH" != "x" ]; then
                    OSG_SINGULARITY_IMAGE="$NEW_IMAGE_PATH"
                fi
            fi
        fi

	#HK> For now, we only allow singularity images from /cvmfs area because we don't know how to deal with otherwise situation
	#HK> This is not a solution. We only use this fake-solution because we are not sure of how to fetch SingularityImage attribute
	#HK> in the validation script and also because it is to late to exit in the wrapper script
        if [ "x$OSG_SINGULARITY_IMAGE" != "x" ]; then
	    echo "Debug: user image name = $OSG_SINGULARITY_IMAGE" 1>&2
	    if ! echo "$OSG_SINGULARITY_IMAGE" | grep /cvmfs >/dev/null 2>&1; then
		export OSG_SINGULARITY_IMAGE="$OSG_SINGULARITY_IMAGE_DEFAULT"
	    fi
        fi
	

        OSG_SINGULARITY_EXTRA_OPTS=""
   
        # cvmfs access inside container (default, but optional)
        if [ "x$OSG_SINGULARITY_BIND_CVMFS" = "x1" ]; then
            OSG_SINGULARITY_EXTRA_OPTS="$OSG_SINGULARITY_EXTRA_OPTS --bind /cvmfs"
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
        CMD=""
        for VAR in "$@"; do
            # two seds to make sure we catch variations of the iwd,
            # including symlinked ones
            VAR=`echo " $VAR" | sed -E "s;$PWD(.*);/srv\1;" | sed -E "s;.*/execute/dir_[0-9a-zA-Z]*(.*);/srv\1;"`
            CMD="$CMD $VAR"
        done

        if $exitcondition; then
            sleep 10m
            exit 1
        else
            export SINGULARITY_REEXEC=1
            exec $OSG_SINGULARITY_PATH exec $OSG_SINGULARITY_EXTRA_OPTS \
                                   --home $PWD:/srv \
                                   --pwd /srv \
                                   --scratch /var/tmp \
                                   --scratch /tmp \
                                   --containall \
                                   "$OSG_SINGULARITY_IMAGE" \
                                   /srv/.osgvo-user-job-wrapper.sh $CMD
	fi
    fi

else
    # we are now inside singularity - fix up the env
    unset TMP
    unset TEMP
    unset X509_CERT_DIR
    for key in X509_USER_PROXY X509_USER_CERT _CONDOR_MACHINE_AD _CONDOR_JOB_AD \
               _CONDOR_SCRATCH_DIR _CONDOR_CHIRP_CONFIG _CONDOR_JOB_IWD \
               OSG_WN_TMP ; do
        eval val="\$$key"
        val=`echo "$val" | sed -E "s;$OSG_SINGULARITY_OUTSIDE_PWD(.*);/srv\1;"`
        eval $key=$val
    done

    # If X509_USER_PROXY and friends are not set by the job, we might see the
    # glidein one - in that case, just unset the env var
    for key in X509_USER_PROXY X509_USER_CERT X509_USER_KEY ; do
        eval val="\$$key"
        if [ "x$val" != "x" ]; then
            if [ ! -e "$val" ]; then
                eval unset $key >/dev/null 2>&1 || true
            fi
        fi
    done

    # override some OSG specific variables
    if [ "x$OSG_WN_TMP" != "x" ]; then
        export OSG_WN_TMP=/tmp
    fi

    # Some java programs have seen problems with the timezone in our containers.
    # If not already set, provide a default TZ
    if [ "x$TZ" = "x" ]; then
        export TZ="UTC"
    fi
fi 



#############################################################################
#
#  modules and env 
#

# prepend HTCondor libexec dir so that we can call chirp
if [ -e ../../main/condor/libexec ]; then
    DER=`(cd ../../main/condor/libexec; pwd)`
    export PATH=$DER:$PATH
fi

# load modules, if available
if [ "x$LMOD_BETA" = "x1" ]; then
    # used for testing the new el6/el7 modules 
    if [ -e /cvmfs/oasis.opensciencegrid.org/osg/sw/module-beta-init.sh ]; then
        . /cvmfs/oasis.opensciencegrid.org/osg/sw/module-beta-init.sh
    fi
elif [ -e /cvmfs/oasis.opensciencegrid.org/osg/sw/module-init.sh ]; then
    . /cvmfs/oasis.opensciencegrid.org/osg/sw/module-init.sh
fi


# fix discrepancy for Squid proxy URLs
if [ "x$GLIDEIN_Proxy_URL" = "x" -o "$GLIDEIN_Proxy_URL" = "None" ]; then
    if [ "x$OSG_SQUID_LOCATION" != "x" -a "$OSG_SQUID_LOCATION" != "None" ]; then
        export GLIDEIN_Proxy_URL="$OSG_SQUID_LOCATION"
    fi
fi


#############################################################################
#
#  Stash cache 
#

function setup_stashcp {
  module load stashcp
 
  # Determine XRootD plugin directory.
  # in lieu of a MODULE_<name>_BASE from lmod, this will do:
  export MODULE_XROOTD_BASE=$(which xrdcp | sed -e 's,/bin/.*,,')
  export XRD_PLUGINCONFDIR=$MODULE_XROOTD_BASE/etc/xrootd/client.plugins.d
 
}
 
# Check for PosixStashCache first
if [ "x$POSIXSTASHCACHE" = "x1" ]; then
  setup_stashcp
 
  # Add the LD_PRELOAD hook
  export LD_PRELOAD=$MODULE_XROOTD_BASE/lib64/libXrdPosixPreload.so:$LD_PRELOAD
 
  # Set proxy for virtual mount point
  # Format: cache.domain.edu/local_mount_point=/storage_path
  # E.g.: export XROOTD_VMP=data.ci-connect.net:/stash=/
  # Currently this points _ONLY_ to the OSG Connect source server
  export XROOTD_VMP=$(stashcp --closest | cut -d'/' -f3):/stash=/
 
elif [ "x$STASHCACHE" = 'x1' ]; then
  setup_stashcp
fi


#############################################################################
#
#  Load user specified modules
#

if [ "X$LoadModules" != "X" ]; then
    ModuleList=`echo $LoadModules | sed 's/^LoadModules = //i' | sed 's/"//g'`
    for Module in $ModuleList; do
        module load $Module
    done
fi


#############################################################################
#
#  Trace callback
#

#############################################################################
#
#  Cleanup
#

rm -f .osgvo-user-job-wrapper.sh >/dev/null 2>&1 || true


#############################################################################
#
#  Run the real job
#
exec "$@"
error=$?
echo "Failed to exec($error): $@" > $_CONDOR_WRAPPER_ERROR_FILE
exit 1



