#!/bin/bash

# Get the log directory and clear it
Log_Dir="$2"
rm $Log_Dir/* -rf

# Setup a fail code
fail=0

echo "-----------------------"
echo "GlideinWMS Tests Starting"
echo "-----------------------"

echo ""
echo "Python Environment Setup Start"
echo ""

# Setup the build environment
WORKSPACE=$(pwd)
export GLIDEINWMS_SRC=$WORKSPACE/glideinwms
source "$GLIDEINWMS_SRC/build/jenkins/run_futurize.sh" || exit 2
source "$GLIDEINWMS_SRC/build/jenkins/run_pylint.sh" || exit 2
source "$GLIDEINWMS_SRC/build/jenkins/run_unittests.sh" || exit 2
source "$GLIDEINWMS_SRC/build/jenkins/utils.sh" || exit 2
setup_python_venv "$WORKSPACE"
cd "$GLIDEINWMS_SRC" || exit 3

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
          <th style=\"$HTML_THEAD_TH\">Futurize Errors</th>
          <th style=\"$HTML_THEAD_TH\">Pylint File Count</th>
          <th style=\"$HTML_THEAD_TH\">Pylint Error Count</th>
          <th style=\"$HTML_THEAD_TH\">Pylint Errors Total</th>
          <th style=\"$HTML_THEAD_TH\">Pylint PEP8 Errors</th>
          <th style=\"$HTML_THEAD_TH\">Pylint Unittests Errors</th>
        </tr>
      </thead>
      <tbody>"


# Create a process branch function
process_branch () {
    echo ""
    echo "Now checking out branch $1"
    echo ""

    cd "$GLIDEINWMS_SRC"
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

    # Start the first column of the mail file
    mail_file="$mail_file
    <tr style=\"$HTML_TR\">
        <th style=\"$HTML_TH\">$1</th>"

    # Starting each test
    echo ""
    echo "Now running each test"
    echo ""
    
    # Get into the sub directory
    cd "$GLIDEINWMS_SRC/../"

    # Save logs with a safe file prefix
    branch_prefix=$(echo "${1//\//_}")

    echo "Running Futurize Test"
    run_futurize "$Log_Dir" "$branch_prefix"

    if [ "$refactored_file_count" -eq "0" ]; then
        # Success
        mail_file="$mail_file
            <td style=\"$HTML_TD_PASSED\">0</td>"
    else
        # Failed
        mail_file="$mail_file
            <td style=\"$HTML_TD_FAILED\">$refactored_file_count</td>"
    fi

    echo "Running Pylint Test"
    run_pylint "$Log_Dir" "$branch_prefix"
    pylint_results_FILES_CHECKED=`echo "$FILES_CHECKED" | wc -l `
    pylint_results_PYLINT_ERROR_FILES_COUNT=$PYLINT_ERROR_FILES_COUNT
    pylint_results_PYLINT_ERROR_COUNT=$PYLINT_ERROR_COUNT
    pylint_results_PEP8_ERROR_COUNT=$PEP8_ERROR_COUNT

    if [ "$pylint_results" -eq "0" ]; then
        # Success
        mail_file="$mail_file
            <td style=\"$HTML_TD_PASSED\">$pylint_results_FILES_CHECKED</td>
            <td style=\"$HTML_TD_PASSED\">$pylint_results_PYLINT_ERROR_FILES_COUNT</td>
            <td style=\"$HTML_TD_PASSED\">$pylint_results_PYLINT_ERROR_COUNT</td>
            <td style=\"$HTML_TD_PASSED\">$pylint_results_PEP8_ERROR_COUNT</td>"
    else
        # Failed
        mail_file="$mail_file
            <td style=\"$HTML_TD_FAILED\">$pylint_results_FILES_CHECKED</td>
            <td style=\"$HTML_TD_FAILED\">$pylint_results_PYLINT_ERROR_FILES_COUNT</td>
            <td style=\"$HTML_TD_FAILED\">$pylint_results_PYLINT_ERROR_COUNT</td>
            <td style=\"$HTML_TD_FAILED\">$pylint_results_PEP8_ERROR_COUNT</td>"
    fi

    echo "Running Unittests"
    run_unittests "$Log_Dir" "$branch_prefix"

    if [ "$unittest_errors" -eq "0" ]; then
        # Success
        mail_file="$mail_file
            <td style=\"$HTML_TD_PASSED\">0</td>"
    else
        # Failed
        mail_file="$mail_file
            <td style=\"$HTML_TD_FAILED\">$unittest_errors</td>
            </tr>"
    fi

    echo ""
    echo "Complete with branch $1"
    echo ""
}

# Get the git branches in to an array
IFS=',' read -r -a git_branches <<< "$1"

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
# fail=201
# check if emailh has $HTML_TD_FAILED

echo "-----------------------"
if [ "$fail" -ne 0 ]; then
    echo "GlideinWMS Tests Complete - Failed"
    echo "-----------------------"
    exit $fail
fi
echo "GlideinWMS Tests Complete - Success"
echo "-----------------------"
