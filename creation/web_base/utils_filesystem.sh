. utils_tarballs.sh
. utils_signals.sh
. utils_log.sh
. utils_xml.sh
. utils_params.sh
. utils_crypto.sh
. utils_http.sh
. glidein_cleanup.sh
. utils_fetch.sh

################################
# Function used to automatically determine and setup work directories
automatic_work_dir() {
    declare -a targets=("${_CONDOR_SCRATCH_DIR}"
                        "${OSG_WN_TMP}"
                        "${TG_NODE_SCRATCH}"
                        "${TG_CLUSTER_SCRATCH}"
                        "${SCRATCH}"
                        "${TMPDIR}"
                        "${TMP}"
                        "${PWD}"
                        )
    unset TMPDIR

    # 1 kB
    disk_required=1000000

    for d in "${targets[@]}"; do

        echo "Checking ${d} for potential use as work space... " 1>&2

        # does the target exist?
        if [ ! -e "${d}" ]; then
            echo "  Workdir: ${d} does not exist" 1>&2
            continue
        fi

        # make sure there is enough available diskspace
        free="$(df -kP "${d}" | awk '{if (NR==2) print $4}')"
        if [ "x${free}" = "x" ] || [ "${free}" -lt ${disk_required} ]; then
            echo "  Workdir: not enough disk space available in ${d}" 1>&2
            continue
        fi

        if touch "${d}/.dirtest.$$" >/dev/null 2>&1; then
            echo "  Workdir: ${d} selected" 1>&2
            rm -f "${d}/.dirtest.$$" >/dev/null 2>&1
            work_dir=${d}
            return 0
        fi
        echo "  Workdir: not allowed to write to ${d}" 1>&2
    done
    return 1
}

################################
# Function used to generate the directory ID
# It creates an ID to distinguish the directories when preserved
dir_id() {
    [[ ! ",${GLIDEIN_DEBUG_OPTIONS}," = *,nocleanup,* ]] && return
    local dir_id=""
    local tmp="${repository_url%%.*}"
    tmp="${tmp#*//}"
    dir_id="${tmp: -4}"
    tmp="${client_repository_url%%.*}"
    tmp="${tmp#*//}"
    dir_id="${dir_id}${tmp: -4}"
    [[ -z "${dir_id}" ]] && dir_id='debug'
    echo "${dir_id}_"
}

########################################
# Function used to make sure nobody else can write my files
# In the Grid world I cannot trust anybody
check_umask(){
    if ! umask 0022; then
        early_glidein_failure "Failed in umask 0022"
    fi
}    

###########################################
# Function used to check the file signature
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

