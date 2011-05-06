#
# Project:
#   glideinWMS
#
# File Version: 
#   $Id: test_gfi.py,v 1.1.1.1.12.1.4.2 2011/05/06 16:01:53 klarson1 Exp $
#

import os,sys,glideFactoryInterface

glideFactoryInterface.factoryConfig.activity_log=sys.stdout
glideFactoryInterface.factoryConfig.warining_log=sys.stdout

glideFactoryInterface.advertizeGlidein("factory_name", "glidein_name", "entry_name", "trust_domain", "auth_methods", ['sha1'], "key_obj")
