#!/bin/bash

image_path=$1
image_name=$2
bucket_name=$3

# Setup Credentials - For NERSC
source /home/tiradani/EucalyptusTools/NERSC-Credentials/eucarc

# Bundle the created image
euca-bundle-image -i ${image_path} -s 10240 -d /tmp/${image_name} --kernel eki-A86F17CD --ramdisk eri-1062190B -p ${image_name}
# Upload the bundled image
euca-upload-bundle -b ${bucket_name} -m /tmp/${image_name}/${image_name}.manifest.xml
# Register the uploaded image
euca-register ${bucket_name}/${image_name}.manifest.xml



