# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

#   This is a custom script for glidein_startup.sh
#   It has the routines to create grid and condor mapfiles
#
# Publishing to glidein_config:
# X509_SKIP_HOST_CHECK_DNS_REGEX, X509_CONDORMAP, X509_GRIDMAP_DNS, X509_GRIDMAP_TRUSTED_DNS

glidein_config="$1"  # Must define $glidein_config to use gconfig_add()

# Aux scripts: import gconfig functions and define error_gen
add_config_line_source=$(grep -m1 '^ADD_CONFIG_LINE_SOURCE ' "$glidein_config" | cut -d ' ' -f 2-)
# shellcheck source=add_config_line.source
. "$add_config_line_source"
error_gen=$(gconfig_get ERROR_GEN_PATH "$glidein_config")
# for debugging: add the following 2 lines and comment the ones below (until the error_gen assignment)
# gconfig_add() { echo -n "CONFIG: "; echo "$@"; }
# error_gen=echo

GLIDEIN_CONDOR_TOKEN=$(gconfig_get GLIDEIN_CONDOR_TOKEN "$glidein_config")
using_tokens() {
    [[ -n "$GLIDEIN_CONDOR_TOKEN" ]]
}


#if an IDTOKEN is available, continue.  Else exit
exit_if_no_token(){
    if [ !  -e "$GLIDEIN_CONDOR_TOKEN" ]; then
        exit $1
    fi
    echo  "create_mapfile.sh" "found" "$GLIDEIN_CONDOR_TOKEN" "..so..continuing"
}

get_proxy_fname() {
    local cert_fname="$1"
    if [ -z "$cert_fname" ]; then
        if [ -n "$X509_USER_PROXY" ]; then
            cert_fname="$X509_USER_PROXY"
        # Ignoring the file in /tmp, it may be confusing
        #else
        #    cert_fname="/tmp/x509up_u`id -u`"
        fi
    fi
    # should it control if the file exists?
    echo "Using proxy file $cert_fname (`[ -e "$cert_fname" ] && echo "OK" || echo "No file"`)" 1>&2
    echo "$cert_fname"
}

