#
# Project:
#   glideinWMS
#
# File Version: 
#   $Id: test_gf.py,v 1.1.1.1.28.1 2010/08/31 18:49:16 parag Exp $
#

import os,sys
import glideFactoryConfig
import glideFactoryLib
os.chdir("/home/sfiligoi/glidein_test9")
glideFactoryLib.factoryConfig.activity_log=sys.stdout
glideFactoryLib.factoryConfig.warining_log=sys.stdout

jobDescript=glideFactoryConfig.JobDescript()
jobParams=glideFactoryConfig.JobParams()

#os.environ['GLIDEIN_VERBOSITY']='dbg'
#os.environ['GLIDEIN_PARAMS']='-param_GLIDEIN_Collector cms-xen6.fnal.gov'

#a=glideFactoryLib.submitGlideins("schedd_glideins@cms-xen6.fnal.gov",1)

q=glideFactoryLib.getCondorQData(jobDescript.data['FactoryName'],jobDescript.data['GlideinName'],'test_gf',jobDescript.data['Schedd'])
s=glideFactoryLib.getCondorStatusData(jobDescript.data['FactoryName'],jobDescript.data['GlideinName'],'test_gf')

glideFactoryLib.logStats(q,s)

a=glideFactoryLib.keepIdleGlideins(q,18,{'GLIDEIN_Collector':'cms-xen6.fnal.gov'})
b=glideFactoryLib.sanitizeGlideins(q,s)

