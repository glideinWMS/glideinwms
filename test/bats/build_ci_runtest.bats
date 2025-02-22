#!/usr/bin/env bats

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

# On the Mac, installed w/ Homebrew
#load '/usr/local/lib/bats-support/load.bash'
#load '/usr/local/lib/bats-assert/load.bash'
load 'lib/bats-support/load'
load 'lib/bats-assert/load'

[[ -z "$GWMS_SOURCEDIR" ]] && GWMS_SOURCEDIR=../..

setup() {
    # executed before each test
    source compat.bash
    source "$GWMS_SOURCEDIR"/build/ci/runtest.sh 2>&3
}

no_teardown() {
    # executed after each test
    echo "teardown" >&3
}


@test "test_logexit" {
    filename=PREFIX
    run logexit "This should be 1"
    [ "$output" == "$filename ERROR: This should be 1" ]
    [ "$status" -eq 1 ]
    run logexit "This should be 2" 2
    [ "$output" == "$filename ERROR: This should be 2" ]
    [ "$status" -eq 2 ]
}


@test "test_robust_realpath" {
    pushd /tmp
    run robust_realpath output
    # on the Mac /tmp is really /private/tmp
    [ "$output" == "/tmp/output" -o "$output" == "/private/tmp/output" ]
    [ "$status" -eq 0 ]
    popd
}


@test "get_files_pattern" {
    skip
    # setup_python_venv
}


@test "is_python3_branch" {
    skip
    # setup_python_venv
}


@test "transpose_table" {
    skip
    # setup_python_venv
}
