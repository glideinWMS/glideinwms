#!/usr/bin/env bats
# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0
load 'lib/bats-support/load'
load 'lib/bats-assert/load'

[[ -z "$GWMS_SOURCEDIR" ]] && GWMS_SOURCEDIR="../../creation/web_base"

setup () {
    source "$GWMS_SOURCEDIR"/utils_gs_tarballs.sh
    source "$GWMS_SOURCEDIR"/utils_io.sh
    source "$GWMS_SOURCEDIR"/get_id_selectors.source
}

#mock
glidein_exit(){
    echo "$1"
    exit 1
}

@test "get_untar_subdir" {
    id="main"
    fname="file"
    touch glidein_config
    run get_untar_subdir ${id} ${fname}
    assert_output --partial "Error, cannot find 'UNTAR_CFG_FILE' in glidein_config."
    [ "$status" -eq 1 ]
    echo "$output" >& 3
    file="trial"
    touch ${file}
    echo "UNTAR_CFG_FILE ${file}" > glidein_config
    run get_untar_subdir ${id} ${fname}
    echo "$output" >& 3
    assert_output --partial "Error, untar dir for"
     [ "$status" -eq 1 ]
    rm glidein_config
    rm ${file}
}
