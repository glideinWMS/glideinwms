#!/bin/bash

function usage {
    echo "Usage: convert_frontend_2to3.sh <options>"
    echo "where <options> are:"
    echo "   -s <path>             : path to top directory glideinWMS source"
    echo "   -i <frontend-2.xml>   : v2 frontend.xml"
    echo "   -o <frontend-3.xml>   : v3 frontend.xml"
}

src=
input=
output=

while getopts "hs:i:o:" opt; do
    case $opt in
	h)
	    usage
	    exit 1
	    ;;
	s)
	    src=$OPTARG
	    ;;
	i)
	    input=$OPTARG
	    ;;
	o)
	    output=$OPTARG
    esac
done

if [[ -z $src ]] || [[ -z $input ]] || [[ -z $output ]]
then
    usage
    exit 1
fi

xsltproc -o $output ${src}/frontend/tools/convert_frontend_2to3.xslt \
    $input
