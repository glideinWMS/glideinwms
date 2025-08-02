#!/usr/bin/env bats

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

load 'lib/bats-support/load'
load 'lib/bats-assert/load'

#load 'helper'


[[ -z "$GWMS_SOURCEDIR" ]] && GWMS_SOURCEDIR=../..


robust_realpath_mock() {
    # intercepting some inputs
    case "$1" in
        /condor/execute/dir_29865*)  echo "/export/data1$1";;
        /export/data1/condor/execute/dir_29865*) echo "$1";;
        *) robust_realpath_orig "$1";;
    esac
}


setup() {
    source compat.bash
    # glidein_config=fixtures/glidein_config
    # export GLIDEIN_QUIET=true
    source "$GWMS_SOURCEDIR"/creation/web_base/singularity_lib.sh 2>&3
    load 'mock_gwms_logs'
    #echo "ENV: `env --help`" >&3
    #echo "ENVg: `genv --help`" >&3
    #echo "ENVmy: `myenv --help`" >&3

    # Mock robust_realpath intercepting some inputs
    # used by singularity_update_path, singularity_setup_inside_env
    eval "$(echo "robust_realpath_orig()"; declare -f robust_realpath | tail -n +2 )"
    echo "Running setup" >&3
    robust_realpath() { robust_realpath_mock "$@"; }

}


setup_nameprint() {
    if [ "${BATS_TEST_NUMBER}" = 1 ];then
        echo "# --- TEST NAME IS $(basename "${BATS_TEST_FILENAME}")" >&3
    fi
}


@test "--- TEST SET NAME IS $(basename "${BATS_TEST_FILENAME}")" {
    skip ''
}


@test "Test that bats is working with basic shell commands" {
    run bash -c "echo 'foo bar baz' | cut -d' ' -f2"
    # Do not use double brackets [[ ]] because they are conditionals and always true
    # At least for Bash <4.1. You can append || false if you must
    [ "$output" = "bar" ]
}


## Tests for dict_... functions
@test "Test dictionary values" {
    my_dict=" key 1:val1:opt1,key2:val2,key3:val3:opt3,key4,key5:,key6 :val6"
    [ "$(dict_get_val my_dict " key 1")" = "val1:opt1" ]
    [ "$(dict_get_val my_dict key2)" = "val2" ]
    [ "$(dict_get_val my_dict key3)" = "val3:opt3" ]
    [ "$(dict_get_val my_dict key4)" = "" ]
    [ "$(dict_get_val my_dict key5)" = "" ]
    [ "$(dict_get_val my_dict "key6 ")" = "val6" ]
}


@test "Test dictionary keys" {
    my_dict=" key 1:val1:opt1,key2:val2,key3:val3:opt3,key4,key5:,key6 :val6"
    for i in " key 1" key2 key3 key4 key5 "key6 "; do
        #echo "Checking <$i>" >&3
        dict_check_key my_dict "$i"
    done
}


@test "Test dictionary set" {
    my_dict=" key 1:val1:opt1,key2:val2,key3:val3:opt3,key4,key5:,key6 :val6"
    run dict_set_val my_dict key2 new2
    [[ ",$output," = *",key2:new2,"* ]] || false
    [ "$status" -eq 0 ]
    run dict_set_val my_dict " key 1"
    [[ ",$output," = *", key 1,"* ]] || false
    [ "$status" -eq 0 ]
    run dict_set_val my_dict key7 "new7 sp"
    [[ ",$output," = *",key7:new7 sp,"* ]] || false
    [ "$status" -eq 1 ]
}

dit() { echo "TEST:<$1><$2><$3>"; }

@test "Test dictionary iterator" {
    my_dict=" key 1:val1:opt1,key2:val2,key3:val3:opt3,key4,key5:,key6 :val6"
    run dict_items_iterator my_dict dit par1
    [ "${lines[0]}" = "TEST:<par1>< key 1><val1:opt1>" ]
    [ "${lines[1]}" = "TEST:<par1><key2><val2>" ]
    [ "${lines[2]}" = "TEST:<par1><key3><val3:opt3>" ]
    [ "${lines[3]}" = "TEST:<par1><key4><>" ]
    [ "${lines[4]}" = "TEST:<par1><key5><>" ]
    [ "${lines[5]}" = "TEST:<par1><key6 ><val6>" ]
    [ "$status" -eq 0 ]
}


