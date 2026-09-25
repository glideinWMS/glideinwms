#!/usr/bin/env bash

# SPDX-FileCopyrightText: 2026 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
set -eo pipefail
set +u

globus_compute_env_file="$script_dir/globus_compute_env.sh"
if [ -f "$globus_compute_env_file" ]; then
    . "$globus_compute_env_file"
fi

globus_compute_debug_log() {
    if [ -n "${GLOBUS_COMPUTE_DEBUG_LOG:-}" ]; then
        printf '%s %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" "$*" >>"$GLOBUS_COMPUTE_DEBUG_LOG"
    fi
}

globus_compute_debug_exit() {
    local rc=$?
    trap - EXIT
    if [ "$rc" -ne 0 ]; then
        globus_compute_debug_log "exit rc=$rc line=$LINENO command=$BASH_COMMAND"
    fi
    exit "$rc"
}

trap 'globus_compute_debug_log "error rc=$? line=$LINENO command=$BASH_COMMAND"' ERR
trap globus_compute_debug_exit EXIT

blah_common="${GLOBUS_COMPUTE_GLITE_DIR:-$script_dir}/blah_common_submit_functions.sh"
if [ ! -f "$blah_common" ]; then
    blah_common="$script_dir/blah_common_submit_functions.sh"
fi
. "$blah_common"

bls_parse_submit_options "$@"
globus_compute_original_arguments="${bls_arguments:-}"
globus_compute_debug_log "parsed command=${bls_opt_the_command:-${bls_opt_cmd:-${bls_opt_command:-}}} workdir=${bls_opt_workdir:-} env=${bls_opt_environment:-} envir=${bls_opt_envir:-} transfer=${TransferInput:-} args=${bls_arguments:-}"
if [ -n "${bls_opt_workdir:-}" ] && [ "${bls_opt_workdir: -1}" != "/" ]; then
    bls_opt_workdir="${bls_opt_workdir}/"
fi
if [ -z "${bls_opt_temp_dir:-}" ]; then
    bls_opt_temp_dir="${TMPDIR:-/tmp}"
fi
globus_compute_debug_log "before_setup_all_files workdir=${bls_opt_workdir:-} temp=${bls_opt_temp_dir:-} pwd=$PWD"
if declare -F bls_setup_all_files >/dev/null 2>&1; then
    set +e
    bls_setup_all_files
    bls_setup_rc=$?
    set -e
    if [ "$bls_setup_rc" -ne 0 ]; then
        echo "Globus Compute submit error: BLAHP file staging setup failed" >&2
        exit "$bls_setup_rc"
    fi
    globus_compute_debug_log "after_setup_all_files inputsand=${bls_inputsand_counter:-0} inputcopy=${bls_inputcopy_counter:-0} outputsand=${bls_outputsand_counter:-0} workdir=${bls_opt_workdir:-}"
fi

globus_compute_csv_append() {
    local current="$1"
    local item="$2"
    item="${item%\"}"
    item="${item#\"}"
    if [ -z "$item" ]; then
        printf '%s' "$current"
    elif [ -z "$current" ]; then
        printf '%s' "$item"
    else
        printf '%s,%s' "$current" "$item"
    fi
}

globus_compute_csv_append_bls_container() {
    local current="$1"
    local container_name="$2"
    local ind
    local local_file
    local counter_var="bls_${container_name}_counter"
    local counter_value="${!counter_var:-0}"

    for (( ind=0 ; ind < counter_value ; ind++ )); do
        local local_var="bls_${container_name}_local_${ind}"
        local_file="${!local_var:-}"
        if [ -n "$local_file" ]; then
            current="$(globus_compute_csv_append "$current" "$local_file")"
        fi
    done
    printf '%s' "$current"
}

globus_compute_quote_command() {
    local command="$1"
    local stdin_path="$2"
    shift 2
    local command_name
    command_name="$(basename "$command")"
    printf './%q' "$command_name"
    for arg in "$@"; do
        printf ' %q' "$arg"
    done
    if [ -n "$stdin_path" ]; then
        printf ' < ./%q' "$(basename "$stdin_path")"
    fi
    printf '\n'
}

globus_compute_import_submit_env_item() {
    local env_item="$1"
    env_item="${env_item%\"}"
    env_item="${env_item#\"}"
    env_item="${env_item%\'}"
    env_item="${env_item#\'}"
    case "$env_item" in
        GLOBUS_COMPUTE_*|GLIDEIN_ARGUMENTS=*) export "$env_item" ;;
    esac
}

job_name="${bls_opt_job_name:-globuscompute-job}"
command_path="${bls_opt_the_command:-${bls_opt_cmd:-${bls_opt_command:-}}}"
if [ -z "$command_path" ]; then
    echo "Globus Compute submit error: BLAHP parser did not provide a command" >&2
    exit 1
