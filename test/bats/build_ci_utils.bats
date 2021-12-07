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
    # on the Mac or some Linux /tmp is asymlink to /private/tmp
    [ "$output" == "/tmp/output" ] || [ "$output" == "/private/tmp/output" ]
    [ "$status" -eq 0 ]
    popd
}


@test "test_setup_python_venv" {
    skip
    # setup_python_venv
}


@test "test_get_source_directories" {
    # .,./factory/,./factory/tools,./frontend,./frontend/tools,./install,./install/services,./lib,./tools,./tools/lib
    result1=".,./factory/,./factory/tools,./frontend,./frontend/tools,./install,./lib"
    result1="${result1},./tools,./tools/lib"
    result2="/p/w,/p/w/factory/,/p/w/factory/tools,/p/w/frontend,/p/w/frontend/tools,/p/w/install"
    result2="${result2},/p/w/lib,/p/w/tools,/p/w/tools/lib"
    echo "$sources"
    # by default it uses the current directory as prefix (.), as in result1
    run get_source_directories
    [ "$output" == "$result1" ]
    [ "$status" -eq 0 ]
    run get_source_directories /p/w
    [ "$output" == "$result2" ]
    [ "$status" -eq 0 ]
}

@test "test_mail_init" {
    #mail_init
    run mail_init
    [ "$output" == " WARNING: Email file not provided. Skipping it" ]
    [ "$status" -eq 0 ]
    tmp_file=/tmp/gwms_bats.$$.txt
    run mail_init "${tmp_file}"
    #[ "${EMAIL_FILE}" == "${tmp_file}" ]
    [ "$output" == "" ]
    [ "$status" -eq 0 ]
    [ -f "${tmp_file}" ]
    [ "$(cat "${tmp_file}")" == "<body>" ]
    # cleanup
    rm "${tmp_file}"
}

@test "test_mail_add" {
    tmp_file=/tmp/gwms_bats.$$.txt
    # cleanup if the file is there
    rm -f "${tmp_file}" || true
    mail_add
    [ ! -f "${tmp_file}" ]
    mail_init "${tmp_file}"
    mail_add "Last line"
    [ -f "${tmp_file}" ]
    run cat "${tmp_file}"
    [ "$status" -eq 0 ]
    # negative indexes require bash 4.3 (not on Mac)
    [ "${lines[${#lines[@]}-1]}" == "Last line" ]
    # cleanup
    rm "${tmp_file}"
}

@test "test_mail_close" {
    tmp_file=/tmp/gwms_bats.$$.txt
    # cleanup if the file is there
    rm -f "${tmp_file}" || true
    mail_init "${tmp_file}"
    mail_add "<p>Content line</p>"
    mail_close
    [ -f "${tmp_file}" ]
    # using tidy to check if the HTML file is OK: http://www.html-tidy.org/
    if command -v tidy &> /dev/null; then
        # Fail if there are errors
        ! tidy -eq "${tmp_file}" | grep "Error:"
        # There could be more strict checks. Normally there are 2 warnings (title and doctype missing)
        # not closed tags are OK in HTML
    fi
    echo "${tmp_file}"
    run cat "${tmp_file}"
    [ "$status" -eq 0 ]
    # negative indexes require bash 4.3 (not on Mac)
    [ "${lines[${#lines[@]}-1]}" == "</body>" ]
    # cleanup
    rm "${tmp_file}"
}

@test "test_mail_send" {
    skip
}
