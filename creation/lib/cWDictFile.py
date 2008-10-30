#######################################################
#
# Classes needed to handle dictionary files
#
#######################################################

import os,os.path,string,copy
import hashCrypto
import cStringIO

########################################
#
# File dictionary classes
#
########################################

class DictFile:
    def __init__(self,dir,fname,sort_keys=False,order_matters=False,
                 fname_idx=None):      # if none, use fname
        self.dir=dir
        self.fname=fname
        if fname_idx==None:
            fname_idx=fname
        self.fname_idx=fname_idx
        
        if sort_keys and order_matters:
            raise RuntimeError,"Cannot preserve the order and sort the keys" 
        self.sort_keys=sort_keys
        self.order_matters=order_matters

        self.is_readonly=False
        self.changed=True
        
        self.keys=[]
        self.vals={}

    def has_key(self,key):
        return key in self.keys

    def __getitem__(self,key):
        return self.vals[key]

    def get_fname(self):
        return self.fname

    def get_dir(self):
        return self.dir

    def get_filepath(self):
        return os.path.join(self.dir,self.fname)

    def erase(self):
        self.keys=[]
        self.vals={}
        self.changed=True
        
    def set_readonly(self,readonly=True):
        self.is_readonly=readonly


    def add(self,key,val,allow_overwrite=False):
        if key in self.keys:
            if self.vals[key]==val:
                return # already exists, nothing to do

        if self.is_readonly:
            raise RuntimeError, "Trying to modify a readonly object!"
        
        if key in self.keys:
            if not allow_overwrite:
                raise RuntimeError, "Key '%s' already exists"%key
            elif not self.is_compatible(self.vals[key],val):
                raise RuntimeError, "Key '%s': Value %s not compatible with old value %s"%(key,val,self.vals[key])
            if self.vals[key]==val:
                return # nothing to do
        else:
            self.keys.append(key)
        self.vals[key]=val
        self.changed=True
        
    def remove(self,key,fail_if_missing=False):
        if not (key in self.keys):
            if not fail_if_missing:
                raise RuntimeError, "Key '%s' does not exist"%key
            else:
                return # nothing to do

        self.keys.remove(key)
        del self.vals[key]
        self.changed=True

    def save(self, dir=None, fname=None,        # if dir and/or fname are not specified, use the defaults specified in __init__
             sort_keys=None,set_readonly=True,reset_changed=True,
             save_only_if_changed=True,
             want_comments=True): 
        if save_only_if_changed and (not self.changed):
            return # no change -> don't save

        if dir==None:
            dir=self.dir
        if fname==None:
            fname=self.fname
        if sort_keys==None:
            sort_keys=self.sort_keys


        filepath=os.path.join(dir,fname)
        try:
            fd=open(filepath,"w")
        except IOError,e:
            raise RuntimeError, "Error creating %s: %s"%(filepath,e)
        try:
            self.save_into_fd(fd,sort_keys,set_readonly,reset_changed,want_comments)
        finally:
            fd.close()

        return

    def save_into_fd(self, fd,
                     sort_keys=None,set_readonly=True,reset_changed=True,
                     want_comments=True):
        if sort_keys==None:
            sort_keys=self.sort_keys

        header=self.file_header(want_comments)
        if header!=None:
            fd.write("%s\n"%header)
        if sort_keys:
            keys=self.keys[0:]
            keys.sort()
        else:
            keys=self.keys
        for k in keys:
            fd.write("%s\n"%self.format_val(k,want_comments))
        footer=self.file_footer(want_comments)
        if footer!=None:
            fd.write("%s\n"%footer)

        if set_readonly:
            self.set_readonly(True)

        if reset_changed:
            self.changed=False
        return

    def save_into_str(self,
                      sort_keys=None,set_readonly=True,reset_changed=True,
                      want_comments=True):
        fd=cStringIO.StringIO()
        self.save_into_fd(fd,sort_keys,set_readonly,reset_changed,want_comments)
        fd.seek(0)
        data=fd.read()
        fd.close()
        return data
    
    def load(self, dir=None, fname=None,
             change_self=True,        # if dir and/or fname are not specified, use the defaults specified in __init__, if they are, and change_self is True, change the self.
             erase_first=True,        # if True, delete old content first
             set_not_changed=True):   # if True, set self.changed to False
        if dir==None:
            dir=self.dir
        if fname==None:
            fname=self.fname

        filepath=os.path.join(dir,fname)
        try:
            fd=open(filepath,"r")
        except IOError,e:
            raise RuntimeError, "Error opening %s: %s"%(filepath,e)
        try:
            try:
                self.load_from_fd(fd,erase_first,set_not_changed)
            except RuntimeError, e:
                raise RuntimeError, "File %s: %s"%(filepath,str(e))
        finally:
            fd.close()

        if change_self:
            self.dir=dir
            self.fname=fname

        return

    def load_from_fd(self, fd,
                     erase_first=True,        # if True, delete old content first
                     set_not_changed=True):   # if True, set self.changed to False
        if erase_first:
            self.erase()

        lines=fd.readlines()

        idx=0
        for line in lines:
            idx+=1
            if line[-1]=='\n':
                # strip newline
                line=line[:-1]
            try:
                self.parse_val(line)
            except RuntimeError, e:
                raise RuntimeError, "Line %i: %s"%(idx,str(e))

        if set_not_changed:
            self.changed=False # the memory copy is now same as the one on disk
        return

    def load_from_str(self, data,
                      erase_first=True,        # if True, delete old content first
                      set_not_changed=True):   # if True, set self.changed to False
        fd=cStringIO.StringIO()
        fd.write(data)
        fd.seek(0)
        try:
            self.load_from_fd(fd,erase_first,set_not_changed)
        except RuntimeError, e:
            raise RuntimeError, "Memory buffer: %s"%(filepath,str(e))
        fd.close()
        return        
        
    def is_equal(self,other,         # other must be of the same class
                 compare_dir=False,compare_fname=False,
                 compare_keys=None): # if None, use order_matters
        if compare_dir and (self.dir!=other.dir):
            return False
        if compare_fname and (self.fname!=other.fname):
            return False
        if compare_keys==None:
            compare_keys=self.order_matters
        if compare_keys and (self.keys!=other.keys):
            return False
        res=(self.save_into_str(sort_keys=None,set_readonly=False,reset_changed=False,want_comments=False)==other.save_into_str(sort_keys=None,set_readonly=False,reset_changed=False,want_comments=False))
        return res

    # PRIVATE
    def is_compatible(self,old_val,new_val):
        return True # everything is compatible
    
    def file_header(self,want_comments):
        if want_comments:
            return "# File: %s\n#"%self.fname
        else:
            return None
    
    def file_footer(self,want_comments):
        return None # no footer
    
    def format_val(self,key,want_comments):
        return "%s \t%s"%(key,self.vals[key])

    def parse_val(self,line):
        if line[0]=='#':
            return # ignore comments
        arr=line.split(None,1)
        if len(arr)==0:
            return # empty line
        if len(arr[0])==0:
            return # empty key

        key=arr[0]
        if len(arr)==1:
            val=''
        else:
            val=arr[1]
        return self.add(key,val)

