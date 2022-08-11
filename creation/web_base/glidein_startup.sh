#!/bin/bash -x
#*******************************************************************#
#                      glidein_startup.sh                           #
#     SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC     #
#              SPDX-License-Identifier: Apache-2.0                  #
#                      File Version:                                 #
#*******************************************************************#


################################
# Default IFS, to protect against unusual environment
# better than "unset IFS" because works with restoring old one
IFS=$' \t\n'

GLOBAL_ARGS="$*"

# GWMS_STARTUP_SCRIPT=$0
GWMS_STARTUP_SCRIPT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/$(basename "${BASH_SOURCE[0]}")"

################################
# Relative to the work directory (GWMS_DIR, gwms_lib_dir, gwms_bin_dir and gwms_exec_dir will be the absolute paths)
# bin (utilities), lib (libraries), exec (aux scripts to be executed/sourced, e.g. pre-job)
GWMS_PATH=""
GWMS_SUBDIR=".gwms.d"

################################
export LANG=C

# General options
GWMS_MULTIUSER_GLIDEIN=
# Set GWMS_MULTIUSER_GLIDEIN if the Glidein may spawn processes (for jobs) as a different user.
# This will prepare the glidein, e.g. setting to 777 the permission of TEMP directories
# This should never happen only when using GlExec. Not in Singularity, not w/o sudo mechanisms.
# Comment the following line if GlExec or similar will not be used
#GWMS_MULTIUSER_GLIDEIN=true

# Default GWMS log server
GWMS_LOGSERVER_ADDRESS='https://fermicloud152.fnal.gov/log'
GWMS_MULTIGLIDEIN_CHILDS=

list_data() {
    # Show a list of the payload tarballed files in this script
    sed '1,/^#EOF$/d' < "${GWMS_STARTUP_SCRIPT}" | tar tz
}