@test "Test dictionary key iterator" {
    my_dict=" key 1:val1:opt1,key2:val2,key3:val3:opt3,key4,key5:,key6 :val6"
    run dict_keys_iterator my_dict dit par1
    [ "${lines[0]}" = "TEST:<par1>< key 1><>" ]
    [ "${lines[1]}" = "TEST:<par1><key2><>" ]
    [ "${lines[2]}" = "TEST:<par1><key3><>" ]
    [ "${lines[3]}" = "TEST:<par1><key4><>" ]
    [ "${lines[4]}" = "TEST:<par1><key5><>" ]
    [ "${lines[5]}" = "TEST:<par1><key6 ><>" ]
    [ "$status" -eq 0 ]
}


@test "Test dictionary dict_get_first" {
    my_dict=" key 1:val1:opt1,key2:val2,key3:val3:opt3,key4,key5:,key6 :val6"
    [ "$(dict_get_first my_dict key)" = " key 1" ]
    [ "$(dict_get_first my_dict)" = "val1:opt1" ]
    [ "$(dict_get_first my_dict item)" = " key 1:val1:opt1" ]
}


@test "Test dictionary dict_get_keys" {
    my_dict=" key 1:val1:opt1,key2:val2,key3:val3:opt3,key4,key5:,key6 :val6"
    [ "$(dict_get_keys my_dict)" = " key 1,key2,key3,key4,key5,key6 " ]
}


@test "Test list intersection" {
    list1="val1,val2,val3,val4,val5"
    list2="val2,val5,val6"
    list3="any"
    [ "$(list_get_intersection "$list1" "$list2")" = "val2,val5" ]
    [ "$(list_get_intersection "$list1" "$list3")" = "$list1" ]
    [ "$(list_get_intersection "$list3" "$list2")" = "$list2" ]
}


## Test for utility functions
@test "Verify uri_is_valid_file_or_remote" {
    # Remote URI
    uri_is_valid_file_or_remote http://user@host:port/path/to/file
    uri_is_valid_file_or_remote ftp://host/path/to/file
    fixture_dir=$(realpath fixtures)
    # Local or file:// - both file:// and file:/// are absolute paths
    # file fixtures/glidein_config is expected to exist
    uri_is_valid_file_or_remote fixtures/glidein_config
    uri_is_valid_file_or_remote "$fixture_dir/glidein_config"
    uri_is_valid_file_or_remote file:/"$fixture_dir/glidein_config"
    uri_is_valid_file_or_remote file://"$fixture_dir/glidein_config"
    # file fixtures/this_file_is_not_there is expected NOT to exist
    ! uri_is_valid_file_or_remote "fixtures/this_file_is_not_there"
    ! uri_is_valid_file_or_remote "$fixture_dir/this_file_is_not_there"
    ! uri_is_valid_file_or_remote "file:/$fixture_dir/this_file_is_not_there"
    ! uri_is_valid_file_or_remote "file://$fixture_dir/this_file_is_not_there"
}


## Tests for env_... functions
@test "Verify env_clear_one" {
    export TEST_VAR=testvalue
    unset GWMS_OLDENV_TEST_VAR
    [ "$TEST_VAR" = "testvalue" ]
    [ "x$GWMS_OLDENV_TEST_VAR" = "x" ]
    env_clear_one TEST_VAR
    echo "For visual inspection, TEST_VAR should be gone: `env | grep TEST_VAR`" >&3
    [ -z "${TEST_VAR+x}" ]
    [ "$GWMS_OLDENV_TEST_VAR" = "testvalue" ]
}


@test "Verify env_process_options" {
    local envoptions=
    [ "$(env_process_options $envoptions)" = "clearpaths" ]  # Default is 'clearpaths'
    [[ ",$(env_process_options clear)," = *",clearall,gwmsset,osgset,condorset,"* ]] || false  # clear substitution
    [[ ",$(env_process_options aaa,osgset)," = *",condorset,"* ]] || false  # osgset implies condorset
    [[ ",$(env_process_options aaa,osgset)," = *",gwmsset,"* ]] || false  # osgset implies gwmsset
    [ "$(env_process_options aaa,osgset,condorset)" = "aaa,osgset,condorset,gwmsset" ]  # should be the same
    echo "Should print a warning (clear+keepall):" >&3
    env_process_options clear,osgset,condorset,keepall
}


@test "Verify env_gets_cleared" {
    env_gets_cleared "command --other --cleanenv --other2"  # clearenv is there, true
    env_gets_cleared "--cleanenv"  # clearenv is there, true
    ! env_gets_cleared "testvalue --cleanenvnot"  # clearenv is not there, falase
}


@test "Verify env_clearlist" {
    VAR1=value1
    export VAR2="complex var, with_spaces"
    unset VAR3
    #export GWMS_OLDENV_VAR1=simplevar
    #export GWMS_OLDENV_VAR2="complex var, with_spaces"
    # GWMS_OLDENV_VAR3 missing on purpose
    env_clearlist VAR1,VAR2,VAR3
    [ -n "${GWMS_OLDENV_VAR1+x}" ]
    [ -n "${GWMS_OLDENV_VAR2+x}" ]
    [ "$GWMS_OLDENV_VAR2" = "complex var, with_spaces" ]
    [ -z "${GWMS_OLDENV_VAR3+x}" ]
}


