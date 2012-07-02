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
        "$error_gen" -error "setup_x509.sh" "WN_Resource" "$STR" "directory" "$X509_CERT_DIR"
        exit 1
    fi
    return 0
}

function check_x509_proxy {
    if [ -a "$X509_USER_PROXY" ]; then
        export X509_USER_PROXY
    else
        STR="Could not find user proxy!"
        STR+="Looked in X509_USER_PROXY='$X509_USER_PROXY'\n"
        STR+=`ls -la "$X509_USER_PROXY"`
        "$error_gen" -error "setup_x509.sh" "Corruption" "$STR" "proxy" "$X509_USER_PROXY"
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

    grid-proxy-info -exists -valid 12:0
    if [ $? -ne 0 ]; then
        voms-proxy-info -exists -valid 12:0
        if [ $? -ne 0 ]; then
            STR="Proxy not valid in 12 hours!\n"
            STR+="Proxy shorter than 12 hours are not allowed\n"
            STR+="grid-proxy-info:\n"
            STR+=`grid-proxy-info`
            STR+="\nvoms-proxy-info:\n"
            STR+=`voms-proxy-info -all`
            "$error_gen" -error "setup_x509.sh" "VO_Proxy" "$STR" "proxy" "$X509_USER_PROXY"
            exit 1
        fi
    fi
    
    return 0
}


# returns the expiration time of the proxy
function get_x509_expiration {
    now=`date +%s`
    if [ $? -ne 0 ]; then
        STR="Date not found!"
        "$error_gen" -error "setup_x509.sh" "WN_Resource" "$STR" "command" "date"
        exit 1 # just to be sure
    fi

    l=`grid-proxy-info -timeleft`
    ret=$?
    if [ $ret -ne 0 ]; then
        l=`voms-proxy-info -timeleft`
        ret=$?
    fi

    if [ $ret -eq 0 ]; then
        echo `/usr/bin/expr $now + $l`
    else
        #echo "Could not obtain -timeleft" 1>&2
        STR="Could not obtain -timeleft"
        "$error_gen" -error "setup_x509.sh" "WN_Resource" "$STR" "command" "grid-proxy-info"
        exit 1
    fi

    return 0
}

############################################################
#
# Main
#
############################################################

error_gen=`grep '^ERROR_GEN_PATH ' $glidein_config | awk '{print $2}'`

# Assume all functions exit on error
config_file="$1"

check_x509_certs
check_x509_proxy

# get X509 expiration time and store it into the config file
X509_EXPIRE=`get_x509_expiration`
cat >> "$config_file" <<EOF
######## setup_x509 ###########
X509_EXPIRE              $X509_EXPIRE
X509_CERT_DIR            $X509_CERT_DIR
X509_USER_PROXY          $X509_USER_PROXY
###############################
EOF

"$error_gen" -ok "setup_x509.sh" "proxy" "$X509_USER_PROXY"

exit 0
