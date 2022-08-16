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

@test "construct_xml" {
    run construct_xml "result"
    echo "$output" >& 3
    # Todo: How  to check if handler correctly assigned?
    assert_output --partial '<?xml version="1.0"?>'
    [ "$status" -eq 0 ]
}

@test "extract_parent_fname" {
    run extract_parent_fname 0
    assert_output --partial "Unknown"
    [ "$status" -eq 0 ]
    touch "otrx_output.xml"
    echo "<?xml version=\"1.0\"?><OSGTestResult id=\"glidein_startup.sh\" version=\"4.3.1\">" > otrx_output.xml
    run extract_parent_fname 0
    assert_output --partial "SUCCESS"
    [ "$status" -eq 0 ]
    run extract_parent_fname 1
    assert_output --partial "glidein_startup.sh"
    [ "$status" -eq 0 ]
}

@test "extract_parent_xml_detail" {
    run extract_parent_xml_detail 0
    assert_output --partial "<status>OK</status>"
    assert_output --partial "No detail. Could not find source XML file."
    [ "$status" -eq 0 ]
    run extract_parent_xml_detail 1
    assert_output --partial "<status>ERROR</status>"
    assert_output --partial "No detail. Could not find source XML file."
    [ "$status" -eq 0 ]
    touch "otrx_output.xml"
    echo "<metric name=\"trial\">Content</metric>" > otrx_output.xml
    run extract_parent_xml_detail 0
    assert_output --partial "<status>OK</status>"
    assert_output --partial "<metric name=\"trial\">Content</metric>"
    [ "$status" -eq 0 ]
    echo "<?xml version=\"1.0\"?><OSGTestResult id=\"glidein_startup.sh\" version=\"4.3.1\">" > otrx_output.xml
    echo "<detail>Trial</detail>\n" >> otrx_output.xml
    run extract_parent_xml_detail 1
    assert_output --partial "<status>ERROR</status>"
    assert_output --partial "<metric name=\"TestID\""
    assert_output --partial "uri=\"local\">glidein_startup.sh</metric>"
    [ "$status" -eq 0 ]
}

@test "basexml2simplexml" {
    argument="<trial>Content</trial>"
    run basexml2simplexml ${argument}
    assert_output --partial "${argument}"
    assert_output --partial  "<env name=\"client_name\">"
    assert_output --partial  "<env name=\"client_group\">"
    assert_output --partial  "<env name=\"user\">"
    assert_output --partial  "<env name=\"arch\">"
    assert_output --partial  "<env name=\"hostname\">"
    echo "$output" >& 3
    [ "$status" -eq 0 ]
}

@test "simplexml2longxml" {
    argument="<trial>Content</trial>"
    run simplexml2longxml ${argument}
    assert_output --partial "${argument}"
    assert_output --partial  "<env name=\"glidein_factory\">"
    assert_output --partial  "<env name=\"glidein_name\">"
    assert_output --partial  "<env name=\"glidein_entry\">"
    assert_output --partial  "<env name=\"condorg_cluster\">"
    assert_output --partial  "<env name=\"condorg_subcluster\">"
    assert_output --partial  "<env name=\"glidein_credential_id\">"
    assert_output --partial  "<env name=\"condorg_schedd\">"
    echo "$output" >& 3
    [ "$status" -eq 0 ]
}

@test "create_xml" {
    run create_xml OSG { oe { e --name "Trial" "Trial" t { c "Trial" tS "Trial" tE "Trial" r { s "Trial" m --name "Trial" --ts "Trial" --uri "Trial" "Trial" } d "Trial" } "Trial" } }
    assert_output --partial "<?xml version=\"1.0\"?>"
    assert_output --partial "<OSGTestResult version=\"4.3.1\">"
    assert_output --partial "<operatingenvironment>"
    assert_output --partial "<env name=\"Trial\">Trial</env>"
    assert_output --partial "<test>"
    assert_output --partial "<cmd>Trial</cmd>"
    assert_output --partial "<tStart>Trial</tStart>"
    assert_output --partial "<tEnd>Trial</tEnd>"
    assert_output --partial "<result>"
    assert_output --partial "<status>Trial</status>"
    assert_output --partial "<metric name=\"Trial\" ts=\"Trial\" uri=\"Trial\">Trial</metric>"
    assert_output --partial "<detail>Trial</detail>"
    assert_output --partial "</detail>"
    assert_output --partial "</result>"
    assert_output --partial "Trial"
    assert_output --partial "</test>"
    assert_output --partial "</operatingenvironment>"
    assert_output --partial "</OSGTestResult>"
    [ "$status" -eq 0 ]
    run create_xml -h
    assert_output --partial "<?xml version=\"1.0\"?>"
    run create_xml -t
    assert_output --partial "</OSGTestResult>"
    run create_xml -s 5 OSG
    assert_output --partial "     <OSGTestResult version=\"4.3.1\"></OSGTestResult>"
}

teardown() {
    rm -f otrx_output.xml
}
