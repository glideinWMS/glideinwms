################################
# Function used to calculate the md5 sum
# Arguments:
#   1: file name
#   2: option (quiet)
# Returns:
#   1 in case the md5sum cannot be calculated, or neither the md5sum nor the md5 can be found
md5wrapper() {
    local ERROR_RESULT
    ERROR_RESULT="???"
    local ONLY_SUM
    if [ "x$2" = "xquiet" ]; then
        ONLY_SUM=yes
    fi
    local executable
    executable=md5sum
    if which ${executable} 1>/dev/null 2>&1; then
        [ -n "${ONLY_SUM}" ] && executable="md5sum \"$1\" | cut -d ' ' -f 1" ||  executable="md5sum \"$1\""
    else
        executable=md5
        if ! which ${executable} 1>/dev/null 2>&1; then
            echo "${ERROR_RESULT}"
            log_warn "md5wrapper error: can't neither find md5sum nor md5"
            return 1
        fi
        [ -n "${ONLY_SUM}" ] && executable="md5 -q \"$1\"" || executable="md5 \"$1\""
    fi
    local res
    # Flagged by some checkers but OK
    if ! res="$(eval "${executable}" 2>/dev/null)"; then
        echo "${ERROR_RESULT}"
        log_warn "md5wrapper error: can't calculate md5sum using ${executable}"
        return 1
    fi
    echo "${res}" # result returned on stdout
}

###########################################
# Function used to check the file signature
# Arguments:
#   1: id
#   2: file name
# Globals:
#   cfs_id
#   cfs_fname
#   cfs_work_dir
#   cfs_desc_fname
#   cfs_signature
#   cfs_rc
#   tmp_signname
# Returns:
#   1 in case of corrupted file
check_file_signature() {
    cfs_id="$1"
    cfs_fname="$2"
    cfs_work_dir="$(get_work_dir "${cfs_id}")"
    cfs_desc_fname="${cfs_work_dir}/${cfs_fname}"
    cfs_signature="${cfs_work_dir}/signature.sha1"
    if [ "${check_signature}" -gt 0 ]; then # check_signature is global for simplicity
        tmp_signname="${cfs_signature}_$$_$(date +%s)_${RANDOM}"
        if ! grep " ${cfs_fname}$" "${cfs_signature}" > "${tmp_signname}"; then
            rm -f "${tmp_signname}"
            echo "No signature for ${cfs_desc_fname}." 1>&2
        else
            (cd "${cfs_work_dir}" && sha1sum -c "${tmp_signname}") 1>&2
            cfs_rc=$?
            if [ ${cfs_rc} -ne 0 ]; then
                "${main_dir}"/error_augment.sh -init
                "${main_dir}"/error_gen.sh -error "check_file_signature" "Corruption" "File $cfs_desc_fname is corrupted." "file" "${cfs_desc_fname}" "source_type" "${cfs_id}"
                "${main_dir}"/error_augment.sh  -process ${cfs_rc} "check_file_signature" "${PWD}" "sha1sum -c ${tmp_signname}" "$(date +%s)" "(date +%s)"
                "${main_dir}"/error_augment.sh -concat
                log_warn "File ${cfs_desc_fname} is corrupted."
                rm -f "${tmp_signname}"
                return 1
            fi
            rm -f "${tmp_signname}"
            echo "Signature OK for ${cfs_id}:${cfs_fname}." 1>&2
        fi
    fi
    return 0
}

########################################
# Function used to set the X509_USER_PROXY path to full path to the file
# Environment variables exported:
#   X509_USER_PROXY
set_proxy_fullpath() {
    if fullpath="$(readlink -f "${X509_USER_PROXY}")"; then
        echo "Setting X509_USER_PROXY ${X509_USER_PROXY} to canonical path ${fullpath}" 1>&2
        export X509_USER_PROXY="${fullpath}"
    else
        echo "Unable to get canonical path for X509_USER_PROXY, using ${X509_USER_PROXY}" 1>&2
    fi
}
