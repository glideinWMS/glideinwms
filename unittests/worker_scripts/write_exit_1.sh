#!/bin/bash

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

# Attempt to fill the write buffer and exit abnormally
for ((i=0; $i<10000; i++)); do
  echo "$i"
  echo "This is line $i" 1>&2
done
exit 1
