# BATS tests

bats is expected to be installed and in the path

Helper modules have been added as subpackages:
```
git submodule add https://github.com/ztombol/bats-support test/bats/lib/bats-support
git submodule add https://github.com/ztombol/bats-assert test/bats/lib/bats-assert
git submodule add https://github.com/jasonkarns/bats-mock test/bats/lib/bats-mock
```
If you want to use bats directly without running first at least once via the scripts in `build/ci`, then you must 
initialize (populate) the subpackages using:
```git submodule update --init --recursive```

Then, to run a test, execute the test files (and add the options for bats), e.g.:
```./example_test.bats -t```

For instructions on using bats and the helpers see:
* https://github.com/bats-core/bats-core
* https://github.com/ztombol/bats-docs
* https://github.com/jasonkarns/bats-mock

Sparse checkout could be enabled but these libraries are small and I found the core files only for bats-mock, so it remains a TODO for now:
```
cd test/bats/lib/bats-mock
git config core.sparsecheckout true

# And from the root of the repo
echo stub.bash >> .git/modules/test/bats/lib/bats-mock/info/sparse-checkout
echo binstub >> .git/modules/test/bats/lib/bats-mock/info/sparse-checkout
```

## Brief notes about tests

The instructions above tell how to write the tests.
Here some brief notes.
* You can find basic examples in `example_tests.sh`
* Tests are similar to shell functions, starting with a line like
`@test "DescriptiveNameOfTest" { test lines }`
* test lines are normal shell commands, the first one failing (returning a non 0 exit code) fails the test. 
Note that you have to terminate positively all branches that are not error. 
E.g. `[ -n "${verbose}" ] && echo "Verbose output"` will fail if it is not verbose, which is not an error, so you should use 
  `[ -n "${verbose}" ] && echo "Verbose output" || true` instead. 
* the `run` helper can be used to invoke a command (or function). 
After it, the `$status` variable contains the status code of the command, 
and the `$output` variable contains the combined contents of the command's standard 
output and standard error streams. `$lines` array, is available for easily accessing individual lines of output.


