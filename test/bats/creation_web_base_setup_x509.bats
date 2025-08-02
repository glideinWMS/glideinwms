#!/usr/bin/env bats

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

load 'lib/bats-support/load'
load 'lib/bats-assert/load'

#load 'helper'


[[ -z "$GWMS_SOURCEDIR" ]] && GWMS_SOURCEDIR=../..

# mocking gconfig_get()
gconfig_get_mock() {
    if [[ "$1" = GLIDEIN_Collector ]]; then
        echo "$collector_host"
    elif [[ "$1" = CCB_ADDRESS ]]; then
        echo "$ccb_address"
    else
        echo ""
    fi
}

setup () {
    source compat.bash
    glidein_config=fixtures/glidein_config
    # export GLIDEIN_QUIET=true
    source "$GWMS_SOURCEDIR"/creation/web_base/add_config_line.source  # 2>&3
    source "$GWMS_SOURCEDIR"/creation/web_base/setup_x509.sh  # 2>&3
    load 'mock_gwms_logs'

    # Mock gconfig_get intercepting some inputs
    # used by get_trust_domain, and others
    eval "$(echo "gconfig_get_orig()"; declare -f gconfig_get | tail -n +2 )"
    # echo "Running setup" >&3
    gconfig_get() { gconfig_get_mock "$@"; }
}

setup_nameprint() {
    if [ "${BATS_TEST_NUMBER}" = 1 ];then
        echo "# --- TEST NAME IS $(basename "${BATS_TEST_FILENAME}")" >&3
    fi
}

token_util_splitting() {
  # This is the trust_domain splitting in token_util.py (when it comes from the COLLECTOR_HOST)
  python3 -c "import re; print(re.split(' |,|\t', '$1')[0])"
}


@test "Test get_trust_domain" {
    # This trust_domain calculation must be compatible w/ the one used to create the IDTOKEN in the Frontand
    # Resilient to multiple collectors, it uses only the first one
    # Resilient to suggested port range or synful strings for secondary collectors (will limit to the host name)
    # Should result in the hostname all the time ("mycollector.domain.edu")
    collector_host='mycollector.domain.edu'
    [ "$(get_trust_domain)" = $(token_util_splitting "$collector_host") ]
    collector_host='mycollector.domain.edu:9618?sock=collector5'
    [ "$(get_trust_domain)" = $(token_util_splitting "$collector_host") ]
    collector_host='mycollector.domain.edu:9621'
    [ "$(get_trust_domain)" = $(token_util_splitting "$collector_host") ]
    collector_host='mycollector.domain.edu:9618-9628'
    [ "$(get_trust_domain)" = $(token_util_splitting "$collector_host") ]
    collector_host='mycollector.domain.edu:$RANDOM_INTEGER(9618,9628)'
    [ "$(get_trust_domain)" = $(token_util_splitting "mycollector.domain.edu:RANDOM") ]
    collector_host='mycollector.domain.edu:9618?sock=collector5,cecollector.domain.edu:9619'
    [ "$(get_trust_domain)" = $(token_util_splitting "$collector_host") ]
    collector_host='mycollector.domain.edu:9618?sock=collector5 , cecollector.domain.edu:9619'
    [ "$(get_trust_domain)" = $(token_util_splitting "$collector_host") ]
    collector_host='mycollector.domain.edu?sock=collector5,cecollector.domain.edu:9619'
    [ "$(get_trust_domain)" = $(token_util_splitting "$collector_host") ]
    collector_host='mycollector.domain.edu?sock=collector5,cecollector.domain.edu:9619'
    [ "$(get_trust_domain)" = $(token_util_splitting "$collector_host") ]
    collector_host='mycollector.domain.edu,cecollector.domain.edu:9619'
    [ "$(get_trust_domain)" = $(token_util_splitting "$collector_host") ]
    ccb_address='mycollector2.domain.edu:9640'
    [ "$(get_trust_domain)" = $(token_util_splitting "$collector_host") ]
    collector_host=''
    [ "$(get_trust_domain)" = $(token_util_splitting "$ccb_address") ]
}
