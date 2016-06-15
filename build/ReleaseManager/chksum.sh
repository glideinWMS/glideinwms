#!/bin/sh

###############################################################################
# Functions
###############################################################################

checksum() {
    md5sum="md5sum"
    file=$1
    chksum_file=$2

    platform="`uname`"
    case $platform in
        Linux)
            md5sum $f >> $chksum_file
            ;;
        Darwin)
            hash="`md5 $file | awk -F'=' '{print $NF}' | tr -d ' '`"
            echo "$hash  $file" >> $chksum_file
            ;;
        *) 
            echo "Build on $platform not supported"
            exit 1
            ;;
    esac
}

###############################################################################
# Main Starts Here
###############################################################################

if [ "x$1" = "x" ]; then
    echo "ERROR: Missing version as command line arg"
    exit 1
fi

version=$1
chksum_file=$2
ignore_patterns=$3
log_file="/tmp/log.$$"

files=`find . | grep -v CVS | grep -v doc | grep -v "pyc$" | grep -v "^\.$" | grep -v "\.swp$" | sort`


# Remove the file if it exists
if [ -f $f ]; then
    rm $chksum_file
fi

echo "###################################################################" >$chksum_file
echo "# GLIDEINWMS_VERSION $version" >>$chksum_file
echo "###################################################################" >>$chksum_file

pats_str=""
for p in $ignore_patterns
do
    pats_str="$pats_str -e $p "
done

for f in $files
do
    ignore="false"
    if [ -f $f ]; then
        res=`echo $f | grep $pats_str`

        if [ "$res" = "" ]; then
            checksum $f $chksum_file
        fi
    fi
done
echo "ALL DONE ... EXITING" >> $log_file
