#!/bin/bash

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

#*******************************************************************#
# utils_gs_io.sh                                                    #
# This script contains I/O utility functions for the                #
# glidein_startup.sh script                                         #
#*******************************************************************#

################################
# Print the tail with the final results of the glideins
# Arguments:
#   1: exit code
#   2: short version of the final results
#   3: long version of the final results
# Globals (r/w):
#   total_time
print_tail() {
  local final_result_simple final_result_long exit_code glidein_end_time
  exit_code=$1
  final_result_simple="$2"
  final_result_long="$3"
  glidein_end_time=$(date +%s)
  let total_time=${glidein_end_time}-${startup_time}
  print_header_line "Glidein ending $(date) (${glidein_end_time}) with code ${exit_code} after ${total_time}"
  echo ""
  print_header_line "XML description of glidein activity"
  echo  "${final_result_simple}" | grep -v "<cmd>"
  print_header_line "End XML description of glidein activity"
  echo "" 1>&2
  print_header_line "Encoded XML description of glidein activity" >& 2
  echo "${final_result_long}" | gzip --stdout - | b64uuencode 1>&2
  print_header_line "End encoded XML description of glidein activity" >& 2
}

################################
# Usage of the glidein_startup.sh script
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
# Parse the glidein startup options
# Parameters:
#   @: shell parameters
# Globals (r/w):
#   params
#   all other global variables to set
parse_options(){
    params=""
    while [ $# -gt 0 ]
        if [[ $1 != "-"* ]]; then
            break
        fi
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
            *)  (log_warn "Unknown option $1"; usage; exit 1) 1>&2; exit 1;;
        esac
        shift 2
    done
}