@test "Verify env_restorelist" {
    unset VAR1
    unset VAR2
    unset VAR3
    export GWMS_OLDENV_VAR1=simplevar
    export GWMS_OLDENV_VAR2="complex var, with_spaces"
    unset GWMS_OLDENV_VAR3
    # GWMS_OLDENV_VAR3 missing on purpose
    env_restorelist VAR1,VAR2,VAR3
    [ -n "${VAR1+x}" ]
    [ -n "${VAR2+x}" ]
    [ "$VAR2" = "complex var, with_spaces" ]
    [ -z "${VAR3+x}" ]
}


@test "Verify env_restore" {
    # Restoring PATH, LD_LIBRARY_PATH, PYTHONPATH
    unset PATH
    unset LD_LIBRARY_PATH
    unset PYTHONPATH
    export GWMS_OLDENV_PATH="/bin:/usr/bin:path with:spaces"
    export GWMS_OLDENV_LD_LIBRARY_PATH=oldldlib
    export GWMS_OLDENV_PYTHONPATH=waspythonpath
    env_restore keepall
    echo "Path should not be here, only old: `/usr/bin/env | /usr/bin/grep PATH`" >&3
    [ -z "${PATH+x}" ]
    [ -z "${LD_LIBRARY_PATH+x}" ]
    [ -z "${PYTHONPATH+x}" ]
    env_restore clear
    # echo "Path should be back: `env | grep PATH`" >&3
    # Note that on a Mac LD_LIBRARY_PATH will not be in the env:
    # https://apple.stackexchange.com/questions/278385/environment-var-ld-library-path-weirdly-hidden-under-bash-on-mac
    echo "Path should be back <$PATH><$LD_LIBRARY_PATH><$PYTHONPATH>: `/usr/bin/env | /usr/bin/grep PATH`" >&3
    [ -n "${PATH+x}" ]
    [ -n "${LD_LIBRARY_PATH+x}" ]
    [ -n "${PYTHONPATH+x}" ]
    [ "$PATH" = "$GWMS_OLDENV_PATH" ]
    [ "$LD_LIBRARY_PATH" = "$GWMS_OLDENV_LD_LIBRARY_PATH" ]
    [ "$PYTHONPATH" = "$GWMS_OLDENV_PYTHONPATH" ]
}


preset_env() {
    # 1- environment file (optional)
    # 2- HTCondor Job ClassAd file (optional)
    local env_file="fixtures/environment_singularity"
    [[ -n "$1" ]] && env_file="$1" || true
    env_sing="$(env -0 | tr '\n' '\\n' | tr '\0' '\n' | tr '=' ' ' | awk '{print $1;}' | grep ^SINGULARITYENV_ || true)"
    for i in $env_sing ; do
        #echo "ENV Unsetting: $i" >&3
        unset $i
    done
    env_appt="$(env -0 | tr '\n' '\\n' | tr '\0' '\n' | tr '=' ' ' | awk '{print $1;}' | grep ^APPTAINERENV_ || true)"
    for i in $env_appt ; do
        #echo "ENV Unsetting: $i" >&3
        unset $i
    done
    # on GNU:
    export $(grep -v "^#" fixtures/environment_singularity | xargs -d '\n' )
    # On BSD like Mac
    #export $(grep -v "^#" fixtures/environment_singularity | xargs -0 )
    # To unset
    #echo "ENV all: `env`" >&3
    #unset $(grep -v "^#" fixtures/environment_singularity | sed -E 's/(.*)=.*/\1/' | xargs )
    [[ -n "$2" ]] && export _CONDOR_JOB_AD="$2" || true  # protecting not to fail the test
}


