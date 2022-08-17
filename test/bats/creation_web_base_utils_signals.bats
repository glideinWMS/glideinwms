#!/usr/bin/env bats
# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0
load 'lib/bats-support/load'
load 'lib/bats-assert/load'

[[ -z "$GWMS_SOURCEDIR" ]] && GWMS_SOURCEDIR="../../creation/web_base"

setup () {
    source "$GWMS_SOURCEDIR"/utils_signals.sh
}

@test "trap_with_arg" {
    echo "Testing the assignment of the handler to some signals..." >& 3
    run trap 'ignore_signal' SIGTERM SIGINT SIGQUIT
    # Todo: How to check if the handler has been correctly assigned?
    [ "$output" == "" ]
    [ "$status" -eq 0 ]
}

@test "on_die" {
    echo "Testing the launch of a signal to a process..." >& 3
    sleep 5 &
    pid=$!
    GWMS_MULTIGLIDEIN_CHILDS="${pid}"
    run on_die "KILL"
    if ! ps -p ${pid} > /dev/null
    then
       [ true ]
    else
       [ false]
    fi
    [ "$status" -eq 0 ]
    assert_output --partial "forwarding KILL signal"
}
