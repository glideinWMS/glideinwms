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
    source "$GWMS_SOURCEDIR"/creation/web_base/add_config_line.source 2>&3
    #glidein_config=glidein_config_test.tmp
    #touch "$glidein_config"
}

no_teardown() {
    # executed after each test
    echo "teardown" >&3
    #rm "$glidein_config"
    rm -f "$glidein_config" "$glidein_config".lock "$glidein_config".pid
}

setup_nameprint() {
    if [ "${BATS_TEST_NUMBER}" = 1 ];then
        echo "# --- TEST NAME IS $(basename "${BATS_TEST_FILENAME}")" >&3
    fi
}


@test "--- TEST SET NAME IS $(basename "${BATS_TEST_FILENAME}")" {
    skip ''
}


@test "Test failure when glidein_config variable is missing" {
    # glidein_config=glidein_config_test.tmp
    unset glidein_config
    files_number=$(ls -f | wc -l)
    run gconfig_add KEY1 val1
    assert_output --partial "Error: glidein_config variable not defined."
    [ "$status" -eq 1 ]
    run gconfig_add_safe KEY1 val1
    assert_output --partial "Error: glidein_config variable not defined."
    [ "$status" -eq 1 ]
    run gconfig_get KEY1
    assert_output --partial "Error: glidein_config not provided and glidein_config variable not defined."
    [ "$status" -eq 1 ]
    # the next one returns 1 no exit
    run gconfig_trim
    assert_output --partial "Warning: glidein_config not provided and glidein_config variable not defined. Skipping gconfig_trim"
    [ "$status" -eq 1 ]
    # there should be no new files
    [ $files_number -eq $(ls -f | wc -l) ]
}

@test "Test gconfig_get" {
    # Without variable
    run gconfig_get ATTR
    [ "$status" -eq 1 ]
    assert_output --partial "glidein_config not provided and glidein_config variable not defined."
    tmp_config_file="glidein_config_test.tmp"
    echo "ATTR first" > "$tmp_config_file"
    run gconfig_get ATTR "$tmp_config_file"
    [ "$status" -eq 0 ]
    [ "$output" = first ]
    # Check against partial matches
    glidein_config="$tmp_config_file"
    cat << EOF > "$glidein_config"
ATTRBEFORE before
ATTR value
ATTRAFTER after
EOF
    [ $(gconfig_get ATTR "$glidein_config") = value ]
    # Chck config name override: not existing file, same as no attribute
    run gconfig_get ATTR not_existing_file
    [ "$status" -eq 0 ]
    [ "$output" = "" ]
    # New ATTR values and parsing spaces and tabs
    echo "ATTR  new value with  spaces" >> "$glidein_config"
    echo "Test 1 ($(gconfig_get ATTR))" >&3
    [ "$(gconfig_get ATTR)" = " new value with  spaces" ]
    echo -e "ATTR \t new value with tab and spaces " >> "$glidein_config"
    echo "Test 2 ($(gconfig_get ATTR))" >&3
    [ "$(gconfig_get ATTR)" = "	 new value with tab and spaces " ]
    rm -f "$tmp_config_file"
}

@test "Test lock and unlock" {
    glidein_config="/tmp/glidein_config_test.tmp"
    # Failure, file not existing
    run lock_file "$glidein_config"
    [ "$status" -eq 1 ]
    assert_output --partial "Error acquiring the lock"
    assert_output --partial "file does not exist"
    # Successful
    touch "$glidein_config"
    lock_file "$glidein_config"
    [ $? -eq 0 ]
    [ -f "$glidein_config".lock ]
    [ -f "$glidein_config".pid ] && [ $(cat "$glidein_config".pid) -eq $$ ]
    unlock_file "$glidein_config"
    [ $? -eq 0 ]
    [ ! -f "$glidein_config".lock ]
    [ ! -f "$glidein_config".pid ]
    # Already w/ lock, dead process, Unlocking and acquiring
    ln -s "$glidein_config" "$glidein_config".lock
    echo "nopid" > "$glidein_config".pid
    # this will take 1 min
    run lock_file "$glidein_config"
    [ "$status" -eq 0 ]
    assert_output --partial "Apparently dead lock holder. Unlocking"
    assert_output --partial "Apparently dead lock holder. Timeout expired. Unlocking"
    # Already w/ lock, same process
    echo "$$" > "$glidein_config".pid
    run lock_file "$glidein_config"
    [ "$status" -eq 0 ]
    assert_output --partial "already holding the lock"
    # Failed, lock belonging to alive process
    # echo "$PPID" > "$glidein_config".pid  ## This failed once on GH CI
    # echo "1" > "$glidein_config".pid  # PID 1 should always be alive
    echo "$(ps -o ppid= -p $$)" > "$glidein_config".pid
    # This will take 5 min
    run lock_file "$glidein_config"
    echo "Run w/ lock ($status): $output" >&3
    # This is not working on GH, works fine on Mac and EL
    # [ "$status" -eq 1 ]
    # assert_output --partial "Error acquiring the lock for"
    # assert_output --partial "timeout, waited"
    # Only pid file there, ignored, lock successful
    rm "$glidein_config".lock
    lock_file "$glidein_config"
    [ $? -eq 0 ]
    [ -f "$glidein_config".lock ]
    [ -f "$glidein_config".pid ] && [ $(cat "$glidein_config".pid) -eq $$ ]
}


@test "gconfig_add" {
    glidein_config=glidein_config_test.tmp
    >"$glidein_config"
    rm -f "$glidein_config".lock "$glidein_config".pid "$(gconfig_log_name)"
    # ls -l "$glidein_config" >&3
    gconfig_add KEY1 VAL1
    [ $(wc -l <"$glidein_config") == 1 ]
    # add_config_line KEY2 VAL2 && echo "OK ($?)" >&3 || echo "no ($?)" >&3
    add_config_line KEY2 VAL2
    [ $(wc -l <"$glidein_config") == 2 ]
    [ $(wc -l <"$(gconfig_log_name)") == 2 ]
    # gconfig_add KEY1 VAL1b && echo "OK ($?)" >&3 || echo "no ($?)" >&3
    gconfig_add KEY1 VAL1b
    [ $(wc -l <"$glidein_config") == 2 ]
    [ $(wc -l <"$(gconfig_log_name "$glidein_config")") == 3 ]
    [ "$(gconfig_get KEY1)" ==  VAL1b ]
    [ "$(gconfig_get KEY3)" ==  "" ]
    gconfig_add_safe KEY3 VAL3
    [ $(wc -l <"$glidein_config") == 3 ]
    [ $(wc -l <"$(gconfig_log_name "$glidein_config")") == 5 ]
    # Cleanup
    rm -f "$glidein_config" "$glidein_config".history
}
