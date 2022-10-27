#!/bin/sh

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

USAGE_STR="$0 [-h] TAG USER [REPO]
 TAG       - tag or branch ID in the Git repository (branch pointers change, use a branch name only for scratch builds)
 USER      - username on the OSG build machine
 REPO      - url of the Git repository (default: https://github.com/glideinWMS/glideinwms.git)
 -h --help - print this message and exit"

[ "$1" == "-h" ] || [ "$1" == "--help" ] && { echo "$USAGE_STR"; exit 0; }

if [ $# -lt 2 ]; then
    echo "ERROR: Missing arguments 'tag' and 'user'"
    echo "$USAGE_STR"
    exit 1
fi

gwms_tag=$1
username=$2
gwms_repo="https://github.com/glideinWMS/glideinwms.git"
if [ $# -eq 3 ]; then
    gwms_repo=$3
fi

# At the end of 2019 OSG switched to moria. library still works but is deprecated. was: osg_buildmachine="library.cs.wisc.edu"
osg_buildmachine="moria.cs.wisc.edu"
osg_uploaddir="/p/vdt/public/html/upstream/glideinwms/$gwms_tag"

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
    local archive_tag
    archive_tag="$gwms_tag"
    if [ -x ./build/bigfiles/bigfiles.sh ]; then
        # Add also uncommitted big files instead of links
        if ! ./build/bigfiles/bigfiles.sh -pr ; then
            echo "WARNING bigfiles.sh returned an error."
        fi
        # From: https://stackoverflow.com/questions/2766600/git-archive-of-repository-with-uncommitted-changes
        # better than "--add-file" solution: no git version requirement, files are already tracked
        archive_tag=$(git stash create)
        if [ -z "$archive_tag" ]; then
            # echo "WARNING: No changes adding big files to ${gwms_tag}. bigfiles.sh may have failed." }
            archive_tag="$gwms_tag"
        else
            echo "Big files changes applied"
            gwms_tag="$gwms_tag+BIGFILES"
        fi
    fi
    git archive ${archive_tag} --prefix='glideinwms/' | gzip > "$gwms_tar"
}


archive_gwms

echo "Tarball Created for $gwms_tag (sha1sum, file): $(sha1sum "$gwms_tar")"
echo "Use the following to update the upstream file:"
echo "echo 'glideinwms/$gwms_tag/glideinwms.tar.gz sha1sum=$(sha1sum "$gwms_tar" | cut -f 1 -d ' ')' > upstream/developer.tarball.source"

if ssh $username@$osg_buildmachine "mkdir -p $osg_uploaddir"; then
    if scp "$gwms_tar" "$username@$osg_buildmachine:$osg_uploaddir"; then
        echo "Tarball Uploaded to $osg_buildmachine: $osg_uploaddir"
    else
        echo "ERROR: failed to upload the tarball to $osg_buildmachine: $osg_uploaddir"
        exit 1
    fi
else
    echo "ERROR: Failed to create directory '$osg_uploaddir' on the OSG build machine"
    exit 1
fi