@test "Verify env_preserve" {
    #echo "ENV path: $PATH" >&3
    # echo "ENV in function: `env --help`" >&3
    env_sing="$(env -0 | tr '\n' '\\n' | tr '\0' '\n' | tr '=' ' ' | awk '{print $1;}' | grep ^SINGULARITYENV_ || true)"
    for i in env_sing ; do
        unset $i
    done
    env_sing="$(env -0 | tr '\n' '\\n' | tr '\0' '\n' | tr '=' ' ' | awk '{print $1;}' | grep ^APPTAINERENV_ || true)"
    for i in env_sing ; do
        unset $i
    done
    preset_env
    env_preserve
    count_env_sing="$(env -0 | tr '\n' '\\n' | tr '\0' '\n' | tr '=' ' ' | awk '{print $1;}' | grep ^SINGULARITYENV_ | wc -l)"
    [ $count_env_sing -eq 13 ]  # default is clearpaths, GWMS set is preserved
    preset_env
    env_preserve gwmsset
    count_env_sing="$(env -0 | tr '\n' '\\n' | tr '\0' '\n' | tr '=' ' ' | awk '{print $1;}' | grep ^SINGULARITYENV_ | wc -l)"
    count_env_appt="$(env -0 | tr '\n' '\\n' | tr '\0' '\n' | tr '=' ' ' | awk '{print $1;}' | grep ^APPTAINERENV_ | wc -l)"
    echo "Count: $count_env_sing, $count_env_appt" >&3
    [ $count_env_appt -eq $count_env_sing ]  # Singularity and Apptainer variables should match
    [ $count_env_sing -eq 13 ]  # 13 variables in GWMS set
    preset_env
    env_preserve condorset
    count_env_sing="$(env -0 | tr '\n' '\\n' | tr '\0' '\n' | tr '=' ' ' | awk '{print $1;}' | grep ^SINGULARITYENV_ | wc -l)"
    count_env_appt="$(env -0 | tr '\n' '\\n' | tr '\0' '\n' | tr '=' ' ' | awk '{print $1;}' | grep ^APPTAINERENV_ | wc -l)"
    echo "Count: $count_env_sing, $count_env_appt" >&3
    [ $count_env_appt -eq $count_env_sing ]  # Singularity and Apptainer variables should match
    [ $count_env_sing -eq 17 ]  # 4 variables in HTCondor set + Job classad (+GWMS set)
    preset_env
    env_preserve osgset
    count_env_sing="$(env -0 | tr '\n' '\\n' | tr '\0' '\n' | tr '=' ' ' | awk '{print $1;}' | grep ^SINGULARITYENV_ | wc -l)"
    count_env_appt="$(env -0 | tr '\n' '\\n' | tr '\0' '\n' | tr '=' ' ' | awk '{print $1;}' | grep ^APPTAINERENV_ | wc -l)"
    echo "Count: $count_env_sing, $count_env_appt" >&3
    [ $count_env_appt -eq $count_env_sing ]  # Singularity and Apptainer variables should match
    [ $count_env_sing -eq 44 ]  # 31 variables in OSG set (+13 in GWMS set, +4 in implied HTCondor set) (4 overlap)
    preset_env
    env_preserve clear
    count_env_sing="$(env -0 | tr '\n' '\\n' | tr '\0' '\n' | tr '=' ' ' | awk '{print $1;}' | grep ^SINGULARITYENV_ | wc -l)"
    echo "Count: $count_env_sing" >&3
    [ $count_env_sing -eq 44 ]  # 44 variables in OSG set (31) + HTCondor (4) + GWMS (13) (4 overlap)
    preset_env
    unset STASHCACHE
    unset STASHCACHE_WRITABLE
    env_preserve gwmsset
    count_env_sing="$(env -0 | tr '\n' '\\n' | tr '\0' '\n' | tr '=' ' ' | awk '{print $1;}' | grep ^SINGULARITYENV_ | wc -l)"
    echo "Count: $count_env_sing" >&3
    [ $count_env_sing -eq 11 ]  # 13 variables in GWMS set, 2 unset
    preset_env
    export SINGULARITYENV_STASHCACHE=val_notfromfile
    env_preserve gwmsset
    count_env_sing="$(env -0 | tr '\n' '\\n' | tr '\0' '\n' | tr '=' ' ' | awk '{print $1;}' | grep ^SINGULARITYENV_ | wc -l)"
    echo "Count: $count_env_sing, SINGULARITYENV_STASHCACHE: $SINGULARITYENV_STASHCACHE" >&3
    [ $count_env_sing -eq 13 ]  # 13 variables in GWMS set, 1 already_protected, still 13
    [ "$(env | grep ^SINGULARITYENV_STASHCACHE= | cut -d'=' -f2 )" = val_notfromfile ]  # val_notfromfile preserved
    # Add a test also with a Job classad w/ a SINGULARITYENV_ in the environment to get a warning
}


@test "Verify mocked robust_realpath" {
    pushd /tmp
    run robust_realpath output
    # on the Mac /tmp is really /private/tmp
    [ "$output" == "/tmp/output" -o "$output" == "/private/tmp/output" ]
    [ "$status" -eq 0 ]
    popd
    # check mocked value
    run robust_realpath /condor/execute/dir_29865/glide_8QOQl2
    [ "$output" == "/export/data1/condor/execute/dir_29865/glide_8QOQl2" ]
    [ "$status" -eq 0 ]
}


