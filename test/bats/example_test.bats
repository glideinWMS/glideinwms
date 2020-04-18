#!/usr/bin/env bats

setup() {
    # executed before each test
    echo "setup" >&3
}

teardown() {
    # executed after each test
    echo "teardown" >&3
}

@test "Running test1" {
    [ "$(echo "1+1" | bc)" = 2 ]
    # Do not use double brackets ( [[ ... ]] ).
    # They are treated as conditionals by bash and will not cause any test to fail, ever.
    # At least for bash < 4.1
    # You can append || false if you must

}

@test "Running test2" {
    run bash -c "echo 'pippo bar rr' | cut -d' ' -f2"
    echo "OUT: <$output> `[[ "$output" == "bar" ]] && echo OK || echo no`" >&3
    echo "step 2" >&3
    [ "$output" == "bar" ]
    echo "step 3" >&3
    [ ! "$output" = "www" ]
    echo "step 4" >&3
}

@test "verify bash version" {
    # GNU bash, version 3.2.57(1)-release-(x86_64-apple-darwin18)
    # GNU bash, version 4.4.20(1)-release-(x86_64-pc-linux-gnu)
    run bash --help
    # echo "OUT: $output" >&3
    [ "$status" -eq 0 ]
    [[ "${lines[0]}" = "GNU bash, version "* ]] || false
}

