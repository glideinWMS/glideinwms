#######################################################
#
# Glidein creation module
# Classes and functions needed to handle dictionary files
# created out of the parameter object
#
#######################################################

import os,os.path,shutil,string
import cgWParams
import cgWDictFile
import cgWCreate
import cgWConsts

# internal, can only be used for multiple inheritance
class glideinCommonDicts:
    def create_dirs(self):
        cgWDictFile.glideinCommonDicts.create_dirs(self)
        try:
            os.mkdir(self.monitor_dir)
        except OSError,e:
            cgWDictFile.glideinCommonDicts.delete_dirs(self)
            raise RuntimeError,"Failed to create dir: %s"%e

        try:
            os.symlink(self.monitor_dir,os.path.join(self.submit_dir,"monitor"))
        except OSError, e:
            cgWDictFile.glideinCommonDicts.delete_dirs(self)
            shutil.rmtree(self.monitor_dir)
            raise RuntimeError,"Failed to create symlink %s: %s"%(os.path.join(self.submit_dir,"monitor"),e)

    def delete_dirs(self):
        cgWDictFile.glideinCommonDicts.delete_dirs(self)
        shutil.rmtree(self.monitor_dir)

class glideinMainDicts(glideinCommonDicts,cgWDictFile.glideinMainDicts):
    def __init__(self,params):
        cgWDictFile.glideinMainDicts.__init__(self,params.submit_dir,params.stage_dir)
        self.monitor_dir=params.monitor_dir
        self.params=params

    def populate(self,params=None):
        if params==None:
            params=self.params

        # put default files in place first
        self.dicts['file_list'].add_placeholder(cgWConsts.CONSTS_FILE,allow_overwrite=True)
        self.dicts['file_list'].add_placeholder(cgWConsts.VARS_FILE,allow_overwrite=True)
        self.dicts['file_list'].add_placeholder(cgWConsts.UNTAR_CFG_FILE,allow_overwrite=True) # this one must be loaded before any tarball
        self.dicts['file_list'].add_placeholder(cgWConsts.GRIDMAP_FILE,allow_overwrite=True) # this one must be loaded before setup_x509.sh
        
        # Load initial system scripts
        # These should be executed before the other scripts
        for script_name in ('cat_consts.sh','setup_x509.sh'):
            self.dicts['file_list'].add_from_file(script_name,(cgWConsts.insert_timestr(script_name),'exec','TRUE','FALSE'),os.path.join(params.src_dir,script_name))

        #load condor tarball
        if params.condor.tar_file!=None: # condor tarball available
            self.dicts['file_list'].add_from_file(cgWConsts.CONDOR_FILE,(cgWConsts.insert_timestr(cgWConsts.CONDOR_FILE),"untar","TRUE",cgWConsts.CONDOR_ATTR),params.condor.tar_file)
        else: # create a new tarball
            condor_fd=cgWCreate.create_condor_tar_fd(params.condor.base_dir)
            condor_fname=cgWConsts.insert_timestr(cgWConsts.CONDOR_FILE)
            self.dicts['file_list'].add_from_fd(cgWConsts.CONDOR_FILE,(condor_fname,"untar","TRUE",cgWConsts.CONDOR_ATTR),condor_fd)
            condor_fd.close()
            params.subparams.data['condor']['tar_file']=os.path.join(self.dicts['file_list'].dir,condor_fname)
        self.dicts['untar_cfg'].add(cgWConsts.CONDOR_FILE,cgWConsts.CONDOR_DIR)

        #load system files
        for file_name in ('parse_starterlog.awk',"condor_config"):
            self.dicts['file_list'].add_from_file(file_name,(cgWConsts.insert_timestr(file_name),"regular","TRUE",'FALSE'),os.path.join(params.src_dir,file_name))
        self.dicts['vars'].load(params.src_dir,'condor_vars.lst',change_self=False,set_not_changed=False)

        # put user files in stage
        for file in params.files:
            add_file_unparsed(file,self.dicts)

        # put user attributes into config files
        for attr_name in params.attrs.keys():
            add_attr_unparsed(attr_name, params.attrs[attr_name],self.dicts,"main")

        if self.dicts['file_list'].is_placeholder(cgWConsts.GRIDMAP_FILE): # gridmapfile is optional, so if not loaded, remove the placeholder
            self.dicts['file_list'].remove(cgWConsts.GRIDMAP_FILE)

        # add the basic standard params
        self.dicts['params'].add("GLIDEIN_Collector",'Fake')
        
        # this must be the last script in the list
        for script_name in (cgWConsts.CONDOR_STARTUP_FILE,):
            self.dicts['file_list'].add_from_file(script_name,(cgWConsts.insert_timestr(script_name),'exec','TRUE','FALSE'),os.path.join(params.src_dir,script_name))
        self.dicts['description'].add(cgWConsts.CONDOR_STARTUP_FILE,"last_script")

        # populate the glidein file
        glidein_dict=self.dicts['glidein']
        glidein_dict.add('FactoryName',params.factory_name)
        glidein_dict.add('GlideinName',params.glidein_name)
        glidein_dict.add('WebURL',params.web_url)
        active_entry_list=[]
        for entry in params.entries.keys():
            if eval(params.entries[entry].enabled,{},{}):
                active_entry_list.append(entry)
        glidein_dict.add('Entries',string.join(active_entry_list,','))

    # reuse as much of the other as possible
    def reuse(self,other):             # other must be of the same class
        if self.monitor_dir!=other.monitor_dir:
            raise RuntimeError,"Cannot change main monitor base_dir! '%s'!='%s'"%(self.monitor_dir,other.monitor_dir)
        
        return cgWDictFile.glideinMainDicts.reuse(self,other)

