#!/usr/bin/env bats

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

# On the Mac, installed w/ Homebrew
#load '/usr/local/lib/bats-support/load.bash'
#load '/usr/local/lib/bats-assert/load.bash'
load 'lib/bats-support/load'
load 'lib/bats-assert/load'

[[ -z "$GWMS_SOURCEDIR" ]] && GWMS_SOURCEDIR=../..

setup() {
    # executed before each test
    source compat.bash
    gconfig_path="$GWMS_SOURCEDIR"/creation/web_base/gconfig.py
    #source "$GWMS_SOURCEDIR"/creation/web_base/add_config_line.source 2>&3
    #glidein_config=glidein_config_test.tmp
    #touch "$glidein_config"
}

no_teardown() {
    # executed after each test
    echo "teardown" >&3
    #rm "$glidein_config"
}

setup_nameprint() {
    if [ "${BATS_TEST_NUMBER}" = 1 ];then
        echo "# --- TEST NAME IS $(basename "${BATS_TEST_FILENAME}")" >&3
    fi
}


@test "--- TEST SET NAME IS $(basename "${BATS_TEST_FILENAME}")" {
    skip ''
}

# The following 2 tests repeat the test for gconfig_get in add_config_line.source
# The first is w/ python3, the second in python2
@test "Test gconfig get w/ python3" {
    PYTHON=python3
    # Without variable
    run $PYTHON "$gconfig_path" get ATTR
    echo "Test 00 ($($PYTHON "$gconfig_path" get ATTR))("$output")" >&3
    [ "$status" -eq 1 ]
    # error msg in stderr:
    assert_output --partial "Unable to locate the glidein configuration file"
    tmp_config_file="glidein_config_test.tmp"
    echo "ATTR first" > "$tmp_config_file"
    run $PYTHON "$gconfig_path" get ATTR "$tmp_config_file"
    [ "$status" -eq 0 ]
    [ "$output" = first ]
    # Check against partial matches
    glidein_config="$tmp_config_file"
    cat << EOF > "$glidein_config"
ATTRBEFORE before
ATTR value
ATTRAFTER after
EOF
    [ $($PYTHON "$gconfig_path" get ATTR "$glidein_config") = value ]
    # Check config name override: not existing file, same as no attribute (in Python exit 1)
    run $PYTHON "$gconfig_path" get ATTR not_existing_file
    echo "Test 0 ($($PYTHON "$gconfig_path" get ATTR not_existing_file))("$output")" >&3
    [ "$status" -eq 1 ]
    # $output has stdout+stderr, no: [ "$output" = "" ]
    assert_output --partial "Unable to locate the glidein configuration file"
    # New ATTR values and parsing spaces and tabs
    echo "ATTR  new value with  spaces" >> "$glidein_config"
    echo "Test 1 ($($PYTHON "$gconfig_path" get ATTR "$glidein_config"))" >&3
    [ "$($PYTHON "$gconfig_path" get ATTR "$glidein_config")" = " new value with  spaces" ]
    echo -e "ATTR \t new value with tab and spaces " >> "$glidein_config"
    echo "Test 2 ($($PYTHON "$gconfig_path" get ATTR "$glidein_config"))" >&3
    [ "$($PYTHON "$gconfig_path" get ATTR "$glidein_config")" = "	 new value with tab and spaces " ]
    rm -f "$tmp_config_file"
}

@test "Test gconfig get w/ python2" {
    PYTHON=python2
    if ! $PYTHON --version >/dev/null; then
        skip "No python2 ($PYTHON). Skipping gconfig get w/ python2"
    fi
    # Without variable
    run $PYTHON "$gconfig_path" get ATTR
    echo "Test 00 ($($PYTHON "$gconfig_path" get ATTR))("$output")" >&3
    [ "$status" -eq 1 ]
    # error msg in stderr:
    assert_output --partial "Unable to locate the glidein configuration file"
    tmp_config_file="glidein_config_test.tmp"
    echo "ATTR first" > "$tmp_config_file"
    run $PYTHON "$gconfig_path" get ATTR "$tmp_config_file"
    [ "$status" -eq 0 ]
    [ "$output" = first ]
    # Check against partial matches
    glidein_config="$tmp_config_file"
    cat << EOF > "$glidein_config"
ATTRBEFORE before
ATTR value
ATTRAFTER after
EOF
    [ $($PYTHON "$gconfig_path" get ATTR "$glidein_config") = value ]
    # Check config name override: not existing file, same as no attribute (in Python exit 1)
    run $PYTHON "$gconfig_path" get ATTR not_existing_file
    echo "Test 0 ($($PYTHON "$gconfig_path" get ATTR not_existing_file))("$output")" >&3
    [ "$status" -eq 1 ]
    # $output has stdout+stderr, no: [ "$output" = "" ]
    assert_output --partial "Unable to locate the glidein configuration file"
    # New ATTR values and parsing spaces and tabs
    echo "ATTR  new value with  spaces" >> "$glidein_config"
    echo "Test 1 ($($PYTHON "$gconfig_path" get ATTR "$glidein_config"))" >&3
    [ "$($PYTHON "$gconfig_path" get ATTR "$glidein_config")" = " new value with  spaces" ]
    echo -e "ATTR \t new value with tab and spaces " >> "$glidein_config"
    echo "Test 2 ($($PYTHON "$gconfig_path" get ATTR "$glidein_config"))" >&3
    [ "$($PYTHON "$gconfig_path" get ATTR "$glidein_config")" = "	 new value with tab and spaces " ]
    rm -f "$tmp_config_file"
}
