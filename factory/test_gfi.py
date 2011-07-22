#
# Project:
#   glideinWMS
#
# File Version: 
#

import os,sys,glideFactoryInterface

glideFactoryInterface.factoryConfig.activity_log=sys.stdout
glideFactoryInterface.factoryConfig.warining_log=sys.stdout

glideFactoryInterface.advertizeGlidein("factory_name", "glidein_name", "entry_name", "trust_domain", "auth_method", ['sha1'], "key_obj")
