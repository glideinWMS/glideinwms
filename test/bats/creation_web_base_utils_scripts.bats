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

@test "add_entry" {
    gwms_exec_dir="/tmp"
    get_untar_subdir(){
        echo "tmp"
    }
    run add_entry name type time coordination period prefix id tar_source
    grep -q "Time    OrderedFilename    RealFilename   Type    Period    Prefix    Id" $gwms_exec_dir/descriptor_file.txt
    grep -q "time    coordination_name    /tmp/name    type    period    prefix    id" $gwms_exec_dir/descriptor_file.txt
    rm -f $gwms_exec_dir/descriptor_file.txt
    run add_entry name type time,time2 coordination period prefix id tar_source
    grep -q "Time    OrderedFilename    RealFilename   Type    Period    Prefix    Id" $gwms_exec_dir/descriptor_file.txt
    grep -q "time    coordination_name    /tmp/name    type    period    prefix    id" $gwms_exec_dir/descriptor_file.txt
    grep -q "time2    coordination_name    /tmp/name    type    period    prefix    id" $gwms_exec_dir/descriptor_file.txt
    rm -f $gwms_exec_dir/descriptor_file.txt
}


@test "extract_entry_files" {
    gwms_exec_dir="/tmp"
    get_untar_subdir(){
        echo "tmp"
    }
    run add_entry name type time2 coordination period prefix id tar_source
    run add_entry name type time3 coordination period prefix id tar_source
    run add_entry name type time coordination period prefix id tar_source
    run extract_entry_files "time"
    grep -q "time    coordination_name    /tmp/name    type    period    prefix    id" $gwms_exec_dir/time_descriptor_file.txt
}

#TODO: Bats tests for custom_scripts not defined due to complexity
