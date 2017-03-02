#!/usr/bin/python
import os
from glideinwms.lib import condorMonitor

#fronmonpath = "/var/lib/gwms-factory/web-area/monitor/frontendmonitorlink.txt"
fronmonpath = "/tmp/frontendmonitorlink.txt"

# glideclient classads contain WebMonitoringURL propagted from Frontends
fronmonconstraint = '(MyType=="glideclient")'
fronmonformat_list = [('WebMonitoringURL','s'), ('FrontendName','s')]

fronmonstatus = condorMonitor.CondorStatus(subsystem_name="any")
fronmondata = fronmonstatus.fetch(constraint=fronmonconstraint, format_list=fronmonformat_list)

# a list of the Name attributes
fronmon_list_names = fronmondata.keys()

if fronmon_list_names is not None:
    urlset = set()
    # no need to keep the previous file
    if os.path.exists(fronmonpath):
       os.remove(fronmonpath)

    for frontend_entry in fronmon_list_names:
        # acquire the list of attributes
        fronmonelement = fronmondata[frontend_entry]
        fronmonurl = fronmonelement['WebMonitoringURL'].encode('utf-8')
        fronmonfrt = fronmonelement['FrontendName'].encode('utf-8')
        if (fronmonfrt,fronmonurl) not in urlset:
           urlset.add((fronmonfrt, fronmonurl))
           with open(fronmonpath, 'a') as f:
                f.write("%s, %s\n" % (fronmonfrt, fronmonurl))

#    for x in urlset:
#        print "Debug: %s, %s" % x



