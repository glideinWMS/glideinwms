#!/bin/bash

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

#*******************************************************************#
# utils_scripts.sh                                                  #
# This script contains scripts utility functions                    #
#*******************************************************************#

################################
# Add an entry to the descriptor file containing the ordered list of scripts to handle
# Arguments:
#   1: filename
#   2: type
#   3: time
#   4: integer_code for coordination
#   5: period
#   6: prefix
#   7: id
#   8: tar_source
add_entry(){
    local e_real_fname e_type e_time e_coordination descriptor_file
    e_real_fname="$1"
    e_type="$2"
    e_time="$3"
    e_coordination="$4"
    e_period="$5"
    e_prefix="$6"
    e_id="$7"
    e_tar_source="$8"
    descriptor_file="testfile"

    if [ ! -f "$descriptor_file" ]; then
        echo "# File: $descriptor_file" > "$descriptor_file"
        echo "#" >> "$descriptor_file"
        echo "# Time    OrderedFilename    RealFilename   Type    Period    Prefix    Id" >> "$descriptor_file"
        echo "################################################################################################" >> "$descriptor_file"
    fi
    OLD_IFS=$IFS
    IFS=', ' read -r -a array <<< $e_time
    for time_entry in "${array[@]}"
    do
        if [[ $e_tar_source != NULL ]]; then
            ffb_short_untar_dir="$(get_untar_subdir "${e_id}" "${e_tar_source}")"
            ffb_untar_dir="${ffb_work_dir}/${ffb_short_untar_dir}"
            e_complete_fname="${ffb_untar_dir}/$e_real_fname"
            #TODO: check if filename is a path what happens
        else
            e_complete_fname="$e_real_fname"
        fi
        echo "${time_entry}    ${e_coordination}_${e_real_fname}    ${e_complete_fname}    ${e_type}    ${e_period}    ${e_prefix}    ${e_id}" >> "$descriptor_file"
   done
    IFS=$OLD_IFS
}

################################
# Extract from the descriptor file the ordered list of scripts to handle
# Arguments:
#   1: target_time
# Globals(r/w):
#   list
extract_entry_files(){
    local target_time descriptor_file
    target_time="$1"
    descriptor_file="testfile"
    grep ^$target_time $descriptor_file | sort > ${target_time}_descriptor_file
}

################################
# Perform the requested action associated to each script of the given time
# Arguments:
#   1: target_time
# Used:
#    list
custom_scripts(){
    local target_time
    target_time="$1"
    extract_entry_files "$target_time"
    # space+tab separated file with multiple elements
    while read -r line
    do
        if [ "${file:0:1}" == "#" ]; then
            continue
        fi
        read -ra arr -d '   ' <<< "$line"
        ffb_target_fname=${arr[2]}
        ffb_file_type=${arr[3]}
        ffb_period=${arr[4]}
        ffb_cc_prefix=${arr[5]}
        ffb_id=${arr[6]}
        # if executable, execute
        if [[ "${ffb_file_type}" = "exec"* ]]; then
            if ! chmod u+x "${ffb_target_fname}"; then
                warn "Error making '${ffb_target_fname}' executable"
                return 1
            fi
            if [ "${ffb_id}" = "main" ] && [ "${ffb_target_fname}" = "${last_script}" ]; then  # last_script global for simplicity
                echo "Skipping last script ${last_script}" 1>&2
            elif [[ "${ffb_target_fname}" = "cvmfs_umount.sh" ]] || [[ -n "${cleanup_script}" && "${ffb_target_fname}" = "${cleanup_script}" ]]; then  # cleanup_script global for simplicity
                # TODO: temporary OR checking for cvmfs_umount.sh; to be removed after Bruno's ticket on cleanup [#25073]
                echo "Skipping cleanup script ${ffb_target_fname} (${cleanup_script})" 1>&2
                cp "${ffb_target_fname}" "$gwms_exec_dir/cleanup/${ffb_target_fname}"
                chmod a+x "${gwms_exec_dir}/cleanup/${ffb_target_fname}"
            else
                echo "Executing (flags:${ffb_file_type#exec}) ${ffb_target_fname}"
                # have to do it here, as this will be run before any other script
                chmod u+rx "${main_dir}"/error_augment.sh

                # the XML file will be overwritten now, and hopefully not an error situation
                have_dummy_otrx=0
                "${main_dir}"/error_augment.sh -init
                START=$(date +%s)
                if [[ "${ffb_file_type}" = "exec:s" ]]; then
                    "${main_dir}/singularity_wrapper.sh" "${ffb_target_fname}" glidein_config "${ffb_id}"
                else
                    "${ffb_target_fname}" glidein_config "${ffb_id}"
                fi
                ret=$?
                END=$(date +%s)
                "${main_dir}"/error_augment.sh -process ${ret} "${ffb_id}/${ffb_target_fname}" "${PWD}" "${ffb_target_fname} glidein_config" "${START}" "${END}" #generating test result document
                "${main_dir}"/error_augment.sh -concat
                if [ ${ret} -ne 0 ]; then
                    echo "=== Validation error in ${ffb_target_fname} ===" 1>&2
                    warn "Error running '${ffb_target_fname}'"
                    < otrx_output.xml awk 'BEGIN{fr=0;}/<[/]detail>/{fr=0;}{if (fr==1) print $0}/<detail>/{fr=1;}' 1>&2
                    return 1
                else
                    # If ran successfully and periodic, schedule to execute with schedd_cron
                    echo "=== validation OK in ${ffb_target_fname} (${ffb_period}) ===" 1>&2
                    if [ "${ffb_period}" -gt 0 ]; then
                        add_periodic_script "${main_dir}/script_wrapper.sh" "${ffb_period}" "${work_dir}" "${ffb_target_fname}" glidein_config "${ffb_id}" "${ffb_cc_prefix}"
                    fi
                fi
            fi
        elif [[ "${ffb_file_type}" = "source"  || "${ffb_file_type}" = "library:shell" ]]; then
            source "${ffb_target_fname}"
            # TODO: what about other library types?
        fi
    done < ${target_time}_descriptor_file
    rm -f ${target_time}_descriptor_file
}

################################
# Ask for the execution of scripts related to a milestone
# Arguments:
#   1: code
# Returns:
#   1 in case of a failure (code including space)
milestone_call(){
    local code
    code=$1
    # no spaces are allowed in the code
    if [[ "$code" == *"\t"* ]]; then
      return 1
    fi
    custom_scripts "milestone:"$code
    return 0
}

################################
# Ask for the execution of scripts related to a failure code
# Arguments:
#   1: exit code
failure_call(){
    local exit_code
    exit_code=$1
    # no spaces are allowed in the code
    if [[ "$exit_code" == *"\t"* ]]; then
      return 1
    fi
    custom_scripts "failure:"$exit_code
    return 0
}
