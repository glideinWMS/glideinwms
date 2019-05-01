#!/bin/bash


function help_msg {
  #filename="$(basename $0)"
  cat << EOF
$filename -i [other options] LOG_DIR
  Runs the Futurize tests on the current glideinwm subdirectory. No branch is checked out.
$filename [options] BRANCH_NAMES LOG_DIR
  Runs Futurize tests in the glideinwms repository (a glidienwms subdirectory with the git repository must exist).
  Tests are run on each of the branches in the list. Test results are saved in LOG_DIR
  Note that the script is checking out the branch and running the tests. It is not cleaning up or restoring to the
  initial content. For something less intrusive use '-i' option to run in place without changing any source file.
BRANCH_NAMES  Comma separated list of branches that needs to be inspected (from glideinwms git repository)
LOG_DIR       Directory including log files (it will be created if not existing)
  -v          verbose
  -h          print this message
  -2          runs futurize stage 2 tests (default is stage 1)
  -l          list files that need to be refactored
  -d          print diffs about the refactoring
  -i          run in place without checking out a branch (see above)
  -s          run sequequentially invoking futurize separately for each file
EOF
}

FUTURIZE_STAGE='-1'
DIFF_OPTION='--no-diffs'
filename="$(basename $0)"

while getopts ":hvldi12s" option
do
  case "${option}"
  in
  h) help_msg; exit 0;;
  v) VERBOSE=yes;;
  l) LIST_FILES=yes;;
  d) DIFF_OPTION='';;
  i) INPLACE=yes;;
  1) FUTURIZE_STAGE='-1';;
  2) FUTURIZE_STAGE='-2';;
  s) SEQUENTIAL=yes;;
  : ) echo "$filename: illegal option: -$OPTARG requires an argument" 1>&2; help_msg 1>&2; exit 1;;  
  *) echo "$filename: illegal option: -$OPTARG" 1>&2; help_msg 1>&2; exit 1;;
  \?) echo "$filename: illegal option: -$OPTARG" 1>&2; help_msg 1>&2; exit 1;;
  esac
done

# f) BRANCHES_FILE=$OPTARG;;

shift $((OPTIND-1))

# Get the parameters: branch names and log directory
if [ -n "$INPLACE" ]; then
  branch_names=''
  Log_Dir="$1"
else
  branch_names=$1
  Log_Dir="$2"
fi

if [ -z "$Log_Dir" ]; then
  echo "Bad syntax:"
  help_msg
  exit 1
fi

# Fix to have the absolute path for the tests invocations
# This works only on linux:
# Log_Dir="$(dirname $(readlink -e $Log_Dir))/$(basename $Log_Dir)"
# Less precise but mor portable
log_head=$(dirname "$Log_Dir")
log_head=$(cd "$log_head" && pwd)
Log_Dir="$log_head/$(basename $Log_Dir)"

# Make sure the log directory is there
[ -d $Log_Dir ] || mkdir -p $Log_Dir

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


if [ ! -e  $GLIDEINWMS_SRC/build/jenkins/utils.sh ]; then
    echo "ERROR: $GLIDEINWMS_SRC/build/jenkins/utils.sh not found!"
    echo "script running in `pwd`, expects a git managed glideinwms subdirectory"
    echo "exiting"
    exit 1
fi

if ! source $GLIDEINWMS_SRC/build/jenkins/utils.sh ; then
    echo "ERROR: $GLIDEINWMS_SRC/build/jenkins/utils.sh contains errors!"
    echo "exiting"
    exit 1
fi



if [ "x$VIRTUAL_ENV" = "x" ]; then
     setup_python_venv $WORKSPACE
fi

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
HTML_TD_CRASHED="border: 0px solid black;border-collapse: collapse;background-color: #800000;padding: 5px;text-align: center;"

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
IFS=',' read -r -a git_branches <<< "$branch_names"

