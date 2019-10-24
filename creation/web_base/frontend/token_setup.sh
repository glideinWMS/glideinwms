#!/bin/bash 
# 

glidein_config_val () {
   grep "^$1 " $glidein_config | cut -d ' ' -f 2-
}

if [ "$glidein_config" = "" ]; then
	glidein_config="$1"
fi

GWMS_THIS_SCRIPT="`basename "$0"`"
GWMS_THIS_SCRIPT_DIR="`dirname "$0"`"


if [ ! -f "$glidein_config" ]; then
    if [ -f "../$glidein_config" ]; then
        glidein_config="../$glidein_config"
    fi
fi
if [ ! -f "$glidein_config" ]; then
    glidein_config=$(find . -name glidein_config)
fi

if [ ! -f "$glidein_config" ]; then
    echo "glidein_config not found! $0 exiting"
    exit 1
fi

echo  "$GWMS_THIS_SCRIPT from directory $GWMS_SCRIPT_DIR starting, `date` in `pwd`"
LOCAL_DIR=`pwd`
GLIDEIN_WORK_DIR=$(glidein_config_val GLIDEIN_WORK_DIR) 
EXTRA_LIB_LIST=$(glidein_config_val EXTRA_LIB_LIST)
TOKEN_FILE=$(glidein_config_val AUTH_TOKEN) 
CONDOR_DIR=$(glidein_config_val CONDOR_DIR)

#
#change $(LOCAL_DIR)/stuff (condor) to ${LOCAL_DIR}/stuff (bash)
#
SEC_TOKEN_DIRECTORY=$(echo $(glidein_config_val SEC_TOKEN_DIRECTORY) | sed -e 's/.*\///')
SEC_TOKEN_DIRECTORY="${LOCAL_DIR}/${SEC_TOKEN_DIRECTORY}"

SEC_TOKEN_SYSTEM_DIRECTORY=$(echo $(glidein_config_val SEC_TOKEN_SYSTEM_DIRECTORY) | sed -e 's/.*\///')
SEC_TOKEN_SYSTEM_DIRECTORY="${LOCAL_DIR}/${SEC_TOKEN_SYSTEM_DIRECTORY}"

SEC_PASSWORD_DIRECTORY=$(echo $(glidein_config_val SEC_PASSWORD_DIRECTORY) | sed -e 's/.*\///')
SEC_PASSWORD_DIRECTORY="${LOCAL_DIR}/${SEC_PASSWORD_DIRECTORY}"

SEC_PASSWORD_FILE=$(echo $(glidein_config_val SEC_PASSWORD_FILE) | sed -e 's/.*\///')
SEC_PASSWORD_FILE="${SEC_PASSWORD_DIRECTORY}/${SEC_PASSWORD_FILE}"



mkdir -p $SEC_TOKEN_SYSTEM_DIRECTORY
mkdir -p $SEC_TOKEN_DIRECTORY
mkdir -p $SEC_PASSWORD_DIRECTORY
touch $SEC_PASSWORD_FILE
cp ticket/$TOKEN_FILE $SEC_TOKEN_DIRECTORY
mv ticket/$TOKEN_FILE $SEC_TOKEN_SYSTEM_DIRECTORY
#for LIB in $EXTRA_LIB_LIST; do
#    mv $GWMS_THIS_SCRIPT_DIR/$LIB ${CONDOR_DIR}/lib
#done
cd ${CONDOR_DIR}/lib 
ln -s libSciTokens.so.0.0.2 libSciTokens.so.0 
ln -s libSciTokens.so.0.0.2 libSciTokens.so 
ln -s libmunge.so.2.0.0 libmunge.so.2 
cd $LOCAL_DIR




