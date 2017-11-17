#!/bin/sh
ls -lart $SPOOF/tmp/setnodes* | tail -1 | perl -ne '@a=split(); print "$a[$#a]\n";'
