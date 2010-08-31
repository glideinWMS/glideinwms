#
# Project:
#   glideinWMS
#
# File Version: 
#   $Id: test_gfi.py,v 1.2.28.1 2010/08/31 18:49:17 parag Exp $
#

import os,sys,glideinFrontendInterface

glideins=glideinFrontendInterface.findGlideins()
for name in glideins.keys():
    print name
    glideinFrontendInterface.advertizeWork(None,"test_gfi","gfi_"+name,
                                           name,4,
                                           {"GLIDEIN_Collector":"cms-xen6.fnal.gov"})

