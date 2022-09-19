#!/usr/bin/env bats
# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0
load 'lib/bats-support/load'
load 'lib/bats-assert/load'

[[ -z "$GWMS_SOURCEDIR" ]] && GWMS_SOURCEDIR=../..

setup () {
    source "$GWMS_SOURCEDIR"/creation/web_base/utils_log.sh
    source "$GWMS_SOURCEDIR"/creation/web_base/utils_xml.sh
    source "$GWMS_SOURCEDIR"/creation/web_base/utils_gs_log.sh
    source "$GWMS_SOURCEDIR"/creation/web_base/logging_utils.source
    source "$GWMS_SOURCEDIR"/creation/web_base/glidein_cleanup.sh 2>&3
    source "$GWMS_SOURCEDIR"/creation/web_base/add_config_line.source
    source "$GWMS_SOURCEDIR"/creation/web_base/glidein_paths.source
    source "$GWMS_SOURCEDIR"/creation/web_base/get_id_selectors.source
}

@test "glidien_cleanup" {
    echo "Checking the case of not existing start_dir..." >& 3
    start_dir="random/stuff/"
    run glidein_cleanup 0
    assert_output --partial "Cannot find ${start_dir} anymore, will remove my current directory"
    [ "$status" -eq 0 ]
    echo "Checking the case of disabled cleanup..." >& 3
    start_dir="/tmp/start_dir/"
    mkdir -p "${start_dir}"
    GLIDEIN_DEBUG_OPTIONS=",nocleanup,"
    run glidein_cleanup 0
    assert_output --partial "Skipping cleanup, disabled via GLIDEIN_DEBUG_OPTIONS"
    [ "$status" -eq 0 ]
    echo "Checking the case of work_dir created..." >& 3
    work_dir="/tmp/work_dir/"
    mkdir -p "${work_dir}"
    GLIDEIN_DEBUG_OPTIONS=""
    work_dir_created=1
    run glidein_cleanup 0
    [ -z "$output" ]
    [ "$status" -eq 0 ]
    echo "Checking the case of glide_local_tmp_dir created..." >& 3
    glide_local_tmp_dir="/tmp/glide_local_tmp_dir/"
    mkdir -p "${glide_local_tmp_dir}"
    mkdir -p "${work_dir}"
    glide_local_tmp_dir_created=1
    run glidein_cleanup 0
    [ -z "$output" ]
    [ "$status" -eq 0 ]
}

@test "early_glidein_failure" {
    echo "Checking the correctness of the xml structure..." >& 3
    glidein_cleanup(){
        echo "glidein_cleanup"
        return 0
    }
    message="message"
    sleep_time=1
    let startup_time=$(date +%s)
    run early_glidein_failure "${message}"
    assert_output --partial "WARN"
    assert_output --partial "glidein_cleanup"
    assert_output --partial "===  Glidein ending"
    assert_output --partial "<metric name=\"failure\""
    assert_output --partial "<status>ERROR</status>"
    assert_output --partial "<detail>"
    assert_output --partial "===  XML description of glidein activity  ==="
    assert_output --partial "===  End XML description of glidein activity  ==="
    assert_output --partial "===  Encoded XML description of glidein activity  ==="
    assert_output --partial "===  End encoded XML description of glidein activity  ==="
    [ "$status" -eq 1 ]
}

@test "glidein_exit" {
    echo "Checking the correctness of the output and gliein_config file in case of exit call with 0 as argument..." >& 3
    if command -v uuidgen >/dev/null 2>&1; then
        glidein_uuid="$(uuidgen)"
    else
        glidein_uuid="$(od -x -w32 -N32 /dev/urandom | awk 'NR==1{OFS="-"; print $2$3,$4,$5,$6,$7$8$9}')"
    fi
    work_dir="$(pwd)"
    GWMS_SUBDIR=".gwms.d"
    GWMS_DIR="${work_dir}/${GWMS_SUBDIR}"
    mkdir -p "${GWMS_DIR}/exec/cleanup"
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
    grep -iq "ADD_CONFIG_LINE_SOURCE" "${glidein_config}"
    grep -iq "GLIDEIN_LOGDIR" "${glidein_config}"
    grep -iq "GLIDEIN_STDOUT_LOGFILE" "${glidein_config}"
    grep -iq "GLIDEIN_STDERR_LOGFILE" "${glidein_config}"
    grep -iq "GLIDEIN_LOG_LOGFILE" "${glidein_config}"
    grep -iq "GLIDEIN_LOG_RELATIVE_BASEPATH" "${glidein_config}"
    grep -iq "CURL_VERSION" "${glidein_config}"
    grep -iq "GLIDEIN_LOG_NO_SEND" "${glidein_config}"
    grep -iq "GLIDEIN_LOG_INITIALIZED" "${glidein_config}"
    [ "$status" -eq 0 ]
    echo "Checking the correctness of the output and gliein_config file in case of exit call with a value different than 0 as argument..." >& 3
    run glidein_exit 1
    assert_output --partial "===  Glidein ending"
    assert_output --partial "===  XML description of glidein activity  ==="
    assert_output --partial "===  End XML description of glidein activity  ==="
    assert_output --partial "===  Encoded XML description of glidein activity  ==="
    assert_output --partial "===  End encoded XML description of glidein activity  ==="
    [ "$status" -eq 1 ]
    grep -iq "ADD_CONFIG_LINE_SOURCE" "${glidein_config}"
    grep -iq "GLIDEIN_LOGDIR" "${glidein_config}"
    grep -iq "GLIDEIN_STDOUT_LOGFILE" "${glidein_config}"
    grep -iq "GLIDEIN_STDERR_LOGFILE" "${glidein_config}"
    grep -iq "GLIDEIN_LOG_LOGFILE" "${glidein_config}"
    grep -iq "GLIDEIN_LOG_RELATIVE_BASEPATH" "${glidein_config}"
    grep -iq "CURL_VERSION" "${glidein_config}"
    grep -iq "GLIDEIN_LOG_NO_SEND" "${glidein_config}"
    grep -iq "GLIDEIN_LOG_INITIALIZED" "${glidein_config}"
    grep -iq "GLIDEIN_ADVERTISE_ONLY" "${glidein_config}"
    grep -iq "GLIDEIN_Failed" "${glidein_config}"
    grep -iq "GLIDEIN_EXIT_CODE" "${glidein_config}"
    grep -iq "GLIDEIN_ToDie" "${glidein_config}"
    grep -iq "GLIDEIN_Expire" "${glidein_config}"
    grep -iq "GLIDEIN_LAST_SCRIPT" "${glidein_config}"
    grep -iq "GLIDEIN_ADVERTISE_TYPE" "${glidein_config}"
    grep -iq "GLIDEIN_FAILURE_REASON" "${glidein_config}"
    # TODO: Missing checks of the special cases of report failed
}

teardown() {
    rm -rf "${glide_local_tmp_dir}"
    rm -rf "${start_dir}"
    rm -f "${PWD}/add_config_line.source"
    rm -f "glidein_config"
    rm -f "glidein_config.history"
    rm -rf "${GWMS_DIR}"
    rm -rf "logs/"
}
