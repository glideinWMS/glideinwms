#!/bin/bash
# Attempt to fill the write buffer and exit normally
for ((i=0; $i<10000; i++)); do
  echo "$i"
  echo "This is line $i" 1>&2
done
exit 0
