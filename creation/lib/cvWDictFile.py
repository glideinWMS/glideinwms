#
# Project:
#   glideinWMS
#
# File Version: 
#
# Description:
#   VO Frontend creation module
#   Classes and functions needed to handle dictionary files
#

import os,os.path,shutil,string,copy
import cvWConsts,cWConsts
import cWDictFile


class ParamsDictFile(cWDictFile.DictFile):
    def file_header(self,want_comments):
        if want_comments:
            return (cWDictFile.DictFile.file_header(self,want_comments)+"\n"+
                    "# Param \tType \tValue                           \n"+
                    "#################################################")
        else:
            return None

    def get_val_type(self,key):
        return self.vals[key][0]

    def get_true_val(self,key):
        return self.vals[key][1]

    def add(self,key,val,allow_overwrite=0):
        if not (type(val) in (type(()),type([]))):
            raise RuntimeError, "Values '%s' not a list or tuple"%val
        if len(val)!=2:
            raise RuntimeError, "Values '%s' not (Type,Val)"%str(val)
        if not (val[0] in ('EXPR','CONST')):
            raise RuntimeError,"Invalid var type '%s', should be either EXPR or CONST val: %s"%(val[0],str(val))

        return cWDictFile.DictFile.add(self,key,val,allow_overwrite)

    def add_extended(self,key,
                     is_expression,
                     val,
                     allow_overwrite=0):
        if is_expression:
            type_str='EXPR'
        else:
            type_str='CONST'
            
        self.add(key,(type_str,val),allow_overwrite)
        
    def format_val(self,key,want_comments):
        return "%s \t%s \t%s"%(key,self.vals[key][0],repr(self.vals[key][1]))
        

    def parse_val(self,line):
        if len(line)==0:
            return #ignore empty lines
        if line[0]=='#':
            return # ignore comments
        arr=line.split(None,2)
        if len(arr)==0:
            return # empty line
        if len(arr)!=3:
            raise RuntimeError,"Not a valid var line (expected 3, found %i elements): '%s'"%(len(arr),line)

        key=arr[0]
        return self.add(key,(arr[1],eval(arr[2])))


################################################
#
# Functions that create default dictionaries
#
################################################

# internal, do not use from outside the module
def get_common_dicts(work_dir,stage_dir,
                     simple_work_dir): # if True, do not create params
    common_dicts={'description':cWDictFile.DescriptionDictFile(stage_dir,cWConsts.insert_timestr(cWConsts.DESCRIPTION_FILE),fname_idx=cWConsts.DESCRIPTION_FILE),
                  'consts':cWDictFile.StrWWorkTypeDictFile(stage_dir,cWConsts.insert_timestr(cWConsts.CONSTS_FILE),fname_idx=cWConsts.CONSTS_FILE),
                  'vars':cWDictFile.VarsDictFile(stage_dir,cWConsts.insert_timestr(cWConsts.VARS_FILE),fname_idx=cWConsts.VARS_FILE),
                  'untar_cfg':cWDictFile.StrDictFile(stage_dir,cWConsts.insert_timestr(cWConsts.UNTAR_CFG_FILE),fname_idx=cWConsts.UNTAR_CFG_FILE),
                  'file_list':cWDictFile.FileDictFile(stage_dir,cWConsts.insert_timestr(cWConsts.FILE_LISTFILE),fname_idx=cWConsts.FILE_LISTFILE),
                  'preentry_file_list':cWDictFile.FileDictFile(stage_dir,cWConsts.insert_timestr(cvWConsts.PREENTRY_FILE_LISTFILE),fname_idx=cvWConsts.PREENTRY_FILE_LISTFILE),
                  "signature":cWDictFile.SHA1DictFile(stage_dir,cWConsts.insert_timestr(cWConsts.SIGNATURE_FILE),fname_idx=cWConsts.SIGNATURE_FILE)}
    if not simple_work_dir:
        common_dicts['params']=ParamsDictFile(work_dir,cvWConsts.PARAMS_FILE)
        common_dicts['attrs']=cWDictFile.ReprDictFile(work_dir,cvWConsts.ATTRS_FILE)

    refresh_description(common_dicts)
    return common_dicts

