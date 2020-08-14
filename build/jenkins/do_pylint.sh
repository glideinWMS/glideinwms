# Shell source file to be sourced to run Python unit tests and coverage
# To be used only inside runtest.sh (runtest.sh and util.sh functions defined, VARIABLES available)
# All function names start with do_...

find_aux () {
    # $1 basename of the aux file
    [ -e "$MYDIR/$1" ] && { echo "$MYDIR/$1"; return; }
    [ -e "$GLIDEINWMS_SRC/$1" ] && { echo "$GLIDEINWMS_SRC/$1"; return; }
    false
}

# TODO
do_help_msg() {
  cat << EOF
${COMMAND} command:
  Run pylint and pycodestyle and output the outfile to standard output
${filename} [options] ${COMMAND} [other command options] TEST_FILES
  Run pylint and pycodestyle on TEST_FILES files in glidinwms/
${filename} [options] ${COMMAND} -a [other command options]
  Run pylint and pycodestyle on all the Python 3 files in glidinwms/
Command options:
  -h        print this message
  -a        run on all Python scripts (see above)
  -t TESTS  string including the digits of the tests to run (Default: 12)
            add 1 for pylint
            add 2 for pycodestyle
EOF
}


#############################################
# CONFIGURABLE PYLINT &
# PYCODESTYLE OPTIONS #
#############################################

# pylint related variables
PYLINT_RCFILE=/dev/null
PYLINT_OPTIONS="--errors-only --rcfile=$PYLINT_RCFILE"
# Starting pylint 1.4 external modules must be whitelisted
PYLINT_OPTIONS="$PYLINT_OPTIONS --extension-pkg-whitelist=htcondor,classad"

# pycodestyle, formally pep8 (pystyle for variable use)

#uncomment or add lines to taste
#see tail of pep8.log for counts of
#various pep8 errors

# Note: The uncommented first line should be
# ="$PYSTYLE_OPTIONS""CODE"

PYSTYLE_OPTIONS="--ignore="