class DictFileTwoKeys(DictFile): # both key and val are keys
    def __init__(self,dir,fname,sort_keys=False,order_matters=False,
                 fname_idx=None):      # if none, use fname
        DictFile.__init__(self,dir,fname,sort_keys,order_matters,fname_idx)
        self.keys2=[]
        self.vals2={}

    def has_key2(self,key):
        return key in self.keys2

    def get_val2(self,key):
        return self.vals2[key]

    def erase(self):
        DictFile.erase(self)
        self.keys2=[]
        self.vals2={}

    def add(self,key,val,allow_overwrite=False):
        if key in self.keys:
            if self.vals[key]==val:
                return # already exists, nothing to do

        if self.is_readonly:
            raise RuntimeError, "Trying to modify a readonly object!"
        
        if key in self.keys:
            old_val=self.vals[key]
            if not allow_overwrite:
                raise RuntimeError, "Key '%s' already exists"%key
            elif not self.is_compatible(old_val,val):
                raise RuntimeError, "Key '%s': Value %s not compatible with old value %s"%(key,val,old_val)
            if old_val==val:
                return # nothing to be changed
            # the second key changed, need to delete the old one
            self.keys2.remove(old_val)
            del self.vals2[old_val]
        else:
            self.keys.append(key)
        self.vals[key]=val

        if val in self.keys2:
            old_key=self.vals2[val]
            if not allow_overwrite:
                raise RuntimeError, "Value '%s' already exists"%val
            elif not self.is_compatible2(old_key,key):
                raise RuntimeError, "Value '%s': Key %s not compatible with old key %s"%(val,key,old_key)
            #if old_key==key: # no need to change again, would have hit the check above
            #    return # nothing to be changed
            # the first key changed, need to delete the old one
            self.keys.remove(old_key)
            del self.vals[old_key]
        else:
            self.keys2.append(val)
        self.vals2[val]=key
        self.changed=True
    
    def remove(self,key,fail_if_missing=False):
        if not (key in self.keys):
            if not fail_if_missing:
                raise RuntimeError, "Key '%s' does not exist"%key
            else:
                return # nothing to do

        val=self.vals[key]

        self.keys.remove(key)
        del self.vals[key]
        self.keys2.remove(val)
        del self.vals2[val]
        self.changed=True

    def is_equal(self,other,         # other must be of the same class
                 compare_dir=False,compare_fname=False,
                 compare_keys=None): # if None, use order_matters
        if compare_dir and (self.dir!=other.dir):
            return False
        if compare_fname and (self.fname!=other.fname):
            return False
        if compare_keys==None:
            compare_keys=self.order_matters
        if compare_keys and ((self.keys!=other.keys) or (self.keys2!=other.keys2)):
            return False
        res=(self.save_into_str(sort_keys=None,set_readonly=False,reset_changed=False,want_comments=False)==other.save_into_str(sort_keys=None,set_readonly=False,reset_changed=False,want_comments=False))
        return res
        
    # PRIVATE
    def is_compatible2(self,old_val2,new_val2):
        return True # everything is compatible


