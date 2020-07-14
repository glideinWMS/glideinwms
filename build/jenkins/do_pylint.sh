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
  Run pylint and exit the outfile to standard output
${filename} [options] ${COMMAND} [other command options] TEST_FILES
  Runs shellcheck on TEST_FILES files in glidinwms/
${filename} [options] ${COMMAND} -a [other command options]
  Run pylint on all the shell files in glidinwms/
Command options:
  -h        print this message
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
# E123 (*)  closing bracket does not match indentation of opening bracket’s line
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
# E201  whitespace after ‘(‘
#PYSTYLE_OPTIONS="$PYSTYLE_OPTIONS,E201"
# E202  whitespace before ‘)’
#PYSTYLE_OPTIONS="$PYSTYLE_OPTIONS,E202"
# E203  whitespace before ‘:’
#PYSTYLE_OPTIONS="$PYSTYLE_OPTIONS,E203"
# E211  whitespace before ‘(‘
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
# E231  missing whitespace after ‘,’, ‘;’, or ‘:’
PYSTYLE_OPTIONS="$PYSTYLE_OPTIONS,E231"
# E241 (*)  multiple spaces after ‘,’
#PYSTYLE_OPTIONS="$PYSTYLE_OPTIONS,E241"
# E242 (*)  tab after ‘,’
#PYSTYLE_OPTIONS="$PYSTYLE_OPTIONS,E242"
# E251  unexpected spaces around keyword / parameter equals
#PYSTYLE_OPTIONS="$PYSTYLE_OPTIONS,E251"
# E261  at least two spaces before inline comment
PYSTYLE_OPTIONS="$PYSTYLE_OPTIONS,E261"
# E262  inline comment should start with ‘# ‘
#PYSTYLE_OPTIONS="$PYSTYLE_OPTIONS,E262"
# E265  block comment should start with ‘# ‘
PYSTYLE_OPTIONS="$PYSTYLE_OPTIONS,E265"
# E266  too many leading ‘#’ for block comment
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
# E711 (^)  comparison to None should be ‘if cond is None:’
#PYSTYLE_OPTIONS="$PYSTYLE_OPTIONS,E711"
# E712 (^)  comparison to True should be ‘if cond is True:’ or ‘if cond:’
#PYSTYLE_OPTIONS="$PYSTYLE_OPTIONS,E712"
# E713  test for membership should be ‘not in’
#PYSTYLE_OPTIONS="$PYSTYLE_OPTIONS,E713"
# E714  test for object identity should be ‘is not’
#PYSTYLE_OPTIONS="$PYSTYLE_OPTIONS,E714"
# E721 (^)  do not compare types, use ‘isinstance()’
#PYSTYLE_OPTIONS="$PYSTYLE_OPTIONS,E721"
# E722  do not use bare except, specify exception instead
#PYSTYLE_OPTIONS="$PYSTYLE_OPTIONS,E722"
# E731  do not assign a lambda expression, use a def
#PYSTYLE_OPTIONS="$PYSTYLE_OPTIONS,E731"
# E741  do not use variables named ‘l’, ‘O’, or ‘I’
#PYSTYLE_OPTIONS="$PYSTYLE_OPTIONS,E741"
# E742  do not define classes named ‘l’, ‘O’, or ‘I’
#PYSTYLE_OPTIONS="$PYSTYLE_OPTIONS,E742"
# E743  do not define functions named ‘l’, ‘O’, or ‘I’
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
# W601  .has_key() is deprecated, use ‘in’
#PYSTYLE_OPTIONS="$PYSTYLE_OPTIONS,W601"
# W602  deprecated form of raising exception
#PYSTYLE_OPTIONS="$PYSTYLE_OPTIONS,W602"
# W603  ‘<>’ is deprecated, use ‘!=’
#PYSTYLE_OPTIONS="$PYSTYLE_OPTIONS,W603"
# W604  backticks are deprecated, use ‘repr()’
#PYSTYLE_OPTIONS="$PYSTYLE_OPTIONS,W604"
# W605  invalid escape sequence ‘x’
#PYSTYLE_OPTIONS="$PYSTYLE_OPTIONS,W605"
# W606  ‘async’ and ‘await’ are reserved keywords starting with Python 3.7
#PYSTYLE_OPTIONS="$PYSTYLE_OPTIONS,W606"


