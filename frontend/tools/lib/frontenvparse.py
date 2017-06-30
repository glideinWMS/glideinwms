# Project:
#   glideinWMS
#
# Description:
#   This module provide common functions needed to parse
#   the arguments used by the frontend environment setting
#   tools
#
# Author:
#   Igor Sfiligoi
#

import os
from glideinwms.frontend import glideinFrontendConfig

class FEConfig:
    def config_optparse(self, argparser):
        """
        Configure a optparse.OptionParser object
        """
        argparser.add_option("-d", "--work-dir", dest="work_dir",
                             help="Frontend work dir (default: $FE_WORK_DIR)", metavar="DIR",
                             default=os.environ.get("FE_WORK_DIR"))
        argparser.add_option("-g", "--group-name", dest="group_name",
                             help="Frontend group name (default: $FE_GROUP_NAME)", metavar="GROUP_NAME",
                             default=os.environ.get("FE_GROUP_NAME"))
        
    def load_frontend_config(self, options):
        """
        Given the reulst of a optparse.OptionParser.parge_args call
        extract the relevant info, load the frontend config and
        return a glideinFrontendConfig.ElementMergedDescript object
        """
        self.options=options
        
        self.validate_options()
        self.elementDescript = glideinFrontendConfig.ElementMergedDescript(self.options.work_dir, self.options.group_name)
        return self.elementDescript

    def set_environment(self, wpilots=True):
        """
        Set the environment to mimic what happens in the Frontend.
        If wpilots is True, also add the pilot DNs in the mapfile.

        Note: Assumes load_frontend_config() was already called.
        """
        self.wpilots = wpilots
        
        os.environ['CONDOR_CONFIG'] = self.elementDescript.frontend_data['CondorConfig']
        if self.wpilots:
            os.environ['_CONDOR_CERTIFICATE_MAPFILE'] = self.elementDescript.element_data['MapFileWPilots']
        else:
            os.environ['_CONDOR_CERTIFICATE_MAPFILE'] = self.elementDescript.element_data['MapFile']
        os.environ['X509_USER_PROXY'] = self.elementDescript.frontend_data['ClassAdProxy']
        os.environ["FE_WORK_DIR"]=self.options.work_dir
        os.environ["FE_GROUP_NAME"]=self.options.group_name


    # INTERNAL
    def validate_options(self):
        if self.options.work_dir is None:
            raise ValueError, "FE work dir not specified (neither -d nor FE_WORK_DIR used), aborting"
        if not os.path.isfile(os.path.join(self.options.work_dir, "frontend.descript")):
            raise ValueError, "%s is not a valid FE work dir"%self.options.work_dir

        if self.options.group_name is None:
            raise ValueError, "FE group name not specified (neither -g nor FE_GROUP_NAME used), aborting"
        if not os.path.isfile(os.path.join(self.options.work_dir, "group_%s/group.descript"%self.options.group_name)):
            raise ValueError, "%s is not a valid FE group name (no valid group_%s subdir found)"%(self.options.group_name, self.options.group_name)


    
