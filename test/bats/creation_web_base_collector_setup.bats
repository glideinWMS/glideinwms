#!/usr/bin/env bats

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

load 'lib/bats-support/load'
load 'lib/bats-assert/load'

#load 'helper'


[[ -z "$GWMS_SOURCEDIR" ]] && GWMS_SOURCEDIR=../..


setup () {
    source compat.bash
    #echo "PWD: `pwd`, $PWD" >&3
    #echo "LS: `ls -l "$GWMS_SOURCEDIR"/creation/web_base/`" >&3
    #echo "LSF: `ls -l "$GWMS_SOURCEDIR"/creation/web_base/collector_setup.sh`" >&3

    glidein_config=fixtures/glidein_config
    # export GLIDEIN_QUIET=true
    source "$GWMS_SOURCEDIR"/creation/web_base/collector_setup.sh 2>&3
    load 'mock_gwms_logs'
    #echo "ENV: `env --help`" >&3
    #echo "ENVg: `genv --help`" >&3
    #echo "ENVmy: `myenv --help`" >&3

#    # Mock robust_realpath intercepting some inputs
#    # used by singularity_update_path, singularity_setup_inside_env
#    eval "$(echo "robust_realpath_orig()"; declare -f robust_realpath | tail -n +2 )"
#    echo "Runnig setup" >&3
#    robust_realpath() { robust_realpath_mock "$@"; }

}

setup_nameprint() {
    if [ "${BATS_TEST_NUMBER}" = 1 ];then
        echo "# --- TEST NAME IS $(basename "${BATS_TEST_FILENAME}")" >&3
    fi
}


@test "Test replace_range" {
    # Since we replace dash and look for "sock" and numbers, these are the elements that may cause trouble
    # Testing part 1 of sed expression (no shared port)
    coll_addr="collhost.domain.edu"
    [ "$(replace_range "$coll_addr")" = "collhost.domain.edu" ]
    coll_addr="collhost.domain.edu:9618"
    [ "$(replace_range "$coll_addr")" = "collhost.domain.edu:9618" ]
    coll_addr="collhost.domain.edu:9618-9628"
    [ "$(replace_range "$coll_addr")" = "collhost.domain.edu:\$RANDOM_INTEGER(9618,9628)" ]
    coll_addr="coll-host.domain.edu:9618-9628"
    [ "$(replace_range "$coll_addr")" = "coll-host.domain.edu:\$RANDOM_INTEGER(9618,9628)" ]
    # Testing part 2 of sed expression, synful string
    coll_addr="host.domain:9618?sock=collect10"
    [ "$(replace_range "$coll_addr")" = "host.domain:9618?sock=collect10" ]
    coll_addr="host.domain:9618?sock=collect10-20"
    [ "$(replace_range "$coll_addr")" = "host.domain:9618?sock=collect\$RANDOM_INTEGER(10,20)" ]
    coll_addr="host.domain:9618?var1=val1&sock=collect10-20&var2=val2"
    [ "$(replace_range "$coll_addr")" = "host.domain:9618?var1=val1&sock=collect\$RANDOM_INTEGER(10,20)&var2=val2" ]
    coll_addr="host.domain:9618?var1=val1&sock=collect10-20&var2=val2-6"
    [ "$(replace_range "$coll_addr")" = "host.domain:9618?var1=val1&sock=collect\$RANDOM_INTEGER(10,20)&var2=val2-6" ]
    coll_addr="my-host.domain:9618?var1=val1&sock=collect10-20&var2=val2-6"
    [ "$(replace_range "$coll_addr")" = "my-host.domain:9618?var1=val1&sock=collect\$RANDOM_INTEGER(10,20)&var2=val2-6" ]
    coll_addr="my_host.do-main:9618?var1=val1-5&sock=collect10-20&var2=val2-6"
    [ "$(replace_range "$coll_addr")" = "my_host.do-main:9618?var1=val1-5&sock=collect\$RANDOM_INTEGER(10,20)&var2=val2-6" ]
    coll_addr="my-host.domain:9618?var1=val1&sock=collect10-20&var2=val2-6"
    [ "$(replace_range "$coll_addr")" = "my-host.domain:9618?var1=val1&sock=collect\$RANDOM_INTEGER(10,20)&var2=val2-6" ]
    coll_addr="host.domain:9618?var1=val1&sock=my5collect30-50"
    [ "$(replace_range "$coll_addr")" = "host.domain:9618?var1=val1&sock=my5collect\$RANDOM_INTEGER(30,50)" ]
    coll_addr="host.domain:9618?sockvar1=val1-5&sock=my5collect30-50"
    [ "$(replace_range "$coll_addr")" = "host.domain:9618?sockvar1=val1-5&sock=my5collect\$RANDOM_INTEGER(30,50)" ]
    coll_addr="host.domain:9618?varsock=val1-5&sock=my5collect30-50"
    [ "$(replace_range "$coll_addr")" = "host.domain:9618?varsock=val1-5&sock=my5collect\$RANDOM_INTEGER(30,50)" ]
    # TODO: verify if dash is allowed or not. Uncomment below and change replace_range if it is 
    coll_addr="host.domain:9618?var1=val1&sock=my-5collect30-50"
    echo $(replace_range "$coll_addr") >&3
    # THIS will fail
    #[ "$(replace_range "$coll_addr")" = "host.domain:9618?var1=val1&sock=my-5collect\$RANDOM_INTEGER(30,50)" ]
}
