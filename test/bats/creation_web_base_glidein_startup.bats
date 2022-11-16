#!/usr/bin/env bats
# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0
load 'lib/bats-support/load'
load 'lib/bats-assert/load'

[[ -z "$GWMS_SOURCEDIR" ]] && GWMS_SOURCEDIR="../../creation/web_base"

setup(){
    source "$GWMS_SOURCEDIR"/utils_gs_tarballs.sh
    source "$GWMS_SOURCEDIR"/utils_log.sh
    source "$GWMS_SOURCEDIR"/utils_params.sh
    source "$GWMS_SOURCEDIR"/utils_signals.sh
    source "$GWMS_SOURCEDIR"/utils_xml.sh
    source "$GWMS_SOURCEDIR"/utils_crypto.sh
    source "$GWMS_SOURCEDIR"/utils_gs_http.sh
    source "$GWMS_SOURCEDIR"/utils_gs_filesystem.sh
    source "$GWMS_SOURCEDIR"/utils_gs_log.sh
    source "$GWMS_SOURCEDIR"/logging_utils.source
    source "$GWMS_SOURCEDIR"/glidein_startup.sh
    source "$GWMS_SOURCEDIR"/add_config_line.source
    source "$GWMS_SOURCEDIR"/glidein_paths.source
    source ../../build/ci/utils.sh
}

@test "do_start_all" {
    echo "Testing the spawning of 5 glideins..." >& 3
    # exporting GWMS_SOURCEDIR in order to be visible to the children
    GWMS_SOURCEDIR="../../../creation/web_base"
    export GWMS_SOURCEDIR
    num_glideins=5
    run do_start_all ${num_glideins}
    for i in ${num_glideins}; do
        assert_output --partial "Starting glidein ${i} in glidein_dir${i}"
        [ -d "glidein_dir${i}" ]
    done
    assert_output --partial "Started multiple glideins"
    [ "$status" -eq 0 ]
    # TODO: Missing case of starting multi-glidein using launcher launchall
}

@test "print_header" {
    echo "Testing the printing in case of debug set..." >& 3
    set_debug=1
    run print_header ""
    assert_output --partial "Initial environment"
    echo "Testing the printing in case of debug not set..." >& 3
    set_debug=0
    run print_header ""
    ! assert_output --partial "Initial environment"
}

@test "spawn_multiple_glideins" {
    echo "Testing the spawning of multiple glideins..." >& 3
    GWMS_SOURCEDIR="../../../creation/web_base"
    export GWMS_SOURCEDIR
    multi_glidein=2
    multi_glidein_restart=""
    run spawn_multiple_glideins
    assert_output --partial "------ Multi-glidein parent waiting for child processes"
    assert_output --partial "------ Exiting multi-glidein parent ----------"
    [ "$status" -eq 0 ]
    echo "Testing the conditions to be chckedd to not spawn glideins..." >& 3
    multi_glidein=""
    run spawn_multiple_glideins
    [ "$output" == "" ]
    [ "$status" -eq 0 ]
    multi_glidein=2
    multi_glidein_restart="yes"
    run spawn_multiple_glideins
    [ "$output" == "" ]
    [ "$status" -eq 0 ]
}

@test "setup_OSG_Globus" {
    echo "Testing the setup.sh presence with globus path present..." >& 3
    OSG_GRID=/tmp/setup_OSG
    mkdir "${OSG_GRID}"
    echo "echo setup" > "${OSG_GRID}"/setup.sh
    GLOBUS_PATH="location"
    run setup_OSG_Globus
    [ "$output" == "setup" ]
    [ "$status" -eq 0 ]
    echo "Testing the cp_1.sh presence with globus path present..." >& 3
    rm "${OSG_GRID}"/setup.sh
    GLITE_LOCAL_CUSTOMIZATION_DIR=/tmp/setup_OSG
    echo "echo cp_1" > "${GLITE_LOCAL_CUSTOMIZATION_DIR}"/cp_1.sh
    run setup_OSG_Globus
    [ "$output" == "cp_1" ]
    [ "$status" -eq 0 ]
    echo "Testing the globus path absence and globus location presence with the globus-user-env.sh file..." >& 3
    GLOBUS_PATH=""
    GLOBUS_LOCATION="/tmp/setup_OSG"
    mkdir "${GLOBUS_LOCATION}"/etc
    echo "echo globus-user-env" > "${GLOBUS_LOCATION}/etc/globus-user-env.sh"
    run setup_OSG_Globus
    [ "$status" -eq 0 ]
    assert_output --partial "cp_1"
    assert_output --partial "globus-user-env"
    rm "${GLOBUS_LOCATION}/etc/globus-user-env.sh"
    echo "Testing the globus path absence and globus location presence without the globus-user-env.sh file..." >& 3
    run setup_OSG_Globus
    [ "$status" -eq 0 ]
    assert_output --partial "GLOBUS_PATH not defined and ${GLOBUS_LOCATION}/etc/globus-user-env.sh does not exist."
    assert_output --partial "Continuing like nothing happened"
    GLOBUS_LOCATION=""
    echo "Testing the globus path and globus location absence..." >& 3
    run setup_OSG_Globus
    assert_output --partial "GLOBUS_LOCATION not defined and could not guess it."
    assert_output --partial "Looked in:"
    assert_output --partial "/opt/globus/etc/globus-user-env.sh"
    assert_output --partial "/osgroot/osgcore/globus/etc/globus-user-env.sh"
    assert_output --partial "Continuing like nothing happened"
    assert_output --partial "GLOBUS_PATH not defined and ${GLOBUS_LOCATION}/etc/globus-user-env.sh does not exist."
    assert_output --partial "Continuing like nothing happened"
    [ "$status" -eq 0 ]
}

#mock
early_glidein_failure() {
    echo "$1"
    exit 1
}

@test "create_glidein_config" {
    glidein_config="glidein_config"
    touch ${glidein_config}
    # if not a root user
    if [ "$EUID" -ne 0 ]; then
        echo "Testing the glidein_config file with no write permissions..." >& 3
        chmod 000 ${glidein_config}
        run create_glidein_config
        [ "$status" -eq 1 ]
        assert_output --partial "${PWD}/${glidein_config}: Permission denied"
        assert_output --partial "Could not create '${PWD}/${glidein_config}'"
    fi
    echo "Testing the glidein_config file with write permissions..." >& 3
    chmod 777 ${glidein_config}
    run create_glidein_config
    echo "$output" >& 3
    [ "$status" -eq 0 ]
    grep -Fxq "# --- glidein_startup vals ---" ${glidein_config}
    grep -Fxq "# --- User Parameters ---" ${glidein_config}
}


teardown() {
    glidein_config="glidein_config"
    rm -rf /tmp/setup_OSG
    rm -f ${glidein_config}
    rm -rf glidein_dir*/
}
