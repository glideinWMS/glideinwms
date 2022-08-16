#!/usr/bin/env bats
# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0
load 'lib/bats-support/load'
load 'lib/bats-assert/load'

[[ -z "$GWMS_SOURCEDIR" ]] && GWMS_SOURCEDIR="../../creation/web_base"

setup () {
    source "$GWMS_SOURCEDIR"/utils_params.sh
    source "$GWMS_SOURCEDIR"/add_config_line.source
}

@test "params_get_simple" {
    run params_get_simple "param2" " param1 value1 param2 value2 "
    [ "$output" == "value2" ]
    run params_get_simple "param1" " param1 value1 param2 value2 "
    [ "$output" == "value1" ]
}

@test "params_decode" {
    run params_decode "param2 .nbsp, .gt, .semicolon, .sclose, .comment, .minus, param3"
    [ "$output" == "param2   > ; ] # - param3" ]
}

#mock
glidein_exit(){
    echo "$1"
    exit 1
}

@test "params2file" {
    file="trial.txt"
    glidein_config="glidein_config"
    touch ${glidein_config}
    run params2file ${file} "param2 .nbsp, .gt, .semicolon, .sclose, .comment, .minus, param3"
    [ "$output" == "PARAM_LIST ${file}" ]
    grep -Fxq "${file} param2   > ; ] # - param3" ${glidein_config}
    rm ${glidein_config}
    rm ${glidein_config}.history
}
