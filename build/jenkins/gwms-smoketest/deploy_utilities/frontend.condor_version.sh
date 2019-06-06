#!/bin/bash
cd `dirname $0`
./frontend.installed_software.sh | grep '^condor\.'
