#!/usr/bin/env bats
# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0
load 'lib/bats-support/load'
load 'lib/bats-assert/load'

[[ -z "$GWMS_SOURCEDIR" ]] && GWMS_SOURCEDIR="../../creation/web_base"

setup () {
    source "$GWMS_SOURCEDIR"/utils_gs_signals.sh
    source "$GWMS_SOURCEDIR"/utils_gs_tarballs.sh
    source "$GWMS_SOURCEDIR"/utils_io.sh
    source "$GWMS_SOURCEDIR"/utils_params.sh
    source "$GWMS_SOURCEDIR"/utils_signals.sh
    source "$GWMS_SOURCEDIR"/utils_tarballs.sh
    source "$GWMS_SOURCEDIR"/utils_xml.sh
    source "$GWMS_SOURCEDIR"/utils_crypto.sh
    source "$GWMS_SOURCEDIR"/utils_gs_http.sh
    source "$GWMS_SOURCEDIR"/utils_gs_filesystem.sh
    source "$GWMS_SOURCEDIR"/utils_gs_io.sh
    source "$GWMS_SOURCEDIR"/logging_utils.source
    source "$GWMS_SOURCEDIR"/glidein_cleanup.sh
    source "$GWMS_SOURCEDIR"/glidein_startup.sh
    source "$GWMS_SOURCEDIR"/add_config_line.source
    source "$GWMS_SOURCEDIR"/glidein_paths.source
    source ../../build/ci/utils.sh
}

@test "do_start_all" {
    GWMS_SOURCEDIR="../../../creation/web_base"
    export GWMS_SOURCEDIR
    num_glideins=5
    run do_start_all ${num_glideins}
    echo "$output" >& 3
    for i in ${num_glideins}; do
        assert_output --partial "Starting glidein ${i} in glidein_dir${i}"
    done
    assert_output --partial "Started multiple glideins"
    # TODO: Missing case of starting multi-glidein using launcher launchall
}

@test "spawn_multiple_glideins" {
    GWMS_SOURCEDIR="../../../creation/web_base"
    export GWMS_SOURCEDIR
    num_glideins=5
    run spawn_multiple_glideins
    echo "$output" >& 3
    assert_output --partial "------ Multi-glidein parent waiting for child processes"
    assert_output --partial "------ Exiting multi-glidein parent ----------"
    [ "$status" -eq 0 ]
    # TODO: Missing case of starting multi-glidein using launcher launchall
}


# TODO: FINISH

@test "add_to_path" {
    GWMS_PATH=""
    run add_to_path "CIAO"
    #assert_output --partial "------ Exiting multi-glidein parent ----------"
    [ "$status" -eq 0 ]
    # TODO: Missing case of starting multi-glidein using launcher launchall
}