def get_main_dicts(work_dir,stage_dir,simple_work_dir,assume_groups):
    main_dicts=get_common_dicts(work_dir,stage_dir,simple_work_dir)
    main_dicts['summary_signature']=cWDictFile.SummarySHA1DictFile(work_dir,cWConsts.SUMMARY_SIGNATURE_FILE)
    main_dicts['frontend_descript']=cWDictFile.StrDictFile(work_dir,cvWConsts.FRONTEND_DESCRIPT_FILE)
    main_dicts['gridmap']=cWDictFile.GridMapDict(stage_dir,cWConsts.insert_timestr(cWConsts.GRIDMAP_FILE))
    if assume_groups:
        main_dicts['aftergroup_file_list']=cWDictFile.FileDictFile(stage_dir,cWConsts.insert_timestr(cvWConsts.AFTERGROUP_FILE_LISTFILE),fname_idx=cvWConsts.AFTERGROUP_FILE_LISTFILE)
        main_dicts['aftergroup_preentry_file_list']=cWDictFile.FileDictFile(stage_dir,cWConsts.insert_timestr(cvWConsts.AFTERGROUP_PREENTRY_FILE_LISTFILE),fname_idx=cvWConsts.AFTERGROUP_PREENTRY_FILE_LISTFILE)
        
    return main_dicts

def get_group_dicts(group_work_dir,group_stage_dir,group_name,simple_work_dir):
    group_dicts=get_common_dicts(group_work_dir,group_stage_dir,simple_work_dir)
    group_dicts['group_descript']=cWDictFile.StrDictFile(group_work_dir,cvWConsts.GROUP_DESCRIPT_FILE)
    return group_dicts

################################################
#
# Functions that load dictionaries
#
################################################

# internal, do not use from outside the module
def load_common_dicts(dicts,           # update in place
                      description_el):
    # first work dir ones (mutable)
    if dicts.has_key('params'):
        dicts['params'].load()
    if dicts.has_key('attrs'):
        try:
            dicts['attrs'].load()
        except RuntimeError,e:
            # to allow for a smooth upgrade path from 2.5.5-, make this file optional
            # in the future, we should remove this try...except block
            dicts['attrs'].erase()
    # now the ones keyed in the description
    dicts['signature'].load(fname=description_el.vals2['signature'])
    dicts['file_list'].load(fname=description_el.vals2['file_list'])
    dicts['preentry_file_list'].load(fname=description_el.vals2['preentry_file_list'])
    file_el=dicts['preentry_file_list']
    # all others are keyed in the file_list
    dicts['consts'].load(fname=file_el[cWConsts.CONSTS_FILE][0])
    dicts['vars'].load(fname=file_el[cWConsts.VARS_FILE][0])
    dicts['untar_cfg'].load(fname=file_el[cWConsts.UNTAR_CFG_FILE][0])
    if dicts.has_key('gridmap'):
        dicts['gridmap'].load(fname=file_el[cWConsts.GRIDMAP_FILE][0])

def load_main_dicts(main_dicts): # update in place
    main_dicts['frontend_descript'].load()
    # summary_signature has keys for description
    main_dicts['summary_signature'].load()
    # load the description
    main_dicts['description'].load(fname=main_dicts['summary_signature']['main'][1])
    # all others are keyed in the description
    if main_dicts.has_key('aftergroup_file_list'):
        main_dicts['aftergroup_file_list'].load(fname=main_dicts['description'].vals2['aftergroup_file_list'])
        # no need for another test, always paired
        main_dicts['aftergroup_preentry_file_list'].load(fname=main_dicts['description'].vals2['aftergroup_preentry_file_list'])
    load_common_dicts(main_dicts,main_dicts['description'])