# E1    Indentation
# E101  indentation contains mixed spaces and tabs
#PYSTYLE_OPTIONS="$PYSTYLE_OPTIONS,E101"
# E111  indentation is not a multiple of four
PYSTYLE_OPTIONS="$PYSTYLE_OPTIONS""E111"
# E112  expected an indented block
#PYSTYLE_OPTIONS="$PYSTYLE_OPTIONS,E112"
# E113  unexpected indentation
#PYSTYLE_OPTIONS="$PYSTYLE_OPTIONS,E113"
# E114  indentation is not a multiple of four (comment)
#PYSTYLE_OPTIONS="$PYSTYLE_OPTIONS,E114"
# E115  expected an indented block (comment)
#PYSTYLE_OPTIONS="$PYSTYLE_OPTIONS,E115"
# E116  unexpected indentation (comment)
#PYSTYLE_OPTIONS="$PYSTYLE_OPTIONS,E116"
# E117  over-indented
#PYSTYLE_OPTIONS="$PYSTYLE_OPTIONS,E117"
# E121 (*^) continuation line under-indented for hanging indent
#PYSTYLE_OPTIONS="$PYSTYLE_OPTIONS,E121"
# E122 (^)  continuation line missing indentation or outdented
#PYSTYLE_OPTIONS="$PYSTYLE_OPTIONS,E122"
# E123 (*)  closing bracket does not match indentation of opening bracket's line
#PYSTYLE_OPTIONS="$PYSTYLE_OPTIONS,E123"
# E124 (^)  closing bracket does not match visual indentation
#PYSTYLE_OPTIONS="$PYSTYLE_OPTIONS,E124"
# E125 (^)  continuation line with same indent as next logical line
#PYSTYLE_OPTIONS="$PYSTYLE_OPTIONS,E125"
# E126 (*^) continuation line over-indented for hanging indent
#PYSTYLE_OPTIONS="$PYSTYLE_OPTIONS,E126"
# E127 (^)  continuation line over-indented for visual indent
#PYSTYLE_OPTIONS="$PYSTYLE_OPTIONS,E127"
# E128 (^)  continuation line under-indented for visual indent
#PYSTYLE_OPTIONS="$PYSTYLE_OPTIONS,E128"
# E129 (^)  visually indented line with same indent as next logical line
#PYSTYLE_OPTIONS="$PYSTYLE_OPTIONS,E129"
# E131 (^)  continuation line unaligned for hanging indent
#PYSTYLE_OPTIONS="$PYSTYLE_OPTIONS,E131"
# E133 (*)  closing bracket is missing indentation
#PYSTYLE_OPTIONS="$PYSTYLE_OPTIONS,E13
# E2    Whitespace3"
#PYSTYLE_OPTIONS="$PYSTYLE_OPTIONS,E2"
# E201  whitespace after '('
#PYSTYLE_OPTIONS="$PYSTYLE_OPTIONS,E201"
# E202  whitespace before ')'
#PYSTYLE_OPTIONS="$PYSTYLE_OPTIONS,E202"
# E203  whitespace before ':'
#PYSTYLE_OPTIONS="$PYSTYLE_OPTIONS,E203"
# E211  whitespace before '('
#PYSTYLE_OPTIONS="$PYSTYLE_OPTIONS,E211"
# E221  multiple spaces before operator
#PYSTYLE_OPTIONS="$PYSTYLE_OPTIONS,E221"
# E222  multiple spaces after operator
#PYSTYLE_OPTIONS="$PYSTYLE_OPTIONS,E222"
# E223  tab before operator
#PYSTYLE_OPTIONS="$PYSTYLE_OPTIONS,E223"
# E224  tab after operator
#PYSTYLE_OPTIONS="$PYSTYLE_OPTIONS,E224"
# E225  missing whitespace around operator
PYSTYLE_OPTIONS="$PYSTYLE_OPTIONS,E225"
# E226 (*)  missing whitespace around arithmetic operator
PYSTYLE_OPTIONS="$PYSTYLE_OPTIONS,E226"
# E227  missing whitespace around bitwise or shift operator
#PYSTYLE_OPTIONS="$PYSTYLE_OPTIONS,E227"
# E228  missing whitespace around modulo operator
PYSTYLE_OPTIONS="$PYSTYLE_OPTIONS,E228"
# E231  missing whitespace after ',', ';', or ':'
PYSTYLE_OPTIONS="$PYSTYLE_OPTIONS,E231"
# E241 (*)  multiple spaces after ','
#PYSTYLE_OPTIONS="$PYSTYLE_OPTIONS,E241"
# E242 (*)  tab after ','
#PYSTYLE_OPTIONS="$PYSTYLE_OPTIONS,E242"
# E251  unexpected spaces around keyword / parameter equals
#PYSTYLE_OPTIONS="$PYSTYLE_OPTIONS,E251"
# E261  at least two spaces before inline comment
PYSTYLE_OPTIONS="$PYSTYLE_OPTIONS,E261"
# E262  inline comment should start with '# '
#PYSTYLE_OPTIONS="$PYSTYLE_OPTIONS,E262"
# E265  block comment should start with '# '
PYSTYLE_OPTIONS="$PYSTYLE_OPTIONS,E265"
# E266  too many leading '#' for block comment
#PYSTYLE_OPTIONS="$PYSTYLE_OPTIONS,E266"
# E271  multiple spaces after keyword
#PYSTYLE_OPTIONS="$PYSTYLE_OPTIONS,E271"
# E272  multiple spaces before keyword
#PYSTYLE_OPTIONS="$PYSTYLE_OPTIONS,E272"
# E273  tab after keyword
#PYSTYLE_OPTIONS="$PYSTYLE_OPTIONS,E273"
# E274  tab before keyword
#PYSTYLE_OPTIONS="$PYSTYLE_OPTIONS,E274"
# E275  missing whitespace after keyword
#PYSTYLE_OPTIONS="$PYSTYLE_OPTIONS,E275"

