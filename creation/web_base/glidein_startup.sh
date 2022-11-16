#!/bin/bash

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

#*******************************************************************#
#  glidein_startup.sh                                               #
# Main Glidein script. Load all components from separate scripts,   #
# start the Glidein up, invoke HTCondor startup, and cleanup        #
# at the end                                                        #
#*******************************************************************#

################################
# Default IFS, to protect against unusual environment
# better than "unset IFS" because works with restoring old one
IFS=$' \t\n'

GLOBAL_ARGS="$*"
# GWMS_STARTUP_SCRIPT=$0
GWMS_STARTUP_SCRIPT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/$(basename "${BASH_SOURCE[0]}")"
GWMS_PATH=""

################################
# Relative to the work directory (GWMS_DIR, gwms_lib_dir, gwms_bin_dir and gwms_exec_dir will be the absolute paths)
# bin (utilities), lib (libraries), exec (aux scripts to be executed/sourced, e.g. pre-job)
GWMS_SUBDIR=".gwms.d"

################################
# General options
GWMS_MULTIUSER_GLIDEIN=
# Set GWMS_MULTIUSER_GLIDEIN if the Glidein may spawn processes (for jobs) as a different user.
# This will prepare the glidein, e.g. setting to 777 the permission of TEMP directories
# This should never happen only when using GlExec. Not in Singularity, not w/o sudo mechanisms.
# Uncomment the following line if GlExec or similar will be used
GWMS_MULTIUSER_GLIDEIN=true

# Default GWMS log server
GWMS_LOGSERVER_ADDRESS='https://fermicloud152.fnal.gov/log'
SIGNAL_CHILDREN_LIST=

export LANG=C

################################
# Start all glideins
# Arguments:
#   1: number of glideins
# Globals (r/w):
#   SIGNAL_CHILDREN_LIST
# Used:
#   params
#   GLOBAL_ARG
# Important variables:
#   GLIDEIN_MULTIGLIDEIN_LAUNCHALL - if set in attrs, command to start all Glideins at once (multirestart 0)
#   GLIDEIN_MULTIGLIDEIN_LAUNCHER - if set in attrs, command to start the individual Glideins
do_start_all() {
    local num_glideins initial_dir multiglidein_launchall multiglidein_launcher g_dir startup_script
    num_glideins=$1
    initial_dir="$(pwd)"
    multiglidein_launchall=$(params_decode "$(params_get_simple GLIDEIN_MULTIGLIDEIN_LAUNCHALL "${params}")")
    multiglidein_launcher=$(params_decode "$(params_get_simple GLIDEIN_MULTIGLIDEIN_LAUNCHER "${params}")")
    startup_script="${GWMS_STARTUP_SCRIPT}"
    if [[ -n "${multiglidein_launchall}" ]]; then
        echo "Starting multi-glidein using launcher: ${multiglidein_launchall}"
        # shellcheck disable=SC2086
        ${multiglidein_launchall} "${startup_script}" -multirestart 0 ${GLOBAL_ARGS} &
        SIGNAL_CHILDREN_LIST="${SIGNAL_CHILDREN_LIST} $!"
    else
        if [[ "${initial_dir}" = "$(dirname "${startup_script}")" ]]; then
            startup_script="./$(basename "${startup_script}")"
        fi
        for i in $(seq 1 "${num_glideins}"); do
            g_dir="glidein_dir${i}"
            copy_all glidein_dir "${g_dir}"
            echo "Starting glidein ${i} in ${g_dir} ${multiglidein_launcher:+"with launcher ${GLIDEIN_MULTIGLIDEIN_LAUNCHER}"}"
            pushd "${g_dir}" || echo "Unable to cd in start directory"
            chmod +x "${startup_script}"
            # shellcheck disable=SC2086
            ${multiglidein_launcher} "${startup_script}" -multirestart "${i}" ${GLOBAL_ARGS} &
            SIGNAL_CHILDREN_LIST="${SIGNAL_CHILDREN_LIST} $!"
            popd || true
        done
        echo "Started multiple glideins: ${SIGNAL_CHILDREN_LIST}"
    fi
}

################################
# Spawn multiple glideins and wait, if needed
# Globals (r/w):
#   ON_DIE
# Used:
#   multi_glidein
#   multi_glidein_restart
spawn_multiple_glideins(){
    if [[ -n "${multi_glidein}" ]] && [[ -z "${multi_glidein_restart}" ]] && [[ "${multi_glidein}" -gt 1 ]]; then
        # start multiple glideins
        ON_DIE=0
        trap 'signal_ignore' SIGHUP
        signal_trap_with_arg 'signal_on_die_multi' SIGTERM SIGINT SIGQUIT
        do_start_all "${multi_glidein}"
        # Wait for all glideins and exit 0
        # TODO: Summarize exit codes and status from all child glideins
        echo "------ Multi-glidein parent waiting for child processes (${SIGNAL_CHILDREN_LIST}) ----------" 1>&2
        wait
        echo "------ Exiting multi-glidein parent ----------" 1>&2
        exit 0
    fi
}

