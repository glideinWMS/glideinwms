#!/usr/bin/env bats
# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0
load 'lib/bats-support/load'
load 'lib/bats-assert/load'

[[ -z "$GWMS_SOURCEDIR" ]] && GWMS_SOURCEDIR="../../creation/web_base"

setup () {
    source "$GWMS_SOURCEDIR"/utils_xml.sh
}

@test "construct_xml" {
    echo "Testing the presence of xml fields in the output..." >& 3
    run construct_xml "result"
    assert_output --partial '<?xml version="1.0"?>'
    assert_output --partial '<OSGTestResult id="glidein_startup.sh" version="4.3.1">'
    assert_output --partial '<operatingenvironment>'
    assert_output --partial '<env name="cwd">'
    assert_output --partial '<test>'
    assert_output --partial '<cmd>'
    assert_output --partial '<tStart>'
    assert_output --partial '<tEnd>'
    assert_output --partial '<result>'
    [ "$status" -eq 0 ]
}

@test "extract_parent_fname" {
    echo "Testing a non-valid parent to extract..." >& 3
    run extract_parent_fname 0
    assert_output --partial "Unknown"
    [ "$status" -eq 0 ]
    echo "Testing a valid parent to extract with exitcode = 0 ..." >& 3
    filename="otrx_output.xml"
    touch $filename
    echo "<?xml version=\"1.0\"?><OSGTestResult id=\"glidein_startup.sh\" version=\"4.3.1\">" > $filename
    run extract_parent_fname 0
    assert_output --partial "SUCCESS"
    [ "$status" -eq 0 ]
    echo "Testing a valid parent to extract with exitcode = 1 ..." >& 3
    run extract_parent_fname 1
    assert_output --partial "glidein_startup.sh"
    [ "$status" -eq 0 ]
}

@test "extract_parent_xml_detail" {
    echo "Testing a call with non-valid XML file and exit code 0..." >& 3
    run extract_parent_xml_detail 0
    assert_output --partial "<status>OK</status>"
    assert_output --partial "No detail. Could not find source XML file."
    [ "$status" -eq 0 ]
    echo "Testing a call with non-valid XML file and exit code 1.." >& 3
    run extract_parent_xml_detail 1
    assert_output --partial "<status>ERROR</status>"
    assert_output --partial "No detail. Could not find source XML file."
    [ "$status" -eq 0 ]
    echo "Testing a call with valid XML file and exit code 0..." >& 3
    filename="otrx_output.xml"
    touch $filename
    echo "<metric name=\"trial\">Content</metric>" > $filename
    run extract_parent_xml_detail 0
    assert_output --partial "<status>OK</status>"
    assert_output --partial "<metric name=\"trial\">Content</metric>"
    [ "$status" -eq 0 ]
    echo "Testing a call with non-valid XML file and exit code 1..." >& 3
    echo "<?xml version=\"1.0\"?><OSGTestResult id=\"glidein_startup.sh\" version=\"4.3.1\">" > $filename
    echo "<detail>Trial</detail>\n" >> $filename
    run extract_parent_xml_detail 1
    assert_output --partial "<status>ERROR</status>"
    assert_output --partial "<metric name=\"TestID\""
    assert_output --partial "uri=\"local\">glidein_startup.sh</metric>"
    [ "$status" -eq 0 ]
}

@test "basexml2simplexml" {
    echo "Testing the addition of env tags..." >& 3
    argument="<trial>Content</trial>"
    run basexml2simplexml ${argument}
    assert_output --partial "${argument}"
    assert_output --partial  "<env name=\"client_name\">"
    assert_output --partial  "<env name=\"client_group\">"
    assert_output --partial  "<env name=\"user\">"
    assert_output --partial  "<env name=\"arch\">"
    assert_output --partial  "<env name=\"hostname\">"
    [ "$status" -eq 0 ]
}

@test "simplexml2longxml" {
    echo "Testing the addition of env tags..." >& 3
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
    [ "$status" -eq 0 ]
}

@test "create_xml" {
    echo "Testing the creation of an xml element with all tags..." >& 3
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
    echo "Testing the creation of an xml header..." >& 3
    run create_xml -h
    assert_output --partial "<?xml version=\"1.0\"?>"
    echo "Testing the creation of an xml tail..." >& 3
    run create_xml -t
    assert_output --partial "</OSGTestResult>"
    echo "Testing the creation of an inner xml (with spaces)..." >& 3
    run create_xml -s 5 OSG
    assert_output --partial "     <OSGTestResult version=\"4.3.1\"></OSGTestResult>"
}

teardown() {
    rm -f "${filename}"
}
