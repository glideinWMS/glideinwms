#!/bin/bash

# Get the log directory
Log_Dir="$2"

# Setup a fail code
fail=0

echo "-----------------------"
echo "Futurize Tests Starting"
echo "-----------------------"

echo ""
echo "Python Environment Setup Start"
echo ""

# Setup the build environment
WORKSPACE=$(pwd)
export GLIDEINWMS_SRC=$WORKSPACE/glideinwms
source "$GLIDEINWMS_SRC/build/jenkins/utils.sh"
setup_python_venv "$WORKSPACE"
cd "$GLIDEINWMS_SRC" || exit 1

echo ""
echo "Python Environment Setup Complete"
echo ""

# Now, setup the email file
HTML_TABLE="border: 1px solid black;border-collapse: collapse;"
HTML_THEAD="font-weight: bold;border: 0px solid black;background-color: #ffcc00;"
HTML_THEAD_TH="border: 0px solid black;border-collapse: collapse;font-weight: bold;background-color: #ffb300;padding: 8px;"
HTML_TH="border: 0px solid black;border-collapse: collapse;font-weight: bold;background-color: #00ccff;padding: 8px;"
HTML_TR="padding: 5px;text-align: center;"
HTML_TD_PASSED="border: 0px solid black;border-collapse: collapse;background-color: #00ff00;padding: 5px;text-align: center;"
HTML_TD_FAILED="border: 0px solid black;border-collapse: collapse;background-color: #ff0000;padding: 5px;text-align: center;"

mail_file="
    <body>
    <table style=\"$HTML_TABLE\">
      <thead style=\"$HTML_THEAD\">
        <tr style=\"$HTML_TR\">
          <th style=\"$HTML_THEAD_TH\">GIT BRANCH</th>
          <th style=\"$HTML_THEAD_TH\">FILES TO BE REFACTORED</th>
        </tr>
      </thead>
      <tbody>"

# Get the git branches in to an array
IFS=',' read -r -a git_branches <<< "$1"

# Create a process branch function
process_branch () {
    # Global Variables Used: $mail_file & $fail - and HTML Constants
    echo ""
    echo "Now checking out branch $1"
    echo ""

    git checkout "$1"

    if [ $? -ne 0 ]; then
        echo "~~~~~~"
        echo "ERROR: Could not switch to branch $1"
        echo "~~~~~~"

        # Add a failed entry to the email
        mail_file="$mail_file
    <tr style=\"$HTML_TR\">
        <th style=\"$HTML_TH\">$1</th>
        <td style=\"$HTML_TD_FAILED\">ERROR: Could not switch to branch</td>
    </tr>"
        fail=1

        # Continue onto the next branch
        return

    fi

    # Starting the futurize test
    echo ""
    echo "Now running test"
    echo ""

    OUTPUT="$(futurize -1 --no-diffs . 2>&1)"
    futurize_ret=$?

    refactoring_ret="$(echo "$OUTPUT" | grep 'Refactored ')"

    # Save the output to a file

    echo "$OUTPUT" > "$Log_Dir/Futurize_Log_$1.txt"

    if [[ $futurize_ret -ne 0 || $refactoring_ret = *[!\ ]* ]]; then
        refactored_files=$(echo "$OUTPUT" | grep 'Refactored ')
        refactored_file_count=$(echo "$refactored_files" | wc -l)

        echo "There are $refactored_file_count files that need to be refactered"

        # Add a passed entry to the email
        mail_file="$mail_file
    <tr style=\"$HTML_TR\">
        <th style=\"$HTML_TH\">$1</th>
        <td style=\"$HTML_TD_FAILED\">$refactored_file_count</td>
    </tr>"
        if [ $futurize_ret -ne 0 ]; then
            exit 1
        else
            fail=201
        fi

    else
        echo ""
        echo "No files need to be refactered"
        echo ""

        # Add a failed entry to the email
        mail_file="$mail_file
    <tr style=\"$HTML_TR\">
        <th style=\"$HTML_TH\">$1</th>
        <td style=\"$HTML_TD_PASSED\">0</td>
    </tr>"

    fi

    echo ""
    echo "Complete with branch $1"
    echo ""
}

# Iterate throughout the git_branches array
for git_branch in "${git_branches[@]}"
do
    process_branch "$git_branch"
done

# Finish off the end of the email
mail_file="$mail_file
    </tbody>
</table>
</body>"

# Save the email to a file
echo "$mail_file" > "$Log_Dir/email.txt"

# All done
echo "-----------------------"
if [ "$fail" -ne 0 ]; then
    echo "Futurize Tests Complete - Failed"
    echo "-----------------------"
    exit $fail
fi
echo "Futurize Tests Complete - Success"
echo "-----------------------"
