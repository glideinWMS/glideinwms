#!/bin/bash

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

#*******************************************************************#
# utils_gs_signals.sh                                               #
# This script contains signals' utility functions for the           #
# glidein_startup.sh script                                         #
#*******************************************************************#

################################
# Forwards signals to the children processes
# Arguments:
#   1: signal
# Globals:
#   ON_DIE
signal_on_die_multi() {
    echo "Multi-Glidein received signal... shutting down child glideins (forwarding $1 signal to ${GWMS_MULTIGLIDEIN_CHILDS})" 1>&2
    ON_DIE=1
    for i in ${GWMS_MULTIGLIDEIN_CHILDS}; do
        kill -s "$1" "${i}"
    done
}
