#!/bin/bash

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

# Description;
#   This is an custom script file executed by glidein_startup.sh
#   It has the routines to setup the credentials (X509 and JWTs files and environment)
#   It must be run from the Glidein workdir (it creates directories there)
#
# If you make change to this file check also check_proxy.sh that has the same get_x509_expiration

glidein_config="$1"

# Constants
GWMS_CREDENTIALS_SUBDIR=cred.d
gwms_credentials_dir=

# Aux scripts: import gconfig functions and define error_gen
add_config_line_source="$(grep '^ADD_CONFIG_LINE_SOURCE ' "$glidein_config" | cut -d ' ' -f 2-)"
# shellcheck source=add_config_line.source
. "$add_config_line_source"
error_gen=$(gconfig_get ERROR_GEN_PATH "$glidein_config")
# for debugging: add the following 2 lines and comment the ones below (until the error_gen assignment)
# gconfig_add() { echo -n "CONFIG: "; echo "$@"; }
# error_gen=echo

warn() {
    echo "$1" >&2
}

# Common setup for credentials
cred_setup() {
    local cred_dir
    cred_dir="$(pwd)/$GWMS_CREDENTIALS_SUBDIR"
    if [[ ! -d "$cred_dir" ]]; then
        if ! mkdir -p "$cred_dir"; then
            echo "Failed in creating credentials directory: $cred_dir."
            return 1
        fi
    fi
    echo "$cred_dir"
}

