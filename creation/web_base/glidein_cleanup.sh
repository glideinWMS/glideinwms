work_dir_created=0
glide_local_tmp_dir_created=0

################################
# Function used to clean up the glidein.
# It cleans-up, print out the message and exit
# It removes Glidein directories (work_dir, glide_local_tmp_dir)
# It uses GLIDEIN_DEBUG_OPTIONS, start_dir, work_dir_created, work_dir, glide_local_tmp_dir_created, glide_local_tmp_dir
# Arguments:
#   1: exit code
glidien_cleanup() {
    if ! cd "${start_dir}"; then
        log_warn "Cannot find ${start_dir} anymore, exiting but without cleanup"
    else
        if [[ ",${GLIDEIN_DEBUG_OPTIONS}," = *,nocleanup,* ]]; then
            log_warn "Skipping cleanup, disabled via GLIDEIN_DEBUG_OPTIONS"
        else
            if [ "${work_dir_created}" -eq "1" ]; then
                # rm -fR does not remove directories read only for the user
                find "${work_dir}" -type d -exec chmod u+w {} \;
                rm -fR "${work_dir}"
            fi
            if [ "${glide_local_tmp_dir_created}" -eq "1" ]; then
                find "${glide_local_tmp_dir}" -type d -exec chmod u+w {} \;
                rm -fR "${glide_local_tmp_dir}"
            fi
        fi
    fi
}

################################
# Function used for early failures of the glidein, when we cannot assume we can write to disk at all
# too bad we end up with some repeated code, but difficult to do better
# Arguments:
#   1: error message
early_glidein_failure() {
  #result = "<metric name=\"failure\" ts=\"%s\" uri=\"local\">%s</metric>
  #                 </result>
  #                 <detail>%s</detail>"
  error_msg="$1"
  log_warn "${error_msg}"
  sleep "${sleep_time}"
  # wait a bit in case of error, to reduce lost glideins
  glidein_end_time="$(date +%s)"
  #printf "$result" "$(date --date=@\"${glidein_end_time}\" +%Y-%m-%dT%H:%M:%S%:z)" "WN_RESOURCE" "${error_msg}"
  result="    <metric name=\"failure\" ts=\"$(date --date=@"${glidein_end_time}" +%Y-%m-%dT%H:%M:%S%:z)\" uri=\"local\">WN_RESOURCE</metric>
    <status>ERROR</status>
    <detail>
     ${error_msg}
    </detail>"
  final_result="$(construct_xml "${result}")"
  final_result_simple="$(basexml2simplexml "${final_result}")"
  # have no global section
  final_result_long="$(simplexml2longxml "${final_result_simple}" "")"
  glidien_cleanup
  print_tail 1 "${final_result_simple}" "${final_result_long}"
  exit 1
}