###########################################
# Function used to prepare and move to the work directory
# Replace known keywords: Condor, CONDOR, OSG, TMPDIR, AUTO, .
# Empty $work_dir means PWD (same as ".")
# A custom path could be provided (no "*)" in case)
prepare_workdir(){
    if [ -z "${work_dir}" ]; then
        work_dir="$(pwd)"
    else
        case "${work_dir}" in
            Condor|CONDOR) work_dir="${_CONDOR_SCRATCH_DIR}";;
            OSG) work_dir="${OSG_WN_TMP}";;
            TMPDIR) work_dir="${TMPDIR}";;
            AUTO) automatic_work_dir;;
            .) work_dir="$(pwd)";;
        esac
    fi
    
    if [ -z "${work_dir}" ]; then
        early_glidein_failure "Unable to identify Startup dir for the glidein."
    fi
    
    if [ ! -e "${work_dir}" ]; then
        early_glidein_failure "Startup dir ${work_dir} does not exist."
    fi
    
    start_dir="$(pwd)"
    echo "Started in ${start_dir}"
    
    def_work_dir="${work_dir}/glide_$(dir_id)XXXXXX"
    if ! work_dir="$(mktemp -d "${def_work_dir}")"; then
        early_glidein_failure "Cannot create temp '${def_work_dir}'"
    else
        if ! cd "${work_dir}"; then
            early_glidein_failure "Dir '${work_dir}' was created but cannot cd into it."
        else
            echo "Running in ${work_dir}"
        fi
    fi
    work_dir_created=1
    
    # GWMS_SUBDIR defined on top
    GWMS_DIR="${work_dir}/$GWMS_SUBDIR"
    if ! mkdir "$GWMS_DIR" ; then
        early_glidein_failure "Cannot create '$GWMS_DIR'"
    fi
    gwms_lib_dir="${GWMS_DIR}/lib"
    if ! mkdir -p "$gwms_lib_dir" ; then
        early_glidein_failure "Cannot create '$gwms_lib_dir'"
    fi
    gwms_bin_dir="${GWMS_DIR}/bin"
    if ! mkdir -p "$gwms_bin_dir" ; then
        early_glidein_failure "Cannot create '$gwms_bin_dir'"
    fi
    gwms_exec_dir="${GWMS_DIR}/exec"
    if ! mkdir -p "$gwms_exec_dir" ; then
        early_glidein_failure "Cannot create '$gwms_exec_dir'"
    else
        for i in setup prejob postjob cleanup setup_singularity ; do
            mkdir -p "$gwms_exec_dir"/$i
        done
    fi
    
    # mktemp makes it user readable by definition (ignores umask)
    # TODO: MMSEC should this change to increase protection? Since GlExec is gone this should not be needed
    if [ -n "${GWMS_MULTIUSER_GLIDEIN}" ]; then
        if ! chmod a+rx "${work_dir}"; then
            early_glidein_failure "Failed chmod '${work_dir}'"
        fi
    fi
    
    def_glide_local_tmp_dir="/tmp/glide_$(dir_id)$(id -u -n)_XXXXXX"
    if ! glide_local_tmp_dir="$(mktemp -d "${def_glide_local_tmp_dir}")"; then
        early_glidein_failure "Cannot create temp '${def_glide_local_tmp_dir}'"
    fi
    glide_local_tmp_dir_created=1
    
    glide_tmp_dir="${work_dir}/tmp"
    if ! mkdir "${glide_tmp_dir}"; then
        early_glidein_failure "Cannot create '${glide_tmp_dir}'"
    fi
    
    if [ -n "${GWMS_MULTIUSER_GLIDEIN}" ]; then
        # TODO: MMSEC should this change to increase protection? Since GlExec is gone this should not be needed
        # the tmpdirs should be world writable
        # This way it will work even if the user spawned by the glidein is different than the glidein user
        # This happened in GlExec, outside user stays the same in Singularity
        if ! chmod 1777 "${glide_local_tmp_dir}"; then
            early_glidein_failure "Failed chmod '${glide_local_tmp_dir}'"
        fi
    
        if ! chmod 1777 "${glide_tmp_dir}"; then
            early_glidein_failure "Failed chmod '${glide_tmp_dir}'"
        fi
    fi
    
    short_main_dir=main
    main_dir="${work_dir}/${short_main_dir}"
    if ! mkdir "${main_dir}"; then
        early_glidein_failure "Cannot create '${main_dir}'"
    fi
    
    short_entry_dir=entry_${glidein_entry}
    entry_dir="${work_dir}/${short_entry_dir}"
    if ! mkdir "${entry_dir}"; then
        early_glidein_failure "Cannot create '${entry_dir}'"
    fi
    
    if [ -n "${client_repository_url}" ]; then
        short_client_dir=client
        client_dir="${work_dir}/${short_client_dir}"
        if ! mkdir "$client_dir"; then
            early_glidein_failure "Cannot create '${client_dir}'"
        fi
    
        if [ -n "${client_repository_group_url}" ]; then
            short_client_group_dir=client_group_${client_group}
            client_group_dir="${work_dir}/${short_client_group_dir}"
            if ! mkdir "${client_group_dir}"; then
                early_glidein_failure "Cannot create '${client_group_dir}'"
            fi
        fi
    fi
    
    # Move the token files from condor to glidein workspace
    mv "${start_dir}/tokens.tgz" .
    mv "${start_dir}/url_dirs.desc" .
    for idtk in ${start_dir}/*.idtoken; do
       if cp "${idtk}" . ; then
           echo "copied idtoken ${idtk} to $(pwd)"
       else
           echo "failed to copy idtoken  ${idtk} to $(pwd)" 1>&2
       fi
    done
    #if [ -e "${GLIDEIN_CONDOR_TOKEN}" ]; then
    #    mkdir -p ticket
    #    tname="$(basename ${GLIDEIN_CONDOR_TOKEN})"
    #    cp "${GLIDEIN_CONDOR_TOKEN}" "ticket/${tname}"
    #    export GLIDEIN_CONDOR_TOKEN="$(pwd)/ticket/${tname}"
    #fi
}
