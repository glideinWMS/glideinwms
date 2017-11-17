#!/bin/bash
cd `dirname $0`
source ./setup.sh
out=$(ssh root@$fact_fqdn "yum list | grep '@'" )
while IFS= read ; do
   echo $REPLY
done <<< "$out"
