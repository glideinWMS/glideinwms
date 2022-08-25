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
#   2 (optional): 1 if needs to write to stdout, 2 if needs to write to stderr
print_header_line(){
    local content
    if [ $# -eq 1 ]; then
        content=$1
        echo "===  ${content}  ==="
    elif [ $# -eq 2 -a $2 -eq 1 ]
        then
           content=$1
           echo "===  ${content}  ==="
    elif [ $# -eq 2 -a $2 -eq 2 ]
    then
        content=$1
        echo "===  ${content}  ===" 1>&2
    fi
}
