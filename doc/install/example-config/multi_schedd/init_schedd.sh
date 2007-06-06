#!/bin/sh
source /opt/glidecondor/new_schedd_setup.sh $1
# add whatever other config you need
# create needed directories
/opt/glidecondor/sbin/condor_init
# copy Quill writer passwd
cp -p $_CONDOR_LOCAL_DIR/../spool/.quillwritepassword $_CONDOR_LOCAL_DIR/spool/ 