def load_group_dicts(group_dicts,                   # update in place
                     group_name,summary_signature): 
    group_dicts['group_descript'].load()
    # load the description (name from summary_signature)
    group_dicts['description'].load(fname=summary_signature[cvWConsts.get_group_stage_dir("",group_name)][1])
    # all others are keyed in the description
    load_common_dicts(group_dicts,group_dicts['description'])

############################################################
#
# Functions that create data out of the existing dictionary
#
############################################################

def refresh_description(dicts): # update in place
    description_dict=dicts['description']
    description_dict.add(dicts['signature'].get_fname(),"signature",allow_overwrite=True)
    for k in ('preentry_file_list','file_list','aftergroup_preentry_file_list','aftergroup_file_list'):
        if dicts.has_key(k):
            description_dict.add(dicts[k].get_fname(),k,allow_overwrite=True)

def refresh_file_list(dicts,is_main, # update in place
                      files_set_readonly=True,files_reset_changed=True):
    file_dict=dicts['preentry_file_list']
    file_dict.add(cWConsts.CONSTS_FILE,(dicts['consts'].get_fname(),"regular","TRUE","CONSTS_FILE",dicts['consts'].save_into_str(set_readonly=files_set_readonly,reset_changed=files_reset_changed)),allow_overwrite=True)
    file_dict.add(cWConsts.VARS_FILE,(dicts['vars'].get_fname(),"regular","TRUE","CONDOR_VARS_FILE",dicts['vars'].save_into_str(set_readonly=files_set_readonly,reset_changed=files_reset_changed)),allow_overwrite=True)
    file_dict.add(cWConsts.UNTAR_CFG_FILE,(dicts['untar_cfg'].get_fname(),"regular","TRUE","UNTAR_CFG_FILE",dicts['untar_cfg'].save_into_str(set_readonly=files_set_readonly,reset_changed=files_reset_changed)),allow_overwrite=True)
    if is_main:
        file_dict.add(cWConsts.GRIDMAP_FILE,(dicts['gridmap'].get_fname(),"regular","TRUE","GRIDMAP",dicts['gridmap'].save_into_str(set_readonly=files_set_readonly,reset_changed=files_reset_changed)),allow_overwrite=True)

# dictionaries must have been written to disk before using this
def refresh_signature(dicts): # update in place
    signature_dict=dicts['signature']
    for k in ('consts','vars','untar_cfg','gridmap','preentry_file_list','file_list','aftergroup_preentry_file_list','aftergroup_file_list','description'):
        if dicts.has_key(k):
            signature_dict.add_from_file(dicts[k].get_filepath(),allow_overwrite=True)
    # add signatures of all the files linked in the lists
    for k in ('preentry_file_list','file_list','aftergroup_preentry_file_list','aftergroup_file_list'):
        if dicts.has_key(k):
            filedict=dicts[k]
            for fname in filedict.get_immutable_files():
                signature_dict.add_from_file(os.path.join(filedict.dir,fname),allow_overwrite=True)
    

################################################
#
# Functions that save dictionaries
#
################################################


# internal, do not use from outside the module
def save_common_dicts(dicts,     # will update in place, too
                      is_main,
                     set_readonly=True):
    # make sure decription is up to date
    refresh_description(dicts)
    # save the immutable ones
    for k in ('description',):
        dicts[k].save(set_readonly=set_readonly)
    # Load files into the file list
    # 'consts','untar_cfg','vars','gridmap' will be loaded
    refresh_file_list(dicts,is_main)
    # save files in the file lists
    for k in ('preentry_file_list','file_list','aftergroup_preentry_file_list','aftergroup_file_list'):
        if dicts.has_key(k):
            dicts[k].save_files(allow_overwrite=True)
    # then save the lists
    for k in ('preentry_file_list','file_list','aftergroup_preentry_file_list','aftergroup_file_list'):
        if dicts.has_key(k):
            dicts[k].save(set_readonly=set_readonly)
    # calc and save the signatues
    refresh_signature(dicts)
    dicts['signature'].save(set_readonly=set_readonly)

    #finally save the mutable one(s)
    if dicts.has_key('params'):
        dicts['params'].save(set_readonly=set_readonly)
    if dicts.has_key('attrs'):
        dicts['attrs'].save(set_readonly=set_readonly)

