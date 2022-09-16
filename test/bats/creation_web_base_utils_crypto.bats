#!/usr/bin/env bats
# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0
load 'lib/bats-support/load'
load 'lib/bats-assert/load'

[[ -z "$GWMS_SOURCEDIR" ]] && GWMS_SOURCEDIR="../../creation/web_base"

setup () {
    source "$GWMS_SOURCEDIR"/utils_crypto.sh
    source "$GWMS_SOURCEDIR"/utils_log.sh
}

@test "md5wrapper" {
    echo "Testing the call to md5wrapper with non-valid file..." >& 3
    run md5wrapper "file"
    assert_output --partial "???"
    assert_output --partial "md5wrapper error: can't calculate md5sum using"
    [ "$status" -eq 1 ]
    echo "Testing the call to md5wrapper with valid file..." >& 3
    filename="/tmp/trial_file"
    touch ${filename}
    run md5wrapper ${filename}
    assert_output --regexp "^[0-9a-z]+  ${filename}"
    [ "$status" -eq 0 ]
}

@test "set_proxy_fullpath" {
    echo "Testing the call to set_proxy_fullpath with non-valid user proxy..." >& 3
    X509_USER_PROXY=
    run set_proxy_fullpath
    assert_output --partial "Unable to get canonical path for X509_USER_PROXY, using ${X509_USER_PROXY}"
    [ "$status" -eq 0 ]
    echo "Testing the call to set_proxy_fullpath with valid user proxy..." >& 3
    mkdir -p "/tmp/trial"
    touch "/tmp/trial/x509up_u"
    X509_USER_PROXY="/tmp/trial/x509up_u"
    run set_proxy_fullpath
    assert_output --partial "Setting X509_USER_PROXY ${X509_USER_PROXY} to canonical path ${X509_USER_PROXY}" || assert_output --partial "Setting X509_USER_PROXY ${X509_USER_PROXY} to canonical path /private${X509_USER_PROXY}"
    [ "$status" -eq 0 ]
}

#TODO: check_file_signature test

teardown(){
    rm -f "${filename}"
    rm -rf "/tmp/trial/"
}
