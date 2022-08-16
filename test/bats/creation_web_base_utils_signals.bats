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


@test "trap_with_arg" {
    run trap_with_arg 'on_die' SIGINT
    # Todo: How  to check if handler correctly assigned?
    [ "$output" == "" ]
    [ "status" == 0]
}
