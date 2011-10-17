use chksum in g-r-m to generate checksum
grep "./" checksum.frontend | grep -v .py > /tmp/exclude
grep -v -f /tmp/exclude checksum.frontend > ck
mv ck checksum.frontend