fi

if [ -n "${bls_opt_environment:-}" ]; then
    read -r -a globus_compute_env_array <<<"$bls_opt_environment"
    for globus_compute_env_item in "${globus_compute_env_array[@]}"; do
        globus_compute_import_submit_env_item "$globus_compute_env_item"
    done
fi
if [ -n "${bls_opt_envir:-}" ]; then
    IFS=";" read -r -a globus_compute_env_array <<<"$bls_opt_envir"
    for globus_compute_env_item in "${globus_compute_env_array[@]}"; do
        globus_compute_import_submit_env_item "$globus_compute_env_item"
    done
fi

. "$script_dir/globus_compute_setup.sh"
set +u
globus_compute_debug_log "setup_ok endpoint=${GLOBUS_COMPUTE_ENDPOINT:-} function=${GLOBUS_COMPUTE_FUNCTION:-} python=${GLOBUS_COMPUTE_PYTHON:-} state=${GLOBUS_COMPUTE_STATE_DIR:-}"

declare -a command_args=()
if declare -p bls_opt_args >/dev/null 2>&1; then
    if declare -p bls_opt_args | grep -q 'declare \-a'; then
        command_args=("${bls_opt_args[@]}")
    else
        read -r -a command_args <<<"$bls_opt_args"
    fi
elif declare -p bls_opt_arguments >/dev/null 2>&1; then
    if declare -p bls_opt_arguments | grep -q 'declare \-a'; then
        command_args=("${bls_opt_arguments[@]}")
    else
        read -r -a command_args <<<"$bls_opt_arguments"
    fi
elif [ -n "${globus_compute_original_arguments:-}" ]; then
    read -r -a command_args <<<"$globus_compute_original_arguments"
fi

input_files=""
input_files="$(globus_compute_csv_append "$input_files" "$command_path")"
if [ -n "${bls_opt_stdin:-}" ]; then
    input_files="$(globus_compute_csv_append "$input_files" "$bls_opt_stdin")"
fi
if [ -n "${bls_opt_input_files:-}" ]; then
    input_files="$(globus_compute_csv_append "$input_files" "$bls_opt_input_files")"
fi
if [ -n "${TransferInput:-}" ]; then
    input_files="$(globus_compute_csv_append "$input_files" "$TransferInput")"
fi
input_files="$(globus_compute_csv_append_bls_container "$input_files" inputsand)"
input_files="$(globus_compute_csv_append_bls_container "$input_files" inputcopy)"

output_files="${bls_opt_output_files:-}"
output_files="$(globus_compute_csv_append_bls_container "$output_files" outputsand)"
globus_compute_debug_log "payload_files input_files=$input_files output_files=$output_files stdout=${bls_opt_stdout:-} stderr=${bls_opt_stderr:-}"

generated_script="$(mktemp "${TMPDIR:-/tmp}/globuscompute-submit.XXXXXX")"
staged_command_name="$(basename "$command_path")"
{
    printf '#!/usr/bin/env bash\n'
    printf 'set -e\n'
    printf 'umask 077\n'
    if [ -n "${GLIDEIN_ARGUMENTS:-}" ]; then
        printf 'export GLIDEIN_ARGUMENTS=%q\n' "$GLIDEIN_ARGUMENTS"
    fi
    printf 'gc_payload_python="$(command -v python3 || command -v python || true)"\n'
    printf 'if [ -n "$gc_payload_python" ] && [ -f ./%q ]; then\n' "$staged_command_name"
    printf '    "$gc_payload_python" - ./%q <<'\''PY'\''\n' "$staged_command_name"
    printf 'from pathlib import Path\n'
    printf 'import sys\n'
    printf 'path = Path(sys.argv[1])\n'
    printf 'data = path.read_bytes()\n'
    printf 'path.write_bytes(data.replace(b"umask 0022", b"umask 0077", 1))\n'
    printf 'PY\n'
    printf 'fi\n'
    globus_compute_quote_command "$command_path" "${bls_opt_stdin:-}" "${command_args[@]}"
} >"$generated_script"

set +e
helper_output="$("$GLOBUS_COMPUTE_PYTHON" "$script_dir/globus_compute_helpers.py" submit \
    --job-name "$job_name" \
    --script "$generated_script" \
    --input-files "$input_files" \
    --stdout "${bls_opt_stdout:-}" \
    --stderr "${bls_opt_stderr:-}" \
    --output-files "$output_files" 2>&1)"
submit_rc=$?
set -e
rm -f "$generated_script"
if [ "$submit_rc" -eq 0 ]; then
    printf '%s\n' "$helper_output"
elif [ -n "$helper_output" ]; then
    printf '%s\n' "$helper_output" >&2
fi
exit "$submit_rc"
