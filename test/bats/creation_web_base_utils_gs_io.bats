#!/usr/bin/env bats
# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0
load 'lib/bats-support/load'
load 'lib/bats-assert/load'

[[ -z "$GWMS_SOURCEDIR" ]] && GWMS_SOURCEDIR="../../creation/web_base"

setup () {
    source "$GWMS_SOURCEDIR"/utils_gs_io.sh
    source "$GWMS_SOURCEDIR"/utils_io.sh
    source "$GWMS_SOURCEDIR"/utils_crypto.sh
}

@test "print_header" {
    set_debug=1
    run print_header ""
    assert_output --partial "Initial environment"
    set_debug=0
    run print_header ""
    ! assert_output --partial "Initial environment"
}

@test "parse_options" {
    run parse_options -name -factory
    assert_output --partial "You cannot set two consecutive options without specifying the option value!"
    [ "$status" -eq 1 ]
    run parse_options -error
    assert_output --partial "Unknown option"
    [ "$status" -eq 1 ]
}
