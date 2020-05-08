# BATS tests

bats is expected to be installed and in the path

Helper modules have been asses as subpackages:
```
git submodule add https://github.com/ztombol/bats-support test/bats/lib/bats-support
git submodule add https://github.com/ztombol/bats-assert test/bats/lib/bats-assert
git submodule add https://github.com/jasonkarns/bats-mock test/bats/lib/bats-mock
```

To run a test execute the test files (add the options for bats):
```./example_test.bats -t```

For instructions on using bats and the helpers see:
* https://github.com/bats-core/bats-core
* https://github.com/ztombol/bats-docs
* https://github.com/jasonkarns/bats-mock

Sparse checkout could be enabled but I found the core files only for bats-mock:
```
cd test/bats/lib/bats-mock
git config core.sparsecheckout true

# And from the root of the repo
echo stub.bash >> .git/modules/test/bats/lib/bats-mock/info/sparse-checkout
echo binstub >> .git/modules/test/bats/lib/bats-mock/info/sparse-checkout
```