# must be invoked after all the groups have been saved
def save_main_dicts(main_dicts, # will update in place, too
                    set_readonly=True):
    main_dicts['frontend_descript'].save(set_readonly=set_readonly)
    save_common_dicts(main_dicts,True,set_readonly=set_readonly)
    summary_signature=main_dicts['summary_signature']
    summary_signature.add_from_file(key="main",filepath=main_dicts['signature'].get_filepath(),fname2=main_dicts['description'].get_fname(),allow_overwrite=True)
    summary_signature.save(set_readonly=set_readonly)


def save_group_dicts(group_dicts,                   # will update in place, too
                     group_name,summary_signature,  # update in place
                     set_readonly=True):
    group_dicts['group_descript'].save(set_readonly=set_readonly)
    save_common_dicts(group_dicts,False,set_readonly=set_readonly)
    summary_signature.add_from_file(key=cvWConsts.get_group_stage_dir("",group_name),filepath=group_dicts['signature'].get_filepath(),fname2=group_dicts['description'].get_fname(),allow_overwrite=True)

################################################
#
# Functions that reuse dictionaries
#
################################################

def reuse_simple_dict(dicts,other_dicts,key,compare_keys=None):
    if dicts[key].is_equal(other_dicts[key],compare_dir=True,compare_fname=False,compare_keys=compare_keys):
        # if equal, just use the old one, and mark it as unchanged and readonly
        dicts[key]=copy.deepcopy(other_dicts[key])
        dicts[key].changed=False
        dicts[key].set_readonly(True)
        return True
    else:
        return False

def reuse_file_dict(dicts,other_dicts,key):
    dicts[key].reuse(other_dicts[key])
    return reuse_simple_dict(dicts,other_dicts,key)

def reuse_common_dicts(dicts, other_dicts,is_main,all_reused):
    # save the immutable ones
    # check simple dictionaries
    for k in ('consts','untar_cfg','vars','gridmap'):
        if dicts.has_key(k):
            all_reused=reuse_simple_dict(dicts,other_dicts,k) and all_reused
    # since the file names may have changed, refresh the file_list    
    refresh_file_list(dicts,is_main)
    # check file-based dictionaries
    for k in ('preentry_file_list','file_list','aftergroup_preentry_file_list','aftergroup_file_list'):
        if dicts.has_key(k):
            all_reused=reuse_file_dict(dicts,other_dicts,k) and all_reused

    if all_reused:
        # description and signature track other files
        # so they change iff the others change
        for k in ('description','signature'):
            dicts[k]=copy.deepcopy(other_dicts[k])
            dicts[k].changed=False
            dicts[k].set_readonly(True)
            
    # check the mutable ones
    for k in ('params','attrs'):
        if dicts.has_key(k):
            reuse_simple_dict(dicts,other_dicts,k)

    return all_reused

def reuse_main_dicts(main_dicts, other_main_dicts):
    reuse_simple_dict(main_dicts, other_main_dicts,'frontend_descript')
    all_reused=reuse_common_dicts(main_dicts, other_main_dicts,True,True)
    # will not try to reuse the summary_signature... being in work_dir
    # can be rewritten and it is not worth the pain to try to prevent it
    return all_reused

def reuse_group_dicts(group_dicts, other_group_dicts,group_name):
    reuse_simple_dict(group_dicts, other_group_dicts,'group_descript')
    all_reused=reuse_common_dicts(group_dicts, other_group_dicts,False,True)
    return all_reused

################################################
#
# Handle dicts as Classes
#
################################################

################################################
#
# This Class contains the main dicts
#
################################################

