#!/bin/bash

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

#*******************************************************************#
# utils_signals.sh                                                  #
# This script contains signals utility functions                    #
#*******************************************************************#

################################
# Extends 'trap' allowing to pass the signal name as argument to the handler
# Arguments:
#   1: handler
signal_trap_with_arg() {
    local func
    func="$1"
    shift 1
    for sig ; do
        # shellcheck disable=SC2064
        trap "${func} ${sig}" "${sig}"
    done
}

################################
# Propagate signals to the children processes
# There is no need to re-raise sigint, caller does unconditional exit (https://www.cons.org/cracauer/sigint.html)
# Arguments:
#   1: signal
# Globals (r/w):
#    ON_DIE
signal_on_die() {
    echo "Received kill signal... shutting down child processes (forwarding $1 signal)" 1>&2
    ON_DIE=1
    kill -s "$1" %1
}

################################
# Ignore signal SIGHUP
signal_ignore() {
    echo "Ignoring SIGHUP signal... Use SIGTERM or SIGQUIT to kill processes" 1>&2
}

###############################
# Forwards signals to the children processes
# Set SIGNAL_CHILDREN_LIST to communicate the list of processes to kill
# Arguments:
#   1: signal
# Globals (r/w):
#   ON_DIE
# Used:
#   SIGNAL_CHILDREN_LIST
signal_on_die_multi() {
    echo "Parent received signal... shutting down children (forwarding $1 signal to ${SIGNAL_CHILDREN_LIST})" 1>&2
    ON_DIE=1
    for i in ${SIGNAL_CHILDREN_LIST}; do
        kill -s "$1" "${i}"
    done
}

################################
# Add child to SIGNAL_CHILDREN_LIST
# Arguments:
#   1: child
# Globals (r/w):
#   SIGNAL_CHILDREN_LIST
signal_add_child(){
    local child
    child=$1
    if [ -z "$SIGNAL_CHILDREN_LIST"]; then
        SIGNAL_CHILDREN_LIST="${child}"
    else
        SIGNAL_CHILDREN_LIST="${SIGNAL_CHILDREN_LIST} ${child}"
    fi
}

################################
# Set list of children in SIGNAL_CHILDREN_LIST
# Arguments:
#   1: children
# Globals (r/w):
#   SIGNAL_CHILDREN_LIST
signal_set_children(){
    local children
    children=$1
    SIGNAL_CHILDREN_LIST="${children}"
}
