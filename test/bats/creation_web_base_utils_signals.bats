#!/usr/bin/env bats
# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0
load 'lib/bats-support/load'
load 'lib/bats-assert/load'

[[ -z "$GWMS_SOURCEDIR" ]] && GWMS_SOURCEDIR="../../creation/web_base"

setup () {
    source "$GWMS_SOURCEDIR"/utils_signals.sh
}

@test "signal_trap_with_arg" {
    echo "Testing the assignment of the handler to some signals..." >& 3
    run trap 'signal_ignore' SIGTERM SIGINT SIGQUIT
    # Todo: How to check if the handler has been correctly assigned?
    [ "$output" == "" ]
    [ "$status" -eq 0 ]
}

@test "signal_on_die" {
    echo "Testing the launch of a signal to a process..." >& 3
    sleep 5 &
    pid=$!
    GWMS_MULTIGLIDEIN_CHILDS="${pid}"
    run signal_on_die "KILL"
    if ! ps -p ${pid} > /dev/null
    then
       [ true ]
    else
       [ false]
    fi
    [ "$status" -eq 0 ]
    assert_output --partial "forwarding KILL signal"
}

@test "signal_on_die_multi" {
     echo "Testing the function killing one child..." >& 3
     sleep 5 &
     pid=$!
     SIGNAL_CHILDREN_LIST="${pid}"
     run signal_on_die_multi "KILL"
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
     SIGNAL_CHILDREN_LIST="${pid} ${pid2}"
     run signal_on_die_multi "KILL"
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
     SIGNAL_CHILDREN_LIST=
     run signal_on_die_multi "KILL"
     [ "$status" -eq 0 ]
 }

 @test "signal_add_child" {
     SIGNAL_CHILDREN_LIST=
     signal_add_child "test"
     echo "$SIGNAL_CHILDREN_LIST" >& 3
     [ "$SIGNAL_CHILDREN_LIST" == "test" ]
     signal_add_child "test"
     [ "$SIGNAL_CHILDREN_LIST" == "test test" ]
     echo "$SIGNAL_CHILDREN_LIST" >& 3
 }

 @test "signal_set_children" {
     SIGNAL_CHILDREN_LIST="test1"
     signal_set_children "test2"
     [ "$SIGNAL_CHILDREN_LIST" == "test2" ]
 }