# descriptions
class DescriptionDictFile(DictFileTwoKeys):
    def format_val(self,key,want_comments):
        return "%s \t%s"%(self.vals[key],key)

    def parse_val(self,line):
        if line[0]=='#':
            return # ignore comments
        arr=line.split(None,1)
        if len(arr)==0:
            return # empty line
        if len(arr)!=2:
            raise RuntimeError,"Not a valid description line: '%s'"%line

        return self.add(arr[1],arr[0])
    
##################################

# signatures
class SHA1DictFile(DictFile):
    def add_from_file(self,filepath,allow_overwrite=False,
                      key=None): # if key==None, use basefname
        sha1=hashCrypto.extract_sha1(filepath)
        if key==None:
            key=os.path.basename(filepath)
        self.add(key,sha1,allow_overwrite)

    def format_val(self,key,want_comments):
        return "%s  %s"%(self.vals[key],key)

    def parse_val(self,line):
        if line[0]=='#':
            return # ignore comments
        arr=line.split(None,1)
        if len(arr)==0:
            return # empty line
        if len(arr)!=2:
            raise RuntimeError,"Not a valid SHA1 line: '%s'"%line

        return self.add(arr[1],arr[0])
    
# summary signatures
# values are (sha1,fname2)
class SummarySHA1DictFile(DictFile):
    def add(self,key,val,allow_overwrite=False):
        if not (type(val) in (type(()),type([]))):
            raise RuntimeError, "Values '%s' not a list or tuple"%val
        if len(val)!=2:
            raise RuntimeError, "Values '%s' not (sha1,fname)"%val
        return DictFile.add(self,key,val,allow_overwrite)

    def add_from_file(self,filepath,
                      fname2=None, # if fname2==None, use basefname
                      allow_overwrite=False,
                      key=None):   # if key==None, use basefname
        sha1=hashCrypto.extract_sha1(filepath)
        if key==None:
            key=os.path.basename(filepath)        
        if fname2==None:
            fname2=os.path.basename(filepath)        
        DictFile.add(self,key,(sha1,fname2),allow_overwrite)

    def format_val(self,key,want_comments):
        return "%s  %s  %s"%(self.vals[key][0],self.vals[key][1],key)

    def parse_val(self,line):
        if line[0]=='#':
            return # ignore comments
        arr=line.split(None,2)
        if len(arr)==0:
            return # empty line
        if len(arr)!=3:
            raise RuntimeError,"Not a valid summary signature line (expected 4, found %i elements): '%s'"%(len(arr),line)

        key=arr[2]
        return self.add(key,(arr[0],arr[1]))