class glideinEntryDicts(glideinCommonDicts,cgWDictFile.glideinEntryDicts):
    def __init__(self,
                 glidein_main_dicts, # must be an instance of glideinMainDicts
                 entry_name):
        cgWDictFile.glideinEntryDicts.__init__(self,glidein_main_dicts,entry_name)
        self.monitor_dir=cgWConsts.get_entry_monitor_dir(glidein_main_dicts.monitor_dir,entry_name)
        self.params=glidein_main_dicts.params

    def erase(self):
        cgWDictFile.glideinEntryDicts.erase(self)
        self.dicts['condor_jdl']=cgWCreate.GlideinSubmitDictFile(self.submit_dir,cgWConsts.SUBMIT_FILE)
        
    def load(self): #will use glidein_main_dicts data, so it must be loaded first
        cgWDictFile.glideinEntryDicts.load(self)
        self.dicts['condor_jdl'].load()

    def save_final(self,set_readonly=True):
        summary_signature=self.glidein_main_dicts['summary_signature']
        entry_stage_dir=cgWConsts.get_entry_stage_dir("",self.entry_name)
        
        self.dicts['condor_jdl'].finalize(summary_signature['main'][0],summary_signature[entry_stage_dir][0],
                                          summary_signature['main'][1],summary_signature[entry_stage_dir][1])
        self.dicts['condor_jdl'].save(set_readonly=set_readonly)
        
    
    def populate(self,schedd_name,params=None):
        if params==None:
            params=self.params

        entry_params=params.entries[self.entry_name]

        # put default files in place first
        self.dicts['file_list'].add_placeholder(cgWConsts.CONSTS_FILE,allow_overwrite=True)
        self.dicts['file_list'].add_placeholder(cgWConsts.VARS_FILE,allow_overwrite=True)
        self.dicts['file_list'].add_placeholder(cgWConsts.UNTAR_CFG_FILE,allow_overwrite=True) # this one must be loaded before any tarball

        # follow by the blacklist file
        file_name="nodes.blacklist"
        self.dicts['file_list'].add_from_file(file_name,(file_name,"nocache","TRUE",'BLACKLIST_FILE'),os.path.join(params.src_dir,file_name))

        # Load initial system scripts
        # These should be executed before the other scripts
        for script_name in ('cat_consts.sh',"validate_node.sh"):
            self.dicts['file_list'].add_from_file(script_name,(cgWConsts.insert_timestr(script_name),'exec','TRUE','FALSE'),os.path.join(params.src_dir,script_name))

        #load system files
        self.dicts['vars'].load(params.src_dir,'condor_vars.lst.entry',change_self=False,set_not_changed=False)
        
        # put user files in stage
        for file in entry_params.files:
            add_file_unparsed(file,self.dicts)

        # put user attributes into config files
        for attr_name in entry_params.attrs.keys():
            add_attr_unparsed(attr_name, entry_params.attrs[attr_name],self.dicts,self.entry_name)

        # put standard attributes into config file
        # override anything the user set
        for dtype in ('attrs','consts'):
            self.dicts[dtype].add("GLIDEIN_Gatekeeper",entry_params.gatekeeper,allow_overwrite=True)
            self.dicts[dtype].add("GLIDEIN_GridType",entry_params.gridtype,allow_overwrite=True)
            if entry_params.rsl!=None:
                self.dicts[dtype].add('GLIDEIN_GlobusRSL',entry_params.rsl,allow_overwrite=True)

        # populate complex files
        populate_job_descript(self.dicts['job_descript'],
                              self.entry_name,entry_params)

        self.dicts['condor_jdl'].populate(cgWConsts.STARTUP_FILE,
                                          params.factory_name,params.glidein_name,self.entry_name,
                                          entry_params.gridtype,entry_params.gatekeeper,entry_params.rsl,
                                          params.web_url,entry_params.proxy_url,entry_params.work_dir)

    # reuse as much of the other as possible
    def reuse(self,other):             # other must be of the same class
        if self.monitor_dir!=other.monitor_dir:
            raise RuntimeError,"Cannot change entry monitor base_dir! '%s'!='%s'"%(self.monitor_dir,other.monitor_dir)
        
        return cgWDictFile.glideinEntryDicts.reuse(self,other)

        
