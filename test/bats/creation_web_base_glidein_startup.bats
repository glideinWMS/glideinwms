#!/usr/bin/env bats
# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0
load 'lib/bats-support/load'
load 'lib/bats-assert/load'

#load 'helper'

[[ -z "$GWMS_SOURCEDIR" ]] && GWMS_SOURCEDIR="../../creation/web_base"

setup () {
    # get the containing directory of this file
    # use $BATS_TEST_FILENAME instead of ${BASH_SOURCE[0]} or $0,
    # as those will point to the bats executable's location or the preprocessed file respectively
    DIR="$( cd "$( dirname "$BATS_TEST_FILENAME" )" >/dev/null 2>&1 && pwd )"
    # make executables in src/ visible to PATH
    PATH="$DIR/../src:$PATH"
    source compat.bash
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
    #load 'mock_gwms_logs'
}

setup_nameprint() {
    if [ "${BATS_TEST_NUMBER}" = 1 ];then
        echo "# --- TEST NAME IS $(basename "${BATS_TEST_FILENAME}")" >&3
    fi
}

@test "copy_all" {
    tmp_dir="/tmp/prova"
    mkdir -p "$tmp_dir"
    cd "$tmp_dir"
    touch file1.txt
    touch file2.txt
    touch file3.txt
    touch afile1.txt
    target_dir="/tmp/prova2"
    mkdir -p "$target_dir"
    run copy_all "pfile" "${target_dir}"
    [ "$output" == "" ]
    [ -f "${target_dir}"/file1.txt ]
    [ -f "${target_dir}"/file2.txt ]
    [ -f "${target_dir}"/file3.txt ]
    [ ! -f "${target_dir}"/pfile1.txt ]
    [ "$status" -eq 0 ]
    rm -rf "$tmp_dir"
    rm -rf "$target_dir"
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
