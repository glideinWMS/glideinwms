#!/usr/bin/env bats
# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0
load 'lib/bats-support/load'
load 'lib/bats-assert/load'

[[ -z "$GWMS_SOURCEDIR" ]] && GWMS_SOURCEDIR="../../creation/web_base"

setup () {
    source "$GWMS_SOURCEDIR"/utils_gs_signals.sh
}

@test "on_die_multi" {
    echo "Testing the function killing one child..." >& 3
    sleep 5 &
    pid=$!
    GWMS_MULTIGLIDEIN_CHILDS="${pid}"
    run on_die_multi "KILL"
    if ! ps -p ${pid} > /dev/null
    then
       [ true ]
    else
       [ false ]
    fi
    [ "$status" -eq 0 ]
    assert_output --partial "forwarding KILL signal to"
    echo "Testing the function killing more than one children..." >& 3
    sleep 6 &
    pid=$!
    sleep 5 &
    pid2=$!
    GWMS_MULTIGLIDEIN_CHILDS="${pid} ${pid2}"
    run on_die_multi "KILL"
    if ! ps -p ${pid} > /dev/null; then
       [ true ]
    else
       [ false ]
    fi
    if ! ps -p ${pid2} > /dev/null; then
       [ true ]
    else
       [ false ]
    fi
    [ "$status" -eq 0 ]
    assert_output --partial "forwarding KILL signal to"
    echo "Testing the function killing no children..." >& 3
    GWMS_MULTIGLIDEIN_CHILDS=
    run on_die_multi "KILL"
    [ "$status" -eq 0 ]
}
