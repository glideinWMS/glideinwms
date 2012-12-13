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
