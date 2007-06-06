if [ $# -ne 1 ]
then
 echo "Schedd name expected!"
 return 1
fi

LD=`condor_config_val LOCAL_DIR`
QDB=`condor_config_val QUILL_DB_NAME`


export _CONDOR_SCHEDD_NAME=schedd_$1
export _CONDOR_MASTER_NAME=${_CONDOR_SCHEDD_NAME}
# SCHEDD and MASTER names MUST be the same (Condor requirement)
export _CONDOR_QUILL_NAME=quill_$1@`uname -n`
export _CONDOR_QUILL_DB_NAME=${QDB}_$1
export _CONDOR_DAEMON_LIST="MASTER, SCHEDD,QUILL"
export _CONDOR_LOCAL_DIR=$LD/$_CONDOR_SCHEDD_NAME
export _CONDOR_LOCK=$_CONDOR_LOCAL_DIR/lock

unset LD
unset QDB
