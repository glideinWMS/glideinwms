# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

#
# Project:
#   glideinWMS
#
# File Version:
#
# Description:
#   This is an include file for glidein_startup.sh
#   It creates a minimal condor_mapfile so that condor_advertise can work in case of problems.
#

glidein_config="$1"

# import add_config_line function
add_config_line_source=$(grep -m1 '^ADD_CONFIG_LINE_SOURCE ' "$glidein_config" | cut -d ' ' -f 2-)
# shellcheck source=./add_config_line.source
. "$add_config_line_source"

error_gen=$(gconfig_get ERROR_GEN_PATH "$glidein_config")

# create a condor_mapfile starting from a grid-mapfile
function create_condormapfile {
    id=`id -un`

    # make sure there is nothing in place already
    rm -f "$X509_CONDORMAP"
    touch "$X509_CONDORMAP"
    chmod go-wx "$X509_CONDORMAP"

    # trust any GSI traffic
    echo "GSI (.*) gsi" >> "$X509_CONDORMAP"

    # add local user
    echo "FS $id localuser" >> "$X509_CONDORMAP"

    # deny any other type of traffic
    echo "FS (.*) anonymous" >> "$X509_CONDORMAP"

    return 0
}

############################################################
#
# Main
#
############################################################

# Assume all functions exit on error
X509_CONDORMAP="$PWD/condor_mapfile"

create_condormapfile

gconfig_add X509_CONDORMAP "$X509_CONDORMAP"

# this is required by the condor_startup script
# A star will allow everyone, which is OK for condor_advertize of the error classad
gconfig_add X509_GRIDMAP_TRUSTED_DNS "*"

"$error_gen" -ok "create_temp_mapfile.sh"

exit 0