# file list
# also hold the content of the file as the last entry in vals
class SimpleFileDictFile(DictFile):
    def get_immutable_files(self):
        return self.keys # keys are files, and all are immutable in this implementation

    def add(self,key, # key is filename in this case
            val,allow_overwrite=False):
        return self.add_from_file(key,val,os.path.join(self.dir,key),allow_overwrite)

    def add_from_str(self,key,val,
                    data, 
                    allow_overwrite=False):
        # make it generic for use by children
        if not (type(val) in (type(()),type([]))):
            DictFile.add(self,key,(val,data),allow_overwrite)
        else:
            DictFile.add(self,key,tuple(val)+(data,),allow_overwrite)

    def add_from_fd(self,key,val,
                    fd, # open file object that has a read() method
                    allow_overwrite=False):
        data=fd.read()
        self.add_from_str(key,val,data,allow_overwrite)

    def add_from_file(self,key,val,
                      filepath,
                      allow_overwrite=False):
        try:
            fd=open(filepath,"r")
        except IOError,e:
            raise RuntimeError,"Could not open file %s"%filepath
        try:
            self.add_from_fd(key,val,fd,allow_overwrite)
        finally:
            fd.close()

    def format_val(self,key,want_comments):
        if self.vals[key][0]!=None:
            return "%s \t%s"%(key,self.vals[key][0])
        else:
            return key

    def parse_val(self,line):
        if line[0]=='#':
            return # ignore comments
        arr=line.split(None,1)
        if len(arr)==0:
            return # empty line
        if len(arr[0])==0:
            return # empty key

        key=arr[0]
        if len(arr)==1:
            val=None
        else:
            val=arr[1]
        return self.add(key,val)

    def save_files(self,allow_overwrite=False):
        for key in self.keys:
            fname=self.get_file_fname(key)
            fdata=self.vals[key][-1]
            filepath=os.path.join(self.dir,fname)
            if (not allow_overwrite) and os.path.exists(filepath):
                raise RuntimeError,"File %s already exists"%filepath
            try:
                fd=open(filepath,"w")
            except IOError,e:
                raise RuntimeError,"Could not create file %s"%filepath
            try:
                try:
                    fd.write(fdata)
                except IOError,e:
                    raise RuntimeError,"Error writing into file %s"%filepath
            finally:
                fd.close()

    def get_file_fname(self,key):
        return key

# file list
# This one contains (real_fname,cache/exec,cond_download,config_out)
# cache/exec should be one of: regular, nocache, exec, untar
# cond_download has a special value of TRUE
# config_out has a special value of FALSE
class FileDictFile(SimpleFileDictFile):
    def add_placeholder(self,key,allow_overwrite=True):
        DictFile.add(self,key,("","","","",""),allow_overwrite)

    def is_placeholder(self,key):
        return (self[key][0]=="") # empty real_fname can only be a placeholder

    def add_from_str(self,key,val,
                     data, 
                     allow_overwrite=False,
                     allow_overwrite_placeholder=True):
        if self.has_key(key) and allow_overwrite_placeholder:
            if self.is_placeholder(key):
                allow_overwrite=True # since the other functions know nothing about placeholders, need to force overwrite
        return SimpleFileDictFile.add_from_str(self,key,val,data,allow_overwrite)

    def add(self,key,
            val,     # will if len(val)==5, use the last one as data, else load from val[0]
            allow_overwrite=False,
            allow_overwrite_placeholder=True):
        if not (type(val) in (type(()),type([]))):
            raise RuntimeError, "Values '%s' not a list or tuple"%val

        if self.has_key(key) and allow_overwrite_placeholder:
            if self.is_placeholder(key):
                allow_overwrite=True # since the other functions know nothing about placeholders, need to force overwrite
        
        if len(val)==5:
            return self.add_from_str(key,val[:4],val[4],allow_overwrite)
        elif len(val)==4:
            return self.add_from_file(key,val,os.path.join(self.dir,val[0]),allow_overwrite)
        else:
            raise RuntimeError, "Values '%s' not (real_fname,cache/exec,cond_download,config_out)"%val

    def format_val(self,key,want_comments):
        return "%s \t%s \t%s \t%s \t%s"%(key,self.vals[key][0],self.vals[key][1],self.vals[key][2],self.vals[key][3])

    def file_header(self,want_comments):
        if want_comments:
            return (DictFile.file_header(self,want_comments)+"\n"+
                    ("# %s \t%s \t%s \t%s \t%s\n"%('Outfile','InFile        ','Cache/exec','Condition','ConfigOut'))+
                    ("#"*78))
        else:
            return None

    def parse_val(self,line):
        if line[0]=='#':
            return # ignore comments
        arr=line.split(None,4)
        if len(arr)==0:
            return # empty line
        if len(arr[0])==0:
            return # empty key

        if len(arr)!=5:
            raise RuntimeError,"Not a valid file line (expected 5, found %i elements): '%s'"%(len(arr),line)

        return self.add(arr[0],arr[1:])

    def get_file_fname(self,key):
        return self.vals[key][0]

    def get_immutable_files(self):
        mkeys=[]
        for k in self.keys:
            val=self.vals[k][1]
            if (val!="nocache"):
                mkeys.append(self.vals[k][0]) # file name is not the key, but the first entry
            
        return mkeys

    def reuse(self,other,
              compare_dir=False,compare_fname=False,
              compare_files_fname=False):
        if compare_dir and (self.dir!=other.dir):
            return # nothing to do, different dirs
        if compare_fname and (self.fname!=other.fname):
            return # nothing to do, different fnames

        for k in self.keys:
            if k in other.keys:
                # the other has the same key, check if they are the same
                if compare_files_fname:
                    is_equal=(self.vals[k]==other.vals[k])
                else: # ignore file name (first element)
                    is_equal=(self.vals[k][1:]==other.vals[k][1:])

                if is_equal:
                    self.vals[k]=copy.deepcopy(other.vals[k])
                # else they are different and there is nothing to be done
                    
        return
            
