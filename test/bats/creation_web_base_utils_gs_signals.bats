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
    sleep 5 &
    pid=$!
    GWMS_MULTIGLIDEIN_CHILDS=${pid}
    run on_die_multi "KILL"
    echo "$output" >& 3
    if ! ps -p ${pid} > /dev/null
    then
       [ 0 -eq 0 ]
    else
       [ 1 -eq 0 ]
    fi
    [ "$status" == 0 ]
    assert_output --partial "forwarding KILL signal to"
}
