#
# Project:
#   glideinWMS
#
# File Version: 
#   $Id: test_gfi.py,v 1.2 2011/02/10 21:35:30 parag Exp $
#

import os,sys,glideFactoryInterface

glideFactoryInterface.factoryConfig.activity_log=sys.stdout
glideFactoryInterface.factoryConfig.warining_log=sys.stdout

glideFactoryInterface.advertizeGlidein("cmsitb_test3",{"Arch":"INTEL","OpSys":"Linux"},{"MinDisk":10000},{"Running":5,"Idle":10})
