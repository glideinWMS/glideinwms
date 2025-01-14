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
SCRIPT_NAME=$(basename "$0")
GWMS_CREDENTIALS_SUBDIR=cred.d
gwms_credentials_dir=

warn() {
    echo "$1" >&2
}

# Common setup for credentials
# Proxy is in credentials dir, idtokens have subdirectory (./idtoken)
# Uses GWMS_CREDENTIALS_SUBDIR
# Out:  credentials directory (full path)
#       error message if creation failed (return code 1)
cred_setup() {
    local cred_dir
    cred_dir="$(pwd)/$GWMS_CREDENTIALS_SUBDIR"
    if [[ ! -d "${cred_dir}/idtokens" ]]; then
        if ! mkdir -p "${cred_dir}/idtokens"; then
            echo "Failed in creating credentials directory: $cred_dir (and ${cred_dir}/idtoken)."
            return 1
        fi
    fi
    echo "$cred_dir"
}

# Refresh credentials (x509 proxy and tokens)
# Copy the proxy file and all tokens in the directory of the token file
# 1. source proxy file to copy (X509_USER_PROXY_ORIG)
# 2. source token file (directory to copy tokens from) (GLIDEIN_CONDOR_TOKEN_ORIG)
# 3. destination proxy file (X509_USER_PROXY)
# 4. destination token file (to get destination token directory)  (GLIDEIN_CONDOR_TOKEN)
# Return: 0 if at least one credential was refreshed
#         1 otherwise
# Now passed as parameter. Was using X509_USER_PROXY_ORIG X509_USER_PROXY GLIDEIN_CONDOR_TOKEN_ORIG GLIDEIN_CONDOR_TOKEN
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
        #now passed as parameter
        #from_dir=$(dirname "${GLIDEIN_CONDOR_TOKEN_ORIG}")
        #to_dir=$(dirname "${GLIDEIN_CONDOR_TOKEN}")
        from_dir=$(dirname "${token_from}")
        to_dir=$(dirname "${token_to}")
        if [[ -d "${from_dir}" && -d "${to_dir}" ]]; then
            for tok in "${from_dir}"/*.idtoken; do
                [[ -e "$tok" ]] || continue  # protect against nullglob (no match)
                cp "${tok}" "${to_dir}" && refreshed="True"
            done
        else
            ERROR="Token variables defined but no directories ($([[ ! -d "${from_dir}" ]] && echo "${from_dir}")"\
            "$([[ ! -d "${to_dir}" ]] && echo "${to_dir}"))."
        fi
    fi

    # Check results
    ERROR="No proxy or token found. $ERROR"
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
# Currently env X509_USER_PROXY is set by the job manager in the evvironment befor starting the Glidein,
# on all CEs where Glideins run and proxyes are provided
# TODO: HTCSS newer version do not define X509_USER_PROXY. Add here canonical paths where to look
#       for possible proxy files (e.g. in ARC CE)
# No more in /tmp/x509up_u`id -u`, other processes form the same user could share /tmp
# $1 - optional certificate file name
# Out: proxy file name to use if returning 0
#      error message if returning 1
get_x509_proxy() {
    local cert_fname=${1:-"$X509_USER_PROXY"}
    if [[ -z "$cert_fname" || ! -e "$cert_fname" ]]; then
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
                return 1
            fi
        fi
    fi
    # Check time left
    if [[ "$l" -lt 60 ]]; then
        echo "Proxy not valid in 1 minute, only $l seconds left! Not enough valid time."
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
# - CE collector tokens: ce_*.idtoken in the start directory GLIDEIN_START_DIR_ORIG (0 to many files)
# 1. from dir: directory to copy from
# 2. to dir: token directory
# Globals (set): GLIDEIN_CONDOR_TOKEN GLIDEIN_CONDOR_TOKEN_ORIG
copy_idtokens() {
    local start_dir from_dir=$1 to_dir=$2
    local cred_glidein_ctr=0 cred_cecoll_ctr=0 cred_ctr=0
    start_dir=$(pwd)
    if ! cd "$from_dir"; then
        ERROR="Cannot cd to from_dir ($from_dir)"
        # did not change directory, OK to just return
        return 1
    fi
    for i in *.idtoken; do
        [[ -e "$i" ]] || continue  # protect against nullglob (no match)
        if cp "$i" "$to_dir/$i"; then
            if [[ "$i" == ce_*.idtoken ]]; then
                warn "Copied CE collector token '${i}' to '${to_dir}/'"
                (( cred_cecoll_ctr++ ))
            elif [[ "$i" == credential_*.idtoken ]]; then
                warn "Copied glidein token '${i}' to '${to_dir}/'"
                (( cred_glidein_ctr++ ))
                GLIDEIN_CONDOR_TOKEN="${to_dir}/$i"
                GLIDEIN_CONDOR_TOKEN_ORIG="${from_dir}/$i"
            else
                warn "Copied token '${i}' to '${to_dir}/'"
                (( cred_ctr++ ))
            fi
        else
            # OK to fail, CE may place tokens w/ different owner
            warn "Failed to copy token '${i}'"
        fi
    done
    (( cred_ctr += (cred_cecoll_ctr+cred_glidein_ctr) ))
    warn "Copied $cred_ctr tokens ($cred_glidein_ctr glidein, $cred_cecoll_ctr CE collector)"
    if [[ "$cred_glidein_ctr" -ne 1 ]]; then
        if [[ "$cred_glidein_ctr" -eq 0 ]]; then
            ERROR="No glidein token found!"
        else
            ERROR="There should be only one glidein token, $cred_glidein_ctr found"
        fi
        cd "$start_dir" || true
        return 1
    fi
    cd "$start_dir" || true
    return
}

# Copy non-idtoken credentials from the start directory to the credentials directory
# Credentials must match: ^credential_.*\.(scitoken|jwt|pem|rsa|txt)$
copy_credentials() {
    local start_dir from_dir=$1 to_dir=$2
    start_dir=$(pwd)
    if ! cd "$from_dir"; then
        ERROR="Cannot cd to from_dir ($from_dir)"
        # did not change directory, OK to just return
        return 1
    fi
    for cred in credential_*; do
        [[ -e "$cred" ]] || continue  # protect against nullglob (no match)
        if [[ "$cred" =~ ^credential_.*\.(scitoken|jwt|pem|rsa|txt)$ ]]; then
            if cp "$cred" "$to_dir/$cred"; then
                warn "Copied credential '${cred}' to '${to_dir}/'"
            else
                warn "Failed to copy credential '${cred}'"
            fi
        else
            warn "Skipping credential '${cred}'"
        fi
    done
    cd "$start_dir" || true
    return
}

# Retrieve trust domain
# Uses TRUST_DOMAIN, GLIDEIN_Collector and CCB_ADDRESS from glidein_config
# Return only the first Collector if more are in the list (separators:,\ \t)
# TODO: should this function return TRUST_DOMAIN or a token issuer?
#  TRUST_DOMAIN can have multiple collectors/CCBs and is OK for the startd TRUST_DOMAIN to differ
#  from the collector one (TJ).
#  issuer (iss in token) depends on the token and should match the first collector of the TRUST_DOMAIN of the server
#  (e.g. collector) the token is used to authenticate with
#  Should this not happen when TRUST_DOMAIN is set explicitly, but only from Collector?
#  Collector may have added CE collector
# TODO (Dennis): why removing after dash? what about host name including "-"?
get_trust_domain() {
    local head_node
    head_node=$(gconfig_get TRUST_DOMAIN "${glidein_config}")
    # It is OK for the startd (Glidein) to have a TRUST_DOMAIN different from the server
    [[ -z "${head_node}" ]] && head_node=$(gconfig_get GLIDEIN_Collector "${glidein_config}") || true
    [[ -z "${head_node}" ]] && head_node=$(gconfig_get CCB_ADDRESS "${glidein_config}") || true
    if [[ -z "${head_node}" ]]; then
        echo "Unable to retrieve trust domain from TRUST_DOMAIN, GLIDEIN_Collector and CCB_ADDRESS"
        return 1
    fi
    # issuer retrieval. HTCSS normally uses the first collector in TRUST_DOMAIN as token issuer
    # TODO: this may be removed/commented if there is interest in the TRUST_DOMAIN and not issuer
    head_node="${head_node#"${head_node%%[![:space:]]*}"}"  # removing leading spaces (should be none)
    local re='(.*)\$RANDOM_INTEGER\([^)]+\)(.*)'  # replace with 'RANDOM' all $RANDOM_INTEGER(n,m) occurrences
    while [[ $head_node =~ $re ]]; do head_node=${BASH_REMATCH[1]}RANDOM${BASH_REMATCH[2]}; done
    head_node="${head_node%%,*}"  # use only the first collector/CCB (glidein_collector is a comma separated list)
    head_node="${head_node%% *}"  # also space
    head_node="${head_node%%$'\t'*}"  # or tab are considered separators
    # head_node="${head_node%"${head_node##*[![:space:]]}"}"  # removing trailing spaces
    # Keeping the port and synful string (they could differ for secondary collectors, but OK)
    # Leave the dash (was removed in previous version)
    echo "${head_node}"
    return 0
}


############################################################
#
# Main
#
############################################################

_main() {
    # Aux scripts: import gconfig functions and define error_gen
    add_config_line_source=$(grep -m1 '^ADD_CONFIG_LINE_SOURCE ' "$glidein_config" | cut -d ' ' -f 2-)
    # shellcheck source=add_config_line.source
    . "$add_config_line_source"
    error_gen=$(gconfig_get ERROR_GEN_PATH "$glidein_config")
    # for debugging: add the following 2 lines and comment the ones below (until the error_gen assignment)
    # gconfig_add() { echo -n "CONFIG: "; echo "$@"; }
    # error_gen=echo

    # Path read from and stored in glidein_config should always be full absolute paths
    GLIDEIN_CONDOR_TOKEN=$(gconfig_get GLIDEIN_CONDOR_TOKEN "$glidein_config")
    GLIDEIN_START_DIR_ORIG=$(gconfig_get GLIDEIN_START_DIR_ORIG "$glidein_config")
    GLIDEIN_WORKSPACE_ORIG=$(gconfig_get GLIDEIN_WORKSPACE_ORIG "$glidein_config")

    # Script terminated w/ exit N, OK to change directory w/o worrying to restore
    [[ -n "$GLIDEIN_WORKSPACE_ORIG" ]] && cd "$GLIDEIN_WORKSPACE_ORIG" || true

    if ! gwms_credentials_dir=$(cred_setup); then
        # the output is the error message in case of error
        "$error_gen" -error "$SCRIPT_NAME" "WN_Resource" "$gwms_credentials_dir"
        exit 1
    fi

    # If it is not the first execution, but a periodic one, just refresh and exit

    if [[ -n "$GLIDEIN_PERIODIC_SCRIPT" ]]; then
        X509_USER_PROXY_ORIG=$(gconfig_get X509_USER_PROXY_ORIG "$glidein_config")
        GLIDEIN_CONDOR_TOKEN_ORIG=$(gconfig_get GLIDEIN_CONDOR_TOKEN_ORIG "$glidein_config")
        X509_USER_PROXY=$(gconfig_get X509_USER_PROXY "$glidein_config")
        GLIDEIN_CONDOR_TOKEN=$(gconfig_get GLIDEIN_CONDOR_TOKEN "$glidein_config")

        if refresh_credentials "$X509_USER_PROXY_ORIG" "$X509_USER_PROXY" "$GLIDEIN_CONDOR_TOKEN_ORIG" "$GLIDEIN_CONDOR_TOKEN"; then
            "$error_gen" -ok "$SCRIPT_NAME" "idtoken" "${GLIDEIN_CONDOR_TOKEN:-unavailable}" "proxy" "${X509_USER_PROXY:-unavailable}"
            exit 0
        fi

        "$error_gen" -error "$SCRIPT_NAME" "WN_Resource" "Periodic execution should not reach setup, probably needed glidein_config variables are not set"
        exit 1
    fi

    # On error functions return 1 and error msg on stdout or in ERROR (optional ERROR_TYPE) if w/ side effect
    # TODO: change error return string to "error_type,mgs" for better error reporting
    cred_updated=

    # IDTOKENS
    if copy_idtokens "$GLIDEIN_START_DIR_ORIG" "${gwms_credentials_dir}"/idtokens; then
        gconfig_add GLIDEIN_CONDOR_TOKEN "$GLIDEIN_CONDOR_TOKEN"
        gconfig_add GLIDEIN_CONDOR_TOKEN_ORIG "$GLIDEIN_CONDOR_TOKEN_ORIG"
        out=$(gconfig_get TRUST_DOMAIN "${glidein_config}")
        if [[ -n "$out" ]]; then
            cred_updated+=idtoken,
        else
            # Retrieve TRUST_DOMAIN from COLLECTOR_HOST and CCB if not already defined in condor_config (config attrs)
            if out=$(get_trust_domain); then
                export TRUST_DOMAIN="$out"
                gconfig_add TRUST_DOMAIN "$out"
                # TRUST_DOMAIN is already in the default condor_vars
                cred_updated+=idtoken,
            else
                warn "$out"
            fi
        fi
    else
        warn "$ERROR"
    fi
    # TODO: Initial copy. Evaluate separately credentials refresh.
    # PAYLOAD CREDENTIALS
    if copy_credentials "$GLIDEIN_START_DIR_ORIG" "${gwms_credentials_dir}"; then
        cred_updated+=credentials,
    else
        warn "$ERROR"
    fi

    # x509 - skip if there is no X509_USER_PROXY
    if ! X509_USER_PROXY=$(get_x509_proxy); then
        warn "Skipping x509, X509_USER_PROXY not available: $X509_USER_PROXY"
        unset X509_USER_PROXY
    else
        if out=$(get_x509_certs_dir); then
            export X509_CERT_DIR="$out"
            if out=$(check_x509_tools); then
                [[ -n "$out" ]] && warn "$out"
                if out=$(safe_copy_and_protect "$X509_USER_PROXY" "$gwms_credentials_dir/myproxy"); then
                    # Copy successful, set env variables
                    export X509_USER_PROXY_ORIG="$X509_USER_PROXY"
                    export X509_USER_PROXY="$out"
                    if out=$(get_x509_expiration "$X509_USER_PROXY"); then
                        # Copy successful and proxy valid, set values in glidein_config
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
                warn "$out"
            fi
        else
            warn "$out"
        fi
    fi

    if [[ -z "$cred_updated" ]]; then
        warn "${SCRIPT_NAME}: No valid credential (x509 proxy or idtoken) found"
        "$error_gen" -error "$SCRIPT_NAME" "WN_Resource" "No valid credential (x509 proxy or idtoken) found"
        exit 1
    fi

    warn "${SCRIPT_NAME}: Credentials copied, verified, amd added to glidein_config: ${cred_updated%,}"
    "$error_gen" -ok "$SCRIPT_NAME" "idtoken" "${GLIDEIN_CONDOR_TOKEN:-unavailable}" "trust_domain" "${TRUST_DOMAIN:-unavailable}" "proxy" "${X509_USER_PROXY:-unavailable}" "cert_dir" "${X509_CERT_DIR:-unavailable}"
    exit 0
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    _main "$@"
fi