########################################
# Setup OSG and/or Globus
# Globals (r/w):
#   GLOBUS_LOCATION
# Used:
#   OSG_GRID
#   GLITE_LOCAL_CUSTOMIZATION_DIR
#   GLOBUS_PATH
setup_OSG_Globus(){
    if [ -r "${OSG_GRID}/setup.sh" ]; then
        . "${OSG_GRID}/setup.sh"
    elif [ -r "${GLITE_LOCAL_CUSTOMIZATION_DIR}/cp_1.sh" ]; then
        . "${GLITE_LOCAL_CUSTOMIZATION_DIR}/cp_1.sh"
    fi

    if [ -z "${GLOBUS_PATH}" ]; then
        if [ -z "${GLOBUS_LOCATION}" ]; then
            # if GLOBUS_LOCATION not defined, try to guess it
            if [ -r "/opt/globus/etc/globus-user-env.sh" ]; then
                GLOBUS_LOCATION=/opt/globus
            elif  [ -r "/osgroot/osgcore/globus/etc/globus-user-env.sh" ]; then
                GLOBUS_LOCATION=/osgroot/osgcore/globus
            else
               log_warn "GLOBUS_LOCATION not defined and could not guess it."
               log_warn "Looked in:"
               log_warn ' /opt/globus/etc/globus-user-env.sh'
               log_warn ' /osgroot/osgcore/globus/etc/globus-user-env.sh'
               log_warn 'Continuing like nothing happened'
            fi
        fi

        if [ -r "${GLOBUS_LOCATION}/etc/globus-user-env.sh" ]; then
            . "${GLOBUS_LOCATION}/etc/globus-user-env.sh"
        else
            log_warn "GLOBUS_PATH not defined and ${GLOBUS_LOCATION}/etc/globus-user-env.sh does not exist."
            log_warn 'Continuing like nothing happened'
        fi
    fi
}

###########################################
# Checks the file signature
# Arguments:
#   1: id
#   2: file name
# Globals (r/w):
#   cfs_id
#   cfs_fname
#   cfs_work_dir
#   cfs_desc_fname
#   cfs_signature
# Used:
#   check_signature
#   tmp_signname
#   main_dir
#   cfs_rc
#   PWD
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
            f
            rm -f "${tmp_signname}"
            echo "Signature OK for ${cfs_id}:${cfs_fname}." 1>&2
            fi
        fi
    fi
    return 0
}

################################
# Print initial information header
# Parameters:
#   @: shell parameters
# Globals(r/w):
#   startup_time
#   retVal
# Used:
#   operation_mode
#   condorg_cluster
#   condorg_subcluster
#   condorg_schedd
#   glidein_uuid
#   glidein_cred_id
#   glidein_factory
#   glidein_name
#   glidein_entry
#   client_name
#   client_group
#   client_descript_file
#   client_descript_group_file
#   client_repository_url
#   client_sign_type
#   client_sign_id
#   client_sign_group_id
#   client_repository_group_url
#   multi_glidein
#   multi_glidein_restart
#   work_dir
#   repository_url
#   sign_type
#   descript_file
#   proxy_url
#   descript_entry_file
#   sign_id
#   sign_entry_id
#   set_debug
print_header(){
    startup_time="$(date +%s)"
    echo "Starting glidein_startup.sh at $(date) (${startup_time})"
    local md5wrapped
    md5wrapped="$(md5wrapper "$0")"
    retVal=$?
    if [ $retVal -ne 0 ]; then
        echo "Error on the md5wrapper"
        glidein_exit 1 #TODO(F): o solo exit?
    fi
    echo "script_checksum   = '${md5wrapped}'"
    echo "debug_mode        = '${operation_mode}'"
    echo "condorg_cluster   = '${condorg_cluster}'"
    echo "condorg_subcluster= '${condorg_subcluster}'"
    echo "condorg_schedd    = '${condorg_schedd}'"
    echo "glidein_uuid      = '${glidein_uuid}'"
    echo "glidein_credential_id = '${glidein_cred_id}'"
    echo "glidein_factory   = '${glidein_factory}'"
    echo "glidein_name      = '${glidein_name}'"
    echo "glidein_entry     = '${glidein_entry}'"
    if [ -n "${client_name}" ]; then
        # client name not required as it is not used for anything but debug info
        echo "client_name       = '${client_name}'"
    fi
    if [ -n "${client_group}" ]; then
        echo "client_group      = '${client_group}'"
    fi
    echo "multi_glidein/restart = '${multi_glidein}'/'${multi_glidein_restart}'"
    echo "work_dir          = '${work_dir}'"
    echo "web_dir           = '${repository_url}'"
    echo "sign_type         = '${sign_type}'"
    echo "proxy_url         = '${proxy_url}'"
    echo "descript_fname    = '${descript_file}'"
    echo "descript_entry_fname = '${descript_entry_file}'"
    echo "sign_id           = '${sign_id}'"
    echo "sign_entry_id     = '${sign_entry_id}'"
    if [ -n "${client_repository_url}" ]; then
        echo "client_web_dir              = '${client_repository_url}'"
        echo "client_descript_fname       = '${client_descript_file}'"
        echo "client_sign_type            = '${client_sign_type}'"
        echo "client_sign_id              = '${client_sign_id}'"
        if [ -n "${client_repository_group_url}" ]; then
            echo "client_web_group_dir        = '${client_repository_group_url}'"
            echo "client_descript_group_fname = '${client_descript_group_file}'"
            echo "client_sign_group_id        = '${client_sign_group_id}'"
        fi
    fi
    echo
    echo "Running on $(uname -n)"
    echo "System: $(uname -a)"
    if [ -e '/etc/redhat-release' ]; then
     echo "Release: $(cat /etc/redhat-release 2>&1)"
    fi
    echo "As: $(id)"
    echo "PID: $$"
    echo

    if [ ${set_debug} -ne 0 ]; then
      echo "------- Initial environment ---------------"  1>&2
      env 1>&2
      echo "------- =================== ---------------" 1>&2
    fi
}

