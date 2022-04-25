#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

import sys

# Attempt to fill the write buffer and exit normally
num_range = list(range(0, 10000))
for x in num_range:
    print(sys.stdout.write(str(x)))
    print(sys.stdout.write("This is line %s" % str(x)))

sys.exit(0)
