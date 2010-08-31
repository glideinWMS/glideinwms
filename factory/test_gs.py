#
# Project:
#   glideinWMS
#
# File Version: 
#   $Id: test_gs.py,v 1.1.1.1.28.1 2010/08/31 18:49:16 parag Exp $
#

import condorMonitor
condorMonitor.set_path("/home/sfiligoi/condor/dist/bin")

def gs_hash(jel):
    universe=jel["JobUniverse"]
    if universe==7: #scheduler
        return None #ignore, will run locally
    elif universe==9: #grid
        if jel.has_key("WMSGlideinName"):
            return ["glidein",jel["WMSGlideinName"]]
        else:
            return None # ignore other Grid jobs
    else:
        return ["job",jel["Owner"]]

x=condorMonitor.CondorQwCount(None,gs_hash)
y=condorMonitor.CondorQwCount('schedd_glideins@cms-xen6.fnal.gov',gs_hash)
z=condorMonitor.CondorMultiQwCount([None,'schedd_glideins@cms-xen6.fnal.gov'],gs_hash)

