#!/usr/bin/env bats
# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0
load 'lib/bats-support/load'
load 'lib/bats-assert/load'

[[ -z "$GWMS_SOURCEDIR" ]] && GWMS_SOURCEDIR="../../creation/web_base"

setup () {
    source "$GWMS_SOURCEDIR"/utils_log.sh
}

@test "log_warn" {
    run log_warn "trial"
    assert_output --partial "WARN"
    [ "$status" -eq 0 ]
}

@test "log_debug" {
    run log_debug "trial"
    assert_output --partial "DEBUG"
    [ "$status" -eq 0 ]
}

@test "print_header_line" {
    run print_header_line "trial"
    [ "$output" == "===  trial  ===" ]
    [ "$status" -eq 0 ]
    run print_header_line "trial" "trial2"
    [ "$output" == "===  trial trial2  ===" ]
    [ "$status" -eq 0 ]
}