# Refresh credentials (x509 proxy and tokens)
# Return: 0 if at least one credential was refreshed
#         1 otherwise
# Uses X509_USER_PROXY_ORIG X509_USER_PROXY GLIDEIN_CONDOR_TOKEN_ORIG GLIDEIN_CONDOR_TOKEN
refresh_credentials() {
    local proxy_from="$1" token_from="$3" proxy_to="$2" token_to="$4" refreshed=
    # If either X509_USER_PROXY_ORIG or GLIDEIN_CONDOR_TOKEN_ORIG
    # are  set it means the script has run at least once

    # Refresh proxy
    if [[ -n "${proxy_from}" && -n "$proxy_to" ]]; then
        # Allow to write, update and protect
        chmod 600 "$proxy_to" && cp "$proxy_from" "$proxy_to" && chmod 400 "$proxy_to" && refreshed="True"
    fi

    # Refresh tokens (all *idtoken files in the source directory)
    # assuming condor will eventually copy in updated tokens like it does proxies now
    if [[ -n "${token_from}" && -n "$token_to" ]]; then
       local from_dir to_dir
       from_dir=$(dirname "${GLIDEIN_CONDOR_TOKEN_ORIG}")
       to_dir=$(dirname "${GLIDEIN_CONDOR_TOKEN}")
       for tok in "${from_dir}"/*idtoken; do
            cp "${tok}" "${to_dir}" && refreshed="True"
       done
    fi

    # Check results
    [[ -z "$refreshed" ]] && return 1 || true
    # Info message with what was refreshed?
    return 0
}

###############################
# x509 functions

# Check that x509 CA certificates exist and set the env variable X509_CERT_DIR
# Using: X509_CERT_DIR, HOME, GLOBUS_LOCATION, X509_CADIR
# Return 1 and error string if failing
#        0 and certs dir path if succeeding
get_x509_certs_dir() {
    local cert_dir
    if [ -e "$X509_CERT_DIR" ]; then
        cert_dir="X509_CERT_DIR"
    elif [ -e "$HOME/.globus/certificates/" ]; then
        cert_dir="$HOME/.globus/certificates/"
    elif [ -e "/etc/grid-security/certificates/" ]; then
        cert_dir=/etc/grid-security/certificates/
    elif [ -e "$GLOBUS_LOCATION/share/certificates/" ]; then
        cert_dir="$GLOBUS_LOCATION/share/certificates/"
    elif [ -e "$X509_CADIR" ]; then
        cert_dir="$X509_CADIR"
    else
        STR="Could not find CA certificates!\n"
        STR+="Looked in:\n"
        STR+="	\$X509_CERT_DIR ($X509_CERT_DIR)\n"
        STR+="	\$HOME/.globus/certificates/ ($HOME/.globus/certificates/)\n"
        STR+="	/etc/grid-security/certificates/"
        STR+="	\$GLOBUS_LOCATION/share/certificates/ ($GLOBUS_LOCATION/share/certificates/)\n"
        STR+="	\$X509_CADIR ($X509_CADIR)\n"
        STR1=$(echo -e "$STR")
        echo "$STR1"
        return 1
    fi
    echo "$cert_dir"
}

# Look for the proxy certificate in $1 and $X509_USER_PROXY
# No more in /tmp/x509up_u`id -u`, other processes form the same user could share /tmp
# $1 - optional certificate file name
# Out: proxy file name to use if returning 0
#      error message if returning 1
# This function is also setting/changing the value of X509_USER_PROXY TODO: needed?
get_x509_proxy() {
    local cert_fname=${1:-"$X509_USER_PROXY"}
    X509_USER_PROXY="$cert_fname"
    if [[ -n "$cert_fname" || ! -e "$cert_fname" ]]; then
        echo "Proxy certificate '$cert_fname' does not exist."
        return 1
    fi
    if [[ ! -r "$cert_fname" ]]; then
        echo "Unable to read '$cert_fname' (user: $(id -u)/$USER)."
        return 1
    fi
    echo "$cert_fname"
}

# Checking which proxy verification commands (grid-proxy-info, voms=proxy-info, openssl) are available
# Failing only if all commands are missing
# If only some are missing only prints warning on stderr
# All functions have to be modified to work with any of the 3 commands
check_x509_tools() {
    local cmd missing_commands=0
    # verify commands
    for cmd in grid-proxy-info voms-proxy-info openssl ; do
        if ! command -v $cmd >& /dev/null; then
            STR="$cmd command not found in path!"
            warn "$STR"
            (( missing_commands++ )) || true
        fi
    done
    if [[ $missing_commands -ne 0 ]]; then
        if [[ $missing_commands -ge 3 ]]; then
            # "$error_gen" -error "setup_x509.sh" "WN_Resource" "$STR"
            echo "No x509 command (grid-proxy-init, voms-proxy-init, openssl) found in path!"
            return 1
        else
            echo "Not all x509 commands found in path ($missing_commands missing)!"
        fi
    fi
    return 0
}

# Copy x509 proxy from the X509_USER_PROXY path
# 1. file to copy from
# 2. file to copy to
# 3. file protection (optional, default: 0400)
# Out: new proxy path when successful (return 0)
#      error message when failing (return 1)
# TODO: manage error info, old messages. Keep until better error reporting is implemented
        # "$error_gen" -error "setup_x509.sh" "Corruption" "$STR1" "proxy" "$X509_USER_PROXY"
        #"$error_gen" -error "setup_x509.sh" "Corruption" "$STR" "file" "$X509_USER_PROXY"
        #"$error_gen" -error "setup_x509.sh" "Corruption" "$STR" "file" "$X509_USER_PROXY" "command" "umask"
        #"$error_gen" -error "setup_x509.sh" "Corruption" "$STR" "directory" "$local_proxy_dir"
        #"$error_gen" -error "setup_x509.sh" "Corruption" "$STR" "file" "$X509_USER_PROXY"
        # exit_if_no_token 1
        # src -> dst
safe_copy_and_protect() {
    local file_from="$1" file_to="$2"
    local file_protection=${3:-0400}
    if [[ ! -a "$file_from" ]]; then
        STR="Could not find credential! Looked in '$file_from':\n"
        STR+=$(ls -la "$file_from")
        STR1=$(echo -e "$STR")
        echo "$STR1"
        return 1
    fi
    # Make the proxy local, so that it does not get
    # "accidentally" deleted by some proxy management tool
    # We don't need renewals
    local old_umask
    if ! old_umask=$(umask) ; then
        echo "Failed in reading old umask!"
        return 1
    fi
    # make sure nobody else can read my proxy
    if ! umask 0077 ; then
        echo "Failed to set umask 0077!"
        return 1
    fi
    local dir_name
    dir_name=$(dirname "$file_to")
    if [ ! -d "$dir_name" ]; then
        echo "Crecentials dir '$dir_name' not available."
        return 1
    fi
    if ! cp "$file_from" "$file_to"; then
        echo "Failed in copying proxy '$file_from' to '$dir_name'."
        return 1
    fi
    # protect from strange sites (only the owner should only read) was: a-wx, go-r
    chmod "$file_protection" "$file_to"
    # cleanup
    if ! umask "$old_umask"; then
        echo "Failed to set back original umask!"
        return 1
    fi
    echo "$file_to"
    return 0
}

# Convert time from date in the PEM certificate/proxy to seconds from epoch
# Compatible w/ BSD/Mac
# 1. time to convert in date format (e.g. Mar 25 18:17:52 2021 GMT)
get_epoch_seconds() {
    local res
    if ! res=$(date +%s -d "$1" 2>/dev/null); then
        # For BSD or Mac OS X
        if ! res=$(date  -j -f "%a %b %d %T %Y %Z" "$1" +"%s" 2>/dev/null); then
            warn "Unable to convert '$1' to seconds from epoch"
        fi
    fi
    echo "$res"
}

# Get proxy remaining lifetime using openssl
# 1. cert pathname
# 2. time to compare in epoch format (optional)
# Out: remaining seconds
openssl_get_x509_timeleft() {
    local cert_pathname="$1"
    local output start_date end_date start_epoch end_epoch epoch_now
    if [ ! -r "$cert_pathname" ]; then
        return 1
    fi
    output=$(openssl x509 -noout -dates -in "$cert_pathname" 2>/dev/null) || return 1
    start_date=$(echo $output | sed 's/.*notBefore=\(.*\).*not.*/\1/g')  # intentional word splittig to remove newline
    end_date=$(echo $output | sed 's/.*notAfter=\(.*\)$/\1/g')  # intentional word splittig to remove newline
    start_epoch=$(get_epoch_seconds "$start_date")
    end_epoch=$(get_epoch_seconds "$end_date")
    epoch_now=${2:-$(date +%s)}
    # Check validity
    if [ "$start_epoch" -gt "$epoch_now" ]; then
        warn "Certificate '$1' is not yet valid"
        seconds_to_expire=0
    else
        seconds_to_expire=$(( end_epoch - epoch_now ))
    fi
    echo $seconds_to_expire
}


