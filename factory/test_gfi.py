#
# Project:
#   glideinWMS
#
# File Version: 
#   $Id: test_gfi.py,v 1.3 2011/06/15 22:06:26 klarson1 Exp $
#

import os,sys,glideFactoryInterface

glideFactoryInterface.factoryConfig.activity_log=sys.stdout
glideFactoryInterface.factoryConfig.warining_log=sys.stdout

glideFactoryInterface.advertizeGlidein("factory_name", 
                                       "glidein_name", 
                                       "entry_name", 
                                       "trust_domain", 
                                       "auth_method", 
                                       "supported_signtypes",
                                       "pub_key_obj",
                                       "myJobAttributes",
                                       "jobParams.data.copy()",
                                       "glidein_monitors.copy()")