test_aux_gwms_from_config() {
    ret=${2:-$3}
    echo "Proc<$ret>"
}

@test "Verify gwms_from_config" {
    # glidein_config
    glidein_config=fixtures/glidein_config
    # default when the key is missing or the file is not readable
    [ "$(gwms_from_config missing_key4 def4)" = "def4" ]
    [ "$(gwms_from_config missing_key4)" = "" ]
    # values and processed values
    [ "$(gwms_from_config VAR1 def1)" = "test" ]
    [ "$(gwms_from_config VAR1 def1 test_aux_gwms_from_config)" = "Proc<test>" ]
    [ "$(gwms_from_config ERROR_GEN_PATH def1)" = "/bin/echo" ]
    glidein_config=fixtures/missing_file_glidein_config
    [ "$(gwms_from_config VAR1 def1)" = "def1" ]
    # defaults are not processed
    [ "$(gwms_from_config VAR1 def1 test_aux_gwms_from_config)" = "def1" ]
}


@test "Verify cvmfs_path_in_cvmfs_literal" {
    cvmfs_path_in_cvmfs_literal /cvmfs
    cvmfs_path_in_cvmfs_literal /cvmfs/dir/file
    ! cvmfs_path_in_cvmfs_literal /cvmfs_dir/file
}


@test "Verify cvmfs_path_in_cvmfs" {
    CVMFS_MOUNT_DIR=
    cvmfs_path_in_cvmfs /cvmfs
    cvmfs_path_in_cvmfs /cvmfs/dir/file
    ! cvmfs_path_in_cvmfs /cvmfs_dir/file
    ! cvmfs_path_in_cvmfs /altcvmfs/dir/file
    CVMFS_MOUNT_DIR=/altcvmfs
    cvmfs_path_in_cvmfs /altcvmfs/dir/file
    ! cvmfs_path_in_cvmfs /cvmfs_dir/file
    CVMFS_MOUNT_DIR=/altcvmfs/
    cvmfs_path_in_cvmfs /altcvmfs
    cvmfs_path_in_cvmfs /altcvmfs/dir/file
    ! cvmfs_path_in_cvmfs /cvmfs_dir/file
}


@test "Verify cvmfs_resolve_path" {
    CVMFS_MOUNT_DIR=
    [ $(cvmfs_resolve_path /cvmfs_dir/file) = "/cvmfs_dir/file" ]
    [ $(cvmfs_resolve_path /cvmfs/dir/file) = "/cvmfs/dir/file" ]
    [ $(cvmfs_resolve_path /cvmfs) = "/cvmfs" ]
    CVMFS_MOUNT_DIR=/altcvmfs/
    [ $(cvmfs_resolve_path /cvmfs_dir/file) = "/cvmfs_dir/file" ]
    [ $(cvmfs_resolve_path /cvmfs/dir/file) = "/altcvmfs/dir/file" ]
    [ $(cvmfs_resolve_path /cvmfs) = "/altcvmfs" ]
}


@test "Verify singularity_check_paths" {
    CVMFS_MOUNT_DIR=
    run singularity_check_paths "c" /src /dst/dir
    [ "$output" == "" ]
    [ "$status" -eq 1 ]
    run singularity_check_paths "c" /altcvmfs
    [ "$output" == "" ]
    [ "$status" -eq 1 ]
    CVMFS_MOUNT_DIR=/altcvmfs/
    run singularity_check_paths "c" /altcvmfs
    [ "$output" == "/altcvmfs," ]
    [ "$status" -eq 0 ]
    run singularity_check_paths "cv" /src /altcvmfs/dir/file:opt1
    [ "$output" == "/src:/altcvmfs/dir/file:opt1," ]
    [ "$status" -eq 0 ]
}


@test "Verify singularity_make_outside_pwd_list" {
    # discard values w/ different realpath
    run singularity_make_outside_pwd_list "/srv/sub1" /tmp
    [ "$output" == "/srv/sub1" ]
    [ "$status" -eq 0 ]
    # : ignores the first parameter for realpath
    run singularity_make_outside_pwd_list ":/srv/sub1" /tmp
    [ "$output" == "/srv/sub1:/tmp" ]
    [ "$status" -eq 0 ]
    # Using mocked value (same realpath)
    run singularity_make_outside_pwd_list /condor/execute/dir_29865/glide_8QOQl2 /export/data1/condor/execute/dir_29865/glide_8QOQl2
    [ "$output" == "/condor/execute/dir_29865/glide_8QOQl2:/export/data1/condor/execute/dir_29865/glide_8QOQl2" ]
    [ "$status" -eq 0 ]
    # Ignore empty values
    run singularity_make_outside_pwd_list "" /condor/execute/dir_29865/glide_8QOQl2 "" /export/data1/condor/execute/dir_29865/glide_8QOQl2
    [ "$output" == "/condor/execute/dir_29865/glide_8QOQl2:/export/data1/condor/execute/dir_29865/glide_8QOQl2" ]
    [ "$status" -eq 0 ]
    run singularity_make_outside_pwd_list ":/srv/sub1" /condor/execute/dir_29865/glide_8QOQl2 /export/data1/condor/execute/dir_29865/glide_8QOQl2
    [ "$output" == "/srv/sub1:/condor/execute/dir_29865/glide_8QOQl2:/export/data1/condor/execute/dir_29865/glide_8QOQl2" ]
    [ "$status" -eq 0 ]
}


