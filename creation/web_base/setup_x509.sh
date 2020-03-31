#
# Project:
#   glideinWMS
#
# File Version:
#
# Description;
#   This is an include file for glidein_startup.sh
#   It has the routins to setup the X509 environment
#
# If you make change to this file check also check_proxy.sh that has the same get_x509_expiration

glidein_config="$1"


# for debugging: add these 2 lines and comment the ones below (until the error_gen assignment)
#function add_config_line { echo -n "CONFIG: "; echo "$@"; }
#error_gen="echo"

# import add_config_line function
add_config_line_source="`grep '^ADD_CONFIG_LINE_SOURCE ' "$glidein_config" | cut -d ' ' -f 2-`"
source "$add_config_line_source"

error_gen="`grep '^ERROR_GEN_PATH ' "$glidein_config" | cut -d ' ' -f 2-`"

# check that x509 certificates exist and set the env variable if needed
check_x509_certs() {
    if [ -e "$X509_CERT_DIR" ]; then
	  export X509_CERT_DIR
    elif [ -e "$HOME/.globus/certificates/" ]; then
	  export X509_CERT_DIR="$HOME/.globus/certificates/"
    elif [ -e "/etc/grid-security/certificates/" ]; then
	  export X509_CERT_DIR=/etc/grid-security/certificates/
    elif [ -e "$GLOBUS_LOCATION/share/certificates/" ]; then
	  export X509_CERT_DIR="$GLOBUS_LOCATION/share/certificates/"
    elif [ -e "$X509_CADIR" ]; then
	  export X509_CERT_DIR="$X509_CADIR"
    else
        STR="Could not find CA certificates!\n"
        STR+="Looked in:\n"
        STR+="	\$X509_CERT_DIR ($X509_CERT_DIR)\n"
        STR+="	\$HOME/.globus/certificates/ ($HOME/.globus/certificates/)\n"
        STR+="	/etc/grid-security/certificates/"
        STR+="	\$GLOBUS_LOCATION/share/certificates/ ($GLOBUS_LOCATION/share/certificates/)\n"
        STR+="	\$X509_CADIR ($X509_CADIR)\n"
	STR1=`echo -e "$STR"`
        echo "WARNING - $STR1" >&2
        #"$error_gen" -error "setup_x509.sh" "WN_Resource" "$STR1" "directory" "$X509_CERT_DIR"
        #exit 1
    fi
    return 0
}


get_x509_proxy() {
    # Look for the certificates in $1, $X509_USER_PROXY, (not /tmp/x509up_u`id -u`)
    # $1 - optional certificate file name
    # This function is also setting/changing the value of X509_USER_PROXY
    cert_fname=$1
    if [ -z "$cert_fname" ]; then
        if [ -n "$X509_USER_PROXY" ]; then
            cert_fname="$X509_USER_PROXY"
        # Skipping proxy in /tmp because it may be confusing
        #else
        #    cert_fname="/tmp/x509up_u`id -u`"
        fi
    else
        X509_USER_PROXY="$cert_fname"
    fi
    if [ ! -e "$cert_fname" ]; then
        echo "Proxy certificate '$cert_fname' does not exist." >&2
        #exit 1
    fi
    if [ ! -r "$cert_fname" ]; then
        echo "Unable to read '$cert_fname' (user: `id -u`/$USER)." >&2
        #exit 1
    fi
    echo "$cert_fname"

}


