#
# Project:
#   glideinWMS
#
# File Version: 
#   $Id: test_gfi.py,v 1.1.1.1.12.1.4.3 2011/06/16 18:23:24 klarson1 Exp $
#

import os,sys,glideFactoryInterface

glideFactoryInterface.factoryConfig.activity_log=sys.stdout
glideFactoryInterface.factoryConfig.warining_log=sys.stdout

glideFactoryInterface.advertizeGlidein("factory_name", "glidein_name", "entry_name", "trust_domain", "auth_method", ['sha1'], "key_obj")
