#######################################################
#
# Glidein creation module
# Classes and functions needed to handle dictionary files
#
#######################################################

import os,os.path,shutil,string,copy
import cgWConsts,cWConsts
import cWDictFile


################################################
#
# Functions that create default dictionaries
#
################################################

# internal, do not use from outside the module
def get_common_dicts(submit_dir,stage_dir):
    common_dicts={'attrs':cWDictFile.ReprDictFile(submit_dir,cgWConsts.ATTRS_FILE),
                  'description':cWDictFile.DescriptionDictFile(stage_dir,cWConsts.insert_timestr(cWConsts.DESCRIPTION_FILE),fname_idx=cWConsts.DESCRIPTION_FILE),
                  'consts':cWDictFile.StrDictFile(stage_dir,cWConsts.insert_timestr(cWConsts.CONSTS_FILE),fname_idx=cWConsts.CONSTS_FILE),
                  'params':cWDictFile.ReprDictFile(submit_dir,cgWConsts.PARAMS_FILE),
                  'vars':cWDictFile.VarsDictFile(stage_dir,cWConsts.insert_timestr(cgWConsts.VARS_FILE),fname_idx=cgWConsts.VARS_FILE),
                  'untar_cfg':cWDictFile.StrDictFile(stage_dir,cWConsts.insert_timestr(cWConsts.UNTAR_CFG_FILE),fname_idx=cWConsts.UNTAR_CFG_FILE),
                  'file_list':cWDictFile.FileDictFile(stage_dir,cWConsts.insert_timestr(cWConsts.FILE_LISTFILE),fname_idx=cWConsts.FILE_LISTFILE),
                  "signature":cWDictFile.SHA1DictFile(stage_dir,cWConsts.insert_timestr(cWConsts.SIGNATURE_FILE),fname_idx=cWConsts.SIGNATURE_FILE)}
    refresh_description(common_dicts)
    return common_dicts

def get_main_dicts(submit_dir,stage_dir):
    main_dicts=get_common_dicts(submit_dir,stage_dir)
    main_dicts['summary_signature']=cWDictFile.SummarySHA1DictFile(submit_dir,cWConsts.SUMMARY_SIGNATURE_FILE)
    main_dicts['glidein']=cWDictFile.StrDictFile(submit_dir,cgWConsts.GLIDEIN_FILE)
    main_dicts['after_file_list']=cWDictFile.FileDictFile(stage_dir,cWConsts.insert_timestr(cWConsts.AFTER_FILE_LISTFILE),fname_idx=cWConsts.AFTER_FILE_LISTFILE)
    return main_dicts

def get_entry_dicts(entry_submit_dir,entry_stage_dir,entry_name):
    entry_dicts=get_common_dicts(entry_submit_dir,entry_stage_dir)
    entry_dicts['job_descript']=cWDictFile.StrDictFile(entry_submit_dir,cgWConsts.JOB_DESCRIPT_FILE)
    entry_dicts['infosys']=cWDictFile.InfoSysDictFile(entry_submit_dir,cgWConsts.INFOSYS_FILE)
    return entry_dicts

################################################
#
# Functions that load dictionaries
#
################################################

# internal, do not use from outside the module
def load_common_dicts(dicts,           # update in place
                      description_el):
    # first submit dir ones (mutable)
    dicts['params'].load()
    dicts['attrs'].load()
    # now the ones keyed in the description
    dicts['signature'].load(fname=description_el.vals2['signature'])
    dicts['file_list'].load(fname=description_el.vals2['file_list'])
    file_el=dicts['file_list']
    # all others are keyed in the file_list
    dicts['consts'].load(fname=file_el[cWConsts.CONSTS_FILE][0])
    dicts['vars'].load(fname=file_el[cgWConsts.VARS_FILE][0])
    dicts['untar_cfg'].load(fname=file_el[cWConsts.UNTAR_CFG_FILE][0])