# E3    Blank line
# E301  expected 1 blank line, found 0
#PYSTYLE_OPTIONS="$PYSTYLE_OPTIONS,E301"
# E302  expected 2 blank lines, found 0
PYSTYLE_OPTIONS="$PYSTYLE_OPTIONS,E302"
# E303  too many blank lines (3)
#PYSTYLE_OPTIONS="$PYSTYLE_OPTIONS,E303"
# E304  blank lines found after function decorator
#PYSTYLE_OPTIONS="$PYSTYLE_OPTIONS,E304"
# E305  expected 2 blank lines after end of function or class
#PYSTYLE_OPTIONS="$PYSTYLE_OPTIONS,E305"
# E306  expected 1 blank line before a nested definition
#PYSTYLE_OPTIONS="$PYSTYLE_OPTIONS,E306"

# E4    Import
# E401  multiple imports on one line
#PYSTYLE_OPTIONS="$PYSTYLE_OPTIONS,E401"
# E402  module level import not at top of file
#PYSTYLE_OPTIONS="$PYSTYLE_OPTIONS,E402"

# E5    Line length
# E501 (^)  line too long (82 > 79 characters)
PYSTYLE_OPTIONS="$PYSTYLE_OPTIONS,E501"
# E502  the backslash is redundant between brackets
#PYSTYLE_OPTIONS="$PYSTYLE_OPTIONS,E502"

# E7    Statement
# E701  multiple statements on one line (colon)
#PYSTYLE_OPTIONS="$PYSTYLE_OPTIONS,E701"
# E702  multiple statements on one line (semicolon)
#PYSTYLE_OPTIONS="$PYSTYLE_OPTIONS,E702"
# E703  statement ends with a semicolon
#PYSTYLE_OPTIONS="$PYSTYLE_OPTIONS,E703"
# E704 (*)  multiple statements on one line (def)
#PYSTYLE_OPTIONS="$PYSTYLE_OPTIONS,E704"
# E711 (^)  comparison to None should be 'if cond is None:'
#PYSTYLE_OPTIONS="$PYSTYLE_OPTIONS,E711"
# E712 (^)  comparison to True should be 'if cond is True:' or 'if cond:'
#PYSTYLE_OPTIONS="$PYSTYLE_OPTIONS,E712"
# E713  test for membership should be 'not in'
#PYSTYLE_OPTIONS="$PYSTYLE_OPTIONS,E713"
# E714  test for object identity should be 'is not'
#PYSTYLE_OPTIONS="$PYSTYLE_OPTIONS,E714"
# E721 (^)  do not compare types, use 'isinstance()'
#PYSTYLE_OPTIONS="$PYSTYLE_OPTIONS,E721"
# E722  do not use bare except, specify exception instead
#PYSTYLE_OPTIONS="$PYSTYLE_OPTIONS,E722"
# E731  do not assign a lambda expression, use a def
#PYSTYLE_OPTIONS="$PYSTYLE_OPTIONS,E731"
# E741  do not use variables named 'l', 'O', or 'I'
#PYSTYLE_OPTIONS="$PYSTYLE_OPTIONS,E741"
# E742  do not define classes named 'l', 'O', or 'I'
#PYSTYLE_OPTIONS="$PYSTYLE_OPTIONS,E742"
# E743  do not define functions named 'l', 'O', or 'I'
#PYSTYLE_OPTIONS="$PYSTYLE_OPTIONS,E743"

# E9    Runtime
# E901  SyntaxError or IndentationError
#PYSTYLE_OPTIONS="$PYSTYLE_OPTIONS,E901"
# E902  IOError
#PYSTYLE_OPTIONS="$PYSTYLE_OPTIONS,E902"

# W1    Indentation warning
# W191  indentation contains tabs
#PYSTYLE_OPTIONS="$PYSTYLE_OPTIONS,W191"