################################################
#
# This Class contains coth the main and
# the entry dicts
#
################################################

class glideinDicts(cgWDictFile.glideinDicts):
    def __init__(self,params,
                 entry_list=None): # if None, get it from params
        if entry_list==None:
            entry_list=params.entries.keys()

        self.params=params
        self.submit_dir=params.submit_dir
        self.stage_dir=params.stage_dir
        self.monitor_dir=params.monitor_dir

        self.main_dicts=glideinMainDicts(params)
        self.entry_list=entry_list[:]
        self.entry_dicts={}
        for entry_name in entry_list:
            self.entry_dicts[entry_name]=glideinEntryDicts(self.main_dicts,entry_name)
        return

    def populate(self,params=None): # will update params (or self.params)
        if params==None:
            params=self.params
        
        self.main_dicts.populate(params)

        # make sure all the schedds are defined
        # if not, define them, in place, so thet it get recorded
        global_schedd_names=string.split(params.schedd_name,',')
        global_schedd_idx=0
        for entry_name in self.entry_list:
            if params.entries[entry_name].schedd_name==None:
                # use one of the global ones if specific not provided
                schedd_name=global_schedd_names[global_schedd_idx%len(global_schedd_names)]
                global_schedd_idx=global_schedd_idx+1
                params.subparams.data['entries'][entry_name]['schedd_name']=schedd_name

        for entry_name in self.entry_list:
            self.entry_dicts[entry_name].populate(params)

    # reuse as much of the other as possible
    def reuse(self,other):             # other must be of the same class
        if self.monitor_dir!=other.monitor_dir:
            raise RuntimeError,"Cannot change monitor base_dir! '%s'!='%s'"%(self.monitor_dir,other.monitor_dir)
        
        return cgWDictFile.glideinDicts.reuse(self,other)

    ###########
    # PRIVATE
    ###########

    # return a new entry object
    def new_entry(self,entry_name):
        return glideinEntryDicts(self.main_dicts,entry_name)
    
############################################################
#
# P R I V A T E - Do not use
# 
############################################################