check_x509_tools() {
    # Failing only if all commands are missing (grid-proxy-info, voms=proxy-info, openssl)
    # If only some are missing only prints warning on stderr
    # All functions have to be modified to work with any of the 3 commands
    missing_commands=0
    # verify grid-proxy-info exists
    command -v grid-proxy-info >& /dev/null
    if [ $? -eq 1 ]; then
	STR="grid-proxy-init command not found in path!"
	echo $STR >&2
        #"$error_gen" -error "setup_x509.sh" "WN_Resource" "$STR" "command" "grid-proxy-init"
	let missing_commands+=1
    fi
    # verify voms-proxy-info exists
    command -v voms-proxy-info >& /dev/null
    if [ $? -eq 1 ]; then
	STR="voms-proxy-init command not found in path!"
	echo $STR >&2
	#"$error_gen" -error "setup_x509.sh" "WN_Resource" "$STR" "command" "voms-proxy-init"
	let missing_commands+=1
    fi
    # verify openssl  exists
    command -v openssl >& /dev/null
    if [ $? -eq 1 ]; then
	STR="openssl command not found in path!"
	echo $STR >&2
	#"$error_gen" -error "setup_x509.sh" "WN_Resource" "$STR" "command" "voms-proxy-init"
	let missing_commands+=1
    fi
    if [ $missing_commands -ne 0 ]; then
        if [ $missing_commands -ge 3 ]; then
	    STR="No x509 command (grid-proxy-init, voms-proxy-init, openssl) found in path!"
            "$error_gen" -error "setup_x509.sh" "WN_Resource" "$STR"
            exit 1
        else
            STR="Not all x509 commands found in path ($missing_commands missing)!"
	    echo $STR >&2
        fi
    fi

    return 0
}


copy_x509_proxy() {
    if [ -a "$X509_USER_PROXY" ]; then
	export X509_USER_PROXY
    else
        STR="Could not find user proxy!"
        STR+="Looked in X509_USER_PROXY='$X509_USER_PROXY'\n"
        STR+=`ls -la "$X509_USER_PROXY"`
	STR1=`echo -e "$STR"`
        "$error_gen" -error "setup_x509.sh" "Corruption" "$STR1" "proxy" "$X509_USER_PROXY"
        exit 1
    fi

    # Make the proxy local, so that it does not get
    # "accidentaly" deleted by some proxy management tool
    # We don't need renewals
    old_umask=`umask`

    if [ $? -ne 0 ]; then
        STR="Failed in reading old umask!"
        "$error_gen" -error "setup_x509.sh" "Corruption" "$STR" "file" "$X509_USER_PROXY"
        exit 1
    fi

    # make sure nobody else can read my proxy
    umask 0077
    if [ $? -ne 0 ]; then
        STR="Failed to set umask 0077!"
        "$error_gen" -error "setup_x509.sh" "Corruption" "$STR" "file" "$X509_USER_PROXY" "command" "umask"
        exit 1
    fi

    local_proxy_dir=`pwd`/ticket
    mkdir -p "$local_proxy_dir"
    if [ $? -ne 0 ]; then
        STR="Failed in creating proxy dir $local_proxy_dir."
        "$error_gen" -error "setup_x509.sh" "Corruption" "$STR" "directory" "$local_proxy_dir"
        exit 1
    fi

    cp "$X509_USER_PROXY" "$local_proxy_dir/myproxy"
    if [ $? -ne 0 ]; then
        STR="Failed in copying proxy $X509_USER_PROXY."
        "$error_gen" -error "setup_x509.sh" "Corruption" "$STR" "file" "$X509_USER_PROXY"
        exit 1
    fi
    x_dir=$(dirname "$X509_USER_PROXY")
    echo "debug x_dir=$x_dir"

    export X509_USER_PROXY_ORIG="$X509_USER_PROXY"
    export X509_USER_PROXY="$local_proxy_dir/myproxy"
    # protect from strange sites (only the owner should only read) was: a-wx, go-r
    chmod 0400 "$X509_USER_PROXY"

    umask $old_umask
    if [ $? -ne 0 ]; then
        STR="Failed to set back umask!"
        "$error_gen" -error "setup_x509.sh" "Corruption" "$STR" "file" "$X509_USER_PROXY" "command" "umask"
        exit 1
    fi
    for TK in "$x_dir/*_token" ; do
    	echo "debug cp $TK $local_proxy_dir"
      	cp $TK $local_proxy_dir
        tk_name=`basename $TK`
        export GLIDEIN_CONDOR_TOKEN="$local_proxy_dir/$tk_name"
    done

    return 0
}


