#!/bin/bash
mydir="$(dirname $0)"

pushd "${mydir}/../.." > /dev/null
echo "List of non ASCII files starting from ($(pwd) - some known directories are skipped):"
find . -type f -not -path "*/.git/*" -not -path "*/images/*" -not -path "*/doc/papers/*" -not -path "*/unittests/fixtures/factory/work-dir/*" -exec file {} \; | grep -v "ASCII text" | grep -v ": empty"
popd > /dev/null
