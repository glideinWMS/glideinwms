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

###########################################
# Untar support function
# Arguments:
#   1: id
#   2: filename
# Global:
#   gus_id
#   gus_fname
#   gus_prefix
#   gus_config_cfg
#   gus_config_file
#   gus_dir
# Returns:
#   0 in case of success, otherwise glidein_exit with 1
get_untar_subdir() {
    gus_id="$1"
    gus_fname="$2"

    gus_prefix="$(get_prefix "${gus_id}")"
    gus_config_cfg="${gus_prefix}UNTAR_CFG_FILE"

    gus_config_file="$(grep "^${gus_config_cfg} " glidein_config | cut -d ' ' -f 2-)"
    if [ -z "${gus_config_file}" ]; then
        log_warn "Error, cannot find '${gus_config_cfg}' in glidein_config."
        glidein_exit 1
    fi

    gus_dir="$(grep -i "^${gus_fname} " "${gus_config_file}" | cut -s -f 2-)"
    if [ -z "${gus_dir}" ]; then
        log_warn "Error, untar dir for '${gus_fname}' cannot be empty."
        glidein_exit 1
    fi

    echo "${gus_dir}"
    return 0
}