#############################################
# Add a user file residing in the stage area
# file as described by Params.file_defaults
def add_file_unparsed(file,dicts):
    absfname=file.absfname
    if absfname==None:
        raise RuntimeError, "Found a file element without an absname: %s"%file
    
    relfname=file.relfname
    if relfname==None:
        relfname=os.path.basename(absfname) # defualt is the final part of absfname
    if len(relfname)<1:
        raise RuntimeError, "Found a file element with an empty relfname: %s"%file

    is_const=eval(file.const,{},{})
    is_executable=eval(file.executable,{},{})
    do_untar=eval(file.untar,{},{})

    if is_executable: # a script
        if not is_const:
            raise RuntimeError, "A file cannot be executable if it is not constant: %s"%file
    
        if do_untar:
            raise RuntimeError, "A tar file cannot be executable: %s"%file

        dicts['file_list'].add_from_file(relfname,(cgWConsts.insert_timestr(relfname),"exec","TRUE",'FALSE'),absfname)
    elif do_untar: # a tarball
        if not is_const:
            raise RuntimeError, "A file cannot be untarred if it is not constant: %s"%file

        wnsubdir=file.untar_options.dir
        if wnsubdir==None:
            wnsubdir=string.split(relfname,'.',1)[0] # deafult is relfname up to the first .

        config_out=file.untar_options.absdir_outattr
        if config_out==None:
            config_out="FALSE"
        cond_attr=file.untar_options.cond_attr


        dicts['file_list'].add_from_file(relfname,(cgWConsts.insert_timestr(relfname),"untar",cond_attr,config_out),absfname)
        dicts['untar_cfg'].add(relfname,wnsubdir)
    else: # not executable nor tarball => simple file
        if is_const:
            val='regular'
            dicts['file_list'].add_from_file(relfname,(cgWConsts.insert_timestr(relfname),val,'TRUE','FALSE'),absfname)
        else:
            val='nocache'
            dicts['file_list'].add_from_file(relfname,(relfname,val,'TRUE','FALSE'),absfname) # no timestamp if it can be modified

#######################
# Register an attribute
# attr_obj as described by Params.attr_defaults
def add_attr_unparsed(attr_name,attr_obj,dicts,description):
    try:
        add_attr_unparsed_real(attr_name,attr_obj,dicts)
    except RuntimeError,e:
        raise RuntimeError, "Error parsing attr %s[%s]: %s"%(description,attr_name,str(e))

def add_attr_unparsed_real(attr_name,attr_obj,dicts):
    if attr_obj.value==None:
        raise RuntimeError, "Attribute '%s' does not have a value: %s"%(attr_name,attr_obj)
    
    do_publish=eval(attr_obj.publish,{},{})
    is_parameter=eval(attr_obj.parameter,{},{})
    is_const=eval(attr_obj.const,{},{})
    attr_val=cgWParams.extract_attr_val(attr_obj)
    
    if do_publish: # publish in factory ClassAd
        if is_parameter: # but also push to glidein
            if is_const:
                dicts['attrs'].add(attr_name,attr_val)
                dicts['consts'].add(attr_name,attr_val)
            else:
                dicts['params'].add(attr_name,attr_val)
        else: # only publish
            if (not is_const):
                raise RuntimeError, "Published attribute '%s' must be either a parameter or constant: %s"%(attr_name,attr_obj)
            
            dicts['attrs'].add(attr_name,attr_val)
    else: # do not publish, only to glidein
        if is_parameter:
            if is_const:
                dicts['consts'].add(attr_name,attr_val)
            else:
                raise RuntimeError, "Parameter attributes '%s' must be either a published or constant: %s"%(attr_name,attr_obj)
        else:
            raise RuntimeError, "Attributes '%s' must be either a published or parameters: %s"%(attr_name,attr_obj) 

    if is_parameter:
        do_glidein_publish=eval(attr_obj.glidein_publish,{},{})
        do_job_publish=eval(attr_obj.job_publish,{},{})

        if do_glidein_publish or do_job_publish:
            # need to add a line only if will be published
            if dicts['vars'].has_key(attr_name):
                # already in the var file, check if compatible
                attr_var_el=dicts['vars'][attr_name]
                attr_var_type=attr_var_el[0]
                if (((attr_obj.type=="int") and (attr_var_type!='I')) or
                    ((attr_obj.type=="string") and (attr_var_type=='I'))):
                    raise RuntimeError, "Types not compatible (%s,%s)"%(attr_obj.type,attr_var_type)
                attr_var_export=attr_var_el[4]
                if do_glidein_publish and (attr_var_export=='N'):
                    raise RuntimeError, "Cannot force glidein publishing"
                attr_var_job_publish=attr_var_el[5]
                if do_job_publish and (attr_var_job_publish=='-'):
                    raise RuntimeError, "Cannot force job publishing"
            else:
                dicts['vars'].add_extended(attr_name,attr_obj.type=="string",None,None,False,do_glidein_publish,do_job_publish)

