#!/bin/bash
cd `dirname $0`
source ./setup.sh
out=$(ssh -t root@$vofe_fqdn "yum list | grep '@'" )
while IFS= read ; do
   echo $REPLY
done <<< "$out"
