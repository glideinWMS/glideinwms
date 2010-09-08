#
# Project:
#   glideinWMS
#
# File Version: 
#   $Id: test_gfi.py,v 1.2.12.1 2010/09/08 03:12:32 parag Exp $
#

import os,sys,glideinFrontendInterface

glideins=glideinFrontendInterface.findGlideins()
for name in glideins.keys():
    print name
    glideinFrontendInterface.advertizeWork(None,"test_gfi","gfi_"+name,
                                           name,4,
                                           {"GLIDEIN_Collector":"cms-xen6.fnal.gov"})