#######################
# Populate job_descript
def populate_job_descript(job_descript_dict,        # will be modified
                          entry_name,entry_params):
    job_descript_dict.add('EntryName',entry_name)
    job_descript_dict.add('GridType',entry_params.gridtype)
    job_descript_dict.add('Gatekeeper',entry_params.gatekeeper)
    if entry_params.rsl!=None:
        job_descript_dict.add('GlobusRSL',entry_params.rsl)
    job_descript_dict.add('Schedd',entry_params.schedd_name)
    job_descript_dict.add('StartupDir',entry_params.work_dir)
    if entry_params.proxy_url!=None:
        job_descript_dict.add('ProxyURL',entry_params.proxy_url)

    
#######################
# Simply symlink a file
def symlink_file(infile,outfile):
    try:
        os.symlink(infile,outfile)
    except IOError, e:
        raise RuntimeError, "Error symlink %s in %s: %s"%(infile,outfile,e)

###########################################################
#
# CVS info
#
# $Id: cgWParamDict.py,v 1.38 2008/04/23 14:24:16 sfiligoi Exp $
#
# Log:
#  $Log: cgWParamDict.py,v $
#  Revision 1.38  2008/04/23 14:24:16  sfiligoi
#  Also publish CE info
#
#  Revision 1.37  2008/04/23 14:18:26  sfiligoi
#  Add CE info to the glidein
#
#  Revision 1.36  2008/01/25 21:45:35  sfiligoi
#  Move the grid-mapfile before setup_x509.sh; this added the remove method to DictFile and is_placeholder to FileDictFile
#
#  Revision 1.35  2008/01/25 20:07:02  sfiligoi
#  Remove condor_mapfile, as it will be dynamically generated
#
#  Revision 1.34  2008/01/17 18:57:06  sfiligoi
#  Add CERTIFICATE_MAPFILE = condor_mapfile
#
#  Revision 1.33  2007/12/28 20:48:20  sfiligoi
#  Add enabled to entry and use it to tell the factory which entries to use.
#
#  Revision 1.32  2007/12/26 20:04:41  sfiligoi
#  Fix file order
#
#  Revision 1.31  2007/12/26 16:22:47  sfiligoi
#  After creating the condor tarball, update the params
#
#  Revision 1.28  2007/12/20 16:41:48  sfiligoi
#  Add reuse
#
#  Revision 1.27  2007/12/18 16:30:50  sfiligoi
#  Correct blacklist load order
#
#  Revision 1.24  2007/12/17 21:00:35  sfiligoi
#  Add timestamps to the user filenames
#
#  Revision 1.23  2007/12/17 20:50:28  sfiligoi
#  Move subsystems into the file_list and add untar_cfg
#
#  Revision 1.22  2007/12/17 20:19:38  sfiligoi
#  Move validate_node into the entry subdir
#
#  Revision 1.20  2007/12/14 22:28:08  sfiligoi
#  Change file_list format and remove script_list (merged into file_list now)
#
#  Revision 1.16  2007/12/14 16:28:53  sfiligoi
#  Move directory creation into the Dict classes
#
#  Revision 1.15  2007/12/14 14:36:11  sfiligoi
#  Make saving optional if the dictionary has not been changed
#
#  Revision 1.11  2007/12/13 22:35:10  sfiligoi
#  Move entry specific arguments into the creation stage
#
#  Revision 1.8  2007/12/13 20:19:46  sfiligoi
#  Move condor jdl into entry subdir, and implement it via a dictionary
#
#  Revision 1.4  2007/12/12 00:35:36  sfiligoi
#  Move creation of glidein and job_descript files from cgWCreate to cgWParamDict
#
#  Revision 1.3  2007/12/11 23:52:40  sfiligoi
#  Create monitor_dir in a single place
#
#  Revision 1.1  2007/12/11 23:09:54  sfiligoi
#  Move the population of dictionaries into cgWParamDict
#
#
###########################################################