# will convert values into python format before writing them out
class ReprDictFile(DictFile):
    def format_val(self,key,want_comments):
        return "%s \t%s"%(key,repr(self.vals[key]))

    def parse_val(self,line):
        if line[0]=='#':
            return # ignore comments
        arr=line.split(None,1)
        if len(arr)==0:
            return # empty line
        if len(arr[0])==0:
            return # empty key

        key=arr[0]
        if len(arr)==1:
            val=''
        else:
            val=arr[1]
        return self.add(key,eval(val))

# will hold only strings
class StrDictFile(DictFile):
    def add(self,key,val,allow_overwrite=False):
        DictFile.add(self,key,str(val),allow_overwrite)

# values are (Type,Default,CondorName,Required,Export,UserName)
class VarsDictFile(DictFile):
    def is_compatible(self,old_val,new_val):
        return ((old_val[0]==new_val[0]) and (old_val[4]==new_val[4]))# at least the type and the export must be preserved
    
    def file_header(self,want_comments):
        if want_comments:
            return (DictFile.file_header(self,want_comments)+"\n"+
                    "# VarName               Type    Default         CondorName                     Req.     Export  UserName           \n"+
                    "#                       S=Quote - = No Default  + = VarName                             Condor   - = Do not export \n"+
                    "#                                                                                                + = Use VarName   \n"+
                    "#                                                                                                @ = Use CondorName\n"
                    "###################################################################################################################")
        else:
            return None

    def add(self,key,val,allow_overwrite=0):
        if not (type(val) in (type(()),type([]))):
            raise RuntimeError, "Values '%s' not a list or tuple"%val
        if len(val)!=6:
            raise RuntimeError, "Values '%s' not (Type,Default,CondorName,Required,Export,UserName)"%str(val)
        if not (val[0] in ('C','S','I')):
            raise RuntimeError,"Invalid var type '%s', should be either C, S or I in val: %s"%(val[1],str(val))
        for i,t in ((3,"Required"),(4,"Export")):
            if not (val[i] in ('Y','N')):
                raise RuntimeError,"Invalid var %s '%s', should be either Y or N in val: %s"%(t,val[i],str(val))

        return DictFile.add(self,key,val,allow_overwrite)

    def add_extended(self,key,
                     is_string,
                     val_default, # None or False==No default (i.e. -)
                     condor_name, # if None or false, Varname (i.e. +)
                     required,
                     export_condor,
                     user_name,   # If None or false, do not export (i.e. -)
                                  # if True, set to VarName (i.e. +)
                     allow_overwrite=0):
        if is_string:
            type_str='S'
        else:
            type_str='I'
            
        if (val_default==None) or (val_default==False):
            val_default='-'
            
        if (condor_name==None) or (condor_name==False):
            condor_name="+"
            
        if required:
            req_str='Y'
        else:
            req_str='N'
            
        if export_condor:
            export_condor_str='Y'
        else:
            export_condor_str='N'

        if (user_name==None) or (user_name==False):
            user_name='-'
        elif user_name==True:
            user_name='+'
            
        self.add(key,(type_str,val_default,condor_name,req_str,export_condor_str,user_name),allow_overwrite)
        
    def format_val(self,key,want_comments):
        return "%s \t%s \t%s \t\t%s \t%s \t%s \t%s"%(key,self.vals[key][0],self.vals[key][1],self.vals[key][2],self.vals[key][3],self.vals[key][4],self.vals[key][5])
        

    def parse_val(self,line):
        if len(line)==0:
            return #ignore emoty lines
        if line[0]=='#':
            return # ignore comments
        arr=line.split(None,6)
        if len(arr)==0:
            return # empty line
        if len(arr)!=7:
            raise RuntimeError,"Not a valid var line (expected 7, found %i elements): '%s'"%(len(arr),line)

        key=arr[0]
        return self.add(key,arr[1:])

