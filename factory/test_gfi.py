#
# Project:
#   glideinWMS
#
# File Version: 
#

import os,sys
from glideinwms.factory import glideFactoryInterface
from glideinwms.lib import classadSupport

glideFactoryInterface.factoryConfig.activity_log=sys.stdout
glideFactoryInterface.factoryConfig.warining_log=sys.stdout

tmpnam = classadSupport.generate_classad_filename(prefix='gfi_ad_gf')

gf_classad = glideFactoryInterface.EntryClassad("factory_name",
                                       "glidein_name", 
                                       "entry_name", 
                                       "trust_domain", 
                                       "auth_method", 
                                       "supported_signtypes",
                                       "pub_key_obj",
                                       "myJobAttributes",
                                       "jobParams.data.copy()",
                                       "glidein_monitors.copy()")

try:
    gf_classad.writeToFile(tmpnam, append=False)
    glideFactoryInterface.exe_condor_advertise(tmpnam, "UPDATE_MASTER_AD", factory_collector=glideFactoryInterface.DEFAULT_VAL)
finally:
    # Unable to write classad
    try:
        os.remove(tmpnam)
    except:
        # Do the possible to remove the file if there
        pass
