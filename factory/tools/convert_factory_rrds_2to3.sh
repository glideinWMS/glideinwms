#!/bin/sh

function usage {
    echo "Usage: convert_factory_rrds_2to3.sh <options>"
    echo "where <options> are:"
    echo "   -c <glideinWMS.xml>   : full path to the v3 glideinWMS config file"
}

src=
input=
output=

while getopts "h:c:" opt; do
    case $opt in
        h)
            usage
            exit 1
            ;;
        c)
            config=$OPTARG
            ;;
    esac
done

if [ -z $config ]; then
    usage
    exit 1
fi

monitor_base_dir=`grep monitor $config | grep base_dir | grep javascriptRRD_dir | awk -F'base_dir=' '{print $2}' | awk -F'"' '{print $2}'`
versioning=`grep factory_versioning $config | awk -F'factory_versioning=' '{print $2}' | awk -F'"' '{print $2}'`

if [ "$versioning" = "True" ]; then
    version=`grep glidein_name $config | awk -F'glidein_name=' '{print $2}' | awk -F'"' '{print $2}'`
    monitor_dir="$monitor_base_dir/glidein_$version"
else
    monitor_dir=$monitor_base_dir
fi

rrds=`find $monitor_dir -name Status_Attributes.rrd`

echo "Using glideinWMS.xml: $config"
echo
echo "Converting relevant rrds (Status_Attributes.rrd) in the monitor dir: $monitor_dir"
echo

for rrd in $rrds
do
    rrdtool tune $rrd --data-source-rename ReqMaxRun:ReqMaxGlideins
done