@test "Verify singularity_update_path" {
    GWMS_SINGULARITY_OUTSIDE_PWD=/notexist/test1
    singularity_update_path /srv /notexist/test1 /notexist/test11 /notexist/test1/dir1 /root/notexist/test1/dir2 notexist/test1/dir2
    [ "${GWMS_RETURN[0]}" = /srv ]
    [ "${GWMS_RETURN[1]}" = /notexist/test11 ]
    [ "${GWMS_RETURN[2]}" = /srv/dir1 ]
    [ "${GWMS_RETURN[3]}" = /root/notexist/test1/dir2 ]
    [ "${GWMS_RETURN[4]}" = notexist/test1/dir2 ]
    GWMS_SINGULARITY_OUTSIDE_PWD=
    GWMS_SINGULARITY_OUTSIDE_PWD_LIST=/notexist/test1:/notexist/test2
    singularity_update_path /srv /notexist/test1 /notexist/test2 /notexist/test2/dir1
    [ "${GWMS_RETURN[0]}" = /srv ]
    [ "${GWMS_RETURN[1]}" = /srv ]
    [ "${GWMS_RETURN[2]}" = /srv/dir1 ]
    # test link or bind mount. Check also that other values are not modified
    pushd /tmp
    mkdir -p /tmp/test.$$/dir1
    cd /tmp/test.$$
    ln -s dir1 dir2
    cd dir2
    mkdir sub1
    mkdir sub2
    GWMS_SINGULARITY_OUTSIDE_PWD=
    GWMS_SINGULARITY_OUTSIDE_PWD_LIST=:/srv/sub1
    singularity_update_path /srv ../dir1 sub1/fout output /tmp/test.$$/dir1 /tmp/test.$$/dir2/fout sub* /tmp/test.$$/dir1/sub* -n -e a:b
    # echo "Outputs: ${GWMS_RETURN[@]}" >&3
    [ "${GWMS_RETURN[0]}" = ../dir1 ]
    [ "${GWMS_RETURN[1]}" = sub1/fout ]
    [ "${GWMS_RETURN[2]}" = output ]
    [ "${GWMS_RETURN[3]}" = /srv ]
    [ "${GWMS_RETURN[4]}" = /srv/fout ]
    [ "${GWMS_RETURN[5]}" = sub1 ]
    [ "${GWMS_RETURN[6]}" = sub2 ]
    [ "${GWMS_RETURN[7]}" = /srv/sub1 ]
    [ "${GWMS_RETURN[8]}" = /srv/sub2 ]
    [ "${GWMS_RETURN[9]}" = "-n" ]
    [ "${GWMS_RETURN[10]}" = "-e" ]
    [ "${GWMS_RETURN[11]}" = "a:b" ]
    popd
}


