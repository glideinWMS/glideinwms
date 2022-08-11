#*******************************************************************#
#                        utils_crypto.sh                            #
#        This script contains tarballs utility functions            #
#                      File Version: 1.0                            #
#*******************************************************************#
# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

##############################
# Utility functions to allow the script to source functions and retrieve data stored as tarball at the end of the script itself

#######################################
# Retrieve the specified data, which is appended as tarball
# Arguments:
#   1: selected file
get_data() {
    sed '1,/^#EOF$/d' < "${GWMS_STARTUP_SCRIPT}" | tar xz -O "$1"
}

#######################################
# Source the specified data, which is appended as tarball, without saving it
# Arguments:
#   1: selected file
source_data() {
    local data
    data=$(get_data "$1")
    [[ -n "$data" ]] && eval "$data"
}

#######################################
# Show a list of the payload tarballed files in this script
list_data() {
    sed '1,/^#EOF$/d' < "${GWMS_STARTUP_SCRIPT}" | tar tz
}

#######################################
# Extract and source all the tarball files
# Global:
#   IFS
extract_all_data() {
    local -a files
    # change separator to split the output file list from 'tar tz' command
    local IFS_OLD
    IFS_OLD="${IFS}"
    IFS=$'\n'
    files=($(list_data))
    for f in "${files[@]}"; do
        echo "Extracting file ${f}"
        get_data "${f}" > "${f}"
        echo "Sourcing file ${f}"
        # source_data "${f}" - can source the file saved instead of re-extracting it
        . "${f}"
    done
    IFS="${IFS_OLD}"
}
