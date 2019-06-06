#!/bin/bash
if [ ! -f latest_nodes.sh ]; then
   cd `dirname $0`
fi
[ "$fact_fqdn" = "" ] ||  [ "$vofe_fqdn" = "" ] && source $(./latest_nodes.sh)