@test "Verify singularity_setup_inside_env" {
    X509_USER_PROXY=/condor/execute/dir_29865/glide_8QOQl2/execute/dir_9182/602e17194771641967ee6db7e7b3ffe358a54c59
    X509_USER_CERT=/condor/execute/dir_29865/glide_8QOQl2/hostcert.pem
    X509_USER_KEY=/condor/execute/dir_29865/glide_8QOQl2/hostkey.pem
    _CONDOR_CREDS=
    _CONDOR_MACHINE_AD=/condor/execute/dir_29865/glide_8QOQl2/execute/dir_9182/.machine.ad
    _CONDOR_EXECUTE=/condor/execute/dir_29865/glide_8QOQl2/execute
    _CONDOR_JOB_AD=/condor/execute/dir_29865/glide_8QOQl2/execute/dir_9182/.job.ad
    _CONDOR_SCRATCH_DIR=/condor/execute/dir_29865/glide_8QOQl2/execute/dir_9182
    _CONDOR_CHIRP_CONFIG=/condor/execute/dir_29865/glide_8QOQl2/execute/dir_9182/.chirp.config
    _CONDOR_JOB_IWD=/condor/execute/dir_29865/glide_8QOQl2/execute/dir_9182
    OSG_WN_TMP=/osg/tmp
    outdir_list=/condor/execute/dir_29865/glide_8QOQl2:/export/data1/condor/execute/dir_29865/glide_8QOQl2
    singularity_setup_inside_env "$outdir_list"
    [ "$X509_USER_PROXY" = /srv/execute/dir_9182/602e17194771641967ee6db7e7b3ffe358a54c59 ]
    [ "$X509_USER_CERT" = /srv/hostcert.pem ]
    [ "$X509_USER_KEY" = /srv/hostkey.pem ]
    [ "$_CONDOR_CREDS" = "" ]
    [ "$_CONDOR_MACHINE_AD" = /srv/execute/dir_9182/.machine.ad ]
    [ "$_CONDOR_EXECUTE" = /srv/execute ]
    [ "$_CONDOR_JOB_AD" = /srv/execute/dir_9182/.job.ad ]
    [ "$_CONDOR_SCRATCH_DIR" = /srv/execute/dir_9182 ]
    [ "$_CONDOR_CHIRP_CONFIG" = /srv/execute/dir_9182/.chirp.config ]
    [ "$_CONDOR_JOB_IWD" = /srv/execute/dir_9182 ]
    [ "$OSG_WN_TMP" = /osg/tmp ]
}

mock_singularity_test_bin() {
    # control Failure w/ mock_singularity_test_bin_control (true or =step to be successful)
    local step="${1%%,*}"
    local sin_path="${1#*,}"
    local sin_version=3.6.4
    local sin_version_full="singularity version 3.6.4"
    local sin_type=mock_$step
    if [[ -z "$sin_path" ]] && [[ "$step" = module || "$step" = PATH ]]; then
        sin_path=/path/to/singularity
    fi
    if [[ "$mock_singularity_test_bin_control" = "true" || "$mock_singularity_test_bin_control" = "$step" ]]; then
        echo -e "_$step\n_$sin_type\n_$sin_version\n_$sin_version_full\n_$sin_path\n_@ $step($sin_path):TT"
    else
        echo -e " $step($sin_path):"
        false
    fi
}

