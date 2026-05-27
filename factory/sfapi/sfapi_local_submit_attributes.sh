#!/bin/bash

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

sfapi_emit_sbatch() {
    local option="$1"
    local value="$2"
    if [ -n "$value" ]; then
        printf '#SBATCH %s=%s\n' "$option" "$value"
    fi
}

sfapi_emit_sbatch "--nodes" "${NODES:-}"
sfapi_emit_sbatch "--ntasks" "${CORES:-}"
sfapi_emit_sbatch "--gpus" "${GPUS:-}"
sfapi_emit_sbatch "--time" "${Walltime:-${WALLTIME:-}}"
sfapi_emit_sbatch "--mem-per-cpu" "${PER_PROCESS_MEMORY:-}"
sfapi_emit_sbatch "--mem" "${TOTAL_MEMORY:-}"
sfapi_emit_sbatch "--job-name" "${JOBNAME:-}"
sfapi_emit_sbatch "--account" "${PROJECT:-}"

if [ -n "${EXTRA_ARGUMENTS:-}" ]; then
    printf '#SBATCH %s\n' "$EXTRA_ARGUMENTS"
fi