# Create a process branch function
process_branch () {
    # Global Variables Used: $mail_file & $fail - and HTML Constants
    fail=0
    if [ -n "$INPLACE" ]; then
        echo ""
        echo "Running on local files in glideinwms subdirectory ($1)"
        echo ""
    else
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
            <td style=\"$HTML_TD_CRASHED\">ERROR: Could not switch to branch</td>
        </tr>"
            fail=301

            # Continue onto the next branch
            return

        fi
    fi

    # Starting the futurize test
    echo ""
    echo "Now running test"
    echo ""

    pyfiles=$(find .  -name '*\.py' -readable -print)
    if [ -n "$SEQUENTIAL" ]; then
        #shopt -s globstar
        OUTPUT1=""
        futurize_ret1=0
        for i in $pyfiles; do
            OUTPUT_TMP="PROC: $i"$'\n'"$(futurize $FUTURIZE_STAGE $DIFF_OPTION ${i} 2>&1)"
            if [ $? -ne 0 ]; then
                futurize_ret1=$?
            else
                OUTPUT1="$OUTPUT1"$'\n'"$OUTPUT_TMP"
            fi
        done
    else
        OUTPUT1="$(futurize $FUTURIZE_STAGE $DIFF_OPTION ${pyfiles} 2>&1)"
        futurize_ret1=$?
    fi

    # get list of python scripts without .py extension
    scripts=$(find . -path .git -prune -o -exec file {} \; -a -type f | grep -i python | grep -vi '\.py' | cut -d: -f1 | grep -v "\.html$")
    if [ -n "$SEQUENTIAL" ]; then
        OUTPUT2=""
        for i in ${scripts}; do
            OUTPUT_TMP="PROC: $i"$'\n'"$(futurize $FUTURIZE_STAGE $DIFF_OPTION ${i} 2>&1)"
            OUTPUT2="$OUTPUT2"$'\n'"$OUTPUT_TMP"
            if [ $? -ne 0 ]; then
                futurize_ret2=$?
            fi
        done
    else
        OUTPUT2="$(futurize $FUTURIZE_STAGE $DIFF_OPTION ${scripts} 2>&1)"
        futurize_ret2=$?
    fi


    refactoring_ret="$(echo "$OUTPUT1"$'\n'"$OUTPUT2" | grep 'Refactored ')"

    # Save the output to a file

    save_as=$(echo "${1//\//_}")

    echo "$OUTPUT1"$'\n'"$OUTPUT2" > "$Log_Dir/Futurize_Log_$save_as.txt"

    if [[ $futurize_ret1 -ne 0 || $futurize_ret2 -ne 0 || $refactoring_ret = *[!\ ]* ]]; then
        refactored_files=$(echo "$OUTPUT1"$'\n'"$OUTPUT2" | grep 'RefactoringTool: Refactored ')
        refactored_file_count=$(echo "$refactored_files" | wc -l)

        echo ""
	echo "There are $refactored_file_count files that need to be refactered"

        if [[ $futurize_ret1 -ne 0 || $futurize_ret2 -ne 0 ]]; then
            echo "ERROR: Futurize CRASHED while analyzing branch $1"
            echo "More than $refactored_file_count files may need to be refactored"
            # Add a Crashed entry to the email
            mail_file="$mail_file
    <tr style=\"$HTML_TR\">
        <th style=\"$HTML_TH\">$1</th>
	<td style=\"$HTML_TD_CRASHED\">ERROR: Futurize crashed (ec:$futurize_ret1/$futurize_ret2) after $refactored_file_count files to refactor</td>
    </tr>"
            fail=301
            #exit 1
        else
            # Add a failed entry to the email
            mail_file="$mail_file
    <tr style=\"$HTML_TR\">
        <th style=\"$HTML_TH\">$1</th>
        <td style=\"$HTML_TD_FAILED\">$refactored_file_count</td>
    </tr>"
            fail=201
        fi
	echo ""

    else
        echo ""
        echo "No files need to be refactered"
        echo ""

        # Add a passed entry to the email
        mail_file="$mail_file
    <tr style=\"$HTML_TR\">
        <th style=\"$HTML_TH\">$1</th>
        <td style=\"$HTML_TD_PASSED\">0</td>
    </tr>"

    fi

    echo ""
    echo "Complete with branch $1 (ec:$fail)"
    echo ""
}

# Iterate throughout the git_branches array
fail_global=0
if [ -n "$INPLACE" ]; then
    process_branch LOCAL
    fail_global=$fail
else
    for git_branch in "${git_branches[@]}"
    do
        process_branch "$git_branch"
	[ $fail -gt $fail_global ] && fail_global=$fail
    done
fi

# Finish off the end of the email
mail_file="$mail_file
    </tbody>
</table>
</body>"

# Save the email to a file
echo "$mail_file" > "$Log_Dir/email.txt"

echo ""
echo "Logs are in $Log_Dir"
echo ""

# All done
echo "-----------------------"
if [ "$fail_global" -ne 0 ]; then
    echo "Futurize Tests Complete - Failed"
    echo "-----------------------"
    exit $fail_global
fi
echo "Futurize Tests Complete - Success"
echo "-----------------------"
