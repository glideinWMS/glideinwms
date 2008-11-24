#######################################################
#
# Frontend creation module
# Classes and functions needed to handle dictionary files
# created out of the parameter object
#
#######################################################

import os,os.path,shutil,string
import cWParams
import cvWDictFile,cWDictFile
import cvWConsts,cWConsts

################################################
#
# This Class contains the main dicts
#
################################################

class frontendMainDicts(cvWDictFile.frontendMainDicts):
    def __init__(self,params,workdir_name):
        cvWDictFile.frontendMainDicts.__init__(self,params.work_dir,params.stage_dir,workdir_name)
        self.monitor_dir=params.monitor_dir
        self.add_dir_obj(cWDictFile.monitorWLinkDirSupport(self.monitor_dir,self.work_dir))
        self.params=params
        self.active_sub_list=[]

    def populate(self,params=None):
        if params==None:
            params=self.params

        # put default files in place first
        self.dicts['preentry_file_list'].add_placeholder(cWConsts.CONSTS_FILE,allow_overwrite=True)
        self.dicts['preentry_file_list'].add_placeholder(cWConsts.VARS_FILE,allow_overwrite=True)
        self.dicts['preentry_file_list'].add_placeholder(cWConsts.UNTAR_CFG_FILE,allow_overwrite=True) # this one must be loaded before any tarball
        self.dicts['preentry_file_list'].add_placeholder(cWConsts.GRIDMAP_FILE,allow_overwrite=True) # this one must be loaded before factory runs setup_x509.sh
        
        # follow by the blacklist file
        file_name=cWConsts.BLACKLIST_FILE
        self.dicts['preentry_file_list'].add_from_file(file_name,(file_name,"nocache","TRUE",'BLACKLIST_FILE'),os.path.join(params.src_dir,file_name))

        # Load initial system scripts
        # These should be executed before the other scripts
        for script_name in ('cat_consts.sh',"validate_node.sh"):
            self.dicts['preentry_file_list'].add_from_file(script_name,(cWConsts.insert_timestr(script_name),'exec','TRUE','FALSE'),os.path.join(params.src_dir,script_name))

        # put user files in stage
        for file in params.files:
            add_file_unparsed(file,self.dicts)

        # put user attributes into config files
        for attr_name in params.attrs.keys():
            add_attr_unparsed(attr_name, params.attrs[attr_name],self.dicts,"main")

        if self.dicts['preentry_file_list'].is_placeholder(cWConsts.GRIDMAP_FILE): # gridmapfile is optional, so if not loaded, remove the placeholder
            self.dicts['preentry_file_list'].remove(cWConsts.GRIDMAP_FILE)

        # populate complex files
        populate_frontend_descript(self.work_dir,self.dicts['frontend_descript'],self.active_sub_list,params)

    # reuse as much of the other as possible
    def reuse(self,other):             # other must be of the same class
        if self.monitor_dir!=other.monitor_dir:
            raise RuntimeError,"Cannot change main monitor base_dir! '%s'!='%s'"%(self.monitor_dir,other.monitor_dir)
        
        return cvWDictFile.frontendMainDicts.reuse(self,other)

################################################
#
# This Class contains the group dicts
#
################################################

