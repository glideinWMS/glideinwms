#!/bin/sh

# NOTE: need some way to remove temp variables 
# look at http://content.hccfl.edu/pollock/ShScript/TempFile.htm

# NOTE: Could simplify methods or consolidate using options

TEST_RESULT="test_result"
OK_OUTPUT="ok_output"
ERROR_OUTPUT="error_output"

# --------------------------------------------------------- #
# header ()                                                 #
# generates and prints header                               #	
# --------------------------------------------------------- #
function header(){
    #OSGTestResult
	VER="<?xml version=\"1.0\"?>\n"
	OSG="<OSGTestResult id=\""
	OSGEnd="\" version=\"1.2\">"
	echo $VER$OSG$1$OSGEnd > $TEST_RESULT
    
    #test
    echo "  <test>\n    <cmd>"$2" "$3" "$4"</cmd>\n" >> $TEST_RESULT
    echo "    <tStart>"$5"</tStart>\n" >> $TEST_RESULT
    echo "    <tEnd>"$6"</tEnd>\n" >> $TEST_RESULT
    echo "  <\test>"
	return
}

# --------------------------------------------------------- #
# result_ok ()                                              #
# generates and prints result tags                          #
# --------------------------------------------------------- #
function result_ok(){
	echo "  <result>" >> $TEST_RESULT
	parse_ok
	echo "  </result>" >> $TEST_RESULT
	return
}

# --------------------------------------------------------- #
# result_error ()                                           #
# generates and prints result tags                          #
# --------------------------------------------------------- #
function result_error(){
	echo "  <result>" >> $TEST_RESULT
	parse_error
	echo "  </result>" >> $TEST_RESULT
	parse_detail
	return
}

# --------------------------------------------------------- #
# parse_ok ()                                               #
# retrieves status and metric from xml output               #
# --------------------------------------------------------- #
function parse_ok(){
	awk ' /status/ {print $0}' $OK_OUTPUT >> $TEST_RESULT
	awk ' /metric/ {print $0}' $OK_OUTPUT >> $TEST_RESULT
}

# --------------------------------------------------------- #
# parse_error ()                                            #
# retrieves status and metric from xml output               #
# --------------------------------------------------------- #
function parse_error(){
	awk ' /status/ {print $0}' error_output >> $TEST_RESULT
	awk ' /metric/ {print $0}' error_output >> $TEST_RESULT
}


# --------------------------------------------------------- #
# parse_detail ()                                           #
# retrieves detail from xml output                          #
# --------------------------------------------------------- #
function parse_detail(){
	awk ' /detail/ {print $0}' error_output >> $TEST_RESULT
}

# --------------------------------------------------------- #
# close ()                                                  #
# generate and append header close tags.                    #
# --------------------------------------------------------- #
function close(){
	echo "</OSGTestResult>" >> $TEST_RESULT
	return
}

############################################################
#
# Main
#
############################################################
header $1 $2 $3 $4 $5 $6
if [ -f $OK_OUTPUT ]; then
	result_ok
fi

if [ -f $ERROR_OUTPUT ]; then
	result_error
fi

close

cat $TEST_RESULT 1>&2




