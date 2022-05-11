#!/bin/bash

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

#
# Project:
#   glideinWMS
#
# File Version:
#

# default IFS, to protect against unusual environment, better than "unset IFS" because works with restoring old one
IFS=$' \t\n'

global_args="$*"
# GWMS_STARTUP_SCRIPT=$0
GWMS_STARTUP_SCRIPT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/$(basename "${BASH_SOURCE[0]}")"
GWMS_PATH=""
# Relative to the work directory (GWMS_DIR, gwms_lib_dir, gwms_bin_dir and gwms_exec_dir will be the absolute paths)
# bin (utilities), lib (libraries), exec (aux scripts to be executed/sourced, e.g. pre-job)
GWMS_SUBDIR=".gwms.d"

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

##############################
# Utility functions to allow the script to source functions and retrieve data stored as tarball at the end of the script itself

get_data() {
    # Retrieve the specified data, which is appended as tarball
    # 1: selected file
    sed '1,/^#EOF$/d' < "${GWMS_STARTUP_SCRIPT}" | tar xz -O "$1"
}

source_data() {
    # Source the specified data, which is appended as tarball, without saving it
    # 1: selected file
    local data
    data=$(get_data "$1")
    [[ -n "$data" ]] && eval "$data"
}

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
# Extends 'trap' allowing to pass the signal name as argument to the handler
trap_with_arg() {
    func="$1" ; shift
    for sig ; do
        # shellcheck disable=SC2064
        trap "${func} ${sig}" "${sig}"
    done
}

#function to handle passing signals to the child processes
# no need to re-raise sigint, caller does unconditional exit (https://www.cons.org/cracauer/sigint.html)
on_die() {
    echo "Received kill signal... shutting down child processes (forwarding $1 signal)" 1>&2
    ON_DIE=1
    kill -s "$1" %1
}

GWMS_MULTIGLIDEIN_CHILDS=
on_die_multi() {
    echo "Multi-Glidein received signal... shutting down child glideins (forwarding $1 signal to ${GWMS_MULTIGLIDEIN_CHILDS})" 1>&2
    ON_DIE=1
    for i in ${GWMS_MULTIGLIDEIN_CHILDS}; do
        kill -s "$1" "${i}"
    done
}

ignore_signal() {
    echo "Ignoring SIGHUP signal... Use SIGTERM or SIGQUIT to kill processes" 1>&2
}

warn() {
    echo "WARN $(date)" "$@" 1>&2
}

logdebug() {
    echo "DEBUG $(date)" "$@" 1>&2
}

# Functions to start multiple glideins
copy_all() {
   # 1:prefix (of the files to skip), 2:directory
   # should it copy also hidden files?
   mkdir -p "$2"
   for f in *; do
       [[ -e "${f}" ]] || break    # TODO: should this be a continue?
       if [[ "${f}" = ${1}* ]]; then
           continue
       fi
       cp -r "${f}" "$2"/
   done
}

do_start_all() {
    # 1:number of glideins
    # GLIDEIN_MULTIGLIDEIN_LAUNCHALL - if set in attrs, command to start all Glideins at once (multirestart 0)
    # GLIDEIN_MULTIGLIDEIN_LAUNCHER - if set in attrs, command to start the individual Glideins
    local num_glideins initial_dir multiglidein_launchall multiglidein_launcher
    num_glideins=$1
    initial_dir="$(pwd)"
    multiglidein_launchall=$(params_decode "$(params_get_simple GLIDEIN_MULTIGLIDEIN_LAUNCHALL "${params}")")
    multiglidein_launcher=$(params_decode "$(params_get_simple GLIDEIN_MULTIGLIDEIN_LAUNCHER "${params}")")

    local startup_script="${GWMS_STARTUP_SCRIPT}"
    if [[ -n "${multiglidein_launchall}" ]]; then
        echo "Starting multi-glidein using launcher: ${multiglidein_launchall}"
        # shellcheck disable=SC2086
        ${multiglidein_launchall} "${startup_script}" -multirestart 0 ${global_args} &
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
            ${multiglidein_launcher} "${startup_script}" -multirestart "${i}" ${global_args} &
            GWMS_MULTIGLIDEIN_CHILDS="${GWMS_MULTIGLIDEIN_CHILDS} $!"
            popd || true
        done
        echo "Started multiple glideins: ${GWMS_MULTIGLIDEIN_CHILDS}"
    fi
}