# values are (Type,System,Ref)
class InfoSysDictFile(DictFile):
    def file_header(self,want_comments):
        if want_comments:
            return (DictFile.file_header(self,want_comments)+"\n"+
                    ("# %s \t%30s \t%s \t\t%s\n"%('Type','Server','Ref','ID'))+
                    ("#"*78))
        else:
            return None

    # key can be None
    # in that case it will be composed out of value
    def add(self,key,val,allow_overwrite=0):
        if not (type(val) in (type(()),type([]))):
            raise RuntimeError, "Values '%s' not a list or tuple"%val
        if len(val)!=3:
            raise RuntimeError, "Values '%s' not (Type,System,Ref)"%str(val)

        if key==None:
            key="%s://%s/%s"%val
        return DictFile.add(self,key,val,allow_overwrite)

    def add_extended(self,
                     infosys_type,
                     server_name,
                     ref_str,
                     allow_overwrite=0):
        self.add(None,(infosys_type,server_name,ref_str))
        
    def format_val(self,key,want_comments):
        return "%s \t%30s \t%s \t\t%s"%(self.vals[key][0],self.vals[key][1],self.vals[key][2],key)
        

    def parse_val(self,line):
        if len(line)==0:
            return #ignore emoty lines
        if line[0]=='#':
            return # ignore comments
        arr=line.split(None,3)
        if len(arr)==0:
            return # empty line
        if len(arr)!=4:
            raise RuntimeError,"Not a valid var line (expected 4, found %i elements): '%s'"%(len(arr),line)

        key=arr[-1]
        return self.add(key,arr[:-1])


class CondorJDLDictFile(DictFile):
    def __init__(self,dir,fname,sort_keys=False,order_matters=False,jobs_in_cluster=None,
                 fname_idx=None):      # if none, use fname
        DictFile.__init__(self,dir,fname,sort_keys,order_matters,fname_idx)
        self.jobs_in_cluster=jobs_in_cluster

    def file_footer(self,want_comments):
        if self.jobs_in_cluster==None:
            return "Queue"
        else:
            return "Queue %s"%self.jobs_in_cluster

    def format_val(self,key,want_comments):
        return "%s = %s"%(key,self.vals[key])

    def parse_val(self,line):
        if line[0]=='#':
            return # ignore comments
        arr=line.split(None,2)
        if len(arr)==0:
            return # empty line

        if arr[0]=='Queue':
            # this is the final line
            if len(arr)==1:
                # default
                self.jobs_in_cluster=None
            else:
                self.jobs_in_cluster=arr[1]
            return
            
        # should be a regular line
        if len(arr)<2:
            raise RuntimeError,"Not a valid Condor JDL line, too short: '%s'"%line
        if arr[1]!='=':
            raise RuntimeError,"Not a valid Condor JDL line, no =: '%s'"%line
        
        if len(arr)==2:
            return self.add(arr[0],"") # key = <empty>
        else:
            return self.add(arr[0],arr[2])

    def is_equal(self,other,         # other must be of the same class
                 compare_dir=False,compare_fname=False,
                 compare_keys=None): # if None, use order_matters
        if self.jobs_in_cluster==other.jobs_in_cluster:
            return DictFile.is_equal(other,compare_dir,compare_fname,compare_keys)
        else:
            return False