# W2    Whitespace warning
# W291  trailing whitespace
PYSTYLE_OPTIONS="$PYSTYLE_OPTIONS,W291"
# W292  no newline at end of file
#PYSTYLE_OPTIONS="$PYSTYLE_OPTIONS,W292"
# W293  blank line contains whitespace
PYSTYLE_OPTIONS="$PYSTYLE_OPTIONS,W293"

# W3    Blank line warning
# W391  blank line at end of file
#PYSTYLE_OPTIONS="$PYSTYLE_OPTIONS,W391"

# W5    Line break warning
# W503 (*)  line break before binary operator
#PYSTYLE_OPTIONS="$PYSTYLE_OPTIONS,W503"
# W504 (*)  line break after binary operator
#PYSTYLE_OPTIONS="$PYSTYLE_OPTIONS,W504"
# W505 (*^) doc line too long (82 > 79 characters)
#PYSTYLE_OPTIONS="$PYSTYLE_OPTIONS,W505"

# W6    Deprecation warning
# W601  .has_key() is deprecated, use 'in'
#PYSTYLE_OPTIONS="$PYSTYLE_OPTIONS,W601"
# W602  deprecated form of raising exception
#PYSTYLE_OPTIONS="$PYSTYLE_OPTIONS,W602"
# W603  '<>' is deprecated, use '!='
#PYSTYLE_OPTIONS="$PYSTYLE_OPTIONS,W603"
# W604  backticks are deprecated, use 'repr()'
#PYSTYLE_OPTIONS="$PYSTYLE_OPTIONS,W604"
# W605  invalid escape sequence 'x'
#PYSTYLE_OPTIONS="$PYSTYLE_OPTIONS,W605"
# W606  'async' and 'await' are reserved keywords starting with Python 3.7
#PYSTYLE_OPTIONS="$PYSTYLE_OPTIONS,W606"


# Uncomment to see all pep8 errors
#PYSTYLE_OPTIONS=""


do_show_flags() {
    echo "Pylint will run with options:"
    echo "$PYLINT_OPTIONS"
    echo "PyCodeStyle will run with options:"
    echo "$PYSTYLE_OPTIONS"
}

DO_TESTS="12"
LIST_FILES=

do_parse_options() {
    while getopts ":hat:" option
    do
      case "${option}"
      in
      h) help_msg; do_help_msg; exit 0;;
      a) LIST_FILES=yes;;
      t) DO_TESTS="$OPTARG";;
      : ) logerror "illegal option: -$OPTARG requires an argument"; help_msg 1>&2; do_help_msg 1>&2; exit 1;;
      *) logerror "illegal option: -$OPTARG"; help_msg 1>&2; do_help_msg 1>&2; exit 1;;
      ##\?) logerror "illegal option: -$OPTARG"; help_msg 1>&2; exit 1;;
      esac
    done

    shift $((OPTIND-1))

    CMD_OPTIONS="$@"

    if [ -n "${SHOW_FLAGS}" ]; then
        do_show_flags
        TEST_COMPLETE=branch
    fi
}

do_use_python() { true; }

do_get_dependencies() { true; }

do_check_requirements() {
    if ! command -v pylint > /dev/null 2>&1; then
        logerror "pylint not available"
        false
        return
    fi
    if ! command -v pycodestyle >/dev/null 2>&1; then
        logwarn "pycodestyle command not found"
        false
        return
    fi
}

