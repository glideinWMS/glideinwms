#!/bin/bash
cd `dirname $0`
[ "$fact_fqdn" = "" ] ||  [ "$vofe_fqdn" = "" ] && source $(./latest_nodes.sh)