def load_main_dicts(main_dicts): # update in place
    main_dicts['glidein'].load()
    # summary_signature has keys for description
    main_dicts['summary_signature'].load()
    # load the description
    main_dicts['description'].load(fname=main_dicts['summary_signature']['main'][1])
    # all others are keyed in the description
    main_dicts['after_file_list'].load(fname=main_dicts['description'].vals2['after_file_list'])
    load_common_dicts(main_dicts,main_dicts['description'])

def load_entry_dicts(entry_dicts,                   # update in place
                     entry_name,summary_signature): 
    try:
        entry_dicts['infosys'].load()
    except RuntimeError:
         pass # ignore errors, this is optional
    entry_dicts['job_descript'].load()
    # load the description (name from summary_signature)
    entry_dicts['description'].load(fname=summary_signature[cgWConsts.get_entry_stage_dir("",entry_name)][1])
    # all others are keyed in the description
    load_common_dicts(entry_dicts,entry_dicts['description'])

############################################################
#
# Functions that create data out of the existing dictionary
#
############################################################

def refresh_description(dicts): # update in place
    description_dict=dicts['description']
    description_dict.add(dicts['signature'].get_fname(),"signature",allow_overwrite=True)
    for k in ('file_list','after_file_list'):
        if dicts.has_key(k):
            description_dict.add(dicts[k].get_fname(),k,allow_overwrite=True)

def refresh_file_list(dicts,is_main, # update in place
                      files_set_readonly=True,files_reset_changed=True):
    entry_str="_ENTRY"
    if is_main:
        entry_str=""
    file_dict=dicts['file_list']
    file_dict.add(cWConsts.CONSTS_FILE,(dicts['consts'].get_fname(),"regular","TRUE","CONSTS%s_FILE"%entry_str,dicts['consts'].save_into_str(set_readonly=files_set_readonly,reset_changed=files_reset_changed)),allow_overwrite=True)
    file_dict.add(cgWConsts.VARS_FILE,(dicts['vars'].get_fname(),"regular","TRUE","CONDOR_VARS%s_FILE"%entry_str,dicts['vars'].save_into_str(set_readonly=files_set_readonly,reset_changed=files_reset_changed)),allow_overwrite=True)
    file_dict.add(cWConsts.UNTAR_CFG_FILE,(dicts['untar_cfg'].get_fname(),"regular","TRUE","UNTAR_CFG%s_FILE"%entry_str,dicts['untar_cfg'].save_into_str(set_readonly=files_set_readonly,reset_changed=files_reset_changed)),allow_overwrite=True)

# dictionaries must have been written to disk before using this
def refresh_signature(dicts): # update in place
    signature_dict=dicts['signature']
    for k in ('consts','vars','untar_cfg','file_list','after_file_list','description'):
        if dicts.has_key(k):
            signature_dict.add_from_file(dicts[k].get_filepath(),allow_overwrite=True)
    # add signatures of all the files linked in the lists
    for k in ('file_list','after_file_list'):
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
    # 'consts','untar_cfg','vars' will be loaded
    refresh_file_list(dicts,is_main)
    # save files in the file lists
    for k in ('file_list','after_file_list'):
        if dicts.has_key(k):
            dicts[k].save_files(allow_overwrite=True)
    # then save the lists
    for k in ('file_list','after_file_list'):
        if dicts.has_key(k):
            dicts[k].save(set_readonly=set_readonly)
    # calc and save the signatues
    refresh_signature(dicts)
    dicts['signature'].save(set_readonly=set_readonly)

    #finally save the mutable one(s)
    dicts['params'].save(set_readonly=set_readonly)
    dicts['attrs'].save(set_readonly=set_readonly)

# must be invoked after all the entries have been saved
def save_main_dicts(main_dicts, # will update in place, too
                    set_readonly=True):
    main_dicts['glidein'].save(set_readonly=set_readonly)
    save_common_dicts(main_dicts,True,set_readonly=set_readonly)
    summary_signature=main_dicts['summary_signature']
    summary_signature.add_from_file(key="main",filepath=main_dicts['signature'].get_filepath(),fname2=main_dicts['description'].get_fname(),allow_overwrite=True)
    summary_signature.save(set_readonly=set_readonly)


