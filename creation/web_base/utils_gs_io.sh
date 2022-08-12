#*******************************************************************#
#                        utils_gs_io.sh                             #
#       This script contains I/O utility functions for the          #
#                 glidein_startup.sh script                         #
#                      File Version: 1.0                            #
#*******************************************************************#
# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

################################
# Function used to print the tail with the final results of the glideins
# Arguments:
#   1: exit code
#   2: short version of the final results
#   3: long version of the final results
# Global:
#   total_time
print_tail() {
  local final_result_simple, final_result_long, exit_code
  exit_code=$1
  final_result_simple="$2"
  final_result_long="$3"
  local glidein_end_time
  glidein_end_time=$(date +%s)
  let total_time=${glidein_end_time}-${startup_time}
  print_header_line "Glidein ending $(date) (${glidein_end_time}) with code ${exit_code} after ${total_time}"
  echo ""
  print_header_line "XML description of glidein activity"
  echo  "${final_result_simple}" | grep -v "<cmd>"
  print_header_line "End XML description of glidein activity"

  echo "" 1>&2
  print_header_line "Encoded XML description of glidein activity" 2
  echo "${final_result_long}" | gzip --stdout - | b64uuencode 1>&2
  print_header_line "End encoded XML description of glidein activity" 2
}

################################
# Function used to have information about the usage of the glidein_startup.sh script
# Returns:
#   1 in any case
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
}

################################
# Function used to print initial information header
# Parameters:
#   @: shell parameters
# Global:
#   startup_time
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
# Function used to parse the glidein startup options
# Parameters:
#   @: shell parameters
# Global:
#   params
#   all other global variables to set
parse_options(){
    params=""
    while [ $# -gt 0 ]
        if [[ $2 == "-"* ]]; then
            (log_warn "Wrong argument: $2 for option $1."; log_warn "You cannot set two consecutive options without specifying the option value!"; usage; exit 1) 1>&2; exit 1
        fi
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
            -h|--help) usage; exit 0;;
            *)  (log_warn "Unknown option $1"; usage; exit 1) 1>&2; exit 1
        esac
        shift 2
    done
}

################################
# Function used to parse and verify arguments
# It allows some parameters to change arguments
# Global:
#   tmp_par
#   repository_entry_url
#   proxy_url
#   client_sign_type
parse_arguments(){
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
        log_warn "Missing descript fname."
        usage
    fi

    if [ -z "${descript_entry_file}" ]; then
        log_warn "Missing descript fname for entry."
        usage
    fi

    if [ -z "${glidein_name}" ]; then
        log_warn "Missing gliden name."
        usage
    fi

    if [ -z "${glidein_entry}" ]; then
        log_warn "Missing glidein entry name."
        usage
    fi


    if [ -z "${repository_url}" ]; then
        log_warn "Missing Web URL."
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
         log_warn "OSG_SQUID_LOCATION undefined, not using any Squid URL" 1>&2
      else
         proxy_url="$(echo "${OSG_SQUID_LOCATION}" | awk -F ':' '{if ($2 =="") {print $1 ":3128"} else {print $0}}')"
      fi
    fi

    if [ -z "${sign_id}" ]; then
        log_warn "Missing signature."
        usage
    fi

    if [ -z "${sign_entry_id}" ]; then
        log_warn "Missing entry signature."
        usage
    fi

    if [ -z "${sign_type}" ]; then
        sign_type="sha1"
    fi

    if [ "${sign_type}" != "sha1" ]; then
        log_warn "Unsupported signtype ${sign_type} found."
        usage
    fi

    if [ -n "${client_repository_url}" ]; then
      # client data is optional, user url as a switch
      if [ -z "${client_sign_type}" ]; then
          client_sign_type="sha1"
      fi

      if [ "${client_sign_type}" != "sha1" ]; then
        log_warn "Unsupported clientsigntype ${client_sign_type} found."
        usage
      fi

      if [ -z "${client_descript_file}" ]; then
        log_warn "Missing client descript fname."
        usage
      fi

      if [ -n "${client_repository_group_url}" ]; then
          # client group data is optional, user url as a switch
          if [ -z "${client_group}" ]; then
              log_warn "Missing client group name."
              usage
          fi

          if [ -z "${client_descript_group_file}" ]; then
              log_warn "Missing client descript fname for group."
              usage
          fi
      fi
    fi
}