usage() {
    echo "Usage: glidein_startup.sh <options>"
    echo "where <options> is:"
    echo "  -factory <name>             : name of this factory"
    echo "  -name <name>                : name of this glidein"
    echo "  -entry <name>               : name of this glidein entry"
    echo "  -clientname <name>          : name of the requesting client"
    echo "  -clientgroup <name>         : group name of the requesting client"
    echo "  -web <baseURL>              : base URL from where to fetch"
    echo "  -proxy <proxyURL>           : URL of the local proxy"
    echo "  -dir <dirID>                : directory ID (supports ., Condor, CONDOR, OSG, TMPDIR, AUTO)"
    echo "  -sign <sign>                : signature of the signature file"
    echo "  -signtype <id>              : type of signature (only sha1 supported for now)"
    echo "  -signentry <sign>           : signature of the entry signature file"
    echo "  -cluster <ClusterID>        : condorG ClusterId"
    echo "  -subcluster <ProcID>        : condorG ProcId"
    echo "  -submitcredid <CredentialID>: Credential ID of this condorG job"
    echo "  -schedd <name>              : condorG Schedd Name"
    echo "  -descript <fname>           : description file name"
    echo "  -descriptentry <fname>      : description file name for entry"
    echo "  -clientweb <baseURL>        : base URL from where to fetch client files"
    echo "  -clientwebgroup <baseURL>   : base URL from where to fetch client group files"
    echo "  -clientsign <sign>          : signature of the client signature file"
    echo "  -clientsigntype <id>        : type of client signature (only sha1 supported for now)"
    echo "  -clientsigngroup <sign>     : signature of the client group signature file"
    echo "  -clientdescript <fname>     : client description file name"
    echo "  -clientdescriptgroup <fname>: client description file name for group"
    echo "  -slotslayout <type>         : how Condor will set up slots (fixed, partitionable)"
    echo "  -v <id>                     : operation mode (std, nodebug, fast, check supported)"
    echo "  -multiglidein <num>         : spawn multiple (<num>) glideins (unless also multirestart is set)"
    echo "  -multirestart <num>         : started as one of multiple glideins (glidein number <num>)"
    echo "  -param_* <arg>              : user specified parameters"
    exit 1
}


# params will contain the full list of parameters
# -param_XXX YYY will become "XXX YYY"
# TODO: can use an array instead?
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
    *)  (warn "Unknown option $1"; usage) 1>&2; exit 1
esac
shift 2
done

# make sure we have a valid slots_layout
if (echo "x${slots_layout}" | grep -i fixed) >/dev/null 2>&1 ; then
    slots_layout="fixed"
else
    slots_layout="partitionable"
fi

construct_xml() {
  result="$1"

  glidein_end_time="$(date +%s)"

  echo "<?xml version=\"1.0\"?>
<OSGTestResult id=\"glidein_startup.sh\" version=\"4.3.1\">
  <operatingenvironment>
    <env name=\"cwd\">${start_dir}</env>
  </operatingenvironment>
  <test>
    <cmd>$0 ${global_args}</cmd>
    <tStart>$(date --date=@"${startup_time}" +%Y-%m-%dT%H:%M:%S%:z)</tStart>
    <tEnd>$(date --date=@"${glidein_end_time}" +%Y-%m-%dT%H:%M:%S%:z)</tEnd>
  </test>
${result}
</OSGTestResult>"
}


extract_parent_fname() {
  exitcode=$1

  if [ -s otrx_output.xml ]; then
      # file exists and is not 0 size
      last_result=$(cat otrx_output.xml)

      if [ "${exitcode}" -eq 0 ]; then
          echo "SUCCESS"
      else
          last_script_name=$(echo "${last_result}" |awk '/<OSGTestResult /{split($0,a,"id=\""); split(a[2],b,"\""); print b[1];}')
          echo "${last_script_name}"
      fi
  else
      echo "Unknown"
  fi
}

extract_parent_xml_detail() {
  exitcode=$1
  glidein_end_time="$(date +%s)"

  if [ -s otrx_output.xml ]; then
      # file exists and is not 0 size
      last_result="$(cat otrx_output.xml)"

      if [ "${exitcode}" -eq 0 ]; then
          echo "  <result>"
          echo "    <status>OK</status>"
          # propagate metrics as well
          echo "${last_result}" | grep '<metric '
          echo "  </result>"
      else
          last_script_name=$(echo "${last_result}" |awk '/<OSGTestResult /{split($0,a,"id=\""); split(a[2],b,"\""); print b[1];}')

          last_script_reason=$(echo "${last_result}" | awk 'BEGIN{fr=0;}/<[/]detail>/{fr=0;}{if (fr==1) print $0}/<detail>/{fr=1;}')
          my_reason="     Validation failed in ${last_script_name}.

${last_script_reason}"

          echo "  <result>"
          echo "    <status>ERROR</status>
    <metric name=\"TestID\" ts=\"$(date --date=@"${glidein_end_time}" +%Y-%m-%dT%H:%M:%S%:z)\" uri=\"local\">${last_script_name}</metric>"
          # propagate metrics as well (will include the failure metric)
          echo "${last_result}" | grep '<metric '
          echo "  </result>"
          echo "  <detail>
${my_reason}
  </detail>"
      fi
  else
      # create a minimal XML file, else
      echo "  <result>"
      if [ "${exitcode}" -eq 0 ]; then
          echo "    <status>OK</status>"
      else
          echo "    <status>ERROR</status>"
          echo "    <metric name=\"failure\" ts=\"$(date --date=@"${glidein_end_time}" +%Y-%m-%dT%H:%M:%S%:z)\" uri=\"local\">Unknown</metric>"
      fi
      echo "  </result>
  <detail>
    No detail. Could not find source XML file.
  </detail>"
  fi
}

basexml2simplexml() {
  final_result="$1"

  # augment with node info
  echo "${final_result}" | awk 'BEGIN{fr=1;}{if (fr==1) print $0}/<operatingenvironment>/{fr=0;}'

  echo "    <env name=\"client_name\">${client_name}</env>"
  echo "    <env name=\"client_group\">${client_group}</env>"

  echo "    <env name=\"user\">$(id -un)</env>"
  echo "    <env name=\"arch\">$(uname -m)</env>"
  if [ -e '/etc/redhat-release' ]; then
      echo "    <env name=\"os\">$(cat /etc/redhat-release)</env>"
  fi
  echo "    <env name=\"hostname\">$(uname -n)</env>"

  echo "${final_result}" | awk 'BEGIN{fr=0;}{if (fr==1) print $0}/<operatingenvironment>/{fr=1;}'
}