# Uncomment to see all pep8 errors
#PYSTYLE_OPTIONS=""

do_show_flags() {
    echo "Pylint will run with options:"
    echo "$PYLINT_OPTIONS"
    echo "PyCodeStyle will run with options:"
    echo "$PYSTYLE_OPTIONS"
}

do_parse_options() {
    pass;
}

do_get_dependencies() { pass; }

do_git_init_command() { git submodule update --init --recursive; }

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

    local branch="$1"
    local outdir="$(dirname "$2")"
    local outfile="$(basename "$2")"
    local branch_noslash="${outfile#*.}"
    shift 2
    local test_date=$(date "+%Y-%m-%d %H:%M:%S")
    #SOURCES="$(get_source_directories)"

    local fail
    local fail_all=0

    local branch_outdir="${outdir}/${branch_noslash}"
    mkdir -p "${branch_outdir}

    echo "#####################################################"
    echo "Start : ${branch}"
    start_time="$(date -u +%s.%N)"

    # get list of python scripts without .py extension
    magic_file="$(find_aux gwms_magic)"
    FILE_MAGIC=
    [ -e  "$magic_file" ] && FILE_MAGIC="-m $magic_file"

    scripts=$(find glideinwms -readable -path glideinwms/.git -prune -o -exec file $FILE_MAGIC {} \; -a -type f | grep -i ':.*python' | grep -vi python3 | grep -vi '\.py' | cut -d: -f1 | grep -v "\.html$" | sed -e 's/glideinwms\///g')
    echo "-- DBG $(echo $scripts | wc -w | tr -d " ") scripts found using magic file ($FILE_MAGIC) --"
    cd "${GLIDEINWMS_SRC}"
    for script in $scripts; do
      #can't seem to get --ignore or --ignore-modules to work, so do it this way
      PYLINT_SKIP="False"
      for ignore in $PYLINT_IGNORE_LIST; do
          if [ "$ignore" = "$script" ] ; then
             echo "pylint skipping $script" >>  "$outfile"
             PYLINT_SKIP="True"
          fi
      done
      if [ "$PYLINT_SKIP" != "True" ]; then
          python3 -m pylint $PYLINT_OPTIONS ${script}  >> $outfile || log_nonzero_rc "pylint" $?
      fi
      python3 -m pycodestyle $PEP8_OPTIONS ${script} >> ${outfile} || log_nonzero_rc "pep8" $?
    done

    currdir=`pwd`
    files_checked=`echo $scripts`

    #now do all the .py files
    #shopt -s globstar
    py_files=$(find . -readable -type f -name '*\.py')
    for file in $py_files
    do
      files_checked="$files_checked $file"
      PYLINT_SKIP="False"
      for ignore in $PYLINT_IGNORE_LIST; do
          if [ "$ignore" = "$file" ] ; then
             echo "pylint skipping $file" >>  "$outfile"
             PYLINT_SKIP="True"
          fi
      done
      if [ "$PYLINT_SKIP" != "True" ]; then
          python3 -m pylint $PYLINT_OPTIONS $file >> "$outfile" || log_nonzero_rc "pylint" $?
      fi
      python3 -m pycodestyle $PEP8_OPTIONS $file >> "${outfile}" || log_nonzero_rc "pep8" $?
    done
    awk '{$1=""; print $0}' ${outfile} | sort | uniq -c | sort -n > ${outfile}.sorted
    echo "-------------------" >> ${outfile}
    echo "error count summary" >> ${outfile}
    echo "-------------------" >> ${outfile}
    cat ${outfile}.sorted     >> ${outfile}
    cd $currdir

    echo "FILES_CHECKED=\"$files_checked\"" >> $outfile
    echo "FILES_CHECKED_COUNT=`echo $files_checked | wc -w | tr -d " "`" >> $outfile
    echo "PYLINT_ERROR_FILES_COUNT=`grep '^\*\*\*\*\*\*' $outfile | wc -l | tr -d " "`" >> $outfile
    echo "PYLINT_ERROR_COUNT=`grep '^E:' $outfile | wc -l | tr -d " "`" >> $outfile
    echo "PEP8_ERROR_COUNT=`cat ${outfile} | wc -l | tr -d " "`" >> $outfile
    echo "----------------"
    cat $outfile
    echo "----------------"

    fail_all=0
#    [[ $total_error -gt 0 ]] && fail_all=1
    return ${fail_all}
}
