#
# Project:
#   glideinWMS
#
# File Version: 
#   $Id: test_gfi.py,v 1.1.1.1.28.1 2010/08/31 18:49:16 parag Exp $
#

import os,sys,glideFactoryInterface

glideFactoryInterface.factoryConfig.activity_log=sys.stdout
glideFactoryInterface.factoryConfig.warining_log=sys.stdout

glideFactoryInterface.advertizeGlidein("cmsitb_test3",{"Arch":"INTEL","OpSys":"Linux"},{"MinDisk":10000},{"Running":5,"Idle":10})
