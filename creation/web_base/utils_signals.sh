. utils_tarballs.sh
. utils_log.sh
. utils_xml.sh
. utils_params.sh
. utils_crypto.sh
. utils_http.sh
. glidein_cleanup.sh
. utils_fetch.sh

################################
# Extends 'trap' allowing to pass the signal name as argument to the handler
# Arguments:
#   1: handler
trap_with_arg() {
    func="$1" ; shift
    for sig ; do
        # shellcheck disable=SC2064
        trap "${func} ${sig}" "${sig}"
    done
}
# TODO: why do we need the shift?

################################
# Function that allows to pass signals to the children processes
# There is no need to re-raise sigint, caller does unconditional exit (https://www.cons.org/cracauer/sigint.html)
# Arguments:
#   1: signal
on_die() {
    echo "Received kill signal... shutting down child processes (forwarding $1 signal)" 1>&2
    ON_DIE=1
    kill -s "$1" %1
}


################################
# Function that forwards signals to the children processes
# Arguments:
#   1: signal
on_die_multi() {
    echo "Multi-Glidein received signal... shutting down child glideins (forwarding $1 signal to ${GWMS_MULTIGLIDEIN_CHILDS})" 1>&2
    ON_DIE=1
    for i in ${GWMS_MULTIGLIDEIN_CHILDS}; do
        kill -s "$1" "${i}"
    done
}

################################
# Function used to ignore signal SIGHUP
ignore_signal() {
    echo "Ignoring SIGHUP signal... Use SIGTERM or SIGQUIT to kill processes" 1>&2
}
