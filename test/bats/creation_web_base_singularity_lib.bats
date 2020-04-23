#!/usr/bin/env bats
#load 'libs/bats-support/load'
#load 'libs/bats-assert/load'
# On the Mac, installed w/ Homebrew
load '/usr/local/lib/bats-support/load.bash'
load '/usr/local/lib/bats-assert/load.bash'

#load 'helper'


[[ -z "$GWMS_SOURCEDIR" ]] && GWMS_SOURCEDIR=../..

setup () {
    source compat.bash
    # glidein_config=fixtures/glidein_config
    # export GLIDEIN_QUIET=true
    source "$GWMS_SOURCEDIR"/creation/web_base/singularity_lib.sh 2>&3
    load 'mock_gwms_logs'
    #echo "ENV: `env --help`" >&3
    #echo "ENVg: `genv --help`" >&3
    #echo "ENVmy: `myenv --help`" >&3

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
    # Al least for Bash <4.1. You can append || false if you must
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

dit () { echo "TEST:<$1><$2><$3>"; }

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



## Tests for env_... functions
@test "Verify env_clear_one" {
    export TEST_VAR=testvalue
    unset GWMS_OLDENV_TEST_VAR
    [ "$TEST_VAR" = "testvalue" ]
    [ "x$GWMS_OLDENV_TEST_VAR" = "x" ]
    env_clear_one TEST_VAR
    echo "For visual inspection, TEST_VAR sould be gone: `env | grep TEST_VAR`" >&3
    [ -z "${TEST_VAR+x}" ]
    [ "$GWMS_OLDENV_TEST_VAR" = "testvalue" ]
}


@test "Verify env_process_options" {
    local envoptions=
    [ "$(env_process_options $envoptions)" = "clearpath" ]  # Default is 'clearpath'
    [[ ",$(env_process_options clear)," = *",clearall,gwmsset,osgset,condorset,"* ]] || false  # clear substitution
    [[ ",$(env_process_options aaa,osgset)," = *",condorset,"* ]] || false  # osgset implies condorset
    [ "$(env_process_options aaa,osgset,condorset)" = "aaa,osgset,condorset" ]  # should be the same
    echo "Should print a warning (clear+keepall):" >&3
    env_process_options clear,osgset,condorset,keepall
}


@test "Verify env_gets_cleared" {
    env_gets_cleared "command --other --cleanenv --other2"  # clearenv is there, true
    env_gets_cleared "--cleanenv"  # clearenv is there, true
    ! env_gets_cleared "testvalue --cleanenvnot"  # clearenv is not there, falase
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


preset_env () {
    # 1- environment file (optional)
    # 2- HTCondor Job ClassAd file (optional)
    local env_file="fixtures/environment_singularity"
    [[ -n "$1" ]] && env_file="$1" || true
    env_sing="$(env -0 | tr '\n' '\\n' | tr '\0' '\n' | tr '=' ' ' | awk '{print $1;}' | grep ^SINGULARITYENV_ || true)"
    for i in $env_sing ; do
        #echo "UE unsetting: $i" >&3
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
    preset_env
    env_preserve
    count_env_sing="$(env -0 | tr '\n' '\\n' | tr '\0' '\n' | tr '=' ' ' | awk '{print $1;}' | grep ^SINGULARITYENV_ | wc -l)"
    [ $count_env_sing -eq 10 ]  # default is clearpath, GWMS set is preserved
    preset_env
    env_preserve gwmsset
    count_env_sing="$(env -0 | tr '\n' '\\n' | tr '\0' '\n' | tr '=' ' ' | awk '{print $1;}' | grep ^SINGULARITYENV_ | wc -l)"
    echo "Count: $count_env_sing" >&3
    [ $count_env_sing -eq 10 ]  # 10 variables in GWMS set
    preset_env
    env_preserve condorset
    count_env_sing="$(env -0 | tr '\n' '\\n' | tr '\0' '\n' | tr '=' ' ' | awk '{print $1;}' | grep ^SINGULARITYENV_ | wc -l)"
    echo "Count: $count_env_sing" >&3
    [ $count_env_sing -eq 14 ]  # 4 variables in HTCondor set + Job classad
    preset_env
    env_preserve osgset
    count_env_sing="$(env -0 | tr '\n' '\\n' | tr '\0' '\n' | tr '=' ' ' | awk '{print $1;}' | grep ^SINGULARITYENV_ | wc -l)"
    echo "Count: $count_env_sing" >&3
    [ $count_env_sing -eq 40 ]  # 34 variables in OSG set + HTCondor
    preset_env
    env_preserve clear
    count_env_sing="$(env -0 | tr '\n' '\\n' | tr '\0' '\n' | tr '=' ' ' | awk '{print $1;}' | grep ^SINGULARITYENV_ | wc -l)"
    echo "Count: $count_env_sing" >&3
    [ $count_env_sing -eq 40 ]  # 40 variables in OSG set + HTCondor + GWMS (5 overlap)
    preset_env
    unset STASHCACHE
    unset STASHCACHE_WRITABLE
    env_preserve gwmsset
    count_env_sing="$(env -0 | tr '\n' '\\n' | tr '\0' '\n' | tr '=' ' ' | awk '{print $1;}' | grep ^SINGULARITYENV_ | wc -l)"
    echo "Count: $count_env_sing" >&3
    [ $count_env_sing -eq 8 ]  # 10 variables in GWMS set, 2 unset
    preset_env
    export SINGULARITYENV_STASHCACHE=val_notfromfile
    env_preserve gwmsset
    count_env_sing="$(env -0 | tr '\n' '\\n' | tr '\0' '\n' | tr '=' ' ' | awk '{print $1;}' | grep ^SINGULARITYENV_ | wc -l)"
    echo "Count: $count_env_sing, SINGULARITYENV_STASHCACHE: $SINGULARITYENV_STASHCACHE" >&3
    [ $count_env_sing -eq 10 ]  # 10 variables in GWMS set, 1 already_protected, still 10
    [ "$(env | grep ^SINGULARITYENV_STASHCACHE= | cut -d'=' -f2 )" = val_notfromfile ]  # val_notfromfile preserved
    # Add a test also with a Job classad w/ a SINGULARITYENV_ in the environment to get a warning
}
