#!/bin/bash

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

#*******************************************************************#
# utils_gs_http.sh                                                  #
# This script contains http utility functions for the               #
# glidein_startup.sh script                                         #
#*******************************************************************#

############################################
# Gets the proper descript file based on id
# Arguments:
#   1: type (main/entry/client/client_group)
# Used:
#   repository_url
#   repository_entry_url
#   client_repository_url
#   client_repository_group_url
# Returns:
#   1 in case of invalid ID
get_repository_url() {
    case "$1" in
        main) echo "${repository_url}";;
        entry) echo "${repository_entry_url}";;
        client) echo "${client_repository_url}";;
        client_group) echo "${client_repository_group_url}";;
        *) echo "[get_repository_url] Invalid id: $1" 1>&2
           return 1
           ;;
    esac
}

#####################
# Periodic execution support function and global variable
add_startd_cron_counter=0

#####################
# Schedules a script for periodic execution using startd_cron
# Arguments:
#   1: wrapper full path
#   2: period
#   3: cwd
#   4: executable path (from cwd),
#   5: config file path (from cwd)
#   6: ID
# Globals (r/w):
#   add_startd_cron_counter
# Used:
#   condor_config_startd_cron_include
add_periodic_script() {
    #TODO: should it allow for variable number of parameters?
    local include_fname
    local s_wrapper
    local s_period_sec
    local s_cwd
    local s_fname
    local s_config
    local s_ffb_id
    local s_cc_prefix
    include_fname=condor_config_startd_cron_include
    s_wrapper="$1"
    s_period_sec="${2}s"
    s_cwd="$3"
    s_fname="$4"
    s_config="$5"
    s_ffb_id="$6"
    s_cc_prefix="$7"
    if [ ${add_startd_cron_counter} -eq 0 ]; then
        # Make sure that no undesired file is there when called for first cron
        rm -f ${include_fname}
    fi

    let add_startd_cron_counter=add_startd_cron_counter+1
    local name_prefix
    name_prefix=GLIDEIN_PS_
    local s_name
    s_name="${name_prefix}${add_startd_cron_counter}"

    # Append the following to the startd configuration
    # Instead of Periodic and Kill wait for completion:
    # STARTD_CRON_DATE_MODE = WaitForExit
    cat >> ${include_fname} << EOF
STARTD_CRON_JOBLIST = \$(STARTD_CRON_JOBLIST) ${s_name}
STARTD_CRON_${s_name}_MODE = Periodic
STARTD_CRON_${s_name}_KILL = True
STARTD_CRON_${s_name}_PERIOD = ${s_period_sec}
STARTD_CRON_${s_name}_EXECUTABLE = ${s_wrapper}
STARTD_CRON_${s_name}_ARGS = ${s_config} ${s_ffb_id} ${s_name} ${s_fname} ${s_cc_prefix}
STARTD_CRON_${s_name}_CWD = ${s_cwd}
STARTD_CRON_${s_name}_SLOTS = 1
STARTD_CRON_${s_name}_JOB_LOAD = 0.01
EOF
    # NOPREFIX is a keyword for not setting the prefix for all condor attributes
    [ "xNOPREFIX" != "x${s_cc_prefix}" ] && echo "STARTD_CRON_${s_name}_PREFIX = ${s_cc_prefix}" >> ${include_fname}
    add_config_line "GLIDEIN_condor_config_startd_cron_include" "${include_fname}"
    add_config_line "# --- Lines starting with ${s_cc_prefix} are from periodic scripts ---"
}

############################################
# Fetches a single regular file
# Check cWDictFile/FileDictFile for the number and type of parameters (has to be consistent)
# Arguments:
#   1: ID
#   2: target fname
#   3: real fname
fetch_file_regular() {
    fetch_file "$1" "$2" "$2" "regular" 0 "GLIDEIN_PS_" "TRUE" "FALSE"
}

