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
