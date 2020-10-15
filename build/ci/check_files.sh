#!/bin/bash
mydir="$(dirname $0)"

pushd "${mydir}/../.." > /dev/null
echo "Checking files starting from: $(pwd)"
echo "List of non ASCII files - some known directories are skipped:"
find . -type f -not -path "*/.git/*" -not -path "*.tar.gz" -not -path "*/.tox/*" -not -path "*/test/bats/lib/*" -not -path "*/doc/api/html/*" -not -path "*/images/*" -not -path "*/doc/papers/*" -not -path "*/unittests/fixtures/factory/work-dir/*" -exec file {} \; | grep -v "ASCII text" | grep -v ": empty"
# To find the non ASCII chars:
# grep --color='auto' -P -n "[^\x00-\x7F]" FILE
# ag "[\x80-\xFF]" FILE

# Looking for leftover git conflicts strings
echo "List of merge conflicts leftover:"
egrep -R "(^=======$|^>>>>>>>|^<<<<<<<)" * 

# count todos in files
echo "Number of TODOs: $(grep -R "TODO:" * | wc -l )"

popd > /dev/null
