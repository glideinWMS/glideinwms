#!/usr/bin/env python

from __future__ import print_function
from builtins import range
from builtins import str
import sys

# Attempt to fill the write buffer and exit normally
num_range = list(range(0, 10000))
for x in num_range:
    print(sys.stdout.write(str(x)))
    print(sys.stdout.write("This is line %s" % str(x)))

sys.exit(0)
