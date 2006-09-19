import os,sys,glideinFrontendInterface

glideins=glideinFrontendInterface.findGlideins()
for name in glideins.keys():
    print name
    glideinFrontendInterface.advertizeWork(None,"test_gfi","gfi_"+name,
                                           name,4,
                                           {"GLIDEIN_Collector":"cms-xen6.fnal.gov"})

