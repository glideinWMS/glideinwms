#!/bin/sh

#############################################################
# variables                                                 #
#############################################################
OK_FILE="ok_output"
ERROR_FILE="error_output"


# --------------------------------------------------------- #
# detail ()                                                 #
# generate and append detail tag                            #
# --------------------------------------------------------- #
function detail(){
	echo "    <detail>"`cat string`"</detail>" >> output
	return
}

# --------------------------------------------------------- #
# header ()                                                 #
# generate and append header tag                            #
# --------------------------------------------------------- #
function header(){
	OSG="<OSGTestResult id=\""
	OSGEnd="\" version=\"1.2\">"
	RES="<result>"
	echo $OSG$1$OSGEnd"\n  "$RES > output #NOTE: wipe previous output file
	return
}

# --------------------------------------------------------- #
# close ()                                                  #
# generate and append header close tags.                    #
# --------------------------------------------------------- #
function close(){
	echo "  </result>\n</OSGTestResult>" >> output
	return
}

# --------------------------------------------------------- #
# metric_error ()                                           #
# generate and append metric tag for errors                 #
# --------------------------------------------------------- #
function metric_error(){
	DATE=`date "+%Y-%m-%dT%H:%M:%S"`
    echo "    <metric name=\"failure\" ts=\""$DATE"\" uri=\"local\">"$1"</metric>" >> output
	echo "    <metric name=\""$2"\" ts=\""$DATE"\" uri=\"local\">"$3"</metric>" >> output
    if [ $# -eq 5 ]; then
        echo "    <metric name=\""$4"\" ts=\""$DATE"\" uri=\"local\">"$5"</metric>" >> output
    fi
	return
}

# --------------------------------------------------------- #
# metric_ok ()                                              #
# generate and append metric tag for OK jobs                #
# --------------------------------------------------------- #
function metric_ok(){
    DATE=`date "+%Y-%m-%dT%H:%M:%S"`
    echo "    <metric name=\""$1"\" ts=\""$DATE"\" uri=\"local\">"$2"</metric>" >> output
    return
}

# --------------------------------------------------------- #
# status_ok ()                                              #
# generate and append status tag for OK jobs                #
# --------------------------------------------------------- #
function status_ok(){
	echo "    <status> OK </status>" >> output
	metric_ok $1 $2
	close
	if [ -f $OK_FILE ]; then
		cat output >> $OK_FILE
	else
		cat output > $OK_FILE
	fi
	return
}

# --------------------------------------------------------- #
# status_error ()                                           #
# generate and append status tag for error jobs             #
# --------------------------------------------------------- #
function status_error(){
	echo "    <status> ERROR </status>" >> output
    if [ $# -eq 3 ]; then
        metric_error $1 $2 $3
    else
        metric_error $1 $2 $3 $4 $5
    fi
	detail
	close
	if [ -f $ERROR_FILE ]; then
		cat output >> $ERROR_FILE
	else
		cat output > $ERROR_FILE
	fi
	return
}


# --------------------------------------------------------- #
# usage ()                                                  #
# print usage                                               #
# --------------------------------------------------------- #
usage()
{
	echo "Usage: -error -ok {params}"; 
	return
}


############################################################
#
# Main
#
############################################################
header $2

if [ $# -eq 7 ]; then
    case "$1" in
        -error)    status_error $3 $4 $5 $6 $7;;
        -ok)       status_ok $3 $4;;
        *)  (warn "Unknown option $1"; usage) 1>&2; exit 1
        esac
else
    case "$1" in
        -error)    status_error $3 $4 $5;;
        -ok)       status_ok $3 $4;;
        *)  (warn "Unknown option $1"; usage) 1>&2; exit 1
    esac
fi


