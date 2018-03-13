#!/bin/bash

function sanitizedCat {
    # This function prints the saniteized content of the file passed as argument.
    # If the content is a number it just prints it, if it is an alphanumeric string it adds quotes
    # and prints it, otherwise it prints "WrongFormat"
    VAL=$(cat "$1")
    if [[ $VAL =~ ^[0-9]+(.[0-9]+)?$ ]]; then
        echo $VAL
    elif [[ $VAL =~ ^[^\"\\]+$ ]]; then
        echo \"$VAL\"
    else
        echo '"WrongFormat"'
    fi
}

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
            sanitizedCat "$VARNAME/$FILENAME"
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
                    sanitizedCat $TMPFILE
                    rm $TMPFILE
                    return
                fi
                rm $TMPFILE
            fi
        fi
    fi
    echo '"Unknown"'
}
