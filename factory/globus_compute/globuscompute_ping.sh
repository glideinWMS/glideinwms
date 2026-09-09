#!/usr/bin/env bash

# SPDX-FileCopyrightText: 2026 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export GLOBUS_COMPUTE_BLAHP_JOB_ID="${GLOBUS_COMPUTE_BLAHP_JOB_ID:-ping}"
. "$script_dir/globus_compute_setup.sh"
echo "0 No error"