simplexml2longxml() {
  final_result_simple="$1"
  global_result="$2"

  echo "${final_result_simple}" | awk 'BEGIN{fr=1;}{if (fr==1) print $0}/<OSGTestResult /{fr=0;}'

  if [ "${global_result}" != "" ]; then
      # subtests first, so it is more readable, when tailing
      echo '  <subtestlist>'
      echo '    <OSGTestResults>'
      echo "${global_result}" | awk '{print "      " $0}'
      echo '    </OSGTestResults>'
      echo '  </subtestlist>'
  fi

  echo "${final_result_simple}" | awk 'BEGIN{fr=0;}{if (fr==1) print $0}/<OSGTestResult /{fr=1;}/<operatingenvironment>/{fr=0;}'

  echo "    <env name=\"glidein_factory\">${glidein_factory}</env>"
  echo "    <env name=\"glidein_name\">${glidein_name}</env>"
  echo "    <env name=\"glidein_entry\">${glidein_entry}</env>"
  echo "    <env name=\"condorg_cluster\">${condorg_cluster}</env>"
  echo "    <env name=\"condorg_subcluster\">${condorg_subcluster}</env>"
  echo "    <env name=\"glidein_credential_id\">${glidein_cred_id}</env>"
  echo "    <env name=\"condorg_schedd\">${condorg_schedd}</env>"

  echo "${final_result_simple}" | awk 'BEGIN{fr=0;}{if (fr==1) print $0}/<operatingenvironment>/{fr=1;}'
}

print_tail() {
  exit_code=$1
  final_result_simple="$2"
  final_result_long="$3"

  glidein_end_time=$(date +%s)
  let total_time=${glidein_end_time}-${startup_time}
  echo "=== Glidein ending $(date) (${glidein_end_time}) with code ${exit_code} after ${total_time} ==="
  echo ""
  echo "=== XML description of glidein activity ==="
  echo  "${final_result_simple}" | grep -v "<cmd>"
  echo "=== End XML description of glidein activity ==="

  echo "" 1>&2
  echo "=== Encoded XML description of glidein activity ===" 1>&2
  echo "${final_result_long}" | gzip --stdout - | b64uuencode 1>&2
  echo "=== End encoded XML description of glidein activity ===" 1>&2
}

####################################
# Cleaup, print out message and exit
work_dir_created=0
glide_local_tmp_dir_created=0


