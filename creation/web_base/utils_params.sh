#!/bin/bash

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

#*******************************************************************#
# utils_params.sh                                                   #
# This script contains parameters utility functions                 #
#*******************************************************************#

################################
# Parameters utility functions

################################
# Retrieve a simple parameter (no special characters in its value) from the param list
# make sure to have a valid slots_layout
# Arguments:
#   1: param
#   2: param_list (quoted string w/ spaces)
params_get_simple() {
    [[ ${2} = *\ ${1}\ * ]] || return
    local retval
    retval="${2##*\ ${1}\ }"
    echo "${retval%%\ *}"
}

###############################
# Decode the parameters
# Arguments:
#   1: param
params_decode() {
    echo "$1" | sed \
 -e 's/\.nbsp,/ /g' \
 -e 's/\.semicolon,/;/g' \
 -e 's/\.colon,/:/g' \
 -e 's/\.tilde,/~/g' \
 -e 's/\.not,/!/g' \
 -e 's/\.question,/?/g' \
 -e 's/\.star,/*/g' \
 -e 's/\.dollar,/$/g' \
 -e 's/\.comment,/#/g' \
 -e 's/\.sclose,/]/g' \
 -e 's/\.sopen,/[/g' \
 -e 's/\.gclose,/}/g' \
 -e 's/\.gopen,/{/g' \
 -e 's/\.close,/)/g' \
 -e 's/\.open,/(/g' \
 -e 's/\.gt,/>/g' \
 -e 's/\.lt,/</g' \
 -e 's/\.minus,/-/g' \
 -e 's/\.plus,/+/g' \
 -e 's/\.eq,/=/g' \
 -e "s/\.singquot,/'/g" \
 -e 's/\.quot,/"/g' \
 -e 's/\.fork,/\`/g' \
 -e 's/\.pipe,/|/g' \
 -e 's/\.backslash,/\\/g' \
 -e 's/\.amp,/\&/g' \
 -e 's/\.comma,/,/g' \
 -e 's/\.dot,/./g'
}

###############################
# Put the parameters into the config file
# Arguments:
#   @: parameters
# Globals (r/w):
#   param_list
#   pfval
# Returns:
#   0 in case of success,
#   otherwise glidein_exit with 1
params2file() {
    param_list=""
    while [ $# -gt 0 ]
    do
        # TODO: Use params_decode. For 3.4.8, not to introduce many changes now. Use params_converter
        # Note: using $() we escape blackslash with \\ like above. Using backticks would require \\\
        pfval=$(echo "$2" | sed \
         -e 's/\.nbsp,/ /g' \
         -e 's/\.semicolon,/;/g' \
         -e 's/\.colon,/:/g' \
         -e 's/\.tilde,/~/g' \
         -e 's/\.not,/!/g' \
         -e 's/\.question,/?/g' \
         -e 's/\.star,/*/g' \
         -e 's/\.dollar,/$/g' \
         -e 's/\.comment,/#/g' \
         -e 's/\.sclose,/]/g' \
         -e 's/\.sopen,/[/g' \
         -e 's/\.gclose,/}/g' \
         -e 's/\.gopen,/{/g' \
         -e 's/\.close,/)/g' \
         -e 's/\.open,/(/g' \
         -e 's/\.gt,/>/g' \
         -e 's/\.lt,/</g' \
         -e 's/\.minus,/-/g' \
         -e 's/\.plus,/+/g' \
         -e 's/\.eq,/=/g' \
         -e "s/\.singquot,/'/g" \
         -e 's/\.quot,/"/g' \
         -e 's/\.fork,/\`/g' \
         -e 's/\.pipe,/|/g' \
         -e 's/\.backslash,/\\/g' \
         -e 's/\.amp,/\&/g' \
         -e 's/\.comma,/,/g' \
         -e 's/\.dot,/./g')
        if ! add_config_line "$1 ${pfval}"; then
            glidein_exit 1
        fi
        if [ -z "${param_list}" ]; then
            param_list="$1"
        else
            param_list="${param_list},$1"
        fi
        shift 2
    done
    echo "PARAM_LIST ${param_list}"
    return 0
}