do_process_branch() {
    # 1 - branch
    # 2 - output file (output directory/output.branch)
    # 3... - files to process (optional)

    local branch="$1"
    local branch_no_slash=$(echo "${1}" | sed -e 's/\//_/g')
    local outfile="$2"
    local out_pylint="${outfile}.pylint"
    local out_pycs="${outfile}.pycs"
    local outdir="$(dirname "$2")"
    local outfilename="$(basename "$2")"
    shift 2
    local test_date=$(date "+%Y-%m-%d %H:%M:%S")

    local fail

    local file_list
    if [[ -n "$LIST_FILES" ]]; then
        if is_python3_branch "${branch}"; then
            files_list="$(get_python3_scripts) $(get_python_files)"
        else
            files_list="$(get_python2_scripts) $(get_python_files)"
        fi
    else
        files_list="$*"
    fi

    print_files_list "Pylint and PyCodeStyle will inspect the following files:" "${files_list}" && return

    is_python3_branch && gwms_python=python3 || gwms_python=python

    # Initialize logs
    > ${out_pylint}
    > ${out_pycs}
    > ${outfile}

    loginfo "#####################################################"
    loginfo "Start : ${branch}"
    start_time="$(date -u +%s.%N)"

    if ! do_check_requirements; then
        # pylint and pycodestyle depend on the Python environment, can change branch by branch
        logerror "Essential software is missing. Skipping branch ${branch}"
        return 1
    fi

    # ALT
    # while read -r filename
    # do
    # done <<< "${files_list}"
    local filename
    local files_checked=
    local files_errors=
    for filename in ${files_list}; do
        if [[ "${DO_TESTS}" == *1* ]]; then
            #can't seem to get --ignore or --ignore-modules to work, so do it this way
            if [[ " ${PYLINT_IGNORE_LIST} " == *" ${filename} "* ]]; then
                loginfo "pylint skipping ${filename}"
            else
                $gwms_python -m pylint $PYLINT_OPTIONS ${filename}  >> ${out_pylint} || log_nonzero_rc "pylint" $?
                [[ $? -ne 0 ]] && files_errors="${files_errors} ${filename}"
                files_checked="${files_checked} ${filename}"
            fi
        fi
        if [[ "${DO_TESTS}" == *2* ]]; then
            $gwms_python -m pycodestyle $PEP8_OPTIONS ${filename} >> ${out_pycs} || log_nonzero_rc "pep8" $?
        fi
    done

    #files_checked="$(echo ${files_list})"

    local out_pycs_summary="${out_pycs}.summary"
    echo "# -------------------" > "${out_pycs_summary}"
    echo "# Error count summary" >> "${out_pycs_summary}"
    echo "# -------------------" >> "${out_pycs_summary}"
    awk '{$1=""; print $0}' ${out_pycs} | sort | uniq -c | sort -n >> "${out_pycs_summary}"
    # cat ${out_pycs}.summary     >> ${out_pycs}

    echo "# Pylint and PyCodeStyle output" >> "${outfile}"
    echo "PYLINT_FILES_CHECKED=\"${files_checked}\"" >> "${outfile}"
    echo "PYLINT_FILES_CHECKED_COUNT=`echo ${files_checked} | wc -w | tr -d " "`" >> "${outfile}"
    echo "PYLINT_PROBLEM_FILES=\"${files_errors}\"" >> "${outfile}"
    echo "PYLINT_ERROR_FILES_COUNT=`grep '^\*\*\*\*\*\*' ${out_pylint} | wc -l | tr -d " "`" >> "${outfile}"
    local pylint_error_count=$(grep '^E:' ${out_pylint} | wc -l | tr -d " ")
    echo "PYLINT_ERROR_COUNT=${pylint_error_count}" >> "${outfile}"
    echo "PEP8_FILES_CHECKED=\"${files_list}\"" >> "${outfile}"
    echo "PEP8_FILES_CHECKED_COUNT=`echo ${files_list} | wc -w | tr -d " "`" >> "${outfile}"
    local pep8_error_count=$(cat ${out_pycs} | wc -l | tr -d " ")
    echo "PEP8_ERROR_COUNT=${pep8_error_count}" >> "${outfile}"
    echo "----------------"
    cat "${outfile}"
    echo "----------------"

    # Ignore PEP8 errors/warning for failure status
    fail=${pylint_error_count}
    return ${fail}
}

do_table_headers() {
    # Tab separated list of fields
    # example of table header 2 fields available start with ',' to keep first field from previous item 
    echo -e "Pylint,Files\t,ErrFiles\t,ErrNum\tPyCodeStyle,ErrNum"
}

