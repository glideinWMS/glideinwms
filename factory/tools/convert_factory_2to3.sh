#!/bin/bash

function usage {
    echo "Usage: convert_factory_2to3.sh <options>"
    echo "where <options> are:"
    echo "   -s <path>             : path to top directory glideinWMS source"
    echo "   -i <glideinWMS-2.xml>   : v2 glideinWMS.xml"
    echo "   -o <glideinWMS-3.xml>   : v3 glideinWMS.xml"
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

xsltproc -o $output ${src}/factory/tools/convert_factory_2to3.xslt \
    $input