def save_entry_dicts(entry_dicts,                   # will update in place, too
                     entry_name,summary_signature,  # update in place
                     set_readonly=True):
    entry_dicts['infosys'].save(set_readonly=set_readonly)
    entry_dicts['job_descript'].save(set_readonly=set_readonly)
    save_common_dicts(entry_dicts,False,set_readonly=set_readonly)
    summary_signature.add_from_file(key=cgWConsts.get_entry_stage_dir("",entry_name),filepath=entry_dicts['signature'].get_filepath(),fname2=entry_dicts['description'].get_fname(),allow_overwrite=True)

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
    for k in ('consts','untar_cfg','vars'):
        all_reused=reuse_simple_dict(dicts,other_dicts,k) and all_reused
    # since the file names may have changed, refresh the file_list    
    refresh_file_list(dicts,is_main)
    # check file-based dictionaries
    for k in ('file_list','after_file_list'):
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
    for k in ('attrs','params'):
        reuse_simple_dict(dicts,other_dicts,k)

    return all_reused

def reuse_main_dicts(main_dicts, other_main_dicts):
    reuse_simple_dict(main_dicts, other_main_dicts,'glidein')
    all_reused=reuse_common_dicts(main_dicts, other_main_dicts,True,True)
    # will not try to reuse the summary_signature... being in submit_dir
    # can be rewritten and it is not worth the pain to try to prevent it
    return all_reused

def reuse_entry_dicts(entry_dicts, other_entry_dicts,entry_name):
    reuse_simple_dict(entry_dicts, other_entry_dicts,'job_descript')
    reuse_simple_dict(entry_dicts, other_entry_dicts,'infosys')
    all_reused=reuse_common_dicts(entry_dicts, other_entry_dicts,False,True)
    return all_reused

################################################
#
# Handle dicts as Classes
#
################################################

# internal, do not use directly from outside the module
class glideinCommonDicts:
    def __init__(self):
        self.dicts=None
        self.submit_dir=None
        self.stage_dir=None
        raise RuntimeError, "glideinCommonDicts should never be directly used"
        
    def keys(self):
        return self.dicts.keys()

    def has_key(self,key):
        return self.dicts.has_key(key)

    def __getitem__(self,key):
        return self.dicts[key]        

    def set_readonly(self,readonly=True):
        for el in self.dicts.values():
            el.set_readonly(readonly)

    def create_dirs(self):
        try:
            os.mkdir(self.submit_dir)
            try:
                os.mkdir(os.path.join(self.submit_dir,'log'))
                os.mkdir(self.stage_dir)
            except:
                shutil.rmtree(self.submit_dir)
                raise
        except OSError,e:
            raise RuntimeError,"Failed to create dir: %s"%e

    def delete_dirs(self):
        shutil.rmtree(self.submit_dir)
        shutil.rmtree(self.stage_dir)