# add the current DN to the list of allowed DNs
# create a new file if none exist
# Global: proxy_cmd (used in error message)
create_gridmapfile() {
    local id
    proxy_cmd="grid-proxy-info"
    if ! id=$(grid-proxy-info -identity 2>/dev/null); then
        proxy_cmd="voms-proxy-info"
        if ! id=$(voms-proxy-info -identity 2>/dev/null); then
            # "openssl x509 -noout -issuer .." works for proxys but may be a CA for certificates
            # did not find something to extract the identity, filtering manually
            cert_fname=$(get_proxy_fname)
            if [[ -z "$cert_fname" ]]; then
                ERROR="Cannot find the x509 proxy."
                return 1
            fi
            proxy_cmd="openssl/$cert_fname"
            if ! id_subject=$(openssl x509 -noout -subject -in "$cert_fname" | cut -c10-) || [[ -z "$id_subject" ]]; then
                # if [ $? -ne 0 -o "x$id_subject" = "x" ]; then
                STR="Cannot get user identity.\n"
                STR+="Tried all grid-proxy-info, voms-proxy-info and openssl x509."
	            ERROR=$(echo -e "$STR")
                return 1
            fi
            # can I use bash variables? id="${id_subject%%/CN=proxy*}"
            # proxy part removed below anyway
            id="$id_subject"
        fi
    fi
    echo "ID ($id) retrieved using $proxy_cmd" 1>&2

    if !  idp=$(echo $id |awk '{split($0,a,"/CN=proxy"); print a[1]}'); then
        ERROR="Cannot remove proxy part from user identity."
        # probably could be classified better... but short on ideas
        return 1
    fi

    touch "$X509_GRIDMAP"
    if [ -e "$GLIDEIN_WORK_DIR/$EXPECTED_GRIDMAP_FNAME" ]; then
        lines=$(wc -l "$GLIDEIN_WORK_DIR/$EXPECTED_GRIDMAP_FNAME" |awk '{print $1}')
        cat "$GLIDEIN_WORK_DIR/$EXPECTED_GRIDMAP_FNAME" >> "$X509_GRIDMAP"
        echo "Using factory main grid-mapfile ($lines)" 1>&2
    fi
    if [ -e "$GLIDEIN_ENTRY_WORK_DIR/$EXPECTED_GRIDMAP_FNAME" ]; then
        lines=$(wc -l "$GLIDEIN_ENTRY_WORK_DIR/$EXPECTED_GRIDMAP_FNAME" |awk '{print $1}')
        cat "$GLIDEIN_ENTRY_WORK_DIR/$EXPECTED_GRIDMAP_FNAME" >> "$X509_GRIDMAP"
        echo "Using factory entry grid-mapfile ($lines)" 1>&2
    fi
    if [ -e "$GLIDECLIENT_WORK_DIR/$EXPECTED_GRIDMAP_FNAME" ]; then
        lines=$(wc -l "$GLIDECLIENT_WORK_DIR/$EXPECTED_GRIDMAP_FNAME" |awk '{print $1}')
        cat "$GLIDECLIENT_WORK_DIR/$EXPECTED_GRIDMAP_FNAME" >> "$X509_GRIDMAP"
        echo "Using client main grid-mapfile ($lines)" 1>&2
    fi
    if [ -e "$GLIDECLIENT_GROUP_WORK_DIR/$EXPECTED_GRIDMAP_FNAME" ]; then
        lines=$(wc -l "$GLIDECLIENT_GROUP_WORK_DIR/$EXPECTED_GRIDMAP_FNAME" |awk '{print $1}')
        cat "$GLIDECLIENT_GROUP_WORK_DIR/$EXPECTED_GRIDMAP_FNAME" >> "$X509_GRIDMAP"
        echo "Using client group grid-mapfile ($lines)" 1>&2
    fi
    echo "\"$idp\"" condor >> "$X509_GRIDMAP"
    if [ $? -ne 0 ]; then
        ERROR="Cannot add user identity to $X509_GRIDMAP!"
        return 1
    fi
    return 0
}

extract_gridmap_DNs() {
    awk -F '"' '/CN/{dn=$2;if (dns=="") {dns=dn;} else {dns=dns "," dn}}END{print dns}' "$X509_GRIDMAP"
}

# create a condor_mapfile starting from a grid-mapfile
create_condormapfile() {
    local id line
    id=$(id -un)

    # make sure there is nothing in place already
    rm -f "$X509_CONDORMAP"
    touch "$X509_CONDORMAP" && chmod go-wx "$X509_CONDORMAP" || { ERROR="Cannot create HTCSS map file '$X509_CONDORMAP'"; return 1; }
    # copy with formatting the glide-mapfile into condor_mapfile
    # filter out lines starting with the comment (#)
    #grep -v "^[ ]*#"  "$X509_GRIDMAP" | while read file
    while read line
    do
        if [[ -n "$line" ]]; then  # ignore empty lines
            # split between DN and UID
            # keep the quotes in DN to not loose trailing spaces
            udn=$(echo "$line" |awk '{print substr($0,1,length($0)-length($NF)-1)}')
            uid=$(echo "$line" |awk '{print $NF}')

            # encode for regexp
            edn_wq=$(echo "$udn" | sed 's/[^[:alnum:]]/\\\&/g')
            # remove backslashes from the first and last quote
            # and add begin and end matching chars
            edn=$(echo "$edn_wq" | awk '{print "\"^" substr(substr($0,3,length($0)-2),1,length($0)-4) "$\"" }')

            echo "GSI $edn $uid" >> "$X509_CONDORMAP"
            if [ "$X509_SKIP_HOST_CHECK_DNS_REGEX" = "" ]; then
                X509_SKIP_HOST_CHECK_DNS_REGEX="$edn_wq"
            else
                X509_SKIP_HOST_CHECK_DNS_REGEX=$X509_SKIP_HOST_CHECK_DNS_REGEX\|$edn_wq
            fi
        fi
    done < <(grep -v "^[ ]*#"  "$X509_GRIDMAP")

    # add local user
    # and deny any other type of traffic
    cat << EOF >> "$X509_CONDORMAP"
FS $id localuser
GSI (.*) anonymous
FS (.*) anonymous
EOF

    X509_SKIP_HOST_CHECK_DNS_REGEX=$(echo $X509_SKIP_HOST_CHECK_DNS_REGEX | sed 's/\\\"//g')
    X509_SKIP_HOST_CHECK_DNS_REGEX="^($(echo \"$X509_SKIP_HOST_CHECK_DNS_REGEX\"))$"
    gconfig_add X509_SKIP_HOST_CHECK_DNS_REGEX "$X509_SKIP_HOST_CHECK_DNS_REGEX"

    echo "--- condor_mapfile ---" 1>&2
    cat "$X509_CONDORMAP" 1>&2
    echo "--- ============== ---" 1>&2
    return 0
}

