#!/bin/bash

############################################################
#
# This script will setup the gLExec parameters
#
############################################################

glidein_config=$1

function append_config {
    echo "$1" >> condor_config
    if [ $? -ne 0 ]; then
	echo "Failed to to update condor_config!" 1>&2
	exit 1
    fi    
}

# --------------------------------------------------
# create a local copy of the shell
# gLExec does not like symlinks adn this way we are sure it is a file
cp -p /bin/sh ./sh
if [ $? -ne 0 ]; then
    echo "Failed to copy /bin/sh to . ($PWD)" 1>&2
    exit 1
fi
append_config "SH=$PWD/sh" 


# --------------------------------------------------
# Set glidein working dir into the tmp dir
# This is needes since the user will be changed and 
# the tmo directory is world writtable
glide_tmp_dir=`grep '^TMP_DIR ' $glidein_config | awk '{print $2}'`
if [ -z "$glide_tmp_dir" ]; then
    echo "TMP_DIR not found!" 1>&2
    exit 1
fi
append_config "GLEXEC_USER_DIR=$glide_tmp_dir"

# --------------------------------------------------
#
# Tell Condor to actually use gLExec
#
glexec_bin=`grep '^GLEXEC_BIN' $glidein_config | awk '{print $2}'`
if [ -z "$glexec_bin" ]; then
    glexec_bin="OSG"
    echo "GLEXEC_BIN not found, using default '$glexec_bin'"
fi

if [ "$glexec_bin" == "OSG" ]; then
    echo "GLEXEC_BIN was OSG, expand to '$OSG_GLEXEC_LOCATION'"
    glexec_bin="$OSG_GLEXEC_LOCATION"
fi

# but first test it does exist

if [ -x "$glexec_bin" ]; then
    echo "Using gLExec binary '$glexec_bin'"
else
    echo "gLExec binary '$glexec_bin' not found!" 1>&2
    exit 1
fi

append_config "GLEXEC_STARTER = True"
append_config "GLEXEC = $glexec_bin"

exit 0