class glideinMainDicts(glideinCommonDicts):
    def __init__(self,submit_dir,stage_dir):
        self.submit_dir=submit_dir
        self.stage_dir=stage_dir
        self.erase()

    def create_dirs(self):
        glideinCommonDicts.create_dirs(self)
        try:
            proxy_dir=os.path.join(self.submit_dir,'client_proxies')
            os.mkdir(proxy_dir)
            os.chmod(proxy_dir,0700)
        except OSError,e:
            shutil.rmtree(self.submit_dir)
            raise RuntimeError,"Failed to create dir: %s"%e

    def get_summary_signature(self): # you can discover most of the other things from this
        return self.dicts['summary_signature']

    def erase(self):
        self.dicts=get_main_dicts(self.submit_dir,self.stage_dir)
    
    def load(self):
        load_main_dicts(self.dicts)

    def save(self,set_readonly=True):
        save_main_dicts(self.dicts,set_readonly=set_readonly)

    def is_equal(self,other,             # other must be of the same class
                 compare_submit_dir=False,compare_stage_dir=False,
                 compare_fnames=False): 
        if compare_submit_dir and (self.submit_dir!=other.submit_dir):
            return False
        if compare_stage_dir and (self.stage_dir!=other.stage_dir):
            return False
        for k in self.dicts.keys():
            if not self.dicts[k].is_equal(other.dicts[k],compare_dir=False,compare_fname=compare_fnames):
                return False
        return True

    # reuse as much of the other as possible
    def reuse(self,other):             # other must be of the same class
        if self.submit_dir!=other.submit_dir:
            raise RuntimeError,"Cannot change main submit base_dir! '%s'!='%s'"%(self.submit_dir,other.submit_dir)
        if self.stage_dir!=other.stage_dir:
            raise RuntimeError,"Cannot change main stage base_dir! '%s'!='%s'"%(self.stage_dir,other.stage_dir)

        reuse_main_dicts(self.dicts,other.dicts)
        
class glideinEntryDicts(glideinCommonDicts):
    def __init__(self,
                 glidein_main_dicts, # must be an instance of glideinMainDicts
                 entry_name):
        self.entry_name=entry_name
        self.glidein_main_dicts=glidein_main_dicts
        self.submit_dir=cgWConsts.get_entry_submit_dir(glidein_main_dicts.submit_dir,entry_name)
        self.stage_dir=cgWConsts.get_entry_stage_dir(glidein_main_dicts.stage_dir,entry_name)
        self.erase()

    def erase(self):
        self.dicts=get_entry_dicts(self.submit_dir,self.stage_dir,self.entry_name)
    
    def load(self): #will use glidein_main_dicts data, so it must be loaded first
        load_entry_dicts(self.dicts,self.entry_name,self.glidein_main_dicts.get_summary_signature())

    def save(self,set_readonly=True):
        save_entry_dicts(self.dicts,self.entry_name,self.glidein_main_dicts.get_summary_signature(),set_readonly=set_readonly)

    def save_final(self,set_readonly=True):
        pass # not needed here, but may be needed by children
    
    def is_equal(self,other,             # other must be of the same class
                 compare_entry_name=False,
                 compare_glidein_main_dicts=False, # if set to True, will do a complete check on the related objects
                 compare_fnames=False): 
        if compare_entry_name and (self.entry_name!=other.entry_name):
            return False
        if compare_glidein_main_dicts and (self.glidein_main_dicts.is_equal(other.glidein_main_dicts,compare_submit_dir=True,compare_stage_dir=True,compare_fnames=compare_fnames)):
            return False
        for k in self.dicts.keys():
            if not self.dicts[k].is_equal(other.dicts[k],compare_dir=False,compare_fname=compare_fnames):
                return False
        return True

    # reuse as much of the other as possible
    def reuse(self,other):             # other must be of the same class
        if self.submit_dir!=other.submit_dir:
            raise RuntimeError,"Cannot change entry submit base_dir! '%s'!='%s'"%(self.submit_dir,other.submit_dir)
        if self.stage_dir!=other.stage_dir:
            raise RuntimeError,"Cannot change entry stage base_dir! '%s'!='%s'"%(self.stage_dir,other.stage_dir)

        reuse_entry_dicts(self.dicts,other.dicts,self.entry_name)
        
################################################
#
# This Class contains both the main and
# the entry dicts
#
################################################

