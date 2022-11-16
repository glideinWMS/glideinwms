#!/usr/bin/env bats
# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0
load 'lib/bats-support/load'
load 'lib/bats-assert/load'

[[ -z "$GWMS_SOURCEDIR" ]] && GWMS_SOURCEDIR="../../creation/web_base"

setup () {
    source "$GWMS_SOURCEDIR"/utils_gs_filesystem.sh
    source ../../build/ci/utils.sh
}

@test "automatic_work_dir" {
    _CONDOR_SCRATCH_DIR="/tmp/condor_scratch/"
    OSG_WN_TMP="/tmp/osg_wn/"
    TG_NODE_SCRATCH="/tmp/tg_node/"
    TG_CLUSTER_SCRATCH="/tmp/tg_cluster/"
    SCRATCH="/tmp/scratch/"
    TMPDIR="/tmp/tmpdir/"
    TMP="/tmp/tmp/"
    echo "Testing the correctness with non-existing work directories..." >& 3
    run automatic_work_dir
    assert_output --partial "Workdir: ${_CONDOR_SCRATCH_DIR} does not exist"
    assert_output --partial "Workdir: ${OSG_WN_TMP} does not exist"
    assert_output --partial "Workdir: ${TG_NODE_SCRATCH} does not exist"
    assert_output --partial "Workdir: ${TG_CLUSTER_SCRATCH} does not exist"
    assert_output --partial "Workdir: ${SCRATCH} does not exist"
    assert_output --partial "Workdir: ${TMPDIR} does not exist"
    assert_output --partial "Workdir: ${TMP} does not exist"
    assert_output --partial "Workdir: ${PWD} selected"
    [ "$status" -eq 0 ]
    echo "Testing the correctness with existing work directories..." >& 3
    mkdir ${_CONDOR_SCRATCH_DIR}
    mkdir ${OSG_WN_TMP}
    mkdir ${TG_NODE_SCRATCH}
    mkdir ${TG_CLUSTER_SCRATCH}
    mkdir ${SCRATCH}
    mkdir ${TMPDIR}
    mkdir ${TMP}
    run automatic_work_dir
    assert_output --partial "Workdir: ${_CONDOR_SCRATCH_DIR} selected"
    [ "$status" == 0 ]
    echo "Testing the correctness with non-existing first target work directory..." >& 3
    rm -rf ${_CONDOR_SCRATCH_DIR}
    run automatic_work_dir
    assert_output --partial "Workdir: ${OSG_WN_TMP} selected"
    [ "$status" == 0 ]
    if [ "$EUID" -ne 0 ]; then
        mkdir ${_CONDOR_SCRATCH_DIR}
        echo "Testing the correctness with non-writable work directory..." >& 3
        chmod 000 ${_CONDOR_SCRATCH_DIR}
        run automatic_work_dir
        assert_output --partial "Workdir: not allowed to write to ${_CONDOR_SCRATCH_DIR}"
        chmod 777 ${_CONDOR_SCRATCH_DIR}
        run automatic_work_dir
        [ "$status" -eq 0 ]
    fi
    rm -rf "${_CONDOR_SCRATCH_DIR}"
    rm -rf "${OSG_WN_TMP}"
    rm -rf "${TG_NODE_SCRATCH}"
    rm -rf "${TG_CLUSTER_SCRATCH}"
    rm -rf "${SCRATCH}"
    rm -rf "${TMPDIR}"
    rm -rf "${TMP}"
}

@test "dir_id" {
    echo "Testing the correctness with no debug options..." >& 3
    GLIDEIN_DEBUG_OPTIONS=""
    repository_url="/tmp/repository/"
    client_repository_url="/tmp/client_repository/"
    run dir_id
    [ "$output" == "" ]
    [ "$status" -eq 0 ]
    echo "Testing the correctness with 'nocleanup' debug option..." >& 3
    GLIDEIN_DEBUG_OPTIONS="nocleanup"
    run dir_id
    [ "$output" == "ory/ory/_" ]
    [ "$status" -eq 0 ]
}

# mock
early_glidein_failure() {
     echo "$1"
     exit 1
}

@test "copy_all" {
    echo "Testing the correctness with some trial files..." >& 3
    tmp_dir="/tmp/prova"
    mkdir -p "$tmp_dir"
    touch "${tmp_dir}/file1.txt"
    touch "${tmp_dir}/file2.txt"
    touch "${tmp_dir}/file3.txt"
    touch "${tmp_dir}/afile1.txt"
    target_dir="/tmp/prova2"
    mkdir -p "$target_dir"
    cd ${tmp_dir}
    run copy_all "pfile" "${target_dir}"
    cd -
    [ "$output" == "" ]
    [ -f "${target_dir}"/file1.txt ]
    [ -f "${target_dir}"/file2.txt ]
    [ -f "${target_dir}"/file3.txt ]
    [ ! -f "${target_dir}"/pfile1.txt ]
    [ "$status" -eq 0 ]
    rm -rf "$tmp_dir"
    rm -rf "$target_dir"
}

@test "add_to_path" {
    echo "Testing the addition of an element to the path..." >& 3
    GWMS_PATH="/tmp/gwms_path"
    PATH="/tmp/path"
    OLD_GWMS_PATH=${GWMS_PATH}
    OLD_PATH=${PATH}
    element="element"
    add_to_path "${element}"
    [ "${PATH}" == "${element}:${OLD_GWMS_PATH}:${OLD_PATH}" ]
    [ "${GWMS_PATH}" == "${element}:${OLD_GWMS_PATH}" ]
    PATH="/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
}