class frontendGroupDicts(cvWDictFile.frontendGroupDicts):
    def __init__(self,params,sub_name,
                 summary_signature,workdir_name):
        cvWDictFile.frontendGroupDicts.__init__(self,params.work_dir,params.stage_dir,sub_name,summary_signature,workdir_name)
        self.monitor_dir=cvWConsts.get_group_monitor_dir(params.monitor_dir,sub_name)
        self.add_dir_obj(cWDictFile.monitorWLinkDirSupport(self.monitor_dir,self.work_dir))
        self.params=params

    def populate(self,params=None):
        if params==None:
            params=self.params

        sub_params=params.groups[self.sub_name]

        # put default files in place first
        self.dicts['preentry_file_list'].add_placeholder(cWConsts.CONSTS_FILE,allow_overwrite=True)
        self.dicts['preentry_file_list'].add_placeholder(cWConsts.VARS_FILE,allow_overwrite=True)
        self.dicts['preentry_file_list'].add_placeholder(cWConsts.UNTAR_CFG_FILE,allow_overwrite=True) # this one must be loaded before any tarball

        # follow by the blacklist file
        file_name=cWConsts.BLACKLIST_FILE
        self.dicts['preentry_file_list'].add_from_file(file_name,(file_name,"nocache","TRUE",'BLACKLIST_FILE'),os.path.join(params.src_dir,file_name))

        # Load initial system scripts
        # These should be executed before the other scripts
        for script_name in ('cat_consts.sh',"validate_node.sh"):
            self.dicts['preentry_file_list'].add_from_file(script_name,(cWConsts.insert_timestr(script_name),'exec','TRUE','FALSE'),os.path.join(params.src_dir,script_name))

        # put user files in stage
        for file in sub_params.files:
            add_file_unparsed(file,self.dicts)

        # put user attributes into config files
        for attr_name in sub_params.attrs.keys():
            add_attr_unparsed(attr_name, sub_params.attrs[attr_name],self.dicts,self.sub_name)

        # populate complex files
        populate_group_descript(self.work_dir,self.dicts['group_descript'],
                                self.sub_name,sub_params)

    # reuse as much of the other as possible
    def reuse(self,other):             # other must be of the same class
        if self.monitor_dir!=other.monitor_dir:
            raise RuntimeError,"Cannot change group monitor base_dir! '%s'!='%s'"%(self.monitor_dir,other.monitor_dir)
        
        return cvWDictFile.frontendGroupDicts.reuse(self,other)

        
################################################
#
# This Class contains both the main and
# the group dicts
#
################################################

class frontendDicts(cvWDictFile.frontendDicts):
    def __init__(self,params,
                 sub_list=None): # if None, get it from params
        if sub_list==None:
            sub_list=params.groups.keys()

        self.params=params
        cvWDictFile.frontendDicts(self,params.work_dir,params.stage_dir,sub_list)

        self.monitor_dir=params.monitor_dir
        self.active_sub_list=[]
        return

    def populate(self,params=None): # will update params (or self.params)
        if params==None:
            params=self.params
        
        self.main_dicts.populate(params)
        self.active_sub_list=self.main_dicts.active_sub_list

        self.local_populate(params)
        for sub_name in self.sub_list:
            self.sub_dicts[sub_name].populate(params)

    # reuse as much of the other as possible
    def reuse(self,other):             # other must be of the same class
        if self.monitor_dir!=other.monitor_dir:
            raise RuntimeError,"Cannot change monitor base_dir! '%s'!='%s'"%(self.monitor_dir,other.monitor_dir)
        
        return cvWDictFile.frontendDicts.reuse(self,other)

    ###########
    # PRIVATE
    ###########

    def local_populate(self,params):
        return # nothing to do
        

    ######################################
    # Redefine methods needed by parent
    def new_MainDicts(self):
        return frontendMainDicts(self.params,self.workdir_name)

    def new_SubDicts(self,sub_name):
        return frontendGroupDicts(self.params,sub_name,
                                 self.main_dicts.get_summary_signature(),self.workdir_name)

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
    is_wrapper=eval(file.wrapper,{},{})
    do_untar=eval(file.untar,{},{})

    if eval(file.after_entry,{},{}):
        file_list_idx='file_list'
    else:
        file_list_idx='preentry_file_list'

    if file.has_key('after_group'):
        if eval(file.after_group,{},{}):
            file_list_idx='aftergroup_%s'%file_list_idx

    if is_executable: # a script
        if not is_const:
            raise RuntimeError, "A file cannot be executable if it is not constant: %s"%file
    
        if do_untar:
            raise RuntimeError, "A tar file cannot be executable: %s"%file

        if is_wrapper:
            raise RuntimeError, "A wrapper file cannot be executable: %s"%file

        dicts[file_list_idx].add_from_file(relfname,(cWConsts.insert_timestr(relfname),"exec","TRUE",'FALSE'),absfname)
    elif is_wrapper: # a sourceable script for the wrapper
        if not is_const:
            raise RuntimeError, "A file cannot be a wrapper if it is not constant: %s"%file
    
        if do_untar:
            raise RuntimeError, "A tar file cannot be a wrapper: %s"%file

        dicts[file_list_idx].add_from_file(relfname,(cWConsts.insert_timestr(relfname),"wrapper","TRUE",'FALSE'),absfname)
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


        dicts[file_list_idx].add_from_file(relfname,(cWConsts.insert_timestr(relfname),"untar",cond_attr,config_out),absfname)
        dicts['untar_cfg'].add(relfname,wnsubdir)
    else: # not executable nor tarball => simple file
        if is_const:
            val='regular'
            dicts[file_list_idx].add_from_file(relfname,(cWConsts.insert_timestr(relfname),val,'TRUE','FALSE'),absfname)
        else:
            val='nocache'
            dicts[file_list_idx].add_from_file(relfname,(relfname,val,'TRUE','FALSE'),absfname) # no timestamp if it can be modified

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
    
    is_parameter=eval(attr_obj.parameter,{},{})
    is_expr=eval(attr_obj.expression,{},{})
    attr_val=cWParams.extract_attr_val(attr_obj)
    
    if is_parameter:
        if is_expr:
            dicts['exprs'].add(attr_name,attr_val)
        else:
            dicts['params'].add(attr_name,attr_val)
    else:
        if is_expr:
            RuntimeError, "Expression '%s' is not a parameter!"%attr_name
        else:
            dicts['consts'].add(attr_name,attr_val)

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

