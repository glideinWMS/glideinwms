#!/bin/bash


run_futurize() {
    # Get the log directory
    local Log_Dir=$1
    local branch_name=$2

    refactored_file_count=0

    OUTPUT="$(futurize -1 --no-diffs $GLIDEINWMS_SRC 2>&1)"
    futurize_ret=$?

    refactoring_ret="$(echo "$OUTPUT" | grep 'Refactored ')"

    # Save the output to a file
    echo "$OUTPUT" > "$Log_Dir/${branch_name}_Futurize_Log.log"

    if [[ $futurize_ret -ne 0 || $refactoring_ret = *[!\ ]* ]]; then
        refactored_files=$(echo "$OUTPUT" | grep 'Refactored ')
        refactored_file_count=$(echo "$refactored_files" | wc -l)

        echo "There are $refactored_file_count files that need to be refactered"
    fi

    export refactored_file_count

    return
}


if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    current_dir=$(pwd)

    WORKSPACE=`pwd`
    export GLIDEINWMS_SRC=$WORKSPACE/glideinwms

    source $GLIDEINWMS_SRC/build/jenkins/utils.sh
    setup_python_venv $WORKSPACE

    run_futurize $current_dir "Futurize"
fi