do_table_values() {
    # 1. branch summary file
    # 2. output format: if not empty triggers annotation
    # Return a tab separated list of the values
    # $VAR1 $VAR2 $VAR3 expected in $1
    . "$1"
    if [[ -n "$2" ]]; then
        local res="${PYLINT_FILES_CHECKED_COUNT}\t"
        res="${res}$(get_annotated_value check0 ${PYLINT_ERROR_FILES_COUNT})\t"
        res="${res}$(get_annotated_value check0 ${PYLINT_ERROR_COUNT})\t"
        echo -e "${res}$(get_annotated_value check0 ${PEP8_ERROR_COUNT} warning)"
    else
        echo -e "${PYLINT_FILES_CHECKED_COUNT}\t${PYLINT_ERROR_FILES_COUNT}\t${PYLINT_ERROR_COUNT}\t${PEP8_ERROR_COUNT}"
    fi
}

do_get_status() {
    # 1. branch summary file
    # Return unknown, success, warning, error
    . "$1"
    [[ -z "${PYLINT_ERROR_COUNT}" ]] && { echo unknown; return 2; }
    if [[ "${PYLINT_ERROR_COUNT}" -eq 0 ]]; then
        [[ "${PEP8_ERROR_COUNT}" -eq 0 ]] && { echo success; return; }
        echo warning
        return
    fi
    echo error
    return 1
}

do_log_init() {
    # No logging when showing the list of files
    [ -n "${SHOW_FILES}"} ] && return 1
    cat << TABLE_START
<table style="$HTML_TABLE">
  <thead style="$HTML_THEAD">
    <tr style="$HTML_TR">
      <th style="$HTML_THEAD_TH">GIT BRANCH</th>
      <th style="$HTML_THEAD_TH">FILES CHECKED</th>
      <th style="$HTML_THEAD_TH">FILES WITH ERRORS</th>
      <th style="$HTML_THEAD_TH">TOTAL ERRORS</th>
      <th style="$HTML_THEAD_TH">PEP8 ERRORS</th>
    </tr>
  </thead>
  <tbody>
TABLE_START
}

do_log_close() {
    cat << TABLE_END
  </tbody>
</table>
TABLE_END
}

do_log_branch() {
    local branch_results="$1"
    unset GIT_BRANCH
    unset GIT_CHECKOUT
    unset FILES_CHECKED_COUNT
    unset PYLINT_ERROR_FILES_COUNT
    unset PYLINT_ERROR_COUNT
    unset PEP8_ERROR_COUNT
    . "$branch_results"

    class=$GIT_CHECKOUT
    if [ "$class" = "PASSED" ]; then
        [ ${PYLINT_ERROR_COUNT:-1} -gt 0 ] && class="FAILED"
    fi
    if [ "$class" = "PASSED" ]; then
        cat << TABLE_ROW_PASSED
<tr style="$HTML_TR">
    <th style="$HTML_TH">$GIT_BRANCH</th>
    <td style="$HTML_TD_PASSED">${FILES_CHECKED_COUNT:-NA}</td>
    <td style="$HTML_TD_PASSED">${PYLINT_ERROR_FILES_COUNT:-NA}</td>
    <td style="$HTML_TD_PASSED">${PYLINT_ERROR_COUNT:-NA}</td>
    <td style="$HTML_TD_PASSED">${PEP8_ERROR_COUNT:-NA}</td>
</tr>
TABLE_ROW_PASSED
    else
        cat << TABLE_ROW_FAILED
<tr style="$HTML_TR">
    <th style="$HTML_TH">$GIT_BRANCH</th>
    <td style="$HTML_TD_FAILED">${FILES_CHECKED_COUNT:-NA}</td>
    <td style="$HTML_TD_FAILED">${PYLINT_ERROR_FILES_COUNT:-NA}</td>
    <td style="$HTML_TD_FAILED">${PYLINT_ERROR_COUNT:-NA}</td>
    <td style="$HTML_TD_FAILED">${PEP8_ERROR_COUNT:-NA}</td>
</tr>
TABLE_ROW_FAILED
    fi
}