glidien_cleanup() {
    # Remove Glidein directories (work_dir, glide_local_tmp_dir)
    # 1 - exit code
    # Using GLIDEIN_DEBUG_OPTIONS, start_dir, work_dir_created, work_dir,
    #   glide_local_tmp_dir_created, glide_local_tmp_dir
    if ! cd "${start_dir}"; then
        warn "Cannot find ${start_dir} anymore, exiting but without cleanup"
    else
        if [[ ",${GLIDEIN_DEBUG_OPTIONS}," = *,nocleanup,* ]]; then
            warn "Skipping cleanup, disabled via GLIDEIN_DEBUG_OPTIONS"
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

# use this for early failures, when we cannot assume we can write to disk at all
# too bad we end up with some repeated code, but difficult to do better
early_glidein_failure() {
  error_msg="$1"

  warn "${error_msg}"

  sleep "${sleep_time}"
  # wait a bit in case of error, to reduce lost glideins

  glidein_end_time="$(date +%s)"
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


# use this one once the most basic ops have been done
glidein_exit() {
  # Removed lines about $lock_file (lock file for whole machine) not present elsewhere

  gwms_process_scripts "$GWMS_DIR" cleanup "${glidein_config}"

  global_result=""
  if [ -f otr_outlist.list ]; then
      global_result=$(cat otr_outlist.list)
      chmod u+w otr_outlist.list
  fi

  ge_last_script_name=$(extract_parent_fname "$1")
  result=$(extract_parent_xml_detail "$1")
  final_result=$(construct_xml "${result}")

  # augment with node info
  final_result_simple=$(basexml2simplexml "${final_result}")

  # Create a richer version, too
  final_result_long=$(simplexml2longxml "${final_result_simple}" "${global_result}")

  if [ "$1" -ne 0 ]; then
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
                warn "Notifying Factory of error"
                "${main_work_dir}/${last_script}" glidein_config
            fi
            if [ "${report_failed}" != "NEVER" ]; then
                add_config_line "GLIDEIN_ADVERTISE_DESTINATION" "VO"
                warn "Notifying VO of error"
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
        warn "Sleeping ${ds}"
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
              warn "Last notification sent to Factory"
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
              warn "Last notification sent to VO"
          fi
      fi
  fi

  log_write "glidein_startup.sh" "text" "glidein is about to exit with retcode $1" "info"
  send_logs_to_remote

  glidien_cleanup

  print_tail "$1" "${final_result_simple}" "${final_result_long}"

  exit "$1"
}

####################################################
# automatically determine and setup work directories
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

#######################################
# Parameters utility functions

params_get_simple() {
    # Retrieve a simple parameter (no special characters in its value) from the param list
    # 1:param, 2:param_list (quoted string w/ spaces)
    [[ ${2} = *\ ${1}\ * ]] || return
    local retval="${2##*\ ${1}\ }"
    echo "${retval%%\ *}"
}

params_decode() {
    echo "$1" | sed \
 -e 's/\.nbsp,/ /g' \
 -e 's/\.semicolon,/;/g' \
 -e 's/\.colon,/:/g' \
 -e 's/\.tilde,/~/g' \
 -e 's/\.not,/!/g' \
 -e 's/\.question,/?/g' \
 -e 's/\.star,/*/g' \
 -e 's/\.dollar,/$/g' \
 -e 's/\.comment,/#/g' \
 -e 's/\.sclose,/]/g' \
 -e 's/\.sopen,/[/g' \
 -e 's/\.gclose,/}/g' \
 -e 's/\.gopen,/{/g' \
 -e 's/\.close,/)/g' \
 -e 's/\.open,/(/g' \
 -e 's/\.gt,/>/g' \
 -e 's/\.lt,/</g' \
 -e 's/\.minus,/-/g' \
 -e 's/\.plus,/+/g' \
 -e 's/\.eq,/=/g' \
 -e "s/\.singquot,/'/g" \
 -e 's/\.quot,/"/g' \
 -e 's/\.fork,/\`/g' \
 -e 's/\.pipe,/|/g' \
 -e 's/\.backslash,/\\/g' \
 -e 's/\.amp,/\&/g' \
 -e 's/\.comma,/,/g' \
 -e 's/\.dot,/./g'
}

# Put parameters into the config file
params2file() {
    param_list=""

    while [ $# -gt 0 ]
    do
        # TODO: Use params_decode. For 3.4.8, not to introduce many changes now. Use params_converter
        # Note: using $() we escape blackslash with \\ like above. Using backticks would require \\\
        pfval=$(echo "$2" | sed \
 -e 's/\.nbsp,/ /g' \
 -e 's/\.semicolon,/;/g' \
 -e 's/\.colon,/:/g' \
 -e 's/\.tilde,/~/g' \
 -e 's/\.not,/!/g' \
 -e 's/\.question,/?/g' \
 -e 's/\.star,/*/g' \
 -e 's/\.dollar,/$/g' \
 -e 's/\.comment,/#/g' \
 -e 's/\.sclose,/]/g' \
 -e 's/\.sopen,/[/g' \
 -e 's/\.gclose,/}/g' \
 -e 's/\.gopen,/{/g' \
 -e 's/\.close,/)/g' \
 -e 's/\.open,/(/g' \
 -e 's/\.gt,/>/g' \
 -e 's/\.lt,/</g' \
 -e 's/\.minus,/-/g' \
 -e 's/\.plus,/+/g' \
 -e 's/\.eq,/=/g' \
 -e "s/\.singquot,/'/g" \
 -e 's/\.quot,/"/g' \
 -e 's/\.fork,/\`/g' \
 -e 's/\.pipe,/|/g' \
 -e 's/\.backslash,/\\/g' \
 -e 's/\.amp,/\&/g' \
 -e 's/\.comma,/,/g' \
 -e 's/\.dot,/./g')
        if ! add_config_line "$1 ${pfval}"; then
            glidein_exit 1
        fi
        if [ -z "${param_list}" ]; then
            param_list="$1"
        else
            param_list="${param_list},$1"
        fi
        shift 2
    done
    echo "PARAM_LIST ${param_list}"
    return 0
}

################
# Parse and verify arguments

# allow some parameters to change arguments
# multiglidein GLIDEIN_MULTIGLIDEIN -> multi_glidein
tmp_par=$(params_get_simple GLIDEIN_MULTIGLIDEIN "${params}")
[ -n "${tmp_par}" ] &&  multi_glidein=${tmp_par}

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
    warn "Missing descript fname."
    usage
fi

if [ -z "${descript_entry_file}" ]; then
    warn "Missing descript fname for entry."
    usage
fi

if [ -z "${glidein_name}" ]; then
    warn "Missing gliden name."
    usage
fi

if [ -z "${glidein_entry}" ]; then
    warn "Missing glidein entry name."
    usage
fi


if [ -z "${repository_url}" ]; then
    warn "Missing Web URL."
    usage
fi

repository_entry_url="${repository_url}/entry_${glidein_entry}"

if [ -z "${proxy_url}" ]; then
  proxy_url="None"
fi

if [ "${proxy_url}" = "OSG" ]; then
  if [ -z "${OSG_SQUID_LOCATION}" ]; then
     # if OSG does not define a Squid, then don't use any
     proxy_url="None"
     warn "OSG_SQUID_LOCATION undefined, not using any Squid URL" 1>&2
  else
     proxy_url="$(echo "${OSG_SQUID_LOCATION}" | awk -F ':' '{if ($2 =="") {print $1 ":3128"} else {print $0}}')"
  fi
fi

if [ -z "${sign_id}" ]; then
    warn "Missing signature."
    usage
fi

if [ -z "${sign_entry_id}" ]; then
    warn "Missing entry signature."
    usage
fi

if [ -z "${sign_type}" ]; then
    sign_type="sha1"
fi

if [ "${sign_type}" != "sha1" ]; then
    warn "Unsupported signtype ${sign_type} found."
    usage
fi

if [ -n "${client_repository_url}" ]; then
  # client data is optional, user url as a switch
  if [ -z "${client_sign_type}" ]; then
      client_sign_type="sha1"
  fi

  if [ "${client_sign_type}" != "sha1" ]; then
    warn "Unsupported clientsigntype ${client_sign_type} found."
    usage
  fi

  if [ -z "${client_descript_file}" ]; then
    warn "Missing client descript fname."
    usage
  fi

  if [ -n "${client_repository_group_url}" ]; then
      # client group data is optional, user url as a switch
      if [ -z "${client_group}" ]; then
          warn "Missing client group name."
          usage
      fi

      if [ -z "${client_descript_group_file}" ]; then
          warn "Missing client descript fname for group."
          usage
      fi
  fi
fi

md5wrapper() {
    # $1 - file name
    # $2 - option (quiet)
    # Result returned on stdout
    local ERROR_RESULT="???"
    local ONLY_SUM
    if [ "x$2" = "xquiet" ]; then
        ONLY_SUM=yes
    fi
    local executable=md5sum
    if which ${executable} 1>/dev/null 2>&1; then
        [ -n "${ONLY_SUM}" ] && executable="md5sum \"$1\" | cut -d ' ' -f 1" ||  executable="md5sum \"$1\""
    else
        executable=md5
        if ! which ${executable} 1>/dev/null 2>&1; then
            echo "${ERROR_RESULT}"
            warn "md5wrapper error: can't neither find md5sum nor md5"
            return 1
        fi
        [ -n "${ONLY_SUM}" ] && executable="md5 -q \"$1\"" || executable="md5 \"$1\""
    fi
    local res
    # Flagged by some checkers but OK
    if ! res="$(eval "${executable}" 2>/dev/null)"; then
        echo "${ERROR_RESULT}"
        warn "md5wrapper error: can't calculate md5sum using ${executable}"
        return 1
    fi
    echo "${res}"
}

# Generate directory ID
dir_id() {
    # create an id to distinguish the directories when preserved
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

# Generate glidein UUID
if command -v uuidgen >/dev/null 2>&1; then
    glidein_uuid="$(uuidgen)"
else
    glidein_uuid="$(od -x -w32 -N32 /dev/urandom | awk 'NR==1{OFS="-"; print $2$3,$4,$5,$6,$7$8$9}')"
fi

startup_time="$(date +%s)"
echo "Starting glidein_startup.sh at $(date) (${startup_time})"

echo "script_checksum   = '$(md5wrapper "$0")'"
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

# Before anything else, spawn multiple glideins and wait, if asked to do so
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

########################################
# make sure nobody else can write my files
# In the Grid world I cannot trust anybody
if ! umask 0022; then
    early_glidein_failure "Failed in umask 0022"
fi

########################################
# Setup OSG and/or Globus
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
       warn "GLOBUS_LOCATION not defined and could not guess it."
       warn "Looked in:"
       warn ' /opt/globus/etc/globus-user-env.sh'
       warn ' /osgroot/osgcore/globus/etc/globus-user-env.sh'
       warn 'Continuing like nothing happened'
    fi
  fi

  if [ -r "${GLOBUS_LOCATION}/etc/globus-user-env.sh" ]; then
    . "${GLOBUS_LOCATION}/etc/globus-user-env.sh"
  else
    warn "GLOBUS_PATH not defined and ${GLOBUS_LOCATION}/etc/globus-user-env.sh does not exist."
    warn 'Continuing like nothing happened'
  fi
fi

set_proxy_fullpath() {
    # Set the X509_USER_PROXY path to full path to the file
    if fullpath="$(readlink -f "${X509_USER_PROXY}")"; then
        echo "Setting X509_USER_PROXY ${X509_USER_PROXY} to canonical path ${fullpath}" 1>&2
        export X509_USER_PROXY="${fullpath}"
    else
        echo "Unable to get canonical path for X509_USER_PROXY, using ${X509_USER_PROXY}" 1>&2
    fi
}


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
# prepare and move to the work directory

# Replace known keywords: Condor, CONDOR, OSG, TMPDIR, AUTO, .
# Empty $work_dir means PWD (same as ".")
# A custom path could be provided (no "*)" in case)
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

# Extract and source all the data contained at the end of this script as tarball
extract_all_data

wrapper_list="${PWD}/wrapper_list.lst"
touch "${wrapper_list}"

# create glidein_config
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
# shellcheck disable=SC2086
params2file ${params}

############################################
# Setup logging
log_init "${glidein_uuid}" "${work_dir}"
# Remove these files, if they are still there
rm -rf tokens.tgz url_dirs.desc tokens
log_setup "${glidein_config}"

############################################
# get the proper descript file based on id
# Arg: type (main/entry/client/client_group)
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
# Check signature
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
                warn "File ${cfs_desc_fname} is corrupted."
                rm -f "${tmp_signname}"
                return 1
            fi
            rm -f "${tmp_signname}"
            echo "Signature OK for ${cfs_id}:${cfs_fname}." 1>&2
        fi
    fi
    return 0
}

#####################
# Untar support func

get_untar_subdir() {
    gus_id="$1"
    gus_fname="$2"

    gus_prefix="$(get_prefix "${gus_id}")"
    gus_config_cfg="${gus_prefix}UNTAR_CFG_FILE"

    gus_config_file="$(grep "^${gus_config_cfg} " glidein_config | cut -d ' ' -f 2-)"
    if [ -z "${gus_config_file}" ]; then
        warn "Error, cannot find '${gus_config_cfg}' in glidein_config."
        glidein_exit 1
    fi

    gus_dir="$(grep -i "^${gus_fname} " "${gus_config_file}" | cut -s -f 2-)"
    if [ -z "${gus_dir}" ]; then
        warn "Error, untar dir for '${gus_fname}' cannot be empty."
        glidein_exit 1
    fi

    echo "${gus_dir}"
    return 0
}

#####################
# Periodic execution support function and global variable
add_startd_cron_counter=0
add_periodic_script() {
    # schedules a script for periodic execution using startd_cron
    # parameters: wrapper full path, period, cwd, executable path (from cwd),
    # config file path (from cwd), ID
    # global variable: add_startd_cron_counter
    #TODO: should it allow for variable number of parameters?
    local include_fname=condor_config_startd_cron_include
    local s_wrapper="$1"
    local s_period_sec="${2}s"
    local s_cwd="$3"
    local s_fname="$4"
    local s_config="$5"
    local s_ffb_id="$6"
    local s_cc_prefix="$7"
    if [ ${add_startd_cron_counter} -eq 0 ]; then
        # Make sure that no undesired file is there when called for first cron
        rm -f ${include_fname}
    fi

    let add_startd_cron_counter=add_startd_cron_counter+1
    local name_prefix=GLIDEIN_PS_
    local s_name="${name_prefix}${add_startd_cron_counter}"

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

#####################
# Fetch a single file
#
# Check cWDictFile/FileDictFile for the number and type of parameters (has to be consistent)
fetch_file_regular() {
    fetch_file "$1" "$2" "$2" "regular" 0 "GLIDEIN_PS_" "TRUE" "FALSE"
}

fetch_file() {
    # custom_scripts parameters format is set in the GWMS configuration (creation/lib)
    # 1. ID
    # 2. target fname
    # 3. real fname
    # 4. file type (regular, exec, exec:s, untar, nocache)
    # 5. period (0 if not a periodic file)
    # 6. periodic scripts prefix
    # 7. config check TRUE,FALSE
    # 8. config out TRUE,FALSE
    # The above is the most recent list, below some adaptations for different versions
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
        warn "Not enough arguments in fetch_file, 8 expected ($#/${ifs_str}): $*"
        glidein_exit 1
    fi

    if ! fetch_file_try "$1" "$2" "$3" "$4" "$5" "$6" "$7" "$8"; then
        glidein_exit 1
    fi
    return 0
}

fetch_file_try() {
    # Verifies if the file should be downloaded and acted upon (extracted, executed, ...) or not
    # There are 2 mechanisms to control the download
    # 1. tar files have the attribute "cond_attr" that is a name of a variable in glidein_config.
    #    if the named variable has value 1, then the file is downloaded. TRUE (default) means always download
    #    even if the mechanism is generic, there is no way to specify "cond_attr" for regular files in the configuration
    # 2. if the file name starts with "gconditional_AAA_", the file is downloaded only if a variable GLIDEIN_USE_AAA
    #    exists in glidein_config and the value is not empty
    # Both conditions are checked. If either one fails the file is not downloaded
    fft_id="$1"
    fft_target_fname="$2"
    fft_real_fname="$3"
    fft_file_type="$4"
    fft_period="$5"
    fft_cc_prefix="$6"
    fft_config_check="$7"
    fft_config_out="$8"

    if [[ "${fft_config_check}" != "TRUE" ]]; then
        # TRUE is a special case, always downloaded and processed
        local fft_get_ss
        fft_get_ss=$(grep -i "^${fft_config_check} " glidein_config | cut -d ' ' -f 2-)
        # Stop download and processing if the cond_attr variable is not defined or has a value different from 1
        [[ "${fft_get_ss}" != "1" ]] && return 0
        # TODO: what if fft_get_ss is not 1? nothing, still skip the file?
    fi

    local fft_base_name fft_condition_attr fft_condition_attr_val
    fft_base_name=$(basename "${fft_real_fname}")
    if [[ "${fft_base_name}" = gconditional_* ]]; then
        fft_condition_attr="${fft_base_name#gconditional_}"
        fft_condition_attr="GLIDEIN_USE_${fft_condition_attr%%_*}"
        fft_condition_attr_val=$(grep -i "^${fft_condition_attr} " glidein_config | cut -d ' ' -f 2-)
        # if the variable fft_condition_attr is not defined or empty, do not download
        [[ -z "${fft_condition_attr_val}" ]] && return 0
    fi

    fetch_file_base "${fft_id}" "${fft_target_fname}" "${fft_real_fname}" "${fft_file_type}" "${fft_config_out}" "${fft_period}" "${fft_cc_prefix}"
    # returning the exit code of fetch_file_base
}

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
        warn "${wget_cmd} failed. version:${wget_version}  exit code ${wget_retval} stderr: ${wget_resp}"
        # cannot use error_*.sh helper functions
        # may not have been loaded yet, and wget fails often
        echo "<OSGTestResult id=\"perform_wget\" version=\"4.3.1\">
  <operatingenvironment>
    <env name=\"cwd\">${PWD}</env>
    <env name=\"uname\">$(uname -a)</env>
    <env name=\"release\">$(cat /etc/system-release)</env>
    <env name=\"wget_version\">${wget_version}</env>
  </operatingenvironment>
  <test>
    <cmd>${wget_cmd}</cmd>
    <tStart>$(date --date=@"${START}" +%Y-%m-%dT%H:%M:%S%:z)</tStart>
    <tEnd>$(date +%Y-%m-%dT%H:%M:%S%:z)</tEnd>
  </test>
  <result>
    <status>ERROR</status>
    <metric name=\"failure\" ts=\"$(date --date=@"${START}" +%Y-%m-%dT%H:%M:%S%:z)\" uri=\"local\">Network</metric>
    <metric name=\"URL\" ts=\"$(date --date=@"${START}" +%Y-%m-%dT%H:%M:%S%:z)\" uri=\"local\">${ffb_url}</metric>
    <metric name=\"http_proxy\" ts=\"$(date --date=@"${START}" +%Y-%m-%dT%H:%M:%S%:z)\" uri=\"local\">${proxy_url}</metric>
    <metric name=\"source_type\" ts=\"$(date --date=@"${START}" +%Y-%m-%dT%H:%M:%S%:z)\" uri=\"local\">${ffb_id}</metric>
  </result>
  <detail>
  Failed to load file '${ffb_real_fname}' from '${ffb_repository}' using proxy '${proxy_url}'.  ${wget_resp}
  </detail>
</OSGTestResult>" > otrb_output.xml
        warn "Failed to load file '${ffb_real_fname}' from '${ffb_repository}'."

        if [ -f otr_outlist.list ]; then
            chmod u+w otr_outlist.list
        else
            touch otr_outlist.list
        fi
        cat otrb_output.xml >> otr_outlist.list
        echo "<?xml version=\"1.0\"?>" > otrx_output.xml
        cat otrb_output.xml >> otrx_output.xml
        rm -f otrb_output.xml
        chmod a-w otr_outlist.list
    fi
    return ${wget_retval}
}

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

    START="$(date +%s)"
    curl_cmd="$(echo "curl" "${curl_args[@]}" | sed 's/"/\\\"/g')"
    curl_resp="$(curl "${curl_args[@]}" 2>&1)"
    curl_retval=$?
    if [ ${curl_retval} -eq 0 ] && [ ! -e "${ffb_tmp_outname}" ] ; then
        touch "${ffb_tmp_outname}"
    fi


    if [ "${curl_retval}" -ne 0 ]; then
        curl_version="$(curl --version 2>&1 | head -1)"
        warn "${curl_cmd} failed. version:${curl_version}  exit code ${curl_retval} stderr: ${curl_resp} "
        # cannot use error_*.sh helper functions
        # may not have been loaded yet, and wget fails often
        echo "<OSGTestResult id=\"perform_curl\" version=\"4.3.1\">
  <operatingenvironment>
    <env name=\"cwd\">${PWD}</env>
    <env name=\"uname\">$(uname -a)</env>
    <env name=\"release\">$(cat /etc/system-release)</env>
    <env name=\"curl_version\">${curl_version}</env>
  </operatingenvironment>
  <test>
    <cmd>${curl_cmd}</cmd>
    <tStart>$(date --date=@"${START}" +%Y-%m-%dT%H:%M:%S%:z)</tStart>
    <tEnd>$(date +%Y-%m-%dT%H:%M:%S%:z)</tEnd>
  </test>
  <result>
    <status>ERROR</status>
    <metric name=\"failure\" ts=\"$(date --date=@"${START}" +%Y-%m-%dT%H:%M:%S%:z)\" uri=\"local\">Network</metric>
    <metric name=\"URL\" ts=\"$(date --date=@"${START}" +%Y-%m-%dT%H:%M:%S%:z)\" uri=\"local\">${ffb_url}</metric>
    <metric name=\"http_proxy\" ts=\"$(date --date=@"${START}" +%Y-%m-%dT%H:%M:%S%:z)\" uri=\"local\">${proxy_url}</metric>
    <metric name=\"source_type\" ts=\"$(date --date=@"${START}" +%Y-%m-%dT%H:%M:%S%:z)\" uri=\"local\">${ffb_id}</metric>
  </result>
  <detail>
  Failed to load file '${ffb_real_fname}' from '${ffb_repository}' using proxy '${proxy_url}'.  ${curl_resp}
  </detail>
</OSGTestResult>" > otrb_output.xml
        warn "Failed to load file '${ffb_real_fname}' from '${ffb_repository}'."

        if [ -f otr_outlist.list ]; then
            chmod u+w otr_outlist.list
        else
            touch otr_outlist.list
        fi
        cat otrb_output.xml >> otr_outlist.list
        echo "<?xml version=\"1.0\"?>" > otrx_output.xml
        cat otrb_output.xml >> otrx_output.xml
        rm -f otrb_output.xml
        chmod a-w otr_outlist.list
    fi
    return ${curl_retval}
}

fetch_file_base() {
    # Perform the file download and corresponding action (untar, execute, ...)
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
    echo "<?xml version=\"1.0\"?>
<OSGTestResult id=\"fetch_file_base\" version=\"4.3.1\">
  <operatingenvironment>
    <env name=\"cwd\">${PWD}</env>
  </operatingenvironment>
  <test>
    <cmd>Unknown</cmd>
    <tStart>$(date +%Y-%m-%dT%H:%M:%S%:z)</tStart>
    <tEnd>$(date +%Y-%m-%dT%H:%M:%S%:z)</tEnd>
  </test>
  <result>
    <status>ERROR</status>
    <metric name=\"failure\" ts=\"$(date +%Y-%m-%dT%H:%M:%S%:z)\" uri=\"local\">Unknown</metric>
    <metric name=\"source_type\" ts=\"$(date +%Y-%m-%dT%H:%M:%S%:z)\" uri=\"local\">${ffb_id}</metric>
  </result>
  <detail>
     An unknown error occurred.
  </detail>
</OSGTestResult>" > otrx_output.xml
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
                warn "wget ${wget_version} cannot disable caching"
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
            warn "Failed to rename ${ffb_tmp_outname} into ${ffb_outname}"
            return 1
        fi
    fi

    # if executable, execute
    if [[ "${ffb_file_type}" = "exec" || "${ffb_file_type}" = "exec:"* ]]; then
        if ! chmod u+x "${ffb_outname}"; then
            warn "Error making '${ffb_outname}' executable"
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
            END=$(date +%s)
            "${main_dir}"/error_augment.sh -process ${ret} "${ffb_id}/${ffb_target_fname}" "${PWD}" "${ffb_outname} glidein_config" "${START}" "${END}" #generating test result document
            "${main_dir}"/error_augment.sh -concat
            if [ ${ret} -ne 0 ]; then
                echo "=== Validation error in ${ffb_outname} ===" 1>&2
                warn "Error running '${ffb_outname}'"
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
        START=$(date +%s)
        (mkdir "${ffb_untar_dir}" && cd "${ffb_untar_dir}" && tar -xmzf "${ffb_outname}") 1>&2
        ret=$?
        if [ ${ret} -ne 0 ]; then
            "${main_dir}"/error_augment.sh -init
            "${main_dir}"/error_gen.sh -error "tar" "Corruption" "Error untarring '${ffb_outname}'" "file" "${ffb_outname}" "source_type" "${cfs_id}"
            "${main_dir}"/error_augment.sh  -process ${cfs_rc} "tar" "${PWD}" "mkdir ${ffb_untar_dir} && cd ${ffb_untar_dir} && tar -xmzf ${ffb_outname}" "${START}" "$(date +%s)"
            "${main_dir}"/error_augment.sh -concat
            warn "Error untarring '${ffb_outname}'"
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
        echo "<?xml version=\"1.0\"?>
<OSGTestResult id=\"fetch_file_base\" version=\"4.3.1\">
  <operatingenvironment>
    <env name=\"cwd\">${PWD}</env>
  </operatingenvironment>
  <test>
    <cmd>Unknown</cmd>
    <tStart>$(date +%Y-%m-%dT%H:%M:%S%:z)</tStart>
    <tEnd>$(date +%Y-%m-%dT%H:%M:%S%:z)</tEnd>
  </test>
  <result>
    <status>OK</status>
  </result>
</OSGTestResult>" > otrx_output.xml
    fi

   return 0
}

# Adds $1 to GWMS_PATH and update PATH
add_to_path() {
    logdebug "Adding to GWMS_PATH: $1"
    local old_path=":${PATH%:}:"
    old_path="${old_path//:$GWMS_PATH:/}"
    local old_gwms_path=":${GWMS_PATH%:}:"
    old_gwms_path="${old_gwms_path//:$1:/}"
    old_gwms_path="${1%:}:${old_gwms_path#:}"
    export GWMS_PATH="${old_gwms_path%:}"
    old_path="${GWMS_PATH}:${old_path#:}"
    export PATH="${old_path%:}"
}

fixup_condor_dir() {
    # All files in the native condor tarballs have a directory like condor-9.0.11-1-x86_64_CentOS7-stripped
    # However the (not used anymore) gwms create_condor_tarball removes that dir
    # Here we remove that dir as well to allow factory ops to use native condor tarballs

    # Check if the condor dir has only one subdir, the one like "condor-9.0.11-1-x86_64_CentOS7-stripped"
    # See https://stackoverflow.com/questions/32429333/how-to-test-if-a-linux-directory-contain-only-one-subdirectory-and-no-other-file
    if [ $(find "${gs_id_work_dir}/condor" -maxdepth 1 -type d -printf 1 | wc -m) -eq 2 ]; then
        echo "Fixing directory structure of condor tarball"
        mv "${gs_id_work_dir}"/condor/condor*/* "${gs_id_work_dir}"/condor > /dev/null
    else
        echo "Condor tarball does not need to be fixed"
    fi
}

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
      warn "No signature in description file ${gs_id_work_dir}/${gs_id_descript_file} (wc: $(wc < "${gs_id_work_dir}/${gs_id_descript_file}" 2>/dev/null))."
      glidein_exit 1
  fi
  signature_file=$(echo "${signature_file_line}" | cut -s -f 2-)

  # Fetch signature file
  gs_id_signature="$(get_signature ${gs_id})"
  fetch_file_regular "${gs_id}" "${signature_file}"
  echo "${gs_id_signature}  ${signature_file}" > "${gs_id_work_dir}/signature.sha1.test"
  if ! (cd "${gs_id_work_dir}" && sha1sum -c signature.sha1.test) 1>&2 ; then
      warn "Corrupted signature file '${gs_id_work_dir}/${signature_file}'."
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
      warn "Corrupted description file ${gs_id_work_dir}/${gs_id_descript_file}."
      glidein_exit 1
  fi
done

###################################################
# get last_script, as it is used by the fetch_file
gs_id_work_dir="$(get_work_dir main)"
gs_id_descript_file="$(get_descript_file main)"
last_script="$(grep "^last_script " "${gs_id_work_dir}/${gs_id_descript_file}" | cut -s -f 2-)"
if [ -z "${last_script}" ]; then
    warn "last_script not in description file ${gs_id_work_dir}/${gs_id_descript_file}."
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
      warn "No '${gs_file_list_id}' in description file ${gs_id_work_dir}/${gs_id_descript_file}."
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
    warn "Error running '${last_script}'"
fi

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