################################
# Parse and verify arguments
# It allows some parameters to change arguments
# Globals (r/w):
#   tmp_par
#   multi_glidein
#   sleep_time
#   set_debug
#   repository_entry_url
#   proxy_url
#   client_sign_type
#   sign_type
# Used:
#   params
#   operation_mode
#   descript_file
#   descript_entry_file
#   glidein_name
#   glidein_entry
#   repository_url
#   client_descript_group_file, client_repository_group_url, client_descript_file, client_repository_url
#   sign_entry_id
#   sign_id
#   OSG_SQUID_LOCATION
parse_arguments(){
    # multiglidein GLIDEIN_MULTIGLIDEIN -> multi_glidein
    tmp_par=$(params_get_simple GLIDEIN_MULTIGLIDEIN "${params}")
    [ -n "${tmp_par}" ] && multi_glidein=${tmp_par}

    case "${operation_mode}" in
        nodebug)
            sleep_time=1199
            set_debug=0;;
        fast)
            sleep_time=150
            set_debug=1;;
        check)
            sleep_time=150
            set -x
            set_debug=2;;
        *)
            sleep_time=1199
            set_debug=1;;
    esac

    if [ -z "${descript_file}" ]; then
        log_warn "Missing descript fname."
        usage
        exit 1
    fi

    if [ -z "${descript_entry_file}" ]; then
        log_warn "Missing descript fname for entry."
        usage
        exit 1
    fi

    if [ -z "${glidein_name}" ]; then
        log_warn "Missing gliden name."
        usage
        exit 1
    fi

    if [ -z "${glidein_entry}" ]; then
        log_warn "Missing glidein entry name."
        usage
        exit 1
    fi


    if [ -z "${repository_url}" ]; then
        log_warn "Missing Web URL."
        usage
        exit 1
    fi

    repository_entry_url="${repository_url}/entry_${glidein_entry}"

    if [ -z "${proxy_url}" ]; then
      proxy_url="None"
    fi

    if [ "${proxy_url}" = "OSG" ]; then
      if [ -z "${OSG_SQUID_LOCATION}" ]; then
         # if OSG does not define a Squid, then don't use any
         proxy_url="None"
         log_warn "OSG_SQUID_LOCATION undefined, not using any Squid URL" 1>&2
      else
         proxy_url="$(echo "${OSG_SQUID_LOCATION}" | awk -F ':' '{if ($2 =="") {print $1 ":3128"} else {print $0}}')"
      fi
    fi

    if [ -z "${sign_id}" ]; then
        log_warn "Missing signature."
        usage
        exit 1
    fi

    if [ -z "${sign_entry_id}" ]; then
        log_warn "Missing entry signature."
        usage
        exit 1
    fi

    if [ -z "${sign_type}" ]; then
        sign_type="sha1"
    fi

    if [ "${sign_type}" != "sha1" ]; then
        log_warn "Unsupported signtype ${sign_type} found."
        usage
        exit 1
    fi

    if [ -n "${client_repository_url}" ]; then
      # client data is optional, user url as a switch
      if [ -z "${client_sign_type}" ]; then
          client_sign_type="sha1"
      fi

      if [ "${client_sign_type}" != "sha1" ]; then
        log_warn "Unsupported clientsigntype ${client_sign_type} found."
        usage
        exit 1
      fi

      if [ -z "${client_descript_file}" ]; then
        log_warn "Missing client descript fname."
        usage
        exit 1
      fi

      if [ -n "${client_repository_group_url}" ]; then
          # client group data is optional, user url as a switch
          if [ -z "${client_group}" ]; then
              log_warn "Missing client group name."
              usage
              exit 1
          fi

          if [ -z "${client_descript_group_file}" ]; then
              log_warn "Missing client descript fname for group."
              usage
              exit 1
          fi
      fi
    fi
}