class glideinDicts:
    def __init__(self,submit_dir,stage_dir,entry_list=[]):
        self.submit_dir=submit_dir
        self.stage_dir=stage_dir
        self.main_dicts=glideinMainDicts(self.submit_dir,self.stage_dir)
        self.entry_list=entry_list[:]
        self.entry_dicts={}
        for entry_name in entry_list:
            self.entry_dicts[entry_name]=glideinEntryDicts(self.main_dicts,entry_name)
        return

    def set_readonly(self,readonly=True):
        self.main_dicts.set_readonly(readonly)
        for el in self.entry_dicts.values():
            el.set_readonly(readonly)

    def erase(self,destroy_old_entries=True): # if false, the entry names will be preserved
        self.main_dicts.erase()
        if destroy_old_entries:
            self.entry_list=[]
            self.entry_dicts={}
        else:
            for entry_name in self.entry_list:
                self.entry_dicts[entry_name].erase()
        return

    def load(self,destroy_old_entries=True): # if false, overwrite the entries you load, but leave the others as they are
        self.main_dicts.load()
        if destroy_old_entries:
            self.entry_list=[]
            self.entry_dicts={}
        # else just leave as it is, will rewrite just the loaded ones

        for sign_key in self.main_dicts.get_summary_signature().keys:
            if sign_key!='main': # main is special, not an entry
                entry_name=cgWConsts.get_entry_name_from_entry_stage_dir(sign_key)
                if not(entry_name in self.entry_list):
                    self.entry_list.append(entry_name)
                self.entry_dicts[entry_name]=self.new_entry(entry_name)
                self.entry_dicts[entry_name].load()



    def save(self,set_readonly=True):
        for entry_name in self.entry_list:
            self.entry_dicts[entry_name].save(set_readonly=set_readonly)
        self.main_dicts.save(set_readonly=set_readonly)
        for entry_name in self.entry_list:
            self.entry_dicts[entry_name].save_final(set_readonly=set_readonly)
   
    def create_dirs(self):
        self.main_dicts.create_dirs()
        try:
            for entry_name in self.entry_list:
                self.entry_dicts[entry_name].create_dirs()
        except:
            self.main_dicts.delete_dirs() # this will clean up also any created entries
            raise
        
    def delete_dirs(self):
        self.main_dicts.delete_dirs() # this will clean up also all entries

    def is_equal(self,other,             # other must be of the same class
                 compare_submit_dir=False,compare_stage_dir=False,
                 compare_fnames=False): 
        if compare_submit_dir and (self.submit_dir!=other.submit_dir):
            return False
        if compare_stage_dir and (self.stage_dir!=other.stage_dir):
            return False
        if not self.main_dicts.is_equal(other.main_dicts,compare_submit_dir=False,compare_stage_dir=False,compare_fnames=compare_fnames):
            return False
        my_entries=self.entry_list[:]
        other_entries=other.entry_list[:]
        if len(my_entries)!=len(other_entries):
            return False

        my_entries.sort()
        other_entries.sort()
        if my_entries!=other_entries: # need to be in the same order to make a comparison
            return False
        
        for k in my_entries:
            if not self.entry_dicts[k].is_equal(other.entry_dicts[k],compare_entry_name=False,
                                                compare_glidein_main_dicts=False,compare_fname=compare_fnames):
                return False
        return True

    # reuse as much of the other as possible
    def reuse(self,other):             # other must be of the same class
        if self.submit_dir!=other.submit_dir:
            raise RuntimeError,"Cannot change submit base_dir! '%s'!='%s'"%(self.submit_dir,other.submit_dir)
        if self.stage_dir!=other.stage_dir:
            raise RuntimeError,"Cannot change stage base_dir! '%s'!='%s'"%(self.stage_dir,other.stage_dir)

        # compare main dictionaires
        self.main_dicts.reuse(other.main_dicts)

        # compare entry dictionaires
        for k in self.entry_list:
            if k in other.entry_list:
                self.entry_dicts[k].reuse(other.entry_dicts[k])
            else:
                # nothing to reuse, but must create dir
                self.entry_dicts[k].create_dirs()

    ###########
    # PRIVATE
    ###########

    # return a new entry object
    def new_entry(self,entry_name):
        return glideinEntryDicts(self.main_dicts,entry_name)
    
