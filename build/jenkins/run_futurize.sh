#!/bin/sh

WORKSPACE=$(pwd)
export GLIDEINWMS_SRC=$WORKSPACE/glideinwms

source $GLIDEINWMS_SRC/build/jenkins/utils.sh

setup_python_venv "$WORKSPACE"

cd "$GLIDEINWMS_SRC" || exit 2

OUTPUT="$(futurize -1 --no-diffs . 2>&1)"
futurize_ret=$?

refactoring_ret="$(echo "${OUTPUT}" | grep 'Refactored ')"

if [[ $futurize_ret -ne 0 || $refactoring_ret = *[!\ ]* ]]; then
	echo "${OUTPUT}" | grep 'Refactored '
	exit 1
else
	exit 0
fi