# Return the expiration time of the proxy
# 1. path of the proxy file
# Out: proxy expiration time (seconds from epoch)
#      error msg if failing (return 1)
get_x509_expiration() {
    if ! now=$(date +%s); then
        echo "x509 verification failed. Command 'date' not found!"
       # "$error_gen" -error "setup_x509.sh" "WN_Resource" "$STR" "command" "date"
        return 1
    fi
    if [ ! -r "$1" ]; then
        echo "Could not obtain remaining time: proxy file not readable"
        return 1
    fi
    local l cmd="grid-proxy-info"
    if ! l=$(grid-proxy-info -timeleft -file "$1" 2>/dev/null); then
        cmd="voms-proxy-info"
        # using  -dont-verify-ac to avoid exit code 1 if AC signatures are not present
        if ! l=$(voms-proxy-info -dont-verify-ac -timeleft -file "$1" 2>/dev/null); then
            cmd="openssl"
            if ! l=$(openssl_get_x509_timeleft "$1" "$now"); then
                # failed to get time left
                echo "Could not obtain proxy remaining time (attempted grid-proxy-info, voms-proxy-info, openssl)"
                #"$error_gen" -error "setup_x509.sh" "WN_Resource" "$STR"
                return 1
            fi
        fi
    fi
    # Check time left
    if [[ "$l" -lt 60 ]]; then
        echo "Proxy not valid in 1 minute, only $l seconds left! Not enough valid time."
        #"$error_gen" -error "setup_x509.sh" "VO_Proxy" "$STR" "proxy" "$X509_USER_PROXY"
        return 1
    fi
    echo $((now + l))
    return 0
}



