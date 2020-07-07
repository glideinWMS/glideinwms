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
    source "$GWMS_SOURCEDIR"/build/jenkins/utils.sh 2>&3
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
    [ "$output" == "Message on verbose" ]
    [ "$status" -eq 0 ]
}


@test "test_name" {
    filename=PERFIX
    run logexit "This should be 1"
    [ "$output" == "$filename ERROR: This should be 1" ]
    [ "$status" -eq 1 ]
    run logexit "$filename ERROR: This should be 2" 2
    [ "$output" == "This should be 2" ]
    [ "$status" -eq 2 ]
}


@test "test_robust_realpath" {
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
    retult1=".,./factory/,./factory/tools,./frontend,./frontend/tools,./install,./install/services,./lib"
    retult1="${retult1},./tools,./tools/lib"
    retult2="/p/w,/p/w/factory/,/p/w/factory/tools,/p/w/frontend,/p/w/frontend/tools,/p/w/install"
    retult2="${retult2},/p/w/install/services,/p/w/lib,/p/w/tools,/p/w/tools/lib"
    echo "$sources"
    run get_source_directories /p/w
    [ "$output" == "$retult1" ]
    [ "$status" -eq 0 ]
    run get_source_directories /p/w
    [ "$output" == "$retult2" ]
    [ "$status" -eq 0 ]
}
