. utils_tarballs.sh
. utils_signals.sh
. utils_log.sh
. utils_xml.sh
. utils_crypto.sh
. utils_http.sh
. glidein_cleanup.sh
. utils_fetch.sh

################################
# Parameters utility functions

################################
# Function used to handle the list of parameters
# params will contain the full list of parameters
# -param_XXX YYY will become "XXX YYY"
menu() {
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
            *)  (log_warn "Unknown option $1"; usage) 1>&2; exit 1
        esac
        shift 2
    done    
}

################################
# Function used to retrieve a simple parameter (no special characters in its value) from the param list
# make sure to have a valid slots_layout
# Arguments:
#   1: param
#   2: param_list (quoted string w/ spaces)
params_get_simple() {
    [[ ${2} = *\ ${1}\ * ]] || return
    local retval="${2##*\ ${1}\ }"
    echo "${retval%%\ *}"
}

###############################
# Function used to decode the parameters
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

###############################
# Function used to put the parameters into the config file
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

################################
# Function used to parse and verify arguments
# It allows some parameters to change arguments
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
