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

glidein_config="$1"

# import add_config_line function
add_config_line_source=`grep '^ADD_CONFIG_LINE_SOURCE ' $glidein_config | awk '{print $2}'`
source $add_config_line_source

error_gen=`grep '^ERROR_GEN_PATH ' $glidein_config | awk '{print $2}'`
X509_CERT_DIR=`grep '^X509_CERT_DIR ' $glidein_config | awk '{print $2}'`
export X509_CERT_DIR
X509_USER_PROXY=`grep '^X509_USER_PROXY ' $glidein_config | awk '{print $2}'`
export X509_USER_PROXY

# returns the expiration time of the proxy
function get_x509_expiration {
    now=`date +%s`
    if [ $? -ne 0 ]; then
        STR="Date not found!"
        "$error_gen" -error "check_proxy.sh" "WN_Resource" "$STR" "command" "date"
        exit 1 # just to be sure
    fi

    l=`grid-proxy-info -timeleft`
    ret=$?
    if [ $ret -ne 0 ]; then
	l=`voms-proxy-info -timeleft`
	ret=$?
    fi

    if [ $ret -eq 0 ]; then
	if [ $l -lt 43200 ]; then 
	    STR="Proxy not valid in 12 hours, only $l seconds left!\n"
	    STR+="Proxy shorter than 12 hours are not allowed"
	    STR1=`echo -e "$STR"`
	    "$error_gen" -error "check_proxy.sh" "VO_Proxy" "$STR1" "proxy" "$X509_USER_PROXY"
	    exit 1
	fi
	echo `/usr/bin/expr $now + $l`
    else
        #echo "Could not obtain -timeleft" 1>&2
        STR="Could not obtain -timeleft"
        "$error_gen" -error "check_proy.sh" "WN_Resource" "$STR" "command" "grid-proxy-info"
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
# get X509 expiration time and store it into the config file
X509_EXPIRE=`get_x509_expiration`

add_config_line X509_EXPIRE  "$X509_EXPIRE"

"$error_gen" -ok "check_proxy.sh" "proxy" "$X509_USER_PROXY" "proxy_expire" "`date --date=@$X509_EXPIRE +%Y-%m-%dT%H:%M:%S%:z`" "cert_dir" "$X509_CERT_DIR"

exit 0