@test "Verify singularity_locate_bin" {
    # Cannot pass back an incremented call counter because singularity_test_bin is called in a subshell
    # using file $tmp_singularity_dir/calls
    singularity_test_bin() {
        echo "Called singularity_test_bin: $*" >> "$tmp_singularity_dir/calls"
        mock_singularity_test_bin "$@"
    }
    singularity_locate_bin_wrapped() {
        local slb_ec
        echo > "$tmp_singularity_dir/calls"
        singularity_locate_bin "$@"
        slb_ec=$?
        stb_attempts=$(grep -ch "Called singularity_test_bin" "$tmp_singularity_dir/calls")
        echo "SLB: $slb_ec, $HAS_SINGULARITY, $GWMS_SINGULARITY_MODE, $GWMS_SINGULARITY_PATH, $stb_attempts"
    }
    # Replace gwms_from_config to alter the output for CONDOR_DIR (to find the condor apptainer)
    eval "original_gwms_from_config()
$(typeset -f gwms_from_config | tail -n +2)"
    gwms_from_config() {
        if [ "$1" = CONDOR_DIR ]; then
            echo "$tmp_singularity_dir"
        else
            original_gwms_from_config "$@"
        fi
    }
    # Prepare a fake singularity binary
    tmp_singularity_dir=$(mktemp -d -t gwms_bats-XXXXXXXXXX)
    tmp_singularity_bin="$tmp_singularity_dir/singularity"
    echo -e '#!/bin/bash\necho "mock singularity v1.0"' > "$tmp_singularity_bin"
    chmod +x "$tmp_singularity_bin"
    # Emulate the HTCondor tar ball apptainer setup
    mkdir -p "$tmp_singularity_dir/usr/libexec"
    ln -s "$tmp_singularity_bin" "$tmp_singularity_dir/usr/libexec/apptainer"
    echo "Singularity binary mocked: $tmp_singularity_bin" >&3

    mock_singularity_test_bin_control=true  # all tests successful
    GLIDEIN_SINGULARITY_BINARY_OVERRIDE="${tmp_singularity_dir}:/tmp/bin"
    run  singularity_locate_bin_wrapped "ppp" "/path/to/image"
    echo "part 0a: $output" >&3
    [ "$output" = "SLB: 0, True, mock_s_override, $tmp_singularity_bin, 1" ]
    GLIDEIN_SINGULARITY_BINARY_OVERRIDE="/tmp/bin:${tmp_singularity_dir}:/tmp/bin"
    run  singularity_locate_bin_wrapped "ppp" "/path/to/image"
    echo "part 0b: $output" >&3
    [ "$output" = "SLB: 0, True, mock_s_override, $tmp_singularity_bin, 1" ]
    GLIDEIN_SINGULARITY_BINARY_OVERRIDE=$tmp_singularity_bin
    run  singularity_locate_bin_wrapped "ppp" "/path/to/image"
    echo "part 1: $output" >&3
    [ "$output" = "SLB: 0, True, mock_s_override, $tmp_singularity_bin, 1" ]
    GLIDEIN_SINGULARITY_BINARY_OVERRIDE=
    run  singularity_locate_bin_wrapped "$tmp_singularity_dir" "/path/to/image"
    echo "part 2: $output" >&3
    [ "$output" = "SLB: 0, True, mock_s_bin, $tmp_singularity_bin, 1" ]
    run  singularity_locate_bin_wrapped "ppp" "/path/to/image"
    echo "part 3: $output" >&3
    #[ "$output" = "SLB: 0, True, mock_OSG, $OSG_SINGULARITY_BINARY_DEFAULT, 1" ]
    [ "$output" = "SLB: 0, True, mock_PATH, apptainer, 1" ]
    OSG_SINGULARITY_BINARY=$tmp_singularity_bin
    # default
    run  singularity_locate_bin_wrapped "" "/path/to/image"
    echo "part 4: $output" >&3
    [ "$output" = "SLB: 0, True, mock_s_bin_OSG, $tmp_singularity_bin, 1" ]
    # keyword PATH
    run  singularity_locate_bin_wrapped "PATH" "/path/to/image"
    echo "part 5: $output" >&3
    [ "$output" = "SLB: 0, True, mock_PATH, apptainer, 1" ]
    # keyword CONDOR
    run  singularity_locate_bin_wrapped "CONDOR" "/path/to/image"
    echo "part 6a: $output" >&3
    [ "$output" = "SLB: 0, True, mock_s_bin_CONDOR, $tmp_singularity_dir/usr/libexec/apptainer, 1" ]
    # keyword OSG
    run  singularity_locate_bin_wrapped "OSG" "/path/to/image"
    echo "part 6b: $output" >&3
    [ "$output" = "SLB: 0, True, mock_s_bin_OSG, $tmp_singularity_bin, 1" ]
    # keyword OSG w/ default OSG_SINGULARITY_BINARY
    OSG_SINGULARITY_BINARY=
    run  singularity_locate_bin_wrapped "OSG" "/path/to/image"
    echo "part 7: $output" >&3
    # The result may change depending on whether CVMFS is installed or not
    if [ -e "$OSG_SINGULARITY_BINARY_DEFAULT" ]; then
        [ "$output" = "SLB: 0, True, mock_s_bin_OSG, $OSG_SINGULARITY_BINARY_DEFAULT, 1" ]
    else
        [ "$output" = "SLB: 0, True, mock_PATH, apptainer, 1" ]
    fi
    mock_singularity_test_bin_control=false  # all fail
    run  singularity_locate_bin_wrapped "" "/path/to/image"
    echo "part 8: $output" >&3
    if [ -e "$OSG_SINGULARITY_BINARY_DEFAULT" ]; then
        [ "$output" = "SLB: 1, False, , , 7" ]
    else
        [ "$output" = "SLB: 1, False, , , 6" ]
    fi
    OSG_SINGULARITY_BINARY=$tmp_singularity_bin # To avoid having 2 versions for when /cvmfs is available and when not
    mock_singularity_test_bin_control=PATH  # only PATH successful
    run  singularity_locate_bin_wrapped "" "/path/to/image"
    echo "part 9: $output" >&3
    [ "$output" = "SLB: 0, True, mock_PATH, apptainer, 2" ]
    mock_singularity_test_bin_control=module  # only module successful
    run  singularity_locate_bin_wrapped "" "/path/to/image"
    echo "part 10: $output" >&3
    [ "$output" = "SLB: 0, True, mock_module, singularitypro, 5" ]
    mock_singularity_test_bin_control=OSG  # only OSG successful
    run  singularity_locate_bin_wrapped "" "/path/to/image"
    echo "part 11: $output" >&3
    [ "$output" = "SLB: 0, True, mock_OSG, $tmp_singularity_bin, 7" ]
    mock_singularity_test_bin_control=CONDOR  # only CONDOR successful
    run  singularity_locate_bin_wrapped "" "/path/to/image"
    echo "part 12: $output" >&3
    [ "$output" = "SLB: 0, True, mock_CONDOR, $tmp_singularity_dir/usr/libexec/apptainer, 4" ]

    [[ -n "${tmp_singularity_dir}" ]] && rm -rf "${tmp_singularity_dir}"
}