############################################################
#
# Main
#
############################################################

# Assume all functions return 1 on error
EXPECTED_GRIDMAP_FNAME="grid-mapfile"

X509_GRIDMAP="$PWD/$EXPECTED_GRIDMAP_FNAME"
X509_CONDORMAP="$PWD/condor_mapfile"

GLIDEIN_WORK_DIR=$(gconfig_get GLIDEIN_WORK_DIR "$glidein_config")
GLIDEIN_ENTRY_WORK_DIR=$(gconfig_get GLIDEIN_ENTRY_WORK_DIR "$glidein_config")
GLIDECLIENT_WORK_DIR=$(gconfig_get GLIDECLIENT_WORK_DIR "$glidein_config")
GLIDECLIENT_GROUP_WORK_DIR=$(gconfig_get GLIDECLIENT_GROUP_WORK_DIR "$glidein_config")

X509_CERT_DIR=$(gconfig_get X509_CERT_DIR "$glidein_config")
X509_USER_PROXY=$(gconfig_get X509_USER_PROXY "$glidein_config")

X509_SKIP_HOST_CHECK_DNS_REGEX=""

if ! create_gridmapfile; then
    if using_tokens; then
        echo "Using tokens, non fatal error setting up x509 in create_mapfile.sh: $ERROR" 1>&2
        # TODO: check if it makes sense to continue w/ the rest, including defining X509... variables in glidein_config
    else
        #1. "$error_gen" -error "create_mapfile.sh" "WN_Resource" "$ERROR" "command" "$proxy_cmd"
	    #2. "$error_gen" -error "create_mapfile.sh" "WN_Resource" "$ERROR" "command" "$proxy_cmd"
        #3. "$error_gen" -error "create_mapfile.sh" "WN_Resource" "$ERROR" "file" "$X509_GRIDMAP"
        "$error_gen" -error "create_mapfile.sh" "WN_Resource" "$ERROR" "command" "$proxy_cmd" "file" "$X509_GRIDMAP"
        exit 1
    fi
fi
X509_GRIDMAP_DNS=$(extract_gridmap_DNs)

if ! create_condormapfile; then
    "$error_gen" -error "create_mapfile.sh" "WN_Resource" "$ERROR" "file" "$X509_CONDORMAP"
    exit 1
fi

gconfig_add X509_CONDORMAP "$X509_CONDORMAP"
gconfig_add X509_GRIDMAP_DNS "$X509_GRIDMAP_DNS"
gconfig_add X509_GRIDMAP_TRUSTED_DNS "$X509_GRIDMAP_DNS"

"$error_gen" -ok "create_mapfile.sh" "DNs" "$X509_GRIDMAP_DNS" "TrustedDNs" "$X509_GRIDMAP_DNS"
exit 0