#########################
# JWT functions

# Copy tokens that need to be copied in the credentials directory:
# - glidein token (to call back to the VO collector): credential_*.idtoken in the start directory GLIDEIN_START_DIR_ORIG
#   (1 file, 0 OK if x509 is used)
#   TODO: could this be also in the work directory GLIDEIN_WORKSPACE_ORIG?
# - CE collector tokens: ce_*.idtoken in the start directory GLIDEIN_START_DIR_ORIG (0 to many files)
# 1. from dir: directory to copy from
# 2. to dir: token directory
# Sets GLIDEIN_CONDOR_TOKEN_ORIG
copy_idtokens() {
    local start_dir from_dir=$1 to_dir=$2
    local cred_glidein cred_glidein_ctr=0 cred_cecoll_ctr=0 cred_ctr=0
    start_dir=$(pwd)
    cd "$from_dir" || true
    for i in *.idtoken; do
        cp "$i" "$to_dir/$i"
        if [[ "$i" == ce_*.idtoken ]]; then
            warn "Copied CE collector token '${i}' to '${to_dir}/'"
            (( cred_cecoll_ctr++ ))
        elif [[ "$i" == credential_*.idtoken ]]; then
            warn "Copied glidein token '${i}' to '${to_dir}/'"
            (( cred_glidein_ctr++ ))
            cred_glidein="${to_dir}/$i"
            GLIDEIN_CONDOR_TOKEN_ORIG="${from_dir}/$i"
        else
            warn "Copied token '${i}' to '${to_dir}/'"
            (( cred_ctr++ ))
        fi
    done
    (( cred_ctr += (cred_cecoll_ctr+cred_glidein) ))
    warn "Copied $cred_ctr tokens ($cred_glidein_ctr glidein, $cred_cecoll_ctr CE collector)"
    if [[ "$cred_glidein_ctr" -ne 1 ]]; then
        if [[ "$cred_glidein_ctr" -eq 0 ]]; then
            echo "No glidein token found!"
        else
            echo "There should be only one glidein token, $cred_glidein_ctr found"
        fi
        return 1
    fi
    cd "$start_dir" || true
    echo "$cred_glidein"
    return
}

# Retrieve trust domain
# Uses GLIDEIN_Collector and CCB_ADDRESS from glidein_config
# TODO: should domain come from the token instead?
# TODO (Dennis): why removing after dash? what about host name including "-"?
get_trust_domain() {
        head_node=$(gconfig_get GLIDEIN_Collector "${glidein_config}")
        [[ -z "${head_node}" ]] && head_node=$(gconfig_get CCB_ADDRESS "${glidein_config}") || true
        if [[ -z "${head_node}" ]]; then
            # TODO error message and return 1 - no DOMAIN, Q should domain come from the token instead?
            echo "Unable to retrieve trust domain from GLIDEIN_Collector and CCB_ADDRESS"
            return 1
        fi
        echo "${head_node}" | sed -e 's/?.*//' -e 's/-.*//'
        return 0
}


############################################################
#
# Main
#
############################################################

start_dir=$(pwd)
[[ -n "$GLIDEIN_WORKSPACE_ORIG" ]] && cd "$GLIDEIN_WORKSPACE_ORIG" || true

if ! gwms_credentials_dir=$(cred_setup); then
    # the output is the error message in case of error
    "$error_gen" -error "setup_x509.sh" "WN_Resource" "$gwms_credentials_dir"
    exit 1
fi

GLIDEIN_CONDOR_TOKEN=$(gconfig_get GLIDEIN_CONDOR_TOKEN "$glidein_config")
GLIDEIN_START_DIR_ORIG=$(gconfig_get GLIDEIN_START_DIR_ORIG "$glidein_config")
GLIDEIN_WORKSPACE_ORIG=$(gconfig_get GLIDEIN_WORKSPACE_ORIG "$glidein_config")

# If it is not the first execution, but a periodic one, just refresh and exit