openssl_get_x509_timeleft() {
    # $1 cert pathname
    if [ ! -r "$1" ]; then
        return 1
    fi
    cert_pathname=$1
    output=$(openssl x509 -noout -subject -dates -in $cert_pathname 2>/dev/null)
    [ $? -eq 0 ] || return 1

    start_date=$(echo $output | sed 's/.*notBefore=\(.*\).*not.*/\1/g')
    end_date=$(echo $output | sed 's/.*notAfter=\(.*\)$/\1/g')

    # For OS X: date  -j -f "%b %d %T %Y %Z" "$start_date" +"%s"
    start_epoch=$(date +%s -d "$start_date")
    end_epoch=$(date +%s -d "$end_date")

    if [ "x$2" = "x" ]; then
        epoch_now=$(date +%s)
    else
        epoch_now=$2
    fi

    if [ "$start_epoch" -gt "$epoch_now" ]; then
        echo "Certificate for $1 is not yet valid" >&2
        seconds_to_expire=0
    else
        seconds_to_expire=$(($end_epoch - $epoch_now))
    fi

    echo $seconds_to_expire
}



# returns the expiration time of the proxy
# return value in RETVAL
get_x509_expiration() {
    RETVAL=0
    now=`date +%s`
    if [ $? -ne 0 ]; then
        STR="Date not found!"
        "$error_gen" -error "setup_x509.sh" "WN_Resource" "$STR" "command" "date"
        exit 1 # just to be sure
    fi
    CMD="grid-proxy-info"
    l=$(grid-proxy-info -timeleft 2>/dev/null)
    ret=$?
    if [ $ret -ne 0 ]; then
        CMD="voms-proxy-info"
        # using  -dont-verify-ac to avoid exit code 1 if AC signatures are not present
        l=$(voms-proxy-info -dont-verify-ac -timeleft 2>/dev/null)
        ret=$?
        if [ $ret -ne 0 ]; then
            CMD="openssl"
            l=$(openssl_get_x509_timeleft "$X509_USER_PROXY" $now)
            ret=$?
        fi
    fi

    if [ $ret -eq 0 ]; then
	if [ $l -lt 60 ]; then
	    STR="Proxy not valid in 1 minute, only $l seconds left!\n"
	    STR+="Not enough time to do anything with it."
	    STR1=`echo -e "$STR"`
	    "$error_gen" -error "setup_x509.sh" "VO_Proxy" "$STR1" "proxy" "$X509_USER_PROXY"
	    exit 1
        fi
        RETVAL="$(/usr/bin/expr $now + $l)"
    else
        #echo "Could not obtain -timeleft" 1>&2
        STR="Could not obtain -timeleft from grid-proxy-info/voms-proxy-info/openssl"
        "$error_gen" -error "setup_x509.sh" "WN_Resource" "$STR" "command" "$CMD"
        exit 1
    fi

    return 0
}


refresh_proxy() {
    X509_USER_PROXY_ORIG="`grep '^X509_USER_PROXY_ORIG ' "$glidein_config" | cut -d ' ' -f 2-`"

    # If X509_USER_PROXY_ORIG is set it means the script has run at least once
    if [ -n "${X509_USER_PROXY_ORIG}" ]; then
        X509_USER_PROXY="`grep '^X509_USER_PROXY ' "$glidein_config" | cut -d ' ' -f 2-`"

        chmod 600 $X509_USER_PROXY
        cp $X509_USER_PROXY_ORIG $X509_USER_PROXY
        chmod 400 $X509_USER_PROXY

        return 0
    fi

    return 1
}


############################################################
#
# Main
#
############################################################

# If it is not the first execution, but a periodic one, just refresh and exit
refresh_proxy && exit 0

# Assume all functions exit on error
check_x509_certs
check_x509_tools
copy_x509_proxy
# no sub-shell, to allow to exit (all script) on error
get_x509_expiration
X509_EXPIRE="$RETVAL"

add_config_line X509_CERT_DIR   "$X509_CERT_DIR"
add_config_line X509_USER_PROXY "$X509_USER_PROXY"
add_config_line X509_USER_PROXY_ORIG "$X509_USER_PROXY_ORIG"
add_config_line X509_EXPIRE  "$X509_EXPIRE"
test -e "$GLIDEIN_CONDOR_TOKEN" && add_config_line GLIDEIN_CONDOR_TOKEN "$GLIDEIN_CONDOR_TOKEN"

"$error_gen" -ok "setup_x509.sh" "proxy" "$X509_USER_PROXY" "cert_dir" "$X509_CERT_DIR"

exit 0

