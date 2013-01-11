#
# Project:
#   glideinWMS
#
# File Version: 
#

import os,sys
from glideinwms.factory import glideFactoryInterface

glideFactoryInterface.factoryConfig.activity_log=sys.stdout
glideFactoryInterface.factoryConfig.warining_log=sys.stdout

glideFactoryInterface.advertizeGlidein("cmsitb_test3",{"Arch":"INTEL","OpSys":"Linux"},{"MinDisk":10000},{"Running":5,"Idle":10})
