#!/usr/bin/env bats
# On the Mac, installed w/ Homebrew
#load '/usr/local/lib/bats-support/load.bash'
#load '/usr/local/lib/bats-assert/load.bash'
load 'lib/bats-support/load'
load 'lib/bats-assert/load'

[[ -z "$GWMS_SOURCEDIR" ]] && GWMS_SOURCEDIR=../..

setup() {
    # executed before each test
    source compat.bash
    source "$GWMS_SOURCEDIR"/build/ci/utils.sh 2>&3
}

no_teardown() {
    # executed after each test
    echo "teardown" >&3
}


@test "test_loginfo" {
    filename=PERFIX
    VERBOSE=
    run loginfo "Message on verbose"
    [ "$output" == "" ]
    [ "$status" -eq 0 ]
    VERBOSE=yes
    run loginfo "Message on verbose"
    [ "$output" == "$filename INFO: Message on verbose" ]
    [ "$status" -eq 0 ]
}


@test "test_logexit" {
    filename=PERFIX
    run logexit "This should be 1"
    [ "$output" == "$filename ERROR: This should be 1" ]
    [ "$status" -eq 1 ]
    run logexit "This should be 2" 2
    [ "$output" == "$filename ERROR: This should be 2" ]
    [ "$status" -eq 2 ]
}


@test "test_robust_realpath" {
    skip
    # function moved to runtest.sh
    pushd /tmp
    run robust_realpath output
    [ "$output" == "/tmp/output" ]
    [ "$status" -eq 0 ]
    popd
}


@test "test_setup_python_venv" {
    skip
    # setup_python_venv
}


@test "test_get_source_directories" {
    # .,./factory/,./factory/tools,./frontend,./frontend/tools,./install,./install/services,./lib,./tools,./tools/lib
    result1=".,./factory/,./factory/tools,./frontend,./frontend/tools,./install,./install/services,./lib"
    result1="${result1},./tools,./tools/lib"
    result2="/p/w,/p/w/factory/,/p/w/factory/tools,/p/w/frontend,/p/w/frontend/tools,/p/w/install"
    result2="${result2},/p/w/install/services,/p/w/lib,/p/w/tools,/p/w/tools/lib"
    echo "$sources"
    run get_source_directories
    [ "$output" == "$result1" ]
    [ "$status" -eq 0 ]
    run get_source_directories /p/w
    [ "$output" == "$result2" ]
    [ "$status" -eq 0 ]
}
