#!/usr/bin/env bats
# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0
load 'lib/bats-support/load'
load 'lib/bats-assert/load'

[[ -z "$GWMS_SOURCEDIR" ]] && GWMS_SOURCEDIR=../..

setup () {
    source "$GWMS_SOURCEDIR"/creation/web_base/utils_io.sh
    source "$GWMS_SOURCEDIR"/creation/web_base/utils_xml.sh
    source "$GWMS_SOURCEDIR"/creation/web_base/utils_gs_io.sh
    source "$GWMS_SOURCEDIR"/creation/web_base/logging_utils.source
    source "$GWMS_SOURCEDIR"/creation/web_base/glidein_cleanup.sh 2>&3
    source "$GWMS_SOURCEDIR"/creation/web_base/add_config_line.source
    source "$GWMS_SOURCEDIR"/creation/web_base/glidein_paths.source
}

@test "glidien_cleanup" {
    start_dir="random/stuff/"
    run glidein_cleanup 0
    echo "$output"
    assert_output --partial "Cannot find ${start_dir} anymore, exiting but without cleanup"
    [ "$status" -eq 0 ]
    start_dir="/tmp/start_dir/"
    mkdir -p /tmp/start_dir/
    GLIDEIN_DEBUG_OPTIONS=",nocleanup,"
    run glidein_cleanup 0
    assert_output --partial "Skipping cleanup, disabled via GLIDEIN_DEBUG_OPTIONS"
    [ "$status" -eq 0 ]
    work_dir="/tmp/work_dir/"
    mkdir -p /tmp/work_dir/
    GLIDEIN_DEBUG_OPTIONS=""
    work_dir_created=1
    run glidein_cleanup 0
    echo "$output" >& 3
    [ "$output" == "" ]
    [ "$status" -eq 0 ]
    work_dir="/tmp/work_dir/"
    mkdir -p /tmp/work_dir/
    glide_local_tmp_dir="/tmp/glide_local_tmp_dir/"
    mkdir -p /tmp/glide_local_tmp_dir/
    glide_local_tmp_dir_created=1
    run glidein_cleanup 0
    echo "$output" >& 3
    [ "$output" == "" ]
    [ "$status" -eq 0 ]
}

@test "early_glidein_failure" {
    message="random"
    sleep_time=1
    let startup_time=$(date +%s)
    run early_glidein_failure "${message}"
    echo "$output" >&3
    assert_output --partial "WARN"
    assert_output --partial "===  Glidein ending"
    assert_output --partial "===  XML description of glidein activity  ==="
    assert_output --partial "===  End XML description of glidein activity  ==="
    assert_output --partial "===  Encoded XML description of glidein activity  ==="
    assert_output --partial "===  End encoded XML description of glidein activity  ==="
    [ "$status" -eq 1 ]
}

@test "glidein_exit" {
    if command -v uuidgen >/dev/null 2>&1; then
        glidein_uuid="$(uuidgen)"
    else
        glidein_uuid="$(od -x -w32 -N32 /dev/urandom | awk 'NR==1{OFS="-"; print $2$3,$4,$5,$6,$7$8$9}')"
    fi
    work_dir="$(PWD)"
    GWMS_SUBDIR=".gwms.d"
    GWMS_DIR="${work_dir}/$GWMS_SUBDIR"
    mkdir -p "$GWMS_DIR/exec/cleanup"
    let startup_time=$(date +%s)
    glidein_config="${PWD}/glidein_config"
    echo "ADD_CONFIG_LINE_SOURCE ${PWD}/add_config_line.source" > glidein_config
    touch "${PWD}/add_config_line.source"
    touch glidein_config
    log_init "${glidein_uuid}" "${work_dir}"
    log_setup "${glidein_config}"
    run glidein_exit 0
    assert_output --partial "===  Glidein ending"
    assert_output --partial "===  XML description of glidein activity  ==="
    assert_output --partial "===  End XML description of glidein activity  ==="
    assert_output --partial "===  Encoded XML description of glidein activity  ==="
    assert_output --partial "===  End encoded XML description of glidein activity  ==="
    [ "$status" -eq 0 ]
    run glidein_exit 1
    echo "$output" >&3
    assert_output --partial "===  Glidein ending"
    [ "$status" -eq 1 ]
    rm "${PWD}/add_config_line.source"
    rm glidein_config
    rm "glidein_config.history"
    rm -rf "$GWMS_DIR"
}

teardown() {
    rm -rf /tmp/glide_local_tmp_dir/
    rm -rf /tmp/work_dir/
    rm -rf /tmp/start_dir/
}
