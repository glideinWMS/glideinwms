#!/bin/bash
#
# Project:
#   glideinWMS
#
# Description:
#   Helper script to finalize finalize the XML output
#   file of a validation test
#   Adds the part that is know to the caller.
#

# --------------------------------------------------------- #
# header ()                                                 #
# generate and append header tag                            #
# --------------------------------------------------------- #
function header() {
    DATEFMT="+%Y-%m-%dT%H:%M:%S%:z"
    echo '<?xml version="1.0"?>' > otrx_output.xml #NOTE: wipe previous output file
    echo "<OSGTestResult id=\"$1\" version=\"4.3.1\">" >>otrx_output.xml
    echo "  <operatingenvironment>" >> otrx_output.xml
    echo "    <env name=\"cwd\">$2</env>" >> otrx_output.xml
    echo "  </operatingenvironment>" >> otrx_output.xml
    echo "  <test>" >> otrx_output.xml
    echo "    <cmd>$3</cmd>" >> otrx_output.xml
    echo "    <tStart>`date --date=@$4 $DATEFMT`</tStart>" >> otrx_output.xml
    echo "    <tEnd>`date --date=@$5 $DATEFMT`</tEnd>" >> otrx_output.xml
    echo "  </test>" >> otrx_output.xml
    return
}

# --------------------------------------------------------- #
# close ()                                                  #
# generate and append header close tags.                    #
# --------------------------------------------------------- #
function close(){
    echo "</OSGTestResult>" >> otrx_output.xml
    return
}

# --------------------------------------------------------- #
# propagate_content ()                                      #
# propagate content from test output to augmented output    #
# --------------------------------------------------------- #
function propagate_content(){
    #copy over only the part between <result> ... </result>
    cat otrb_output.xml | awk 'BEGIN{fr=0;}/<[/]OSGTestResult>/{fr=0;}{if (fr==1) print $0}/<OSGTestResult/{fr=1;}' >> otrx_output.xml
    return
}

# ------------------------------------------------------------- #
# process_valid_file ()                                         #
# process the test output file and create an augmented version  #
# assume the file is valid
# ------------------------------------------------------------- #
function process_valid_file() {
    shift
    header "$@"
    propagate_content
    close
    return
}

# --------------------------------------------------------- #
# create_empty ()                                           #
# create a augmented file with minimal info                 #
# --------------------------------------------------------- #
function create_empty() {
    res=$1
    shift
    header "$@"
    echo "  <result>" >> otrx_output.xml
    if [ "$res" -eq 0 ]; then
	echo "    <status>OK</status>" >> otrx_output.xml
    else
	echo "    <status>ERROR</status>" >> otrx_output.xml
    fi
    echo "  </result>" >> otrx_output.xml
    echo "  <detail>" >> otrx_output.xml
    echo "     The test script did not produce an XML file. No further information available." >> otrx_output.xml
    echo "  </detail>" >> otrx_output.xml
    close
    return
}

# ------------------------------------ #
# validate ()                          #
# validate the test output file        #
# return 0 iff it is considered valid  #
# ------------------------------------ #
function validate() {
    # do only basic testing
    # do not want to rely on external xml tools

    h1=`cat otrb_output.xml |head -4| grep '<OSGTestResult '`
    if [ "$h1" == "" ]; then
	# could not find header
	return 1
    fi

    h2=`cat otrb_output.xml |head -8| grep '<result>'`
    if [ "$h2" == "" ]; then
	# could not find header
	return 1
    fi

    f1=`cat otrb_output.xml |tail -4| grep '</OSGTestResult>'`
    if [ "$f1" == "" ]; then
	# could not find footer
	return 1
    fi

    f2=`cat otrb_output.xml |grep '</result>'`
    if [ "$f2" == "" ]; then
	# could not find footer
	return 1
    fi

    s1=`cat otrb_output.xml |grep '<status>'`
    if [ "$s1" == "" ]; then
	# could not find status line
	return 1
    fi

    s2=`echo "$s1" |grep OK`
    if [ "$1" -eq 0 ]; then
	if [ "$s2" == "" ]; then
	    # the status should have been OK, but I cannot find that
	    return 1
	fi
    else
	if [ "$s2" != "" ]; then
	    # the status cannot be OK! the script failed
	    return 1
	fi
    fi
   
    return 0
}


# ------------------------------------------------------------- #
# process_file ()                                               #
# process the test output file and create an augmented version  #
# ------------------------------------------------------------- #
function process_file() {
    validate "$1"
    rc=$?

    if [ $rc -ne 0 ]; then
	create_empty "$@"
    else
	process_valid_file "$@" 
    fi
}

# --------------------------------------------------------- #
# init_file ()                                              #
# initialize output file                                    #
# --------------------------------------------------------- #
function init_file() {
    echo "" > otrb_output.xml
}

# --------------------------------------------------------- #
# concat_file ()                                            #
# concatenate the augmented file to the list                #
# --------------------------------------------------------- #
function concat_file() {
    if [ -f otr_outlist.list ]; then
      chmod u+w otr_outlist.list
    else
      touch otr_outlist.list
    fi
    # strip out any spurious items
    cat otrx_output.xml |awk 'BEGIN{fr=0;}/<OSGTestResult/{fr=1;}{if (fr==1) print $0}/<[/]OSGTestResult>/{fr=0;}' >> otr_outlist.list
    # make sure it is not modified by mistake by any test script
    chmod a-w otr_outlist.list
    return
}

# --------------------------------------------------------- #
# usage ()                                                  #
# print usage                                               #
# --------------------------------------------------------- #
function usage(){
    echo "Usage: -init|-process|-concat [params]"
    echo "       -init"
    echo "       -process errno id cwd cmdline start end"
    echo "       -concat"
    return
}


############################################################
#
# Main
#
############################################################
mycmd=$1
shift

case "$mycmd" in
    -init)    init_file ;;
    -process) process_file "$@";;
    -concat)  concat_file ;;
    *)  (warn "Unknown option $mycmd"; usage) 1>&2; exit 1
esac


