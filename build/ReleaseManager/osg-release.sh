#!/bin/sh

if [ $# -ne 2 ]; then
    echo "ERROR: Missing arguments 'tag' and 'user'"
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
    git archive $gwms_tag --prefix='glideinwms/' | gzip > $gwms_tar
}


archive_gwms

ssh $username@$osg_buildmachine "mkdir -p $osg_uploaddir"

if [ "$?" = "0" ]; then
    scp $gwms_tar $username@$osg_buildmachine:$osg_uploaddir
    echo "Tarball Uploaded to $osg_buildmachine: $osg_uploaddir"
else
    echo "ERROR: Failed to create directory $osg_uploaddir"
fi
