#!/bin/bash

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

#*******************************************************************#
# utils_io.sh                                                       #
# This script contains I/O utility functions                        #
#*******************************************************************#

################################
# Log warning statements
# Arguments:
#   @: content to warn
log_warn() {
    echo "WARN $(date)" "$@" 1>&2
}

################################
# Log debug statements
# Arguments:
#   @: content to debug
log_debug() {
    echo "DEBUG $(date)" "$@" 1>&2
}

#####################
# Print a header line, i.e. === HEADER ===
# Arguments:
#   1: content of the header line
print_header_line(){
    echo "===  $*  ==="
}
