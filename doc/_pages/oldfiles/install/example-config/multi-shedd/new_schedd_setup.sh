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
#-- condor_shares_port daemon attributes --
## export _CONDOR_USE_SHARED_PORT=True
## export _CONDOR_SHARED_PORT_DAEMON_AD_FILE=$LD/log/shared_port_ad
## export _CONDOR_DAEMON_SOCKET_DIR=$LD/log/daemon_sock
unset LD
