#!/usr/bin/env bats
# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0
load 'lib/bats-support/load'
load 'lib/bats-assert/load'

[[ -z "$GWMS_SOURCEDIR" ]] && GWMS_SOURCEDIR="../../creation/web_base"

setup () {
    source "$GWMS_SOURCEDIR"/utils_gs_http.sh
    source "$GWMS_SOURCEDIR"/utils_log.sh
}

@test "get_repository_url" {
    echo "Testing the possible options of arguments..." >& 3
    run get_repository_url main
    [ "$status" -eq 0 ]
    run get_repository_url entry
    [ "$status" -eq 0 ]
    run get_repository_url client
    [ "$status" -eq 0 ]
    run get_repository_url client_group
    [ "$status" -eq 0 ]
    echo "Testing a possible wrong argument..." >& 3
    id="id"
    run get_repository_url id
    [ "$status" -eq 1 ]
    assert_output --partial "[get_repository_url] Invalid id: ${id}"
}

#mock
add_config_line(){
    echo "Added config line: $1"
}


@test "add_periodic_script" {
    echo "Testing the config line content in case of NOPREFIX..." >& 3
    add_startd_cron_counter=0
    GLIDEIN_PS_=glidein_ps
    wrapper="wrapper"
    period="period"
    cwd="cwd"
    fname="fname"
    config="config"
    ffb_id="ffb_id"
    prefix="NOPREFIX"
    run add_periodic_script ${wrapper} ${period} ${cwd} ${fname} ${config} ${ffb_id} ${prefix}
    assert_output --partial "Added config line: GLIDEIN_condor_config_startd_cron_include"
    assert_output --partial "Added config line: # --- Lines starting with ${prefix} are from periodic scripts ---"
    [ -f condor_config_startd_cron_include ]
    let add_startd_cron_counter=add_startd_cron_counter+1
    grep -Fxq "STARTD_CRON_JOBLIST = \$(STARTD_CRON_JOBLIST) GLIDEIN_PS_${add_startd_cron_counter}
               STARTD_CRON_GLIDEIN_PS_${add_startd_cron_counter}_MODE = Periodic
               STARTD_CRON_GLIDEIN_PS_${add_startd_cron_counter}_KILL = True
               STARTD_CRON_GLIDEIN_PS_${add_startd_cron_counter}_PERIOD = periods
               STARTD_CRON_GLIDEIN_PS_${add_startd_cron_counter}_EXECUTABLE = wrapper
               STARTD_CRON_GLIDEIN_PS_${add_startd_cron_counter}_ARGS = config ffb_id GLIDEIN_PS_${add_startd_cron_counter} fname cc_prefix
               STARTD_CRON_GLIDEIN_PS_${add_startd_cron_counter}_CWD = cwd
               STARTD_CRON_GLIDEIN_PS_${add_startd_cron_counter}_SLOTS = 1
               STARTD_CRON_GLIDEIN_PS_${add_startd_cron_counter}_JOB_LOAD = 0.01" condor_config_startd_cron_include
    rm condor_config_startd_cron_include
    echo "Testing the config line content in case of cc_prefix..." >& 3
    prefix="cc_prefix"
    run add_periodic_script ${wrapper} ${period} ${cwd} ${fname} ${config} ${ffb_id} ${prefix}
    assert_output --partial "Added config line: GLIDEIN_condor_config_startd_cron_include"
    assert_output --partial "Added config line: # --- Lines starting with ${prefix} are from periodic scripts ---"
    [ -f condor_config_startd_cron_include ]
    let add_startd_cron_counter=add_startd_cron_counter+1
    grep -Fxq "STARTD_CRON_JOBLIST = \$(STARTD_CRON_JOBLIST) GLIDEIN_PS_${add_startd_cron_counter}
               STARTD_CRON_GLIDEIN_PS_${add_startd_cron_counter}_MODE = Periodic
               STARTD_CRON_GLIDEIN_PS_${add_startd_cron_counter}_KILL = True
               STARTD_CRON_GLIDEIN_PS_${add_startd_cron_counter}_PERIOD = periods
               STARTD_CRON_GLIDEIN_PS_${add_startd_cron_counter}_EXECUTABLE = wrapper
               STARTD_CRON_GLIDEIN_PS_${add_startd_cron_counter}_ARGS = config ffb_id GLIDEIN_PS_${add_startd_cron_counter} fname cc_prefix
               STARTD_CRON_GLIDEIN_PS_${add_startd_cron_counter}_CWD = cwd
               STARTD_CRON_GLIDEIN_PS_${add_startd_cron_counter}_SLOTS = 1
               STARTD_CRON_GLIDEIN_PS_${add_startd_cron_counter}_JOB_LOAD = 0.01
               STARTD_CRON_GLIDEIN_PS_1_PREFIX = cc_prefix" condor_config_startd_cron_include
}

#mock
glidein_exit(){
    return 1
}

@test "fetch_file" {
    echo "Testing different possible numbers of arguments..." >& 3
    run fetch_file 1 2 3 4 5 6 7 8 9
    assert_output --partial "More then 8 arguments, considering the first 8"
    run fetch_file 1
    assert_output --partial "Not enough arguments in fetch_file, 8 expected"
    run fetch_file 1 2
    assert_output --partial "Not enough arguments in fetch_file, 8 expected"
    run fetch_file 1 2 3
    assert_output --partial "Not enough arguments in fetch_file, 8 expected"
    run fetch_file 1 2 3 4
    assert_output --partial "Not enough arguments in fetch_file, 8 expected"
    run fetch_file 1 2 3 4 5
    assert_output --partial "Not enough arguments in fetch_file, 8 expected"
}

#TODO: Test fetch_file_try, fetch_file_base, perform_wget, perform_curl

teardown() {
    rm -f condor_config_startd_cron_include
}
