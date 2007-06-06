if [ -z "$CONDOR_BASE_PATH" ]
then
 export CONDOR_BASE_PATH=/home/gcbuser/condor/dist
 #export CONDOR_IDS=4732.5063
 export CONDOR_CONFIG=$CONDOR_BASE_PATH/etc/condor_config

 export PATH=$PATH:$CONDOR_BASE_PATH/bin/
 export MANPATH=$MANPATH:$CONDOR_BASE_PATH/man
fi
