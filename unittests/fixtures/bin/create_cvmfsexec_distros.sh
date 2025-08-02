#!/bin/bash

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

# create_cvmfsexec_distros.sh replacement for testing purposes
# this allows to run the unit tests involving create_cvmfsexec_distros.sh
# on platforms where cvmfsexec is not supported (e.g. Mac)

echo "Stub for create_cvmfsexec_distros.sh"

# Uncomment this to just exit and not run the script
#exit 0

export CVMFSEXEC_FAILURES_OK=yes
(
#shopt -s extglob
#PATH="${PATH#*fixtures/bin?(/):}"
PATH="${PATH#*fixtures/bin/:}"
PATH="${PATH#*fixtures/bin:}"
create_cvmfsexec_distros.sh "$@"
)

#TODO: cleanup of the files produced by create_cvmfsexec_distros.sh during testing
