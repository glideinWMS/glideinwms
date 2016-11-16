#!/bin/bash

function getValueFromFileOrURL {
    # The function takes as an argument a filename and a variable name
    # The variable contains the url or the directory location of the file,
    # so $1 can be shutdowntime_job
    # and $2 /path/to/jobfeature/dir
    # The function returns the value found in the file (by cat-ing it), or Unknown
    # if the file does not exist or $2 is empty
    FILENAME="$1"
    VARNAME="$2"
    if [ -n "$VARNAME" ]; then
        if [ -f "$VARNAME/$FILENAME" ]; then
            cat "$VARNAME/$FILENAME"
            return
        else
            #check if shutdowntime job is a URL and wget it
            ADDRESS="$VARNAME/$FILENAME"
            echo $ADDRESS | grep -E '^https?' > /dev/null
            if [ $? -eq 0 ]; then
                #use quiet mode and redirect file to a temporary one
                TMPFILE=tmp_$(uuidgen)
                wget -qO- $ADDRESS > $TMPFILE
                if [ $? -eq 0 ]; then
                    cat $TMPFILE
                    rm $TMPFILE
                    return
                fi
                rm $TMPFILE
            fi
        fi
    fi
    echo '"Unknown"'
}


function python_b64uuencode {
    echo "begin-base64 644 -"
    python -c 'import binascii,sys;fd=sys.stdin;buf=fd.read();size=len(buf);idx=0
while size>57:
 print binascii.b2a_base64(buf[idx:idx+57]),;
 idx+=57;
 size-=57;
print binascii.b2a_base64(buf[idx:]),'
    echo "===="
}


function base64_b64uuencode {
    echo "begin-base64 644 -"
    base64 -
    echo "===="
}


# Filter b64 encoding stdin to stdout
# Not all nodes have all the tools installed: using alternatively uuencode, base64, python
function b64uuencode {
    which uuencode >/dev/null 2>&1
    if [ $? -eq 0 ]; then
        uuencode -m -
    else
        which base64 >/dev/null 2>&1
        if [ $? -eq 0 ]; then
            base64_b64uuencode
        else
            python_b64uuencode
        fi
    fi
}


function print_file_limited {
    # Echo to stderr the file passed (or portion of it), compressed and uuencoded
    # $1 = fname - descriptive name for the output stream
    # $2 = flength - length in MB to keep (0 no limit (default), +n n MB from the end, -n n MB from the head)
    # $3 = fpath - this may include multiple files (but they are put together in the same stream)
    local fname=$1
    local lim_num
    local lim_cmd=""
    if [ $2 -ne 0 ]; then
        # tail works also w/ negative numbers, head requires positive ones
        let lim_num=$2*1024*-1024
        if [ $2 -gt 0 ]; then
            lim_cmd="tail -c $lim_num"
        else
            lim_cmd="head -c $lim_num"
        fi
    fi
    shift 2
    # Use ls to allow fpath to include wild cards
    files_to_zip="`ls -1 $@ 2>/dev/null`"
    if [ "$files_to_zip" != "" ]; then
        echo "$fname" 1>&2
        if [ -z "$lim_cmd" ]; then
            echo "======== gzip | uuencode =============" 1>&2
            gzip --stdout $files_to_zip | b64uuencode 1>&2
        else
            echo "======== $lim_cmd | gzip | uuencode =============" 1>&2
            cat $files_to_zip | $lim_cmd | gzip --stdout | b64uuencode 1>&2
        fi
        echo
    fi
}


