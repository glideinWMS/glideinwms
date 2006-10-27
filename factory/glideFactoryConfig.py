import string

############################################################
#
# Configuration
#
############################################################

class FactoryConfig:
    def __init__(self):
        # set default values
        # user should modify if needed

        self.job_descript_file = "job.descript"
        self.job_attrs_file = "attributes.cfg"
        self.job_params_file = "params.cfg"

# global configuration of the module
factoryConfig=FactoryConfig()


############################################################
#
# Generic Class
# You most probably don't want to use these
#
############################################################

# loads a file composed of
#   NAME VAL
# and creates
#   self.data[NAME]=VAL
# It also defines:
#   self.config_file="name of file"
class ConfigFile:
    def __init__(self,config_file,convert_function=repr):
        self.config_file=config_file
        self.load(config_file,convert_function)

    def load(self,fname,convert_function):
        self.data={}
        fd=open(fname,"r")
        try:
            lines=fd.readlines()
            for line in lines:
                if line[0]=="#":
                    continue # comment
                if len(string.strip(line))==0:
                    continue # empty line
                larr=string.split(line,None,1)
                lname=larr[0]
                if len(larr)==1:
                    lval=""
                else:
                    lval=larr[1][:-1] #strip newline
                exec("self.data['%s']=%s"%(lname,convert_function(lval)))
        finally:
            fd.close()

############################################################
#
# Configuration
#
############################################################

class JobDescript(ConfigFile):
    def __init__(self):
        global factoryConfig
        ConfigFile.__init__(self,factoryConfig.job_descript_file,
                            repr) # convert everything in strings

class JobAttributes(ConfigFile):
    def __init__(self):
        global factoryConfig
        ConfigFile.__init__(self,factoryConfig.job_attrs_file,
                            lambda s:s) # values are in python format


class JobParams(ConfigFile):
    def __init__(self):
        global factoryConfig
        ConfigFile.__init__(self,factoryConfig.job_params_file,
                            lambda s:s) # values are in python format


