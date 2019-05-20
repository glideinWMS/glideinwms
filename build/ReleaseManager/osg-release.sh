#!/bin/sh

USAGE_STR="$0 [-h] TAG USER
 TAG       - tag or branch ID in the Git repository (branch pointers change, use a branch name only for scratch builds)
 USER      - username on the OSG build machine
 -h --help - print this message and exit"
 
[ "$1" == "-h" ] || [ "$1" == "--help" ] && { echo "$USAGE_STR"; exit 0; } 

if [ $# -ne 2 ]; then
    echo "ERROR: Missing arguments 'tag' and 'user'"
    echo "$USAGE_STR"
    exit 1
fi

gwms_tag=$1
username=$2
osg_buildmachine="library.cs.wisc.edu"
osg_uploaddir="/p/vdt/public/html/upstream/glideinwms/$gwms_tag"

gwms_repo="ssh://p-glideinwms@cdcvs.fnal.gov/cvs/projects/glideinwms"

work_dir="/tmp/osgrelease.$$"
gwms_location="$work_dir/glideinwms"

gwms_tar="$work_dir/glideinwms.tar.gz"

archive_gwms() {
    mkdir -p $work_dir
    cd $work_dir
    git clone $gwms_repo
    cd $gwms_location
    git checkout $gwms_tag
    [ $? -ne 0 ] && { echo "ERROR: Failed to checkout $gwms_tag, aborting. Did you push your commit?"; exit 1; }
    git archive $gwms_tag --prefix='glideinwms/' | gzip > $gwms_tar
}


archive_gwms

ssh $username@$osg_buildmachine "mkdir -p $osg_uploaddir"

if [ $? -eq 0 ]; then
    scp $gwms_tar $username@$osg_buildmachine:$osg_uploaddir
    [ $? -eq 0 ] && echo "Tarball Uploaded to $osg_buildmachine: $osg_uploaddir" || { echo "ERROR: failed to upload the tarball to $osg_buildmachine: $osg_uploaddir"; exit 1; }
else
    echo "ERROR: Failed to create directory $osg_uploaddir on the OSG build machine"
    exit 1
fi
