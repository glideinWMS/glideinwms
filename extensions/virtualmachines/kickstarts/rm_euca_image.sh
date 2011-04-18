#!/bin/bash

bucket=$1
prefix=$2
final_suffix=$3
ami_id=$4

cfg=/home/tiradani/EucalyptusTools/s3cmd/s3cfg

i=0
while [ $i -le $final_suffix ]
do
    echo "Deleting s3://${bucket}/${prefix}.part.${i}"
    s3cmd -c $cfg del s3://${bucket}/${prefix}.part.${i}
    i=$(( $i + 1 ))
done
echo "Deleting s3://${bucket}/${prefix}.manifest.xml"
s3cmd  -c $cfg del s3://${bucket}/${prefix}.manifest.xml

euca-deregister ${ami_id}