###################################
# Create the frontend descript file
def populate_frontend_descript(work_dir,
                               frontend_dict,active_sub_list,        # will be modified
                               params):
        # if a user does not provide a file name, use the default one
        down_fname=params.downtimes.absfname
        if down_fname==None:
            down_fname=os.path.join(work_dir,'frontend.downtimes')

        frontend_dict.add('FrontendName',params.frontend_name)
        frontend_dict.add('WebURL',params.web_url)
        frontend_dict.add('SymKeyType',params.security.sym_key)
        if params.security.x509_proxy!=None:
            frontend_dict.add('X509Proxy',params.security.x509_proxy)

        active_sub_list[:] # erase all
        for sub in params.groups.keys():
            if eval(params.groups[sub].enabled,{},{}):
                active_sub_list.append(sub)
        frontend_dict.add('Groups',string.join(active_sub_list,','))

        for tel in (("factory_query_expr",'FactoryQueryExpr'),("job_query_expr",'JobQueryExpr'),("match_expr",'MatchExpr')):
            param_tname,str_tname=tel
            frontend_dict.add(str_tname,params.match[param_tname])
        frontend_dict.add('JobMatchAttrs',repr(params.match.job_match_attrs))

        frontend_dict.add('LoopDelay',params.loop_delay)
        frontend_dict.add('AdvertiseDelay',params.advertise_delay)

        frontend_dict.add('DowntimesFile',down_fname)
        for tel in (("max_days",'MaxDays'),("min_days",'MinDays'),("max_mbytes",'MaxMBs')):
            param_tname,str_tname=tel
            frontend_dict.add('LogRetention%s'%str_tname,params.log_retention[param_tname])

        for el in (('Frontend',params.monitor.frontend),('Group',params.monitor.group)):
            prefix=el[0]
            dict=el[1]
            val="Basic"
            if bool(eval(dict.want_split_graphs)):
                val+=",Split"
            if bool(eval(dict.want_trend_graphs)):
                val+=",Trend"
            if bool(eval(dict.want_infoage_graphs)):
                val+=",InfoAge"
            frontend_dict.add('%sWantedMonitorGraphs'%prefix,val)

#######################
# Populate group descript
def populate_group_descript(work_dir,group_descript_dict,        # will be modified
                            sub_name,sub_params):
    # if a user does not provide a file name, use the default one
    down_fname=sub_params.downtimes.absfname
    if down_fname==None:
        down_fname=os.path.join(work_dir,'group.downtimes')

    group_descript_dict.add('GroupName',sub_name)

    for tel in (("factory_query_expr",'FactoryQueryExpr'),("job_query_expr",'JobQueryExpr'),("match_expr",'MatchExpr')):
        param_tname,str_tname=tel
        group_descript_dict.add(str_tname,params.match[param_tname])
    group_descript_dict.add['JobMatchAttrs']=repr(params.match.job_match_attrs)

    group_descript_dict.add('DowntimesFile',down_fname)
    group_descript_dict.add('MaxRunning',sub_params.config.max_running_jobs)
    group_descript_dict.add('MaxIdlePerEntry',sub_params.config.idle_glideins_per_entry.max)
    group_descript_dict.add('ReserveIdlePerEntry',sub_params.config.idle_glideins_per_entry.reserve)
    group_descript_dict.add('MaxIdleVMsPerEntry',sub_params.config.idle_vms_per_entry.max)
    group_descript_dict.add('CurbIdleVMsPerEntry',sub_params.config.idle_vms_per_entry.curb)



    