###########################################
# Prepare and move to the work directory
# Replace known keywords: Condor, CONDOR, OSG, TMPDIR, AUTO, .
# Empty $work_dir means PWD (same as ".")
# A custom path could be provided (no "*)" in case)
# Globals (r/w):
#   work_dir
#   start_dir
#   def_work_dir
#   work_dir_created
#   GWMS_DIR
#   gwms_lib_dir
#   gwms_bin_dir
#   gwms_exec_dir
#   def_glide_local_tmp_dir
#   glide_local_tmp_dir_created
#   glide_tmp_dir
#   short_main_dir
#   main_dir
#   short_entry_dir
#   entry_dir
#   short_client_dir
#   client_dir
#   short_client_group_dir
#   client_group_dir
# Used:
#   _CONDOR_SCRATCH_DIR
#   OSG_WN_TMP
#   TMPDIR
#   GWMS_SUBDIR
#   dir_id
#   GWMS_MULTIUSER_GLIDEIN
#   client_repository_url
#   client_repository_group_url
#TODO: find a way to define bats test altering global variables and testing the work directory creation
prepare_workdir(){
    tmp="${work_dir}"
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
        early_glidein_failure "Unable to identify Startup dir for the glidein ($tmp)."
    fi

    if [ ! -e "${work_dir}" ]; then
        early_glidein_failure "Startup dir '${work_dir}' ($tmp) does not exist."
    fi

    start_dir="$(pwd)"
    echo "Started in '${start_dir}' ($tmp)"

    work_dir_template="${work_dir}/glide_$(dir_id)XXXXXX"
    if ! work_dir="$(mktemp -d "${work_dir_template}")"; then
        early_glidein_failure "Cannot create word_dir '${work_dir_template}'"
    else
        if ! cd "${work_dir}"; then
            early_glidein_failure "Work dir '${work_dir}' was created but cannot cd into it."
        else
            echo "Running in ${work_dir}"
        fi
    fi
    work_dir_created=1

    # GWMS_SUBDIR defined on top
    GWMS_DIR="${work_dir}/$GWMS_SUBDIR"
    if ! mkdir "$GWMS_DIR" ; then
        early_glidein_failure "Cannot create GWMS_DIR '$GWMS_DIR'"
    fi
    gwms_lib_dir="${GWMS_DIR}/lib"
    if ! mkdir -p "$gwms_lib_dir" ; then
        early_glidein_failure "Cannot create lib dir '$gwms_lib_dir'"
    fi
    gwms_bin_dir="${GWMS_DIR}/bin"
    if ! mkdir -p "$gwms_bin_dir" ; then
        early_glidein_failure "Cannot create bin dir '$gwms_bin_dir'"
    fi
    gwms_exec_dir="${GWMS_DIR}/exec"
    if ! mkdir -p "$gwms_exec_dir" ; then
        early_glidein_failure "Cannot create exec dir '$gwms_exec_dir'"
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

    glide_local_tmp_dir_template="/tmp/glide_$(dir_id)$(id -u -n)_XXXXXX"
    if ! glide_local_tmp_dir="$(mktemp -d "${glide_local_tmp_dir_template}")"; then
        early_glidein_failure "Cannot create temp '${glide_local_tmp_dir_template}'"
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
    # TODO: compare this w/ setup_x509.sh
    # monitoring tokens, Should be using same credentials directory?
    mv "${start_dir}/tokens.tgz" .
    mv "${start_dir}/url_dirs.desc" .
    # idtokens are handled in setup_x509.sh - TODO: remove once verified
    #for idtk in ${start_dir}/*.idtoken; do
    #   if cp "${idtk}" . ; then
    #       echo "copied idtoken ${idtk} to $(pwd)"
    #   else
    #       echo "failed to copy idtoken  ${idtk} to $(pwd)" 1>&2
    #   fi
    #done
    #if [ -e "${GLIDEIN_CONDOR_TOKEN}" ]; then
    #    mkdir -p ticket
    #    tname="$(basename ${GLIDEIN_CONDOR_TOKEN})"
    #    cp "${GLIDEIN_CONDOR_TOKEN}" "ticket/${tname}"
    #    export GLIDEIN_CONDOR_TOKEN="$(pwd)/ticket/${tname}"
    #fi
}

