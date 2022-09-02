#!/usr/bin/env bats
# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0
load 'lib/bats-support/load'
load 'lib/bats-assert/load'

[[ -z "$GWMS_SOURCEDIR" ]] && GWMS_SOURCEDIR="../../creation/web_base"

setup () {
    source "$GWMS_SOURCEDIR"/utils_scripts.sh
}

@test "milestone_call" {
    #mock
    custom_scripts(){
        echo "$1"
    }
    run milestone_call "code\tcode"
    [ "$status" -eq 1 ]
    run milestone_call "code"
    [ "$output" == "milestone:code" ]
    [ "$status" -eq 0 ]
}

@test "failure_call" {
    #mock
    custom_scripts(){
        echo "$1"
    }
    run failure_call "code\tcode"
    [ "$status" -eq 1 ]
    run failure_call "code"
    [ "$output" == "failure:code" ]
    [ "$status" -eq 0 ]
}

#TODO: Bats tests for custom_scripts, extract_entry_files and add_entry not defined since they work on the descriptor_file statically defined
