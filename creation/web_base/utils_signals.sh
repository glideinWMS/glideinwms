#*******************************************************************#
#                        utils_signals.sh                           #
#       This script contains signals utility functions              #
#                      File Version: 1.0                            #
#*******************************************************************#
# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

################################
# Extends 'trap' allowing to pass the signal name as argument to the handler
# Arguments:
#   1: handler
trap_with_arg() {
    local func
    func="$1"
    for sig ; do
        # shellcheck disable=SC2064
        trap "${func} ${sig}" "${sig}"
    done
}

################################
# Function that allows to pass signals to the children processes
# There is no need to re-raise sigint, caller does unconditional exit (https://www.cons.org/cracauer/sigint.html)
# Arguments:
#   1: signal
# Global:
#    ON_DIE
on_die() {
    echo "Received kill signal... shutting down child processes (forwarding $1 signal)" 1>&2
    ON_DIE=1
    kill -s "$1" %1
}

################################
# Function used to ignore signal SIGHUP
ignore_signal() {
    echo "Ignoring SIGHUP signal... Use SIGTERM or SIGQUIT to kill processes" 1>&2
}