if [[ -n "$GLIDEIN_PERIODIC_SCRIPT" ]]; then
    X509_USER_PROXY_ORIG=$(gconfig_get X509_USER_PROXY_ORIG "$glidein_config")
    GLIDEIN_CONDOR_TOKEN_ORIG=$(gconfig_get GLIDEIN_CONDOR_TOKEN_ORIG "$glidein_config")
    X509_USER_PROXY=$(gconfig_get X509_USER_PROXY "$glidein_config")
    GLIDEIN_CONDOR_TOKEN=$(gconfig_get GLIDEIN_CONDOR_TOKEN "$glidein_config")

    if refresh_credentials "$X509_USER_PROXY_ORIG" "$X509_USER_PROXY" "$GLIDEIN_CONDOR_TOKEN_ORIG" "$GLIDEIN_CONDOR_TOKEN"; then
        "$error_gen" -ok "setup_x509.sh" "JWT" "${GLIDEIN_CONDOR_TOKEN:-unavailable}" "proxy" "${X509_USER_PROXY:-unavailable}"
        exit 0
    fi

    "$error_gen" -error "setup_x509.sh" "WN_Resource" "Periodic execution should not reach setup, probably needed glidein_config veriables are not set"
    exit 1
fi

# On error functions return 1 and error msg on stdout
# TODO: change error return string to "error_type,mgs" for better error reporting
cred_updated=

# IDTOKENS
if out=$(copy_idtokens "$GLIDEIN_START_DIR_ORIG" "$gwms_credentials_dir"/idtokens/); then
    export GLIDEIN_CONDOR_TOKEN="$out"
    gconfig_add GLIDEIN_CONDOR_TOKEN "$GLIDEIN_CONDOR_TOKEN"
    gconfig_add GLIDEIN_CONDOR_TOKEN_ORIG "$GLIDEIN_CONDOR_TOKEN_ORIG"
    if out=$(get_trust_domain); then
        export TRUST_DOMAIN="$out"
        gconfig_add TRUST_DOMAIN "$out"
        cred_updated+=idtoken,
    else
        warn "$out"
    fi
else
    warn "$out"
fi

# x509
if out=$(get_x509_certs_dir); then
    export X509_CERT_DIR="$out"
    if out=$(check_x509_tools); then
        [[ -n "$out" ]] && warn "$out"
        if out=$(safe_copy_and_protect "$X509_USER_PROXY" "$gwms_credentials_dir/myproxy"); then
            # Copy successful, set env variables
            export X509_USER_PROXY_ORIG="$X509_USER_PROXY"
            export X509_USER_PROXY="$out"
            if out=$(get_x509_expiration "$X509_USER_PROXY"); then
                # Copy succesfull and proxy valid, set values in glidein_config
                gconfig_add X509_CERT_DIR   "$X509_CERT_DIR"
                gconfig_add X509_USER_PROXY "$X509_USER_PROXY"
                gconfig_add X509_USER_PROXY_ORIG "$X509_USER_PROXY_ORIG"
                gconfig_add X509_EXPIRE  "$out"
                cred_updated+="proxy,"
            else
                warn "$out"
            fi
        else
            warn "$out"
        fi
    else
        # "$error_gen" -error "setup_x509.sh" "WN_Resource" "$STR"
        warn "$out"
    fi
else
    #"$error_gen" -error "setup_x509.sh" "WN_Resource" "$STR1" "directory" "$X509_CERT_DIR"
    warn "$out"
fi

if [[ -z "$cred_updated" ]]; then
    warn "setup_x509.sh: No valid credential (x509 proxy or token) found"
    "$error_gen" -error "setup_x509.sh" "WN_Resource" "No valid credential (x509 proxy or token) found"
    exit 1
fi

echo "setup_x509.sh: Credentials copied, verified, amd added to glidein_config: ${cred_updated%,}"
"$error_gen" -ok "setup_x509.sh" "JWT" "${GLIDEIN_CONDOR_TOKEN:-unavailable}" "trust_domain" "${TRUST_DOMAIN:-unavailable}" "proxy" "${X509_USER_PROXY:-unavailable}" "cert_dir" "${X509_CERT_DIR:-unavailable}"
exit 0
