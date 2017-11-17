#!/bin/bash
cd `dirname $0`
./factory.installed_software.sh | grep '^condor\.'
