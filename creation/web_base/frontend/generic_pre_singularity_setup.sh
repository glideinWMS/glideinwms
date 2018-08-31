#!/bin/bash
#
glidein_config="$1"

function advertise {
    key="$1"
    value="$2"
    atype="$3"

    if [ "$glidein_config" != "NONE" ]; then
        add_config_line $key "$value"
        add_condor_vars_line $key "$atype" "-" "+" "Y" "Y" "+"
    fi

    if [ "$atype" = "S" ]; then
        echo "$key = \"$value\""
    else
        echo "$key = $value"
    fi
}

if [ "$glidein_config" != "NONE" ]; then
    # import advertise and add_condor_vars_line functions
    if [ "x$add_config_line_source" = "x" ]; then
        export add_config_line_source=`grep '^ADD_CONFIG_LINE_SOURCE ' $glidein_config | awk '{print $2}'`
        export       condor_vars_file=`grep -i "^CONDOR_VARS_FILE "    $glidein_config | awk '{print $2}'`
    fi
    source $add_config_line_source
fi

# Important: each VO must replace the following variable with the paths to singularity images that they want to use.
# The format of SINGULARITY_IMAGES_DICT is a comma separated list of key:image, where:
# - key is the platform of the image (an ID that can be requested in REQUIRED_OS). It cannot contain colons (:) or commas (,)
# - image is the path (or URL) to the image to use with Singularity. It cannot contain commas (,)
# If you set an image for the key 'default', this will be picked if no preference is expressed by the job
# And also remember that for now, GWMS supports Singularity images under /cvmfs/, preferably under
# /cvmfs/singularity.opensciencegrid.org/ or at least on a path which existence can be verified (-e test)

# Note that you can add SINGULARITY_IMAGES_DICT also as attribute in the Factory or Frontend configuration

# Note the legacy variables/attributes  SINGULARITY_IMAGE_DEFAULT, SINGULARITY_IMAGE_DEFAULT6 and SINGULARITY_IMAGE_DEFAULT7 will override the
# dictionary values fro 'rhel6' and 'rhel7' respectively
# you have to comment out both export and advertise lines together!!

export SINGULARITY_IMAGES_DICT="rhel6:/cvmfs/singularity.opensciencegrid.org/opensciencegrid/osgvo-el6:latest,rhel7:/cvmfs/singularity.opensciencegrid.org/opensciencegrid/osgvo-el7:latest"
advertise SINGULARITY_IMAGES_DICT "$SINGULARITY_IMAGES_DICT" "S"

exit 0
