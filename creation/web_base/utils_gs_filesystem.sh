#!/bin/bash

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

#*******************************************************************#
# utils_gs_filesystem.sh                                            #
# This script contains filesystem utility functions for the         #
# glidein_startup.sh script                                         #
#*******************************************************************#

################################
# Generate the directory ID
# It creates an ID to distinguish the directories when preserved
dir_id() {
    [[ ! ",${GLIDEIN_DEBUG_OPTIONS}," = *,nocleanup,* ]] && return
    local dir_id
    dir_id=""
    local tmp
    tmp="${repository_url%%.*}"
    tmp="${tmp#*//}"
    dir_id="${tmp: -4}"
    tmp="${client_repository_url%%.*}"
    tmp="${tmp#*//}"
    dir_id="${dir_id}${tmp: -4}"
    [[ -z "${dir_id}" ]] && dir_id='debug'
    echo "${dir_id}_"
}

################################
# Copy all files from a directory to another
# (to support when needed to start multiple glideins)
# Arguments:
#   1: prefix of the files to skip
#   2: destination directory
copy_all() {
   mkdir -p "$2"
   for f in *; do
       [[ -e "${f}" ]] || break    # TODO: should this be a continue?
       if [[ "${f}" = ${1}* ]]; then
           continue
       fi
       cp -r "${f}" "$2"/
   done
}
# TODO: should it copy also hidden files?

########################################
# Add $1 to GWMS_PATH and update PATH
# Environment:
#   GWMS_PATH
#   PATH
add_to_path() {
    logdebug "Adding to GWMS_PATH: $1"
    local old_path
    old_path=":${PATH%:}:"
    old_path="${old_path//:$GWMS_PATH:/}"
    local old_gwms_path
    old_gwms_path=":${GWMS_PATH%:}:"
    old_gwms_path="${old_gwms_path//:$1:/}"
    old_gwms_path="${1%:}:${old_gwms_path#:}"
    export GWMS_PATH="${old_gwms_path%:}"
    old_path="${GWMS_PATH}:${old_path#:}"
    export PATH="${old_path%:}"
}

################################
# Automatically determine and setup work directories
# Globals (r/w):
#   targets (_CONDOR_SCRATCH_DIR, OSG_WN_TMP, TG_NODE_SCRATCH, TG_CLUSTER_SCRATCH, SCRATCH, TMPDIR, TMP, PWD)
#   work_dir
# Used:
#   _CONDOR_SCRATCH_DIR
#   OSG_WN_TMP
#   TG_NODE_SCRATCH
#   TG_CLUSTER_SCRATCH
#   SCRATCH
#   TMP
#   TMPDIR
#   PWD
# Returns:
#   1 in case you are not allowed to write
automatic_work_dir() {
    declare -a targets=("${_CONDOR_SCRATCH_DIR}"
                        "${OSG_WN_TMP}"
                        "${TG_NODE_SCRATCH}"
                        "${TG_CLUSTER_SCRATCH}"
                        "${SCRATCH}"
                        "${TMPDIR}"
                        "${TMP}"
                        "${PWD}"
                        )
    unset TMPDIR

    local disk_required free
    # 1 kB
    disk_required=1000000

    for d in "${targets[@]}"; do

        echo "Checking ${d} for potential use as work space... " 1>&2

        # does the target exist?
        if [ ! -e "${d}" ]; then
            echo "  Workdir: ${d} does not exist" 1>&2
            continue
        fi

        # make sure there is enough available diskspace
        free="$(df -kP "${d}" | awk '{if (NR==2) print $4}')"
        if [ "x${free}" = "x" ] || [ "${free}" -lt ${disk_required} ]; then
            echo "  Workdir: not enough disk space available in ${d}" 1>&2
            continue
        fi

        if touch "${d}/.dirtest.$$" >/dev/null 2>&1; then
            echo "  Workdir: ${d} selected" 1>&2
            rm -f "${d}/.dirtest.$$" >/dev/null 2>&1
            work_dir=${d}
            return 0
        fi
        echo "  Workdir: not allowed to write to ${d}" 1>&2
    done
    return 1
}