extract_all_data() {
    # Extract and source all the tarball files
    local -a files
    # change separator to split the output file list from 'tar tz' command
    local IFS_OLD="${IFS}"
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

################################
# Function used to start multiple glideins
# Arguments:
#   1: prefix of the files to skip
#   2: directory
copy_all() {
   mkdir -p "$2"
   for f in *; do
       [[ -e "${f}" ]] || break    # TODO: should this be a continue?
       if [[ "${f}" = ${1}* ]]; then
           continue
       fi
       cp -r "${f}" "$2"/
   done
}
# TODO: should it copy also hidden files?

################################
# Function used to start all glideins
# Arguments:
#   1: number of glideins
# Global:
#   GWMS_MULTIGLIDEIN_CHILDS
# Important Variables:
#   GLIDEIN_MULTIGLIDEIN_LAUNCHALL - if set in attrs, command to start all Glideins at once (multirestart 0)
#   GLIDEIN_MULTIGLIDEIN_LAUNCHER - if set in attrs, command to start the individual Glideins
do_start_all() {
    local num_glideins initial_dir multiglidein_launchall multiglidein_launcher g_dir
    num_glideins=$1
    initial_dir="$(pwd)"
    multiglidein_launchall=$(params_decode "$(params_get_simple GLIDEIN_MULTIGLIDEIN_LAUNCHALL "${params}")")
    multiglidein_launcher=$(params_decode "$(params_get_simple GLIDEIN_MULTIGLIDEIN_LAUNCHER "${params}")")
    local startup_script
    startup_script="${GWMS_STARTUP_SCRIPT}"
    if [[ -n "${multiglidein_launchall}" ]]; then
        echo "Starting multi-glidein using launcher: ${multiglidein_launchall}"
        # shellcheck disable=SC2086
        ${multiglidein_launchall} "${startup_script}" -multirestart 0 ${GLOBAL_ARGS} &
        GWMS_MULTIGLIDEIN_CHILDS="${GWMS_MULTIGLIDEIN_CHILDS} $!"
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
            GWMS_MULTIGLIDEIN_CHILDS="${GWMS_MULTIGLIDEIN_CHILDS} $!"
            popd || true
        done
        echo "Started multiple glideins: ${GWMS_MULTIGLIDEIN_CHILDS}"
    fi
}

# TODO (HERE)

################################
# Function used to spawn multiple glideins and wait, if needed
# Global:
#   ON_DIE
spawn_multiple_glideins(){
    if [[ -n "${multi_glidein}" ]] && [[ -z "${multi_glidein_restart}" ]] && [[ "${multi_glidein}" -gt 1 ]]; then
        # start multiple glideins
        ON_DIE=0
        trap 'ignore_signal' SIGHUP
        trap_with_arg 'on_die_multi' SIGTERM SIGINT SIGQUIT
        do_start_all "${multi_glidein}"
        # Wait for all glideins and exit 0
        # TODO: Summarize exit codes and status from all child glideins
        echo "------ Multi-glidein parent waiting for child processes (${GWMS_MULTIGLIDEIN_CHILDS}) ----------" 1>&2
        wait
        echo "------ Exiting multi-glidein parent ----------" 1>&2
        exit 0
    fi
}  

########################################
# Function used to setup OSG and/or Globus
# Global:
#   GLOBUS_LOCATION
setup_OSG_Globus(){
    if [ -r "${OSG_GRID}/setup.sh" ]; then
        . "${OSG_GRID}/setup.sh"
    else
      if [ -r "${GLITE_LOCAL_CUSTOMIZATION_DIR}/cp_1.sh" ]; then
        . "${GLITE_LOCAL_CUSTOMIZATION_DIR}/cp_1.sh"
      fi
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

########################################
# Function used to add $1 to GWMS_PATH and update PATH
# Environment:
#   GWMS_PATH
#   PATH
add_to_path() {
    logdebug "Adding to GWMS_PATH: $1"
    local old_path
    old_path=":${PATH%:}:"
    old_path="${old_path//:$GWMS_PATH:/}"
    local old_gwms_path
    old_gwms_path=":${GWMS_PATH%:}:"
    old_gwms_path="${old_gwms_path//:$1:/}"
    old_gwms_path="${1%:}:${old_gwms_path#:}"
    export GWMS_PATH="${old_gwms_path%:}"
    old_path="${GWMS_PATH}:${old_path#:}"
    export PATH="${old_path%:}"
}

########################################
# Function that removes the native condor tarballs directory to allow factory ops to use native condor tarballs
# All files in the native condor tarballs have a directory like condor-9.0.11-1-x86_64_CentOS7-stripped
# However the (not used anymore) gwms create_condor_tarball removes that dir
fixup_condor_dir() {
    # Check if the condor dir has only one subdir, the one like "condor-9.0.11-1-x86_64_CentOS7-stripped"
    # See https://stackoverflow.com/questions/32429333/how-to-test-if-a-linux-directory-contain-only-one-subdirectory-and-no-other-file
    if [ $(find "${gs_id_work_dir}/condor" -maxdepth 1 -type d -printf 1 | wc -m) -eq 2 ]; then
        echo "Fixing directory structure of condor tarball"
        mv "${gs_id_work_dir}"/condor/condor*/* "${gs_id_work_dir}"/condor > /dev/null
    else
        echo "Condor tarball does not need to be fixed"
    fi
}

########################################
# Function that creates the glidein configuration
# Global:
#   glidein_config
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
        echo "GLIDEIN_START_DIR_ORIG  ${start_dir}"
        echo "GLIDEIN_WORKSPACE_ORIG  $(pwd)"
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

################################
# Block of code used to handle the list of parameters
# params will contain the full list of parameters
# -param_XXX YYY will become "XXX YYY"
#TODO: can use an array instead?
params=""
while [ $# -gt 0 ]
    do case "$1" in
        -factory)    glidein_factory="$2";;
        -name)       glidein_name="$2";;
        -entry)      glidein_entry="$2";;
        -clientname) client_name="$2";;
        -clientgroup) client_group="$2";;
        -web)        repository_url="$2";;
        -proxy)      proxy_url="$2";;
        -dir)        work_dir="$2";;
        -sign)       sign_id="$2";;
        -signtype)   sign_type="$2";;
        -signentry)  sign_entry_id="$2";;
        -cluster)    condorg_cluster="$2";;
        -subcluster) condorg_subcluster="$2";;
        -submitcredid) glidein_cred_id="$2";;
        -schedd)     condorg_schedd="$2";;
        -descript)   descript_file="$2";;
        -descriptentry)   descript_entry_file="$2";;
        -clientweb)             client_repository_url="$2";;
        -clientwebgroup)        client_repository_group_url="$2";;
        -clientsign)            client_sign_id="$2";;
        -clientsigntype)        client_sign_type="$2";;
        -clientsigngroup)       client_sign_group_id="$2";;
        -clientdescript)        client_descript_file="$2";;
        -clientdescriptgroup)   client_descript_group_file="$2";;
        -slotslayout)           slots_layout="$2";;
        -v)          operation_mode="$2";;
        -multiglidein)  multi_glidein="$2";;
        -multirestart)  multi_glidein_restart="$2";;
        -param_*)    params="$params $(echo "$1" | awk '{print substr($0,8)}') $2";;
        *)  (log_warn "Unknown option $1"; usage; exit 1) 1>&2; exit 1
    esac
    shift 2
done  

################################
# Code block used to set the slots_layout
# make sure to have a valid slots_layout
if (echo "x${slots_layout}" | grep -i fixed) >/dev/null 2>&1 ; then
    slots_layout="fixed"
else
    slots_layout="partitionable"
fi

################################
parse_arguments

################################
# Code block used to generate the glidein UUID
if command -v uuidgen >/dev/null 2>&1; then
    glidein_uuid="$(uuidgen)"
else
    glidein_uuid="$(od -x -w32 -N32 /dev/urandom | awk 'NR==1{OFS="-"; print $2$3,$4,$5,$6,$7$8$9}')"
fi

################################
print_header "@"

################################
spawn_multiple_glideins 

########################################
# Code block used to make sure nobody else can write my files
# in the Grid world I cannot trust anybody
if ! umask 0022; then
    early_glidein_failure "Failed in umask 0022"
fi

########################################
setup_OSG_Globus

########################################
# Code block used to set the tokens
[ -n "${X509_USER_PROXY}" ] && set_proxy_fullpath
num_gct=0
for tk in "$(pwd)/credential_"*".idtoken"; do
    echo "Setting GLIDEIN_CONDOR_TOKEN to ${tk} " 1>&2
    num_gct=$(( num_gct + 1 ))
    export GLIDEIN_CONDOR_TOKEN="${tk}"
    fullpath="$(readlink -f "${tk}" )"
    if [ $? -eq 0 ]; then
        echo "Setting GLIDEIN_CONDOR_TOKEN ${tk} to canonical path ${fullpath}" 1>&2
        export GLIDEIN_CONDOR_TOKEN="${fullpath}"
    else
        echo "Unable to get canonical path for GLIDEIN_CONDOR_TOKEN ${tk}" 1>&2
    fi
done
if [ ! -f "${GLIDEIN_CONDOR_TOKEN}" ] ; then
    token_err_msg="problem setting GLIDEIN_CONDOR_TOKEN"
    token_err_msg="${token_err_msg} will attempt to recover, but condor IDTOKEN auth may fail"
    echo "${token_err_msg}"
    echo "${token_err_msg}" 1>&2
fi
if [ ! "${num_gct}" -eq  1 ] ; then
    token_err_msg="WARNING  GLIDEIN_CONDOR_TOKEN set ${num_gct} times, should be 1 !"
    token_err_msg="${token_err_msg} condor IDTOKEN auth may fail"
    echo "${token_err_msg}"
    echo "${token_err_msg}" 1>&2
fi

########################################
prepare_workdir

########################################
# extract and source all the data contained at the end of this script as tarball
extract_all_data 

########################################
wrapper_list="${PWD}/wrapper_list.lst"
touch "${wrapper_list}"

########################################
create_glidein_config 

########################################
# shellcheck disable=SC2086
params2file ${params}

############################################
# Setup logging
log_init "${glidein_uuid}" "${work_dir}"
# Remove these files, if they are still there
rm -rf tokens.tgz url_dirs.desc tokens
log_setup "${glidein_config}"
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

#TODO(F): qui

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
trap 'ignore_signal' SIGHUP
trap_with_arg 'on_die' SIGTERM SIGINT SIGQUIT
#trap 'on_die' TERM
#trap 'on_die' INT
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
#Things like periodic scripts might put messages here if they want them printed in the (stderr) logfile
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
