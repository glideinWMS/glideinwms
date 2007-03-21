#
# This is an include file for glidein_startup.sh
# It has the routins to setup the X509 environment
#

# check that x509 certificates exist and set the env variable if needed
function check_x509_certs {
    if [ -e "$X509_CERT_DIR" ]; then
	export X509_CERT_DIR
    elif [ -e "/etc/grid-security/certificates/" ]; then
	export X509_CERT_DIR=/etc/grid-security/certificates/
    else
	echo "Could not find grid-certificates!" 1>&2
	echo "Looked in:" 1>&2
	echo ' $X509_CERT_DIR' 1>&2
 	echo ' /etc/grid-security/certificates/' 1>&2
	exit 1
    fi
    return 0
}

function check_x509_proxy {
    if [ -a "$X509_USER_PROXY" ]; then
	export X509_USER_PROXY
    else
	echo "Could not find user proxy!" 1>&2
	exit 1
    fi

    # Make the proxy local, so that it does not get
    # "accidentaly" deleted by some proxy management tool
    # We don't need renewals
    old_umask=`umask`

    if [ $? -ne 0 ]; then
	echo "Failed in reading old umask!" 1>&2
	exit 1
    fi

    # make sure nobody else can read my proxy
    umask 0077
    if [ $? -ne 0 ]; then
	echo "Failed to set umask 0077!" 1>&2
	exit 1
    fi    

    local_proxy_dir=`pwd`/ticket
    mkdir "$local_proxy_dir"
    if [ $? -ne 0 ]; then
	echo "Failed in creating proxy dir $local_proxy_dir." 1>&2
	exit 1
    fi

    cp "$X509_USER_PROXY" "$local_proxy_dir/myproxy"
    if [ $? -ne 0 ]; then
	echo "Failed in copying proxy $X509_USER_PROXY." 1>&2
	exit 1
    fi

    export X509_USER_PROXY="$local_proxy_dir/myproxy"
    # protect from strange sites
    chmod a-wx "$X509_USER_PROXY"
    chmod go-r "$X509_USER_PROXY"

    umask $old_umask
    if [ $? -ne 0 ]; then
	echo "Failed to set back umask!" 1>&2
	exit 1
    fi    

    grid-proxy-info -exists -valid 12:0
    if [ $? -ne 0 ]; then
	voms-proxy-info -exists -valid 12:0
	if [ $? -ne 0 ]; then
	    echo "Proxy not valid in 12 hours!" 1>&2
	    exit 1
	fi
    fi
    
    return 0
}

function create_gridmapfile {
    id=`grid-proxy-info -identity`
    if [ $? -ne 0 ]; then
	id=`voms-proxy-info -identity`
	if [ $? -ne 0 ]; then
	    echo "Cannot get user identity!" 1>&2
	    echo "Tried both grid-proxy-info and voms-proxy-info." 1>&2
	    exit 1
	fi
    fi

    idp=`echo $id |awk '{split($0,a,"/CN=proxy"); print a[1]}'`
    if [ $? -ne 0 ]; then
	echo "Cannot remove proxy part from user identity!" 1>&2
	exit 1
    fi

    touch grid-mapfile
    echo "\"$idp\"" condor >> grid-mapfile
    if [ $? -ne 0 ]; then
	echo "Cannot add user identity to grid-mapfile!" 1>&2
	exit 1
    fi

    return 0
}

# returns the expiration time of the proxy
function get_x509_expiration {
    now=`date +%s`
    if [ $? -ne 0 ]; then
        echo "Date not found!" 1>&2
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
	echo "Could not obtain -timeleft" 1>&2
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
config_file=$1

check_x509_certs
check_x509_proxy
create_gridmapfile

# get X509 expiration time and store it into the config file
X509_EXPIRE=`get_x509_expiration`
cat >> "$config_file" <<EOF
X509_EXPIRE       $X509_EXPIRE
X509_CERT_DIR     $X509_CERT_DIR
X509_USER_PROXY   $X509_USER_PROXY
EOF

exit 0
