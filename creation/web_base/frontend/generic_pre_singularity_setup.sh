#!/bin/bash

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

#
glidein_config="$1"

advertise() {
    key="$1"
    value="$2"
    atype="$3"

    if [ "$glidein_config" != "NONE" ]; then
        gconfig_add $key "$value"
        add_condor_vars_line $key "$atype" "-" "+" "Y" "Y" "+"
    fi

    if [ "$atype" = "S" ]; then
        echo "$key = \"$value\""
    else
        echo "$key = $value"
    fi
}

if [[ "$glidein_config" != "NONE" ]]; then
    # import advertise and add_condor_vars_line functions
    if [[ -z "$add_config_line_source" ]]; then
        export add_config_line_source=$(grep -m1 '^ADD_CONFIG_LINE_SOURCE ' "$glidein_config" | cut -d ' ' -f 2-)
        export       condor_vars_file=$(grep -m1 -i "^CONDOR_VARS_FILE "    "$glidein_config" | cut -d ' ' -f 2-)
    fi
    . "$add_config_line_source"
fi

# Important: each VO must replace the following variable with the paths to singularity images that they want to use.
# The format of SINGULARITY_IMAGES_DICT is a comma separated list of key:image, where:
# - key is the platform of the image (an ID that can be requested in REQUIRED_OS). It cannot contain colons (:) or commas (,)
# - image is the path (or URL) to the image to use with Singularity. It cannot contain commas (,)
# If you set an image for the key 'default', this will be picked if no preference is expressed by the job
# And also remember that for now, GWMS supports Singularity images under /cvmfs/, preferably under
# /cvmfs/singularity.opensciencegrid.org/ or at least on a path which existence can be verified (-e test)
# CVMFS path as /cvmfs, the eventual translation to $CVMFS_MOUNT_DIR will happen later since the value may change

# Note that you can add SINGULARITY_IMAGES_DICT also as attribute in the Factory or Frontend configuration

# Note the legacy variables/attributes  SINGULARITY_IMAGE_DEFAULT, SINGULARITY_IMAGE_DEFAULT6 and SINGULARITY_IMAGE_DEFAULT7 will override the
# dictionary values fro 'rhel7', 'rhel6' and 'rhel8' respectively
# you have to comment out both export and advertise lines together!!

export SINGULARITY_IMAGES_DICT="rhel7:/cvmfs/singularity.opensciencegrid.org/opensciencegrid/osgvo-el7:latest,rhel6:/cvmfs/singularity.opensciencegrid.org/opensciencegrid/osgvo-el6:latest,rhel8:/cvmfs/singularity.opensciencegrid.org/opensciencegrid/osgvo-el8:latest"
advertise SINGULARITY_IMAGES_DICT "$SINGULARITY_IMAGES_DICT" "S"

exit 0