############################################
# Fetches a single file
# custom_scripts parameters format is set in the GWMS configuration (creation/lib)
# Check cWDictFile/FileDictFile for the number and type of parameters (has to be consistent)
# Arguments:
#   1: ID
#   2: target fname
#   3: real fname
#   4: file type (regular, exec, exec:s, untar, nocache)
#   5: period (0 if not a periodic file)
#   6: periodic scripts prefix
#   7: config check TRUE,FALSE
#   8: config out TRUE,FALSE
# The above is the most recent list, below some adaptations for different versions
# Used:
#   ifs_str
#   IFS
# Returns:
#   0 in case of success
#   otherwise glidein_exit with 1
fetch_file() {
    if [ $# -gt 8 ]; then
        # For compatibility w/ future versions (add new parameters at the end)
        echo "More then 8 arguments, considering the first 8 ($#/${ifs_str}): $*" 1>&2
    elif [ $# -ne 8 ]; then
        if [ $# -eq 7 ]; then
            #TODO: remove in version 3.3
            # For compatibility with past versions (old file list formats)
            # 3.2.13 and older: prefix (par 6) added in #12705, 3.2.14?
            # 3.2.10 and older: period (par 5) added:  fetch_file_try "$1" "$2" "$3" "$4" 0 "GLIDEIN_PS_" "$5" "$6"
            if ! fetch_file_try "$1" "$2" "$3" "$4" "$5" "GLIDEIN_PS_" "$6" "$7"; then
                glidein_exit 1
            fi
            return 0
        fi
        if [ $# -eq 6 ]; then
            # added to maintain compatibility with older (3.2.10) file list format
            #TODO: remove in version 3.3
            if ! fetch_file_try "$1" "$2" "$3" "$4" 0 "GLIDEIN_PS_" "$5" "$6"; then
                glidein_exit 1
            fi
            return 0
        fi
        local ifs_str
        printf -v ifs_str '%q' "${IFS}"
        log_warn "Not enough arguments in fetch_file, 8 expected ($#/${ifs_str}): $*"
        glidein_exit 1
    fi

    if ! fetch_file_try "$1" "$2" "$3" "$4" "$5" "$6" "$7" "$8"; then
        glidein_exit 1
    fi
    return 0
}

############################################
# Verifies if the file should be downloaded and acted upon (extracted, executed, ...) or not
# There are 2 mechanisms to control the download
# 1. tar files have the attribute "cond_attr" that is a name of a variable in glidein_config.
#    if the named variable has value 1, then the file is downloaded. TRUE (default) means always download
#    even if the mechanism is generic, there is no way to specify "cond_attr" for regular files in the configuration
# 2. if the file name starts with "gconditional_AAA_", the file is downloaded only if a variable GLIDEIN_USE_AAA
#    exists in glidein_config and the value is not empty
# Both conditions are checked. If either one fails the file is not downloaded
# Arguments:
#   1: ID
#   2: target fname
#   3: real fname
#   4: file type (regular, exec, exec:s, untar, nocache)
#   5: period (0 if not a periodic file)
#   6: periodic scripts prefix
#   7: config check TRUE,FALSE
#   8: config out TRUE,FALSE
# Globals (r/w):
#   fft_id
#   fft_target_fname
#   fft_real_fname
#   fft_file_type
#   fft_period
#   fft_cc_prefix
#   fft_config_check
#   fft_config_out
#   fft_get_ss
#   fft_base_name
#   fft_condition_attr
#   fft_condition_attr_val
# Returns:
#   0 in case of success
#   otherwise it returns the exit code of fetch_file_base
fetch_file_try() {
    fft_id="$1"
    fft_target_fname="$2"
    fft_real_fname="$3"
    fft_file_type="$4"
    fft_period="$5"
    fft_cc_prefix="$6"
    fft_config_check="$7"
    fft_config_out="$8"

    if [[ "${fft_config_check}" != "TRUE" ]]; then
        # TRUE is a special case, always be downloaded and processed
        fft_get_ss=$(grep -i "^${fft_config_check} " glidein_config | cut -d ' ' -f 2-)
        # Stop download and processing if the cond_attr variable is not defined or has a value different from 1
        [[ "${fft_get_ss}" != "1" ]] && return 0
        # TODO: what if fft_get_ss is not 1? nothing, still skip the file?
    fi

    fft_base_name=$(basename "${fft_real_fname}")
    if [[ "${fft_base_name}" = gconditional_* ]]; then
        fft_condition_attr="${fft_base_name#gconditional_}"
        fft_condition_attr="GLIDEIN_USE_${fft_condition_attr%%_*}"
        fft_condition_attr_val=$(grep -i "^${fft_condition_attr} " glidein_config | cut -d ' ' -f 2-)
        # if the variable fft_condition_attr is not defined or empty, do not download
        [[ -z "${fft_condition_attr_val}" ]] && return 0
    fi

    fetch_file_base "${fft_id}" "${fft_target_fname}" "${fft_real_fname}" "${fft_file_type}" "${fft_config_out}" "${fft_period}" "${fft_cc_prefix}"
    return $?
    # returning the exit code of fetch_file_base
}

############################################
# Performs the file download and corresponding action (untar, execute, ...)
# Arguments:
#   1: ID
#   2: target fname
#   3: real fname
#   4: file type (regular, exec, exec:s, untar, nocache)
#   5: config out TRUE,FALSE
#   5: period (0 if not a periodic file)
#   6: periodic scripts prefix
# Globals:
#   ffb_id
#   ffb_target_fname
#   ffb_real_fname
#   ffb_file_type
#   ffb_period
#   ffb_cc_prefix
#   ffb_config_out
#   ffb_work_dir
#   ffb_repository
#   ffb_tmp_outname
#   ffb_short_untar_dir
#   ffb_untar_dir
#   ffb_outname
#   ffb_prefix
#   have_dummy_otrx
#   user_agent
#   ffb_url
#   curl_version
#   curl_args
#   wget_version
#   wget_args
#   fetch_completed
#   ret
# Used:
#   glidein_entry
#   condorg_schedd
#   condorg_cluster
#   condorg_subcluster
#   client_name
#   ffb_nocache_str
#   gwms_exec_dir
#   main_dir
#   work_dir
#   cfs_id
#   result
# Returns:
#   1 in case the error is already displayed inside the function,
#   in case of tarring, in case of failure in renaming it,
#   of making it executable, or executing it
fetch_file_base() {
    ffb_id="$1"
    ffb_target_fname="$2"
    ffb_real_fname="$3"
    ffb_file_type="$4"
    ffb_config_out="$5"
    ffb_period=$6
    # condor cron prefix, used only for periodic executables
    ffb_cc_prefix="$7"
    ffb_work_dir="$(get_work_dir "${ffb_id}")"
    ffb_repository="$(get_repository_url "${ffb_id}")"
    ffb_tmp_outname="${ffb_work_dir}/${ffb_real_fname}"
    ffb_outname="${ffb_work_dir}/${ffb_target_fname}"

    # Create a dummy default in case something goes wrong
    # cannot use error_*.sh helper functions
    # may not have been loaded yet
    have_dummy_otrx=1
    date=$(date +%Y-%m-%dT%H:%M:%S%:z)
    create_xml OSG --id fetch_file_base { oe { e --name cwd "${PWD}" } t { c Unknown tStart "${date}" tEnd "${date}" } r { s ERROR m --name failure --ts "${date}" --uri local Unknown m --name source_type --ts "${date}" --uri local "${ffb_id}" } d "An unknown error occurred." }
    echo -e "$result" > otrx_output.xml
    user_agent="glidein/${glidein_entry}/${condorg_schedd}/${condorg_cluster}.${condorg_subcluster}/${client_name}"
    ffb_url="${ffb_repository}/${ffb_real_fname}"
    curl_version=$(curl --version | head -1 )
    wget_version=$(wget --version | head -1 )
    #old wget command:
    #wget --user-agent="wget/glidein/$glidein_entry/$condorg_schedd/$condorg_cluster.$condorg_subcluster/$client_name" "$ffb_nocache_str" -q  -O "$ffb_tmp_outname" "$ffb_repository/$ffb_real_fname"
    #equivalent to:
    #wget ${ffb_url} --user-agent=${user_agent} -q  -O "${ffb_tmp_outname}" "${ffb_nocache_str}"
    #with env http_proxy=$proxy_url set if proxy_url != "None"
    #
    #construct curl equivalent so we can try either

    wget_args=("${ffb_url}" "--user-agent" "wget/${user_agent}"  "--quiet"  "--output-document" "${ffb_tmp_outname}" )
    curl_args=("${ffb_url}" "--user-agent" "curl/${user_agent}" "--silent"  "--show-error" "--output" "${ffb_tmp_outname}")

    if [ "${ffb_file_type}" = "nocache" ]; then
        if [ "${curl_version}" != "" ]; then
            curl_args+=("--header")
            curl_args+=("'Cache-Control: no-cache'")
        fi
        if [ "${wget_version}" != "" ]; then
            if wget --help | grep -q "\-\-no-cache "; then
                wget_args+=("--no-cache")
            elif wget --help |grep -q "\-\-cache="; then
                wget_args+=("--cache=off")
            else
                log_warn "wget ${wget_version} cannot disable caching"
            fi
         fi
    fi

    if [ "${proxy_url}" != "None" ];then
        if [ "${curl_version}" != "" ]; then
            curl_args+=("--proxy")
            curl_args+=("${proxy_url}")
        fi
        if [ "${wget_version}" != "" ]; then
            #these two arguments have to be last as coded, put any future
            #wget args earlier in wget_args array
            wget_args+=("--proxy")
            wget_args+=("${proxy_url}")
        fi
    fi

    fetch_completed=1
    if [ ${fetch_completed} -ne 0 ] && [ "${wget_version}" != "" ]; then
        perform_wget "${wget_args[@]}"
        fetch_completed=$?
    fi
    if [ ${fetch_completed} -ne 0 ] && [ "${curl_version}" != "" ]; then
        perform_curl "${curl_args[@]}"
        fetch_completed=$?
    fi

    if [ ${fetch_completed} -ne 0 ]; then
        return ${fetch_completed}
    fi

    # check signature
    if ! check_file_signature "${ffb_id}" "${ffb_real_fname}"; then
        # error already displayed inside the function
        return 1
    fi

    # rename it to the correct final name, if needed
    if [ "${ffb_tmp_outname}" != "${ffb_outname}" ]; then
        if ! mv "${ffb_tmp_outname}" "${ffb_outname}"; then
            log_warn "Failed to rename ${ffb_tmp_outname} into ${ffb_outname}"
            return 1
        fi
    fi

    # if executable, execute
    if [[ "${ffb_file_type}" = "exec" || "${ffb_file_type}" = "exec:"* ]]; then
        if ! chmod u+x "${ffb_outname}"; then
            log_warn "Error making '${ffb_outname}' executable"
            return 1
        fi
        if [ "${ffb_id}" = "main" ] && [ "${ffb_target_fname}" = "${last_script}" ]; then  # last_script global for simplicity
            echo "Skipping last script ${last_script}" 1>&2
        elif [[ "${ffb_target_fname}" = "cvmfs_umount.sh" ]] || [[ -n "${cleanup_script}" && "${ffb_target_fname}" = "${cleanup_script}" ]]; then  # cleanup_script global for simplicity
            # TODO: temporary OR checking for cvmfs_umount.sh; to be removed after Bruno's ticket on cleanup [#25073]
            echo "Skipping cleanup script ${ffb_outname} (${cleanup_script})" 1>&2
            cp "${ffb_outname}" "$gwms_exec_dir/cleanup/${ffb_target_fname}"
            chmod a+x "${gwms_exec_dir}/cleanup/${ffb_target_fname}"
        else
            echo "Executing (flags:${ffb_file_type#exec}) ${ffb_outname}"
            # have to do it here, as this will be run before any other script
            chmod u+rx "${main_dir}"/error_augment.sh

            # the XML file will be overwritten now, and hopefully not an error situation
            have_dummy_otrx=0
            "${main_dir}"/error_augment.sh -init
            START=$(date +%s)
            if [[ "${ffb_file_type}" = "exec:s" ]]; then
                "${main_dir}/singularity_wrapper.sh" "${ffb_outname}" glidein_config "${ffb_id}"
            else
                "${ffb_outname}" glidein_config "${ffb_id}"
            fi
            ret=$?
            local END
            END=$(date +%s)
            "${main_dir}"/error_augment.sh -process ${ret} "${ffb_id}/${ffb_target_fname}" "${PWD}" "${ffb_outname} glidein_config" "${START}" "${END}" #generating test result document
            "${main_dir}"/error_augment.sh -concat
            # TODO(F): qui
            if [ ${ret} -ne 0 ]; then
                echo "=== Validation error in ${ffb_outname} ===" 1>&2
                log_warn "Error running '${ffb_outname}'"
                < otrx_output.xml awk 'BEGIN{fr=0;}/<[/]detail>/{fr=0;}{if (fr==1) print $0}/<detail>/{fr=1;}' 1>&2
                return 1
            else
                # If ran successfully and periodic, schedule to execute with schedd_cron
                echo "=== validation OK in ${ffb_outname} (${ffb_period}) ===" 1>&2
                if [ "${ffb_period}" -gt 0 ]; then
                    add_periodic_script "${main_dir}/script_wrapper.sh" "${ffb_period}" "${work_dir}" "${ffb_outname}" glidein_config "${ffb_id}" "${ffb_cc_prefix}"
                fi
            fi
        fi
    elif [ "${ffb_file_type}" = "wrapper" ]; then
        echo "${ffb_outname}" >> "${wrapper_list}"
    elif [ "${ffb_file_type}" = "untar" ]; then
        ffb_short_untar_dir="$(get_untar_subdir "${ffb_id}" "${ffb_target_fname}")"
        ffb_untar_dir="${ffb_work_dir}/${ffb_short_untar_dir}"
        local START
        START=$(date +%s)
        (mkdir "${ffb_untar_dir}" && cd "${ffb_untar_dir}" && tar -xmzf "${ffb_outname}") 1>&2
        ret=$?
        if [ ${ret} -ne 0 ]; then
            "${main_dir}"/error_augment.sh -init
            "${main_dir}"/error_gen.sh -error "tar" "Corruption" "Error untarring '${ffb_outname}'" "file" "${ffb_outname}" "source_type" "${cfs_id}"
            "${main_dir}"/error_augment.sh  -process ${cfs_rc} "tar" "${PWD}" "mkdir ${ffb_untar_dir} && cd ${ffb_untar_dir} && tar -xmzf ${ffb_outname}" "${START}" "$(date +%s)"
            "${main_dir}"/error_augment.sh -concat
            log_warn "Error untarring '${ffb_outname}'"
            return 1
        fi
    fi

    if [ "${ffb_config_out}" != "FALSE" ]; then
        ffb_prefix="$(get_prefix "${ffb_id}")"
        if [ "${ffb_file_type}" = "untar" ]; then
            # when untaring the original file is less interesting than the untar dir
            if ! add_config_line "${ffb_prefix}${ffb_config_out}" "${ffb_untar_dir}"; then
                glidein_exit 1
            fi
        else
            if ! add_config_line "${ffb_prefix}${ffb_config_out}" "${ffb_outname}"; then
                glidein_exit 1
            fi
        fi
    fi

    if [ "${have_dummy_otrx}" -eq 1 ]; then
        # no one should really look at this file, but just to avoid confusion
        local date
        date="$(date +%Y-%m-%dT%H:%M:%S%:z)"
        create_xml OSG --id fetch_file_base { oe { e --name cwd "${PWD}" } t { c Unknown tStart "${date}" tEnd "${date}" } r { status OK } }
        echo -e "$result" > otrx_output.xml
    fi

   return 0
}

################################
# Perform a wget request
# Arguments:
#   @: wget args
# Globals (r/w):
#   wget_args
#   wget_cmd
#   wget_resp
#   wget_retval
#   wget_version
#   arg_len
#   ffb_url
#   ffb_repository
#   ffb_real_fname
#   ffb_tmp_outname
#   proxy_url
# Returns:
#   wget_retval
# Environment:
#   http_proxy
perform_wget() {
    wget_args=("$@")
    arg_len="${#wget_args[@]}"
    ffb_url="${wget_args[0]}"
    ffb_repository=$(dirname "${ffb_url}")
    ffb_real_fname=$(basename "${ffb_url}")
    proxy_url="None"
    for ((i=0; i<arg_len; i++));
    do
        if [ "${wget_args[${i}]}" = "--output-document" ]; then
            ffb_tmp_outname=${wget_args[${i}+1]}
        fi
        if [ "${wget_args[${i}]}" = "--proxy" ]; then
            proxy_url=${wget_args[${i}+1]}
        fi
    done
    local START
    START=$(date +%s)
    if [ "${proxy_url}" != "None" ]; then
        wget_args=(${wget_args[@]:0:${arg_len}-2})
        wget_cmd=$(echo "env http_proxy=${proxy_url} wget" "${wget_args[@]}"| sed 's/"/\\\"/g')
        wget_resp=$(env http_proxy="${proxy_url}" wget "${wget_args[@]}" 2>&1)
        wget_retval=$?
    else
        wget_cmd=$(echo "wget" "${wget_args[@]}"| sed 's/"/\\\"/g')
        wget_resp=$(wget "${wget_args[@]}" 2>&1)
        wget_retval=$?
    fi

    if [ ${wget_retval} -ne 0 ]; then
        wget_version=$(wget --version 2>&1 | head -1)
        log_warn "${wget_cmd} failed. version:${wget_version}  exit code ${wget_retval} stderr: ${wget_resp}"
        # cannot use error_*.sh helper functions
        # may not have been loaded yet, and wget fails often
        local tStart tEnd xmlResult
        tStart="$(date --date=@"${START}" +%Y-%m-%dT%H:%M:%S%:z)"
        tEnd="$(date +%Y-%m-%dT%H:%M:%S%:z)"
        xmlResult=""
        create_xml OSG --id perform_wget { oe { e --name cwd "${PWD}" e --name uname "$(uname -a)" e --name release "$(cat /etc/system-release)" e --name wget_version "${wget_version}" }
        xmlResult+=$result
        create_xml -s 1 t { c "${wget_cmd}" tS "${tStart}" tE "${tEnd}" } r { s ERROR m --name failure --ts "${tStart}" --uri local Network m --name URL --ts "${tStart}" --uri local "${ffb_url}" m --name http_proxy --ts "${tStart}" --uri local "${proxy_url}" m --name source_type --ts "${tStart}" --uri local "${ffb_id}" }
        xmlResult+=$result
        create_xml -s 1 d "Failed to load file '${ffb_real_fname}' from '${ffb_repository}' using proxy '${proxy_url}'.  ${wget_resp}"
        xmlResult+=$result
        create_xml -t
        xmlResult+=$result
        echo -e "$xmlResult" > otrb_output.xml
        log_warn "Failed to load file '${ffb_real_fname}' from '${ffb_repository}'."

        if [ -f otr_outlist.list ]; then
            chmod u+w otr_outlist.list
        else
            touch otr_outlist.list
        fi
        cat otrb_output.xml >> otr_outlist.list
        create_xml -h
        echo $result > otrx_output.xml
        cat otrb_output.xml >> otrx_output.xml
        rm -f otrb_output.xml
        chmod a-w otr_outlist.list
    fi
    return ${wget_retval}
}

################################
# Perform a curl request
# Arguments:
#   @: curl args
# Globals (r/w):
#   curl_args
#   arg_len
#   ffb_url
#   ffb_repository
#   ffb_real_fname
#   ffb_tmp_outname
#   proxy_url
#   curl_cmd
#   curl_resp
#   curl_retval
#   curl_version
# Returns:
#   curl_retval
# Environment:
#   http_proxy
perform_curl() {
    curl_args=("$@")
    arg_len="${#curl_args[@]}"
    ffb_url="${curl_args[0]}"
    ffb_repository="$(dirname "${ffb_url}")"
    ffb_real_fname="$(basename "${ffb_url}")"
    for ((i=0; i<arg_len; i++));
    do
        if [ "${curl_args[${i}]}" = "--output" ]; then
            ffb_tmp_outname="${curl_args[${i}+1]}"
        fi
        if [ "${curl_args[${i}]}" = "--proxy" ]; then
            proxy_url="${curl_args[${i}+1]}"
        fi
    done
    local START
    START="$(date +%s)"
    curl_cmd="$(echo "curl" "${curl_args[@]}" | sed 's/"/\\\"/g')"
    curl_resp="$(curl "${curl_args[@]}" 2>&1)"
    curl_retval=$?
    if [ ${curl_retval} -eq 0 ] && [ ! -e "${ffb_tmp_outname}" ] ; then
        touch "${ffb_tmp_outname}"
    fi

    if [ "${curl_retval}" -ne 0 ]; then
        curl_version="$(curl --version 2>&1 | head -1)"
        log_warn "${curl_cmd} failed. version:${curl_version}  exit code ${curl_retval} stderr: ${curl_resp} "
        # cannot use error_*.sh helper functions
        # may not have been loaded yet, and wget fails often
        local tStart tEnd xmlResult
        tStart="$(date --date=@"${START}" +%Y-%m-%dT%H:%M:%S%:z)"
        tEnd="$(date +%Y-%m-%dT%H:%M:%S%:z)"
        xmlResult=""
        create_xml OSG --id perform_curl { oe { e --name cwd "${PWD}" e --name uname "$(uname -a)" e --name release "$(cat /etc/system-release)" e --name curl_version "${curl_version}" }
        xmlResult+=$result
        create_xml -s 1 t { c "${curl_cmd}" tS "${tStart}" tE "${tEnd}" } r { s ERROR m --name failure --ts "${tStart}" --uri local Network m --name URL --ts "${tStart}" --uri local "${ffb_url}" m --name http_proxy --ts "${tStart}" --uri local "${proxy_url}" m --name source_type --ts "${tStart}" --uri local "${ffb_id}" }
        xmlResult+=$result
        create_xml -s 1 d "Failed to load file '${ffb_real_fname}' from '${ffb_repository}' using proxy '${proxy_url}'.  ${curl_resp}"
        xmlResult+=$result
        create_xml -t
        xmlResult+=$result
        echo -e "$xmlResult" > otrb_output.xml
        log_warn "Failed to load file '${ffb_real_fname}' from '${ffb_repository}'."

        if [ -f otr_outlist.list ]; then
            chmod u+w otr_outlist.list
        else
            touch otr_outlist.list
        fi
        cat otrb_output.xml >> otr_outlist.list
        create_xml -h
        echo $result > otrx_output.xml
        cat otrb_output.xml >> otrx_output.xml
        rm -f otrb_output.xml
        chmod a-w otr_outlist.list
    fi
    return ${curl_retval}
}
