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
# To make chhanges to this file check first setup_x509.sh that defines X509_CERT_DIR and X509_USER_PROXY
# and has the same get_x509_expiration function

glidein_config="$1"

# import add_config_line function
add_config_line_source=`grep '^ADD_CONFIG_LINE_SOURCE ' $glidein_config | awk '{print $2}'`
source $add_config_line_source

error_gen=`grep '^ERROR_GEN_PATH ' $glidein_config | awk '{print $2}'`
X509_CERT_DIR=`grep '^X509_CERT_DIR ' $glidein_config | awk '{print $2}'`
export X509_CERT_DIR
X509_USER_PROXY=`grep '^X509_USER_PROXY ' $glidein_config | awk '{print $2}'`
export X509_USER_PROXY


function openssl_get_x509_timeleft {
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
function get_x509_expiration {
    RETVAL=0
    now=`date +%s`
    if [ $? -ne 0 ]; then
        STR="Date not found!"
        "$error_gen" -error "check_proxy.sh" "WN_Resource" "$STR" "command" "date"
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
	if [ $l -lt 43200 ]; then 
	    STR="Proxy not valid in in 12 hours, only $l seconds left!\n"
	    STR+="Proxy shorter than 12 hours are not allowed."
	    STR1=`echo -e "$STR"`
	    "$error_gen" -error "check_proxy.sh" "VO_Proxy" "$STR1" "proxy" "$X509_USER_PROXY"
	    exit 1
        fi
        RETVAL="$(/usr/bin/expr $now + $l)"
    else
        #echo "Could not obtain -timeleft" 1>&2
        STR="Could not obtain -timeleft from grid-proxy-info/voms-proxy-info/openssl"
        "$error_gen" -error "check_proxy.sh" "WN_Resource" "$STR" "command" "$CMD"
        exit 1
    fi

    return 0
}

############################################################
#
# Main
#
############################################################

# Assume all functions exit on error
# get X509 expiration time and validate the lifetime
# no need to store the result... was already done
# but do report it in the metrics
# no sub-shell, to allow to exit (all script) on error
get_x509_expiration
X509_EXPIRE="$RETVAL"

"$error_gen" -ok "check_proxy.sh" "proxy" "$X509_USER_PROXY" "proxy_expire" "`date --date=@$X509_EXPIRE +%Y-%m-%dT%H:%M:%S%:z`" "cert_dir" "$X509_CERT_DIR"

exit 0
