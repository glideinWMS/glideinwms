#!/usr/bin/env bats
# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0
load 'lib/bats-support/load'
load 'lib/bats-assert/load'

#load 'helper'

[[ -z "$GWMS_SOURCEDIR" ]] && GWMS_SOURCEDIR="../../creation/web_base"

setup () {
    # get the containing directory of this file
    # use $BATS_TEST_FILENAME instead of ${BASH_SOURCE[0]} or $0,
    # as those will point to the bats executable's location or the preprocessed file respectively
    DIR="$( cd "$( dirname "$BATS_TEST_FILENAME" )" >/dev/null 2>&1 && pwd )"
    # make executables in src/ visible to PATH
    PATH="$DIR/../src:$PATH"
    source compat.bash
    source "$GWMS_SOURCEDIR"/utils_io.sh
    #load 'mock_gwms_logs'
}

setup_nameprint() {
    if [ "${BATS_TEST_NUMBER}" = 1 ];then
        echo "# --- TEST NAME IS $(basename "${BATS_TEST_FILENAME}")" >&3
    fi
}

@test "log_warn" {
    run log_warn "trial"
    assert_output --partial "WARN"
    [ "$status" == 0 ]
}

@test "log_debug" {
    run log_debug "trial"
    assert_output --partial "DEBUG"
    [ "$status" == 0 ]
}

@test "print_header_line" {
    run print_header_line "trial"
    [ "$output" == "===  trial  ===" ]
    [ "$status" == 0 ]
    run print_header_line "trial" 1
    [ "$output" == "===  trial  ===" ]
    [ "$status" == 0 ]
    run print_header_line "trial" 2
    [ "$output" == "===  trial  ===" ]
    [ "$status" == 0 ]
}