########################################
# Creates the glidein configuration
# Globals (r/w):
#   glidein_config
# Used:
#   glidein_uuid, glidein_factory, glidein_name, glidein_entry, glidein_cred_id
#   client_name, client_group, client_dir, client_descript_file, client_sign_id. client_repository_group_url
#   client_group_dir, client_descript_group_file, client_sign_group_id
#   condorg_cluster, condorg_schedd, condorg_subcluster
#   set_debug, proxy_url, PWD, wrapper_list, slots_layout, GLIDEIN_CONDOR_TOKEN
#   start_dir, main_dir, entry_dir, glide_tmp_dir, glide_local_tmp_dir
#   descript_file, descript_entry_file
#   sign_id, sign_entry_id
create_glidein_config(){
    glidein_config="${PWD}/glidein_config"
    if ! echo > "${glidein_config}"; then
        early_glidein_failure "Could not create '${glidein_config}'"
    fi
    if ! {
        echo "# --- glidein_startup vals ---"
        echo "GLIDEIN_UUID ${glidein_uuid}"
        echo "GLIDEIN_Factory ${glidein_factory}"
        echo "GLIDEIN_Name ${glidein_name}"
        echo "GLIDEIN_Entry_Name ${glidein_entry}"

        if [ -n "${client_name}" ]; then
            # client name not required as it is not used for anything but debug info
            echo "GLIDECLIENT_Name ${client_name}"
        fi
        if [ -n "${client_group}" ]; then
            # client group not required as it is not used for anything but debug info
            echo "GLIDECLIENT_Group ${client_group}"
        fi
        echo "GLIDEIN_CredentialIdentifier ${glidein_cred_id}"
        echo "CONDORG_CLUSTER ${condorg_cluster}"
        echo "CONDORG_SUBCLUSTER ${condorg_subcluster}"
        echo "CONDORG_SCHEDD ${condorg_schedd}"
        echo "DEBUG_MODE ${set_debug}"
        echo "GLIDEIN_STARTUP_PID $$"
        echo "GLIDEIN_START_DIR_ORIG ${start_dir}"
        echo "GLIDEIN_WORKSPACE_ORIG $(pwd)"
        echo "GLIDEIN_WORK_DIR ${main_dir}"
        echo "GLIDEIN_ENTRY_WORK_DIR ${entry_dir}"
        echo "TMP_DIR ${glide_tmp_dir}"
        echo "GLIDEIN_LOCAL_TMP_DIR ${glide_local_tmp_dir}"
        echo "PROXY_URL ${proxy_url}"
        echo "DESCRIPTION_FILE ${descript_file}"
        echo "DESCRIPTION_ENTRY_FILE ${descript_entry_file}"
        echo "GLIDEIN_Signature ${sign_id}"
        echo "GLIDEIN_Entry_Signature ${sign_entry_id}"

        if [ -n "${client_repository_url}" ]; then
            echo "GLIDECLIENT_WORK_DIR ${client_dir}"
            echo "GLIDECLIENT_DESCRIPTION_FILE ${client_descript_file}"
            echo "GLIDECLIENT_Signature ${client_sign_id}"
            if [ -n "${client_repository_group_url}" ]; then
                echo "GLIDECLIENT_GROUP_WORK_DIR ${client_group_dir}"
                echo "GLIDECLIENT_DESCRIPTION_GROUP_FILE ${client_descript_group_file}"
                echo "GLIDECLIENT_Group_Signature ${client_sign_group_id}"
            fi
        fi
        echo "B64UUENCODE_SOURCE ${PWD}/b64uuencode.source"
        echo "ADD_CONFIG_LINE_SOURCE ${PWD}/add_config_line.source"
        echo "GET_ID_SELECTORS_SOURCE ${PWD}/get_id_selectors.source"
        echo "LOGGING_UTILS_SOURCE ${PWD}/logging_utils.source"
        echo "GLIDEIN_PATHS_SOURCE ${PWD}/glidein_paths.source"
        echo "WRAPPER_LIST ${wrapper_list}"
        echo "SLOTS_LAYOUT ${slots_layout}"
        # Add a line saying we are still initializing...
        echo "GLIDEIN_INITIALIZED 0"
        # ...but be optimist, and leave advertise_only for the actual error handling script
        echo "GLIDEIN_ADVERTISE_ONLY 0"
        echo "GLIDEIN_CONDOR_TOKEN ${GLIDEIN_CONDOR_TOKEN}"
        echo "# --- User Parameters ---"
    } >> "${glidein_config}"; then
        early_glidein_failure "Failed in updating '${glidein_config}'"
    fi
}

