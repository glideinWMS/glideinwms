#!/bin/bash
# 
EXITSLEEP=5

function info {
    echo "INFO  " $@ 1>&2
}

function info_dbg {
    if [ "x$GLIDEIN_DEBUG_OUTPUT" != "x" ]; then
        info "DEBUG: file:"$0 $@
    fi
}

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
    val=`(grep -i "^$2 " $1 | cut -d= -f2 | sed -e "s/^[\"' \t\n\r]//g" -e "s/[\"' \t\n\r]$//g" | sed -e "s/^[\"' \t\n\r]//g" ) 2>/dev/null`
    echo $val
}



if [ "x$GWMS_SINGULARITY_REEXEC" = "x" ]; then
    # set up environment so we can execute singularity
    
    if [ "x$_CONDOR_JOB_AD" = "x" ]; then
        export _CONDOR_JOB_AD="NONE"
    fi
    if [ "x$_CONDOR_MACHINE_AD" = "x" ]; then
        export _CONDOR_MACHINE_AD="NONE"
    fi

 
    ## from singularity_setup.sh executed earlier
    export HAS_SINGULARITY=$(getPropBool $_CONDOR_MACHINE_AD HAS_SINGULARITY)
    export GWMS_SINGULARITY_PATH=$(getPropStr $_CONDOR_MACHINE_AD SINGULARITY_PATH)
    export GWMS_SINGULARITY_VERSION=$(getPropStr $_CONDOR_MACHINE_AD SINGULARITY_VERSION)
    export GWMS_SINGULARITY_IMAGE_DEFAULT6=$(getPropStr $_CONDOR_MACHINE_AD SINGULARITY_IMAGE_DEFAULT6)
    export GWMS_SINGULARITY_IMAGE_DEFAULT7=$(getPropStr $_CONDOR_MACHINE_AD SINGULARITY_IMAGE_DEFAULT7)
    export GLIDEIN_REQUIRED_OS=$(getPropStr $_CONDOR_MACHINE_AD GLIDEIN_REQUIRED_OS)
    export GLIDEIN_DEBUG_OUTPUT=$(getPropStr $_CONDOR_MACHINE_AD GLIDEIN_DEBUG_OUTPUT)
  
    ## from Job ClassAd
    export REQUIRED_OS=$(getPropStr $_CONDOR_JOB_AD REQUIRED_OS)
    export GWMS_SINGULARITY_IMAGE=$(getPropStr $_CONDOR_JOB_AD SingularityImage)
    export CVMFS_REPOS_LIST=$(getPropStr $_CONDOR_JOB_AD CVMFSReposList)
    if [ "x$GLIDEIN_DEBUG_OUTPUT" = "x" ]; then
        export GLIDEIN_DEBUG_OUTPUT=$(getPropStr $_CONDOR_JOB_AD GLIDEIN_DEBUG_OUTPUT)
    fi
  
 
 
    #GWMS we do not allow users to set SingularityAutoLoad
    export GWMS_SINGULARITY_AUTOLOAD=1
    export GWMS_SINGULARITY_BIND_CVMFS=1

    #############################################################################
    #
    #  Singularity
    #
    if [ "x$HAS_SINGULARITY" = "x1" -a "xGWMS_SINGULARITY_PATH" != "x" ]; then

        # We make sure that every cvmfs repository that users specify in CVMFSReposList is available, otherwise this script exits with 1
        info_dbg "CVMFS Repos List = $CVMFS_REPOS_LIST" 
        holdfd=3
        if [ "x$CVMFS_REPOS_LIST" != "x" ]; then
            for x in $(echo $CVMFS_REPOS_LIST | sed 's/,/ /g'); do
                if eval "exec $holdfd</cvmfs/$x"; then
                    echo "/cvmfs/$x exists and available"
                    let "holdfd=holdfd+1"
                else
                    echo "/cvmfs/$x NOT available"
                    sleep $EXITSLEEP
                    exit 1
                fi
              done
        fi

        if [ "x$GWMS_SINGULARITY_IMAGE" = "x" ]; then
            # Use OS matching to determine default; otherwise, set to the global default.
            if [ "x$GLIDEIN_REQUIRED_OS" = "xany" ]; then
                DESIRED_OS=$REQUIRED_OS
                if [ "x$DESIRED_OS" = "xany" ]; then
                    DESIRED_OS="rhel7"
                fi
            else
                DESIRED_OS=$(python -c "print sorted(list(set('$REQUIRED_OS'.split(',')).intersection('$GLIDEIN_REQUIRED_OS'.split(','))))[0]" 2>/dev/null)
            fi

            if [ "x$DESIRED_OS" = "x" ]; then
                if [ "x$SINGULARITY_IMAGE_DEFAULT6" != "x" ]; then 
                    GWMS_SINGULARITY_IMAGE="$SINGULARITY_IMAGE_DEFAULT6"
                else
                    GWMS_SINGULARITY_IMAGE="$SINGULARITY_IMAGE_DEFAULT7"
                fi
            elif [ "x$DESIRED_OS" = "xrhel6" ]; then
                GWMS_SINGULARITY_IMAGE="$SINGULARITY_IMAGE_DEFAULT6"
            else # For now, we just enumerate RHEL6 and RHEL7.
                GWMS_SINGULARITY_IMAGE="$SINGULARITY_IMAGE_DEFAULT7"
            fi
        fi
        # At this point, GWMS_SINGULARITY_IMAGE is still empty, something is wrong
        if [ "x$GWMS_SINGULARITY_IMAGE" = "x" ]; then 
           echo "Error: If you get this error when you did not specify desired OS, your VO does not support any default image" 1>&2
           echo "Error: If you get this error when you specified desired OS, your VO does not support that OS" 1>&2
           exit 1
        fi

    else #if [ "x$HAS_SINGULARITY" = "x1" -a "xSINGULARITY_PATH" != "x" ];

        if ! echo "$GWMS_SINGULARITY_IMAGE" | grep ^"/cvmfs" >/dev/null 2>&1; then
            echo "warning: $GWMS_SINGULARITY_IMAGE is not in /cvmfs area" 1>&2
            exit 1
        fi
    fi

    # for /cvmfs based directory images, expand the path without symlinks so that
    # the job can stay within the same image for the full duration
    if echo "$GWMS_SINGULARITY_IMAGE" | grep /cvmfs >/dev/null 2>&1; then
        if (cd $GWMS_SINGULARITY_IMAGE) >/dev/null 2>&1; then
            NEW_IMAGE_PATH=`(cd $GWMS_SINGULARITY_IMAGE && pwd -P) 2>/dev/null`
            if [ "x$NEW_IMAGE_PATH" != "x" ]; then
                export GWMS_SINGULARITY_IMAGE_HUMAN=$GWMS_SINGULARITY_IMAGE
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
    # cvmfs access inside container (default, but optional)
    if [ "x$GWMS_SINGULARITY_BIND_CVMFS" = "x1" ]; then
        GWMS_SINGULARITY_EXTRA_OPTS="$GWMS_SINGULARITY_EXTRA_OPTS --bind /cvmfs"
    fi

    # We want to bind $PWD to /srv within the container - however, in order
    # to do that, we have to make sure everything we need is in $PWD, most
    # notably the user-job-wrapper.sh (this script!)
    cp $0 .osgvo-user-job-wrapper.sh
    export JOB_WRAPPER_SINGULARITY="/srv/.osgvo-user-job-wrapper.sh"

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

    #quote $GWMS_SINGULARITY_PATH to deal with a path that contains whitespaces
    #
    info_dbg  exec "$GWMS_SINGULARITY_PATH" exec $GWMS_SINGULARITY_EXTRA_OPTS \
                               --home $PWD:/srv \
                               --pwd /srv  --scratch /var/tmp  --scratch /tmp  \
                               --contain --ipc --pid   \
                               "$GWMS_SINGULARITY_IMAGE"  $JOB_WRAPPER_SINGULARITY $CMD

    exec "$GWMS_SINGULARITY_PATH" exec $GWMS_SINGULARITY_EXTRA_OPTS \
                               --home $PWD:/srv \
                               --pwd /srv --scratch /var/tmp --scratch /tmp \
                               --contain --ipc --pid  \
                               "$GWMS_SINGULARITY_IMAGE" $JOB_WRAPPER_SINGULARITY  $CMD
   

