#!/usr/bin/env bats
# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0
load 'lib/bats-support/load'
load 'lib/bats-assert/load'

[[ -z "$GWMS_SOURCEDIR" ]] && GWMS_SOURCEDIR="../../creation/web_base"

setup () {
    source "$GWMS_SOURCEDIR"/utils_gs_tarballs.sh
    source "$GWMS_SOURCEDIR"/utils_log.sh
    source "$GWMS_SOURCEDIR"/get_id_selectors.source
}

#mock
glidein_exit(){
    echo "$1"
    exit 1
}

@test "get_untar_subdir" {
    echo "Testing the absence of 'UNTAR_CFG_FILE' in glidein_config..." >& 3
    id="main"
    fname="/tmp/file"
    glidein_config="glidein_config"
    touch "${glidein_config}"
    run get_untar_subdir "${id}" "${fname}"
    assert_output --partial "Error, cannot find 'UNTAR_CFG_FILE' in glidein_config."
    [ "$status" -eq 1 ]
    echo "Testing the case of untar empty directory..." >& 3
    file="/tmp/trial"
    touch "${file}"
    echo "UNTAR_CFG_FILE ${file}" > "${glidein_config}"
    run get_untar_subdir "${id}" "${fname}"
    assert_output --partial "Error, untar dir for"
    [ "$status" -eq 1 ]
    # TODO: Handle the case of correct directory
}

@test "fixup_condor_dir" {
    echo "Testing the case of condor tarballs that do not need to be fixed..." >& 3
    gs_id_work_dir="/tmp/gs/"
    mkdir "${gs_id_work_dir}"
    mkdir "${gs_id_work_dir}/condor"
    mkdir "${gs_id_work_dir}/condor/condor_1/"
    mkdir "${gs_id_work_dir}/condor/condor_2/"
    mkdir "${gs_id_work_dir}/condor/condor_3/"
    run fixup_condor_dir
    assert_output --partial "Condor tarball does not need to be fixed"
    echo "Testing the case of condor tarballs that needs to be fixed..." >& 3
    rm -rf "${gs_id_work_dir}/condor/condor_3/"
    run fixup_condor_dir
    # assert_output --partial "Fixing directory structure of condor tarball"
    # printf not working
}

teardown() {
    rm -rf "${gs_id_work_dir}"
    rm -f "${glidein_config}"
    rm -f "${file}"
    rm -f "${fname}"
}