################################
# Function used for exiting the glidein, to be used when the most basic ops have been done
# too bad we end up with some repeated code, but difficult to do better
# Arguments:
#   1: exit code
glidein_exit() {
  exit_code=$1
  # Removed lines about $lock_file (lock file for whole machine) not present elsewhere
  gwms_process_scripts "$GWMS_DIR" cleanup "${glidein_config}"
  global_result=""
  if [ -f otr_outlist.list ]; then
      global_result=$(cat otr_outlist.list)
      chmod u+w otr_outlist.list
  fi
  ge_last_script_name=$(extract_parent_fname "${exit_code}")
  result=$(extract_parent_xml_detail "${exit_code}")
  final_result=$(construct_xml "${result}")
  # augment with node info
  final_result_simple=$(basexml2simplexml "${final_result}")
  # Create a richer version, too
  final_result_long=$(simplexml2longxml "${final_result_simple}" "${global_result}")
  if [ "${exit_code}" -ne 0 ]; then
      report_failed=$(grep -i "^GLIDEIN_Report_Failed " "${glidein_config}" | cut -d ' ' -f 2-)

      if [ -z "${report_failed}" ]; then
          report_failed="NEVER"
      fi
      
      factory_report_failed=$(grep -i "^GLIDEIN_Factory_Report_Failed " "${glidein_config}" | cut -d ' ' -f 2-)

      if [ -z "${factory_report_failed}" ]; then
          factory_collector=$(grep -i "^GLIDEIN_Factory_Collector " "${glidein_config}" | cut -d ' ' -f 2-)
          if [ -z "${factory_collector}" ]; then
              # no point in enabling it if there are no collectors
              factory_report_failed="NEVER"
          else
              factory_report_failed="ALIVEONLY"
          fi
      fi
      do_report=0
      if [ "${report_failed}" != "NEVER" ] || [ "${factory_report_failed}" != "NEVER" ]; then
          do_report=1
      fi
      # wait a bit in case of error, to reduce lost glideins
      let "dl=$(date +%s) + ${sleep_time}"
      dlf=$(date --date="@${dl}")
      add_config_line "GLIDEIN_ADVERTISE_ONLY" "1"
      add_config_line "GLIDEIN_Failed" "True"
      add_config_line "GLIDEIN_EXIT_CODE" "$1"
      add_config_line "GLIDEIN_ToDie" "${dl}"
      add_config_line "GLIDEIN_Expire" "${dl}"
      add_config_line "GLIDEIN_LAST_SCRIPT" "${ge_last_script_name}"
      add_config_line "GLIDEIN_ADVERTISE_TYPE" "Retiring"

      add_config_line "GLIDEIN_FAILURE_REASON" "Glidein failed while running ${ge_last_script_name}. Keeping node busy until ${dl} (${dlf})."

      condor_vars_file="$(grep -i "^CONDOR_VARS_FILE " "${glidein_config}" | cut -d ' ' -f 2-)"
      if [ -n "${condor_vars_file}" ]; then
         # if we are to advertise, this should be available... else, it does not matter anyhow
         add_condor_vars_line "GLIDEIN_ADVERTISE_ONLY" "C" "True" "+" "Y" "Y" "-"
         add_condor_vars_line "GLIDEIN_Failed" "C" "True" "+" "Y" "Y" "-"
         add_condor_vars_line "GLIDEIN_EXIT_CODE" "I" "-" "+" "Y" "Y" "-"
         add_condor_vars_line "GLIDEIN_ToDie" "I" "-" "+" "Y" "Y" "-"
         add_condor_vars_line "GLIDEIN_Expire" "I" "-" "+" "Y" "Y" "-"
         add_condor_vars_line "GLIDEIN_LAST_SCRIPT" "S" "-" "+" "Y" "Y" "-"
         add_condor_vars_line "GLIDEIN_FAILURE_REASON" "S" "-" "+" "Y" "Y" "-"
      fi
      main_work_dir="$(get_work_dir main)"

      for ((t=$(date +%s); t < dl; t=$(date +%s)))
      do
        if [ -e "${main_work_dir}/${last_script}" ] && [ "${do_report}" = "1" ] ; then
            # if the file exists, we should be able to talk to the collectors
            # notify that things went badly and we are waiting
            if [ "${factory_report_failed}" != "NEVER" ]; then
                add_config_line "GLIDEIN_ADVERTISE_DESTINATION" "Factory"
                log_warn "Notifying Factory of error"
                "${main_work_dir}/${last_script}" glidein_config
            fi
            if [ "${report_failed}" != "NEVER" ]; then
                add_config_line "GLIDEIN_ADVERTISE_DESTINATION" "VO"
                log_warn "Notifying VO of error"
                "${main_work_dir}/${last_script}" glidein_config
            fi
        fi
        # sleep for about 5 mins... but randomize a bit
        let "ds=250+${RANDOM}%100"
        let "as=$(date +%s) + ${ds}"
        if [ ${as} -gt ${dl} ]; then
            # too long, shorten to the deadline
            let "ds=${dl} - $(date +%s)"
        fi
        log_warn "Sleeping ${ds}"
        sleep ${ds}
      done
      if [ -e "${main_work_dir}/${last_script}" ] && [ "${do_report}" = "1" ]; then
          # notify that things went badly and we are going away
          if [ "${factory_report_failed}" != "NEVER" ]; then
              add_config_line "GLIDEIN_ADVERTISE_DESTINATION" "Factory"
              if [ "${factory_report_failed}" = "ALIVEONLY" ]; then
                  add_config_line "GLIDEIN_ADVERTISE_TYPE" "INVALIDATE"
              else
                  add_config_line "GLIDEIN_ADVERTISE_TYPE" "Killing"
                  add_config_line "GLIDEIN_FAILURE_REASON" "Glidein failed while running ${ge_last_script_name}. Terminating now. (${dl}) (${dlf})"
              fi
              "${main_work_dir}/${last_script}" glidein_config
              log_warn "Last notification sent to Factory"
          fi
          if [ "${report_failed}" != "NEVER" ]; then
              add_config_line "GLIDEIN_ADVERTISE_DESTINATION" "VO"
              if [ "${report_failed}" = "ALIVEONLY" ]; then
                  add_config_line "GLIDEIN_ADVERTISE_TYPE" "INVALIDATE"
              else
                  add_config_line "GLIDEIN_ADVERTISE_TYPE" "Killing"
                  add_config_line "GLIDEIN_FAILURE_REASON" "Glidein failed while running ${ge_last_script_name}. Terminating now. (${dl}) (${dlf})"
              fi
              "${main_work_dir}/${last_script}" glidein_config
              log_warn "Last notification sent to VO"
          fi
      fi
  fi
  log_write "glidein_startup.sh" "text" "glidein is about to exit with retcode $1" "info"
  send_logs_to_remote
  glidien_cleanup
  print_tail "$1" "${final_result_simple}" "${final_result_long}"
  exit "$1"
}

