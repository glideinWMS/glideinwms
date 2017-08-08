#!/bin/bash
#
glidein_config="$1"

#error_gen=`grep '^ERROR_GEN_PATH ' $glidein_config | awk '{print $2}'`

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

export SINGULARITY_IMAGE_DEFAULT6="/cvmfs/singularity.opensciencegrid.org/bbockelm/cms:rhel6"
export SINGULARITY_IMAGE_DEFAULT7="/cvmfs/singularity.opensciencegrid.org/bbockelm/cms:rhel7"

advertise SINGULARITY_IMAGE_DEFAULT6 "$SINGULARITY_IMAGE_DEFAULT6" "S"
advertise SINGULARITY_IMAGE_DEFAULT7 "$SINGULARITY_IMAGE_DEFAULT7" "S"

exit 0