else # if [ "x$GWMS_SINGULARITY_REEXEC" = "x" ] 
    # we are now inside singularity - fix up the env
    info_dbg "running inside singularity env = "`printenv`
    unset TMP
    unset TEMP
    unset X509_CERT_DIR
    for key in X509_USER_PROXY X509_USER_CERT _CONDOR_MACHINE_AD _CONDOR_JOB_AD \
               _CONDOR_SCRATCH_DIR _CONDOR_CHIRP_CONFIG _CONDOR_JOB_IWD ; do
        eval val="\$$key"
        val=`echo "$val" | sed -E "s;$GWMS_SINGULARITY_OUTSIDE_PWD(.*);/srv\1;"`
        eval $key=$val
        info_dbg "changed $key => $val"
    done

    # If X509_USER_PROXY and friends are not set by the job, we might see the
    # glidein one - in that case, just unset the env var
    for key in X509_USER_PROXY X509_USER_CERT X509_USER_KEY ; do
        eval val="\$$key"
        if [ "x$val" != "x" ]; then
            if [ ! -e "$val" ]; then
                eval unset $key >/dev/null 2>&1 || true
                info_dbg "unset $key"
            fi
        fi
    done

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
    export PATH="$DER:$PATH"
fi

rm -f .osgvo-user-job-wrapper.sh >/dev/null 2>&1 || true

#############################################################################
#
#  Run the real job
#
exec "$@"
error=$?
echo "Failed to exec($error): $@" > $_CONDOR_WRAPPER_ERROR_FILE
info "exec $@ failed: exit code $error"
exit $error

