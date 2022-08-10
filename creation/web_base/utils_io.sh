################################
# Function used to log warning statements
# Arguments:
#   @: content to warn 
log_warn() {
    echo "WARN $(date)" "$@" 1>&2
}

################################
# Function used to log debug statements
# Arguments:
#   @: content to debug 
log_debug() {
    echo "DEBUG $(date)" "$@" 1>&2
}

#####################
# Function used to prit a header line
# Arguments:
#   1: content of the header line
#   2 (optional): 2 if needs to write to stderr 
print_header_line(){
    local content
    if [ $# -eq 1 ]; then
        content=$1
        echo "===  ${content}  ==="
    elif [ $# -eq 2 && $2 -eq 2]; then
        #TODO(F): Check
        content=$1
        echo "===  ${content}  ===" 1>&2
    fi
}

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
  #echo "=== Glidein ending $(date) (${glidein_end_time}) with code ${exit_code} after ${total_time} ==="
  echo ""
  print_header_line "XML description of glidein activity"
  #echo "=== XML description of glidein activity ==="
  echo  "${final_result_simple}" | grep -v "<cmd>"
  print_header_line "End XML description of glidein activity"
  #echo "=== End XML description of glidein activity ==="

  echo "" 1>&2
  print_header_line "Encoded XML description of glidein activity" 2
  #echo "=== Encoded XML description of glidein activity ===" 1>&2
  echo "${final_result_long}" | gzip --stdout - | b64uuencode 1>&2
  print_header_line "End encoded XML description of glidein activity" 2
  #echo "=== End encoded XML description of glidein activity ===" 1>&2
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
    exit 1 #TODO(F): why?
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
}
