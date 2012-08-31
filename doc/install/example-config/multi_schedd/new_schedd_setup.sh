if [ $# -ne 1 ]
then
 echo "ERROR: arg1 should be schedd name."
 return 1
fi
LD=/opt/glidecondor/condor_local
export _CONDOR_SCHEDD_NAME=schedd_$1
export _CONDOR_MASTER_NAME=${_CONDOR_SCHEDD_NAME}
# SCHEDD and MASTER names MUST be the same (Condor requirement)
export _CONDOR_DAEMON_LIST="MASTER,SCHEDD"
export _CONDOR_LOCAL_DIR=$LD/$_CONDOR_SCHEDD_NAME
export _CONDOR_LOCK=$_CONDOR_LOCAL_DIR/lock
#-- condor shared port attributes, in case you enable it (at install time or later) --
#-- This is the actual global LOG dir --
#-- Make sure it actually points to the current value --
GLOBAL_LOG=$LD/log
#-- Basically, preserve the global values, since we do not run a private shared_port daemon --
export _CONDOR_SHARED_PORT_DAEMON_AD_FILE=${GLOBAL_LOG}/shared_port_ad
export _CONDOR_DAEMON_SOCKET_DIR=${GLOBAL_LOG}/daemon_sock
unset GLOBAL_LOG
unset LD
