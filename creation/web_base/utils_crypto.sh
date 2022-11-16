#!/bin/bash

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0
#*******************************************************************#
# utils_crypto.sh                                                   #
# This script contains cryptography utility functions               #
#*******************************************************************#

################################
# Calculates the md5 sum
# Arguments:
#   1: file name
#   2: option (quiet)
# Returns:
#   1 in case the md5sum cannot be calculated, or neither the md5sum nor the md5 can be found
# Globals (r/w):
#   res
md5wrapper() {
    local ERROR_RESULT
    ERROR_RESULT="???"
    local ONLY_SUM
    if [ "x$2" = "xquiet" ]; then
        ONLY_SUM=yes
    fi
    local executable
    executable=md5sum
    if which ${executable} 1>/dev/null 2>&1; then
        [ -n "${ONLY_SUM}" ] && executable="md5sum \"$1\" | cut -d ' ' -f 1" ||  executable="md5sum \"$1\""
    else
        executable=md5
        if ! which ${executable} 1>/dev/null 2>&1; then
            echo "${ERROR_RESULT}"
            log_warn "md5wrapper error: can't neither find md5sum nor md5"
            return 1
        fi
        [ -n "${ONLY_SUM}" ] && executable="md5 -q \"$1\"" || executable="md5 \"$1\""
    fi
    # Flagged by some checkers but OK
    if ! res="$(eval "${executable}" 2>/dev/null)"; then
        echo "${ERROR_RESULT}"
        log_warn "md5wrapper error: can't calculate md5sum using ${executable}"
        return 1
    fi
    echo "${res}" # result returned on stdout
}

########################################
# Set the X509_USER_PROXY path to full path to the file
# Environment variables exported:
#   X509_USER_PROXY
set_proxy_fullpath() {
    local fullpath
    if fullpath="$(readlink -f "${X509_USER_PROXY}")"; then
        echo "Setting X509_USER_PROXY ${X509_USER_PROXY} to canonical path ${fullpath}" 1>&2
        export X509_USER_PROXY="${fullpath}"
    else
        echo "Unable to get canonical path for X509_USER_PROXY, using ${X509_USER_PROXY}" 1>&2
    fi
}