##############################
# Utility functions to allow the script to source functions and retrieve data stored as tarball at the end of the script itself
#TODO: Bats test files need to be defined for these functions

#######################################
# Retrieve the specified data, which is appended as tarball
# Arguments:
#   1: selected file
# Used:
#   GWMS_STARTUP_SCRIPT
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
# Used:
#   GWMS_STARTUP_SCRIPT
list_data() {
    sed '1,/^#EOF$/d' < "${GWMS_STARTUP_SCRIPT}" | tar tz
}

#######################################
# Extract and source all the tarball files
# Global:
#   IFS
extract_and_source_all_data() {
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

_main(){

    ################################
    parse_options "$@"

    ################################
    # Set the slots_layout, make sure to have a valid slots_layout
    if (echo "x${slots_layout}" | grep -i fixed) >/dev/null 2>&1 ; then
        slots_layout="fixed"
    else
        slots_layout="partitionable"
    fi

    ################################
    parse_arguments

    ################################
    # Generate the glidein UUID
    if command -v uuidgen >/dev/null 2>&1; then
        glidein_uuid="$(uuidgen)"
    else
        glidein_uuid="$(od -x -w32 -N32 /dev/urandom | awk 'NR==1{OFS="-"; print $2$3,$4,$5,$6,$7$8$9}')"
    fi

    ################################
    print_header "$@"

    ################################
    spawn_multiple_glideins

    ########################################
    # Make sure nobody else can write my files. In the Grid world I cannot trust anybody.
    if ! umask 0022; then
        early_glidein_failure "Failed in umask 0022"
    fi

    ########################################
    setup_OSG_Globus

    ########################################
    # Set the tokens
    [ -n "${X509_USER_PROXY}" ] && set_proxy_fullpath
    num_gct=0

    # TODO: this is covered in setup_x590,sh - remove once verified
    #for tk in "$(pwd)/credential_"*".idtoken"; do
    #    echo "Setting GLIDEIN_CONDOR_TOKEN to ${tk} " 1>&2
    #    num_gct=$(( num_gct + 1 ))
    #    export GLIDEIN_CONDOR_TOKEN="${tk}"
    #    fullpath="$(readlink -f "${tk}" )"
    #    if [ $? -eq 0 ]; then
    #        echo "Setting GLIDEIN_CONDOR_TOKEN ${tk} to canonical path ${fullpath}" 1>&2
    #        export GLIDEIN_CONDOR_TOKEN="${fullpath}"
    #    else
    #        echo "Unable to get canonical path for GLIDEIN_CONDOR_TOKEN ${tk}" 1>&2
    #    fi
    #done
    #if [ ! -f "${GLIDEIN_CONDOR_TOKEN}" ] ; then
    #    token_err_msg="problem setting GLIDEIN_CONDOR_TOKEN"
    #    token_err_msg="${token_err_msg} will attempt to recover, but condor IDTOKEN auth may fail"
    #    echo "${token_err_msg}"
    #    echo "${token_err_msg}" 1>&2
    #fi
    #if [ ! "${num_gct}" -eq  1 ] ; then
    #    token_err_msg="WARNING  GLIDEIN_CONDOR_TOKEN set ${num_gct} times, should be 1 !"
    #    token_err_msg="${token_err_msg} condor IDTOKEN auth may fail"
    #    echo "${token_err_msg}"
    #    echo "${token_err_msg}" 1>&2
    #fi

    ########################################
    prepare_workdir

    ######################################
    # extract and source all the data contained at the end of this script as tarball
    extract_and_source_all_data

    #####################################
    wrapper_list="${PWD}/wrapper_list.lst"
    touch "${wrapper_list}"

    #####################################
    create_glidein_config

    #####################################
    # shellcheck disable=SC2086
    params2file ${params}

    #####################################
    # setup logging
    log_init "${glidein_uuid}" "${work_dir}"
    # remove these files, if they are still there
    rm -rf tokens.tgz url_dirs.desc tokens
    log_setup "${glidein_config}"

    #####################################
    echo "Downloading files from Factory and Frontend"
    log_write "glidein_startup.sh" "text" "Downloading file from Factory and Frontend" "debug"

    #####################################
    # Fetch descript and signature files
    # disable signature check before I get the signature file itself
    # check_signature is global
    check_signature=0

    for gs_id in main entry client client_group
    do
      if [ -z "${client_repository_url}" ]; then
          if [ "${gs_id}" = "client" ]; then
              # no client file when no cilent_repository
              continue
          fi
      fi
      if [ -z "${client_repository_group_url}" ]; then
          if [ "${gs_id}" = "client_group" ]; then
              # no client group file when no cilent_repository_group
              continue
          fi
      fi

      gs_id_work_dir="$(get_work_dir ${gs_id})"

      # Fetch description file
      gs_id_descript_file="$(get_descript_file ${gs_id})"
      fetch_file_regular "${gs_id}" "${gs_id_descript_file}"
      if ! signature_file_line="$(grep "^signature " "${gs_id_work_dir}/${gs_id_descript_file}")"; then
          log_warn "No signature in description file ${gs_id_work_dir}/${gs_id_descript_file} (wc: $(wc < "${gs_id_work_dir}/${gs_id_descript_file}" 2>/dev/null))."
          glidein_exit 1
      fi
      signature_file=$(echo "${signature_file_line}" | cut -s -f 2-)

      # Fetch signature file
      gs_id_signature="$(get_signature ${gs_id})"
      fetch_file_regular "${gs_id}" "${signature_file}"
      echo "${gs_id_signature}  ${signature_file}" > "${gs_id_work_dir}/signature.sha1.test"
      if ! (cd "${gs_id_work_dir}" && sha1sum -c signature.sha1.test) 1>&2 ; then
          log_warn "Corrupted signature file '${gs_id_work_dir}/${signature_file}'."
          glidein_exit 1
      fi
      # for simplicity use a fixed name for signature file
      mv "${gs_id_work_dir}/${signature_file}" "${gs_id_work_dir}/signature.sha1"
    done

    # re-enable for everything else
    check_signature=1

    # Now verify the description was not tampered with
    # doing it so late should be fine, since nobody should have been able
    # to fake the signature file, even if it faked its name in
    # the description file
    for gs_id in main entry client client_group
    do
      if [ -z "${client_repository_url}" ]; then
          if [ "${gs_id}" = "client" ]; then
              # no client file when no cilent_repository
              continue
          fi
      fi
      if [ -z "${client_repository_group_url}" ]; then
          if [ "${gs_id}" = "client_group" ]; then
              # no client group file when no cilent_repository_group
              continue
          fi
      fi

      gs_id_descript_file="$(get_descript_file ${gs_id})"
      if ! check_file_signature "${gs_id}" "${gs_id_descript_file}"; then
          gs_id_work_dir="$(get_work_dir ${gs_id})"
          log_warn "Corrupted description file ${gs_id_work_dir}/${gs_id_descript_file}."
          glidein_exit 1
      fi
    done


    ###################################################
    # get last_script, as it is used by the fetch_file
    gs_id_work_dir="$(get_work_dir main)"
    gs_id_descript_file="$(get_descript_file main)"
    last_script="$(grep "^last_script " "${gs_id_work_dir}/${gs_id_descript_file}" | cut -s -f 2-)"
    if [ -z "${last_script}" ]; then
        log_warn "last_script not in description file ${gs_id_work_dir}/${gs_id_descript_file}."
        glidein_exit 1
    fi
    #cleanup_script="$(grep "^cleanup_script " "${gs_id_work_dir}/${gs_id_descript_file}" | cut -s -f 2-)"
    cleanup_script=$(grep "^GLIDEIN_CLEANUP_SCRIPT " "${glidein_config}" | cut -d ' ' -f 2-)


    ##############################
    # Fetch all the other files
    for gs_file_id in "main file_list" "client preentry_file_list" "client_group preentry_file_list" "client aftergroup_preentry_file_list" "entry file_list" "main at_file_list" "client file_list" "client_group file_list" "client aftergroup_file_list" "main after_file_list"
    do
        gs_id="$(echo "${gs_file_id}" |awk '{print $1}')"

        if [ -z "${client_repository_url}" ]; then
            if [ "${gs_id}" = "client" ]; then
                # no client file when no client_repository
                continue
            fi
        fi
        if [ -z "${client_repository_group_url}" ]; then
            if [ "${gs_id}" = "client_group" ]; then
                # no client group file when no client_repository_group
                continue
            fi
        fi

        gs_file_list_id="$(echo "${gs_file_id}" |awk '{print $2}')"

        gs_id_work_dir="$(get_work_dir "${gs_id}")"
        gs_id_descript_file="$(get_descript_file "${gs_id}")"

        # extract list file name
        if ! gs_file_list_line="$(grep "^${gs_file_list_id} " "${gs_id_work_dir}/${gs_id_descript_file}")"; then
            if [ -z "${client_repository_group_url}" ]; then
                if [ "${gs_file_list_id:0:11}" = "aftergroup_" ]; then
                    # afterfile_.. files optional when no client_repository_group
                    continue
                fi
            fi
          log_warn "No '${gs_file_list_id}' in description file ${gs_id_work_dir}/${gs_id_descript_file}."
          glidein_exit 1
        fi
        # space+tab separated file with multiple elements (was: awk '{print $2}', not safe for spaces in file name)
        gs_file_list="$(echo "${gs_file_list_line}" | cut -s -f 2 | sed -e 's/[[:space:]]*$//')"

        # fetch list file
        fetch_file_regular "${gs_id}" "${gs_file_list}"

        # Fetch files contained in list
        # TODO: $file is actually a list, so it cannot be doublequoted (expanding here is needed). Can it be made more robust for linters? for now, just suppress the sc warning here
        # shellcheck disable=2086
        while read -r file
        do
            if [ "${file:0:1}" != "#" ]; then
                fetch_file "${gs_id}" $file
            fi
        done < "${gs_id_work_dir}/${gs_file_list}"

        # Files to go into the GWMS_PATH
        if [ "$gs_file_id" = "main at_file_list" ]; then
            # setup here to make them available for other setup scripts
            add_to_path "$gwms_bin_dir"
            # all available now: gwms-python was in main,file_list; condor_chirp is in main,at_file_list
            for file in "gwms-python" "condor_chirp"
            do
                cp "${gs_id_work_dir}/$file" "$gwms_bin_dir"/
            done
            cp -r "${gs_id_work_dir}/lib"/* "$gwms_lib_dir"/
        elif [ "$gs_file_id" = "main after_file_list" ]; then
            # in case some library has been added/updated
            rsync -ar "${gs_id_work_dir}/lib"/ "$gwms_lib_dir"/
            # new knowns binaries? add a loop like above: for file in ...
        elif [[ "$gs_file_id" = client* ]]; then
            # TODO: gwms25073 this is a workaround until there is an official designation for setup script fragments
            [[ -e "${gs_id_work_dir}/setup_prejob.sh" ]] && { cp "${gs_id_work_dir}/setup_prejob.sh" "$gwms_exec_dir"/prejob/ ; chmod a-x "$gwms_exec_dir"/prejob/setup_prejob.sh ; }
        fi
    done

    #############################
    fixup_condor_dir

    ##############################
    # Start the glidein main script
    add_config_line "GLIDEIN_INITIALIZED" "1"
    log_write "glidein_startup.sh" "text" "Starting the glidein main script" "info"
    log_write "glidein_startup.sh" "file" "${glidein_config}" "debug"
    send_logs_to_remote          # checkpoint
    echo "# --- Last Script values ---" >> glidein_config
    last_startup_time=$(date +%s)
    let validation_time=${last_startup_time}-${startup_time}
    echo "=== Last script starting $(date) (${last_startup_time}) after validating for ${validation_time} ==="
    echo
    ON_DIE=0
    trap 'signal_ignore' SIGHUP
    signal_trap_with_arg 'signal_on_die' SIGTERM SIGINT SIGQUIT
    #trap 'signal_on_die' TERM
    #trap 'signal_on_die' INT
    gs_id_work_dir=$(get_work_dir main)
    "${main_dir}"/error_augment.sh -init
    "${gs_id_work_dir}/${last_script}" glidein_config &
    wait $!
    ret=$?
    if [ ${ON_DIE} -eq 1 ]; then
        ret=0
    fi
    last_startup_end_time=$(date +%s)
    "${main_dir}"/error_augment.sh  -process ${ret} "${last_script}" "${PWD}" "${gs_id_work_dir}/${last_script} glidein_config" "${last_startup_time}" "${last_startup_end_time}"
    "${main_dir}"/error_augment.sh -concat
    let last_script_time=${last_startup_end_time}-${last_startup_time}
    echo "=== Last script ended $(date) (${last_startup_end_time}) with code ${ret} after ${last_script_time} ==="
    echo
    if [ ${ret} -ne 0 ]; then
        log_warn "Error running '${last_script}'"
    fi

    #############################
    # Things like periodic scripts might put messages here if they want them printed in the (stderr) logfile
    echo "=== Exit messages left by periodic scripts ===" 1>&2
    if [ -f exit_message ]; then
        cat exit_message 1>&2
    else
        echo "No message left" 1>&2
    fi
    echo 1>&2

    #########################
    # clean up after I finish
    glidein_exit ${ret}
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
	_main "$@"
fi