class frontendMainDicts(cWDictFile.fileMainDicts):
    def __init__(self,
                 work_dir,stage_dir,
                 workdir_name,
                 simple_work_dir=False, # if True, do not create the lib and lock work_dir subdirs, nor the params dict
                 assume_groups=True,
                 log_dir=None):         # used only if simple_work_dir=False
        self.assume_groups=assume_groups
        cWDictFile.fileMainDicts.__init__(self,work_dir,stage_dir,workdir_name,simple_work_dir,log_dir)
        

    ######################################
    # Redefine methods needed by parent
    def load(self):
        load_main_dicts(self.dicts)

    def save(self,set_readonly=True):
        save_main_dicts(self.dicts,set_readonly=set_readonly)

    # reuse as much of the other as possible
    def reuse(self,other):             # other must be of the same class
        cWDictFile.fileMainDicts.reuse(self,other)
        reuse_main_dicts(self.dicts,other.dicts)

    ####################
    # Internal
    ####################

    def get_daemon_log_dir(self,base_dir):
        return os.path.join(base_dir,"frontend")

    # Overwritting the empty one
    def get_main_dicts(self):
        return get_main_dicts(self.work_dir,self.stage_dir,self.simple_work_dir,self.assume_groups)
    
        
################################################
#
# This Class contains the group dicts
#
################################################

class frontendGroupDicts(cWDictFile.fileSubDicts):
    ######################################
    # Redefine methods needed by parent
    def load(self):
        load_group_dicts(self.dicts,self.sub_name,self.summary_signature)

    def save(self,set_readonly=True):
        save_group_dicts(self.dicts,self.sub_name,self.summary_signature,set_readonly=set_readonly)

    def save_final(self,set_readonly=True):
        pass # nothing to do
    
    # reuse as much of the other as possible
    def reuse(self,other):             # other must be of the same class
        cWDictFile.fileSubDicts.reuse(self,other)
        reuse_group_dicts(self.dicts,other.dicts,self.sub_name)

    ####################
    # Internal
    ####################

    def get_sub_work_dir(self,base_dir):
        return cvWConsts.get_group_work_dir(base_dir,self.sub_name)
    
    def get_sub_log_dir(self,base_dir):
        return cvWConsts.get_group_log_dir(base_dir,self.sub_name)
    
    def get_sub_stage_dir(self,base_dir):
        return cvWConsts.get_group_stage_dir(base_dir,self.sub_name)
    
    def get_sub_dicts(self):
        return get_group_dicts(self.work_dir,self.stage_dir,self.sub_name,self.simple_work_dir)
    
    def reuse_nocheck(self,other):
        reuse_group_dicts(self.dicts,other.dicts,self.sub_name)
        
################################################
#
# This Class contains both the main and
# the group dicts
#
################################################

class frontendDicts(cWDictFile.fileDicts):
    def __init__(self,work_dir,stage_dir,group_list=[],workdir_name='submit',
                 simple_work_dir=False, # if True, do not create the lib and lock work_dir subdirs, nor the params dict
                 log_dir=None):         # used only if simple_work_dir=False
        cWDictFile.fileDicts.__init__(self,work_dir,stage_dir,group_list,workdir_name,simple_work_dir,log_dir)

    ###########
    # PRIVATE
    ###########

    ######################################
    # Redefine methods needed by parent
    def new_MainDicts(self):
        return frontendMainDicts(self.work_dir,self.stage_dir,self.workdir_name,self.simple_work_dir,assume_groups=True,log_dir=self.log_dir)

    def new_SubDicts(self,sub_name):
        return frontendGroupDicts(self.work_dir,self.stage_dir,sub_name,self.main_dicts.get_summary_signature(),self.workdir_name,self.simple_work_dir,self.log_dir)

    def get_sub_name_from_sub_stage_dir(self,sign_key):
        return cvWConsts.get_group_name_from_group_stage_dir(sign_key)
    
