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

# check that x509 certificates exist and set the env variable if needed
function check_x509_certs {
    if [ -e "$X509_CERT_DIR" ]; then
	  export X509_CERT_DIR
    elif [ -e "$HOME/.globus/certificates/" ]; then
	  export X509_CERT_DIR=$HOME/.globus/certificates/
    elif [ -e "/etc/grid-security/certificates/" ]; then
	  export X509_CERT_DIR=/etc/grid-security/certificates/
    else
        STR="Could not find grid-certificates!\n"
        STR+="Looked in:\n"
        STR+="	\$X509_CERT_DIR ($X509_CERT_DIR)\n"
        STR+="	\$HOME/.globus/certificates/ ($HOME/.globus/certificates/)\n"
        STR+="	/etc/grid-security/certificates/"
	STR1=`echo -e "$STR"`
        "$error_gen" -error "setup_x509.sh" "WN_Resource" "$STR1" "directory" "$X509_CERT_DIR"
        exit 1
    fi
    return 0
}

function check_x509_tools {
    # verify grid-proxy-info exists
    command -v grid-proxy-info >& /dev/null
    if [ $? -eq 1 ]; then
	STR="grid-proxy-init command not found in path!"
	"$error_gen" -error "setup_x509.sh" "WN_Resource" "$STR" "command" "grid-proxy-init"
	exit 1
    fi
    # verify voms-proxy-info exists
    command -v voms-proxy-info >& /dev/null
    if [ $? -eq 1 ]; then
	STR="voms-proxy-init command not found in path!"
	"$error_gen" -error "setup_x509.sh" "WN_Resource" "$STR" "command" "voms-proxy-init"
	exit 1
    fi

    return 0
}

function copy_x509_proxy {
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
    mkdir "$local_proxy_dir"
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

    export X509_USER_PROXY="$local_proxy_dir/myproxy"
    # protect from strange sites
    chmod a-wx "$X509_USER_PROXY"
    chmod go-r "$X509_USER_PROXY"

    umask $old_umask
    if [ $? -ne 0 ]; then
        STR="Failed to set back umask!"
        "$error_gen" -error "setup_x509.sh" "Corruption" "$STR" "file" "$X509_USER_PROXY" "command" "umask"
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
check_x509_certs
check_x509_tools
copy_x509_proxy

add_config_line X509_CERT_DIR   "$X509_CERT_DIR"
add_config_line X509_USER_PROXY "$X509_USER_PROXY"

"$error_gen" -ok "setup_x509.sh" "proxy" "$X509_USER_PROXY" "cert_dir" "$X509_CERT_DIR"

exit 0
