#
# Project:
#   glideinWMS
#
# File Version: 
#
# Desscription:
#   This module contains the generic params classes
#
# Extracted from:
#   cgWParams.py
#
# Author:
#   Igor Sfiligoi
#

import os
import copy
import sys
import os.path
import string
import socket
import types
import traceback
from glideinwms.lib import xmlParse
import xml.parsers.expat
from glideinwms.lib import xmlFormat

class SubParams:
    def __init__(self,data):
        self.data=data

    def __eq__(self,other):
        if other is None:
            return False
        if not isinstance(other,self.__class__):
            return False
        return self.data==other.data

    # make data elements look like class attributes
    def __getattr__(self,name):
        return self.get_el(name)

    # make data elements look like a dictionary
    def keys(self):
        return self.data.keys()
    def has_key(self,name):
        return self.data.has_key(name)
    def __getitem__(self,name):
        return self.get_el(name)    
    def __repr__(self):
        return str(self.data)
    def __str__(self):
        return str(self.data)

    #
    # PROTECTED
    #

    # validate input against bae template (i.e. the defaults)
    def validate(self,base,path_text):
        for k in self.data.keys():
            if not base.has_key(k):
                # element not in base, report
                raise RuntimeError, "Unknown parameter %s.%s"%(path_text,k)
            else:
                # verify subelements, if any
                defel=base[k]
                if isinstance(defel,xmlParse.OrderedDict):
                    # subdictionary
                    self[k].validate(defel,"%s.%s"%(path_text,k))
                else:
                    # final element
                    defvalue,ktype,txt,subdef=defel

                    if isinstance(defvalue,xmlParse.OrderedDict):
                        # dictionary el elements
                        data_el=self[k]
                        for data_subkey in data_el.keys():
                            data_el[data_subkey].validate(subdef,"%s.%s.%s"%(path_text,k,data_subkey))
                    elif type(defvalue)==type([]):
                        # list of elements
                        if isinstance(self.data[k],xmlParse.OrderedDict):
                            if len(self.data[k].keys())==0:
                                self.data[k]=[]  #XML does not know if an empty list is a dictionary or not.. fix this

                        mylist=self[k]
                        if type(mylist)!=type([]):
                            raise RuntimeError, "Parameter %s.%s not a list: %s %s"%(path_text,k,type(mylist),mylist)
                        for data_el in mylist:
                            data_el.validate(subdef,"%s.*.%s"%(path_text,k))
                    else:
                        # a simple value
                        pass #nothing to be done

    # put default values where there is nothing
    def use_defaults(self,defaults):
        for k in defaults.keys():
            defel=defaults[k]
            if isinstance(defel,xmlParse.OrderedDict):
                # subdictionary
                if not self.data.has_key(k):
                    self.data[k]=xmlParse.OrderedDict() # first create empty, if does not exist

                # then, set defaults on all elements of subdictionary
                self[k].use_defaults(defel)
            else:
                # final element
                defvalue,ktype,txt,subdef=defel

                if isinstance(defvalue,xmlParse.OrderedDict):
                    # dictionary el elements
                    if not self.data.has_key(k):
                        self.data[k]=xmlParse.OrderedDict() # no elements yet, set and empty dictionary
                    else:
                        # need to set defaults on all elements in the dictionary
                        data_el=self[k]
                        for data_subkey in data_el.keys():
                            data_el[data_subkey].use_defaults(subdef)
                elif type(defvalue)==type([]):
                    # list of elements
                    if not self.data.has_key(k):
                        self.data[k]=[] # no elements yet, set and empty list
                    else:
                        # need to set defaults on all elements in the list
                        for data_el in self[k]:
                            data_el.use_defaults(subdef)
                else:
                    # a simple value
                    if not self.data.has_key(k):
                        self.data[k]=copy.deepcopy(defvalue)
                    # else nothing to do, already set

            

    #
    # PRIVATE
    #
    def get_el(self,name):
        el=self.data[name]
        if isinstance(el,xmlParse.OrderedDict):
            return self.__class__(el)
        elif type(el)==type([]):
            outlst=[]
            for k in el:
                if isinstance(k,xmlParse.OrderedDict):
                    outlst.append(self.__class__(k))
                else:
                    outlst.append(k)
            return outlst
        else:
            return el

# abstract class
# children must define
#   get_top_element(self)
#   init_defaults(self)
#   derive(self)
#   get_xml_format(self)
class Params:
    def __init__(self,usage_prefix,src_dir,argv):
        self.usage_prefix=usage_prefix

        # support dir
        self.src_dir=src_dir

        # initialize the defaults
        self.defaults=xmlParse.OrderedDict()
        self.init_defaults()

        try:
            if len(argv)<2:
                raise RuntimeError, "Missing config file"

            if argv[1]=="-help":
                raise RuntimeError,"\nA config file will contain:\n%s\n\nThe config file will be in XML format."%self.get_description("  ")
                
            self.cfg_name=os.path.abspath(argv[1])
            self.load_file(self.cfg_name)

            self.subparams.validate(self.defaults,self.get_top_element())

            # make a copy of the loaded data, so that I can always tell what was derived and what was not
            self.org_data=copy.deepcopy(self.data)

            self.subparams.use_defaults(self.defaults)
            
            # create derived values
            self.derive()
        except RuntimeError, e:
            raise RuntimeError,"Unexpected error occurred loading the configuration file.\n\n%s" % e
        pass

    def derive(self):
        return # by default nothing... children should overwrite this

    def get_xml(self):
        old_default_ignore_nones=xmlFormat.DEFAULT_IGNORE_NONES
        old_default_lists_params=xmlFormat.DEFAULT_LISTS_PARAMS
        old_default_dicts_params=xmlFormat.DEFAULT_DICTS_PARAMS
        xmlFormat.DEFAULT_IGNORE_NONES=True
        # these are used internally, do not need to be ordered
        xml_format=self.get_xml_format()
        xmlFormat.DEFAULT_LISTS_PARAMS=xml_format['lists_params']
        xmlFormat.DEFAULT_DICTS_PARAMS=xml_format['dicts_params']
        # hack needed to make xmlFormat to properly do the formating
        old_DictType=types.DictType
        types.DictType=type(xmlParse.OrderedDict())
        out=xmlFormat.class2string(self.data,self.get_top_element())
        types.DictType=old_DictType
        xmlFormat.DEFAULT_IGNORE_NONES=old_default_ignore_nones
        xmlFormat.DEFAULT_LISTS_PARAMS=old_default_lists_params
        xmlFormat.DEFAULT_DICTS_PARAMS=old_default_dicts_params
        return out

    def get_description(self,indent="",width=80):
        return defdict2string(self.defaults,indent,width)


    #load from a file
    #one element per line
    # -opt val
    def load_file(self,fname):
        if fname=="-":
            fname=sys.stdin
        try:
            self.data=xmlParse.xmlfile2dict(fname,use_ord_dict=True)
        except xml.parsers.expat.ExpatError, e:
            raise RuntimeError, "XML error parsing config file: %s"%e
        except IOError, e:
            raise RuntimeError, "Config file error: %s"%e
        self.subparams=self.get_subparams_class()(self.data)
        return

    def __eq__(self,other):
        if other is None:
            return False
        if not isinstance(other,Params):
            return False
        return self.subparams==other.subparams

    def __getattr__(self,name):
        return self.subparams.__getattr__(name)

    #save into a file
    #The file should be usable for reload
    def save_into_file(self,fname,set_ro=False):
        fd=open(fname,"w")
        try:
            fd.write(self.get_xml())
            fd.write("\n")
        finally:
            fd.close()
        if set_ro:
            os.chmod(fname,os.stat(fname)[0]&0444)
        return
    
    #save into a file (making a backup)
    #The file should be usable for reload
    def save_into_file_wbackup(self,fname,set_ro=False):
        # rewrite config file (write tmp file first)
        tmp_name="%s.tmp"%fname
        try:
            os.unlink(tmp_name)
        except:
            pass # just protect
        self.save_into_file(tmp_name)

        # also save old one with backup name
        backup_name="%s~"%fname
        try:
            os.unlink(backup_name)
        except:
            pass # just protect
        try:
            os.rename(fname,backup_name)
            # make it user writable
            os.chmod(backup_name,(os.stat(backup_name)[0]&0666)|0200)
        except:
            pass # just protect
        
        # finally rename to the proper name
        os.rename(tmp_name,fname)
        if set_ro:
            os.chmod(fname,os.stat(fname)[0]&0444)

    # used internally to define subtype class
    def get_subparams_class(self):
        return SubParams

######################################################
# Ordered dictionary with comment support
class commentedOrderedDict(xmlParse.OrderedDict):
    def __init__(self, dict = None):
        # cannot call directly the parent due to the particular implementation restrictions
        self._keys = []
        xmlParse.UserDict.__init__(self, dict)
        self["comment"]=(None,"string","Humman comment, not used by the code",None)

####################################################################
# INTERNAL, don't use directly
# Use the class definition instead
#
# return attribute value in the proper python format
def extract_attr_val(attr_obj):
    if (not attr_obj.type in ("string","int","expr")):
        raise RuntimeError, "Wrong attribute type '%s', must be either 'int' or 'string'"%attr_obj.type

    if attr_obj.type in ("string","expr"):
        return str(attr_obj.value)
    else:
        return int(attr_obj.value)

######################################################
# Define common defaults
class CommonSubParams(SubParams):
    # return attribute value in the proper python format
    def extract_attr_val(self,attr_obj):
        return extract_attr_val(attr_obj)

class CommonParams(Params):
    # populate self.defaults
    def init_support_defaults(self):
        # attributes are generic, shared between frontend and factory
        self.attr_defaults=commentedOrderedDict()
        self.attr_defaults["value"]=(None,"Value","Value of the attribute (string)",None)
        self.attr_defaults["parameter"]=("True","Bool","Should it be passed as a parameter?",None)
        self.attr_defaults["glidein_publish"]=("False","Bool","Should it be published by the glidein? (Used only if parameter is True.)",None)
        self.attr_defaults["job_publish"]=("False","Bool","Should the glidein publish it to the job? (Used only if parameter is True.)",None)
        self.attr_defaults["type"]=["string","string|int","What kind on data is value.",None]

        # most file attributes are generic, shared between frontend and factory
        self.file_defaults=commentedOrderedDict()
        self.file_defaults["absfname"]=(None,"fname","File name on the local disk.",None)
        self.file_defaults["relfname"]=(None,"fname","Name of the file once it gets to the worker node. (defaults to the last part of absfname)",None)
        self.file_defaults["const"]=("True","Bool","Will the file be constant? If True, the file will be signed. If False, it can be modified at any time and will not be cached.",None)
        self.file_defaults["executable"]=("False",'Bool','Is this an executable that needs to be run in the glidein?',None)
        self.file_defaults["wrapper"]=("False",'Bool','Is this a wrapper script that needs to be sourced in the glidein job wrapper?',None)
        self.file_defaults["untar"]=("False",'Bool','Do I need to untar it? ',None)
        self.file_defaults["period"]=(0,'int','Re-run the executable every "period" seconds if > 0.',None)
        # to add check scripts around jobs: self.file_defaults["job_wrap"]=("no","pre|post|no",'Run the executable before (pre) or after (post) each job.',None)

        untar_defaults=commentedOrderedDict()
        untar_defaults["cond_attr"]=("TRUE","attrname","If not the special value TRUE, the attribute name used at runtime to determine if the file should be untarred or not.",None)
        untar_defaults["dir"]=(None,"dirname","Subdirectory in which to untar. (defaults to relname up to first .)",None)
        untar_defaults["absdir_outattr"]=(None,"attrname",'Attribute to be set to the abs dir name where the tarball was unpacked. Will be defined only if untar effectively done. (Not defined if None)',None)
        self.file_defaults["untar_options"]=untar_defaults

        self.monitor_defaults=commentedOrderedDict()
        self.monitor_defaults["javascriptRRD_dir"]=(os.path.join(self.src_dir,"../../externals/flot"),"base_dir","Location of the javascriptRRD library.",None)
        self.monitor_defaults["flot_dir"]=(os.path.join(self.src_dir,"../../externals/flot"),"base_dir","Location of the flot library.",None)
        self.monitor_defaults["jquery_dir"]=(os.path.join(self.src_dir,"../../externals/jquery"),"base_dir","Location of the jquery library.",None)
        return

    def get_subparams_class(self):
        return CommonSubParams

    # return attribute value in the proper python format
    def extract_attr_val(self,attr_obj):
        return extract_attr_val(attr_obj)

################################################
# Check is a string can be used as a valid name
# Whitelist based

# only allow ascii charactersm, the numbers and a few punctuations
# no spaces, not special characters or other punctuation
VALID_NAME_CHARS=string.ascii_letters+string.digits+'._-'

def is_valid_name(name):
    # empty name is not valid
    if name is None:
        return False
    if name=="":
        return False
    
    for c in name:
        if not (c in VALID_NAME_CHARS):
            return False
    return True


############################################################
#
# P R I V A T E - Do not use
# 
############################################################

#######################################################
# Wrap a text string to a fixed length
def col_wrap(text,width,indent):
    short_text,next_char=shorten_text(text,width)
    if len(short_text)!=len(text): # was shortened
        #print short_text
        org_short_text=short_text[0:]
        # make sure you are not breaking words.
        while not (next_char in ('',' ','\t')):
            if len(short_text)==0:
                # could not break on word boundary, leave as is
                short_text=org_short_text
                break
            next_char=short_text[-1]
            short_text=short_text[:-1]
        
        if len(short_text)<=len(indent):
            # too short, just split as it was
            short_text=org_short_text

        # calc next lines
        subtext=col_wrap(indent+text[len(short_text):].lstrip(' \t'),width,indent)
        # glue
        return short_text+"\n"+subtext
    else:
        return text

# shorten text, make sure you properly account tabs
# return (shorten text,next char)
def shorten_text(text,width):
    count=0
    idx=0
    for c in text:
        if count>=width:
            return (text[:idx],c)
        if c=='\t':
            count=((count+8)/8)*8 #round to neares mult of 8
            if count>width:
                return (text[:idx],c)
            idx=idx+1
        else:
            count=count+1
            idx=idx+1
        
    return (text[:idx],'')

##################################################
# convert defualts to a string
def defdict2string(defaults,indent,width=80):
    outstrarr=[]

    keys=defaults.keys()
    keys.sort()

    final_keys=[]
    # put simple elements first
    for k in keys:
        el=defaults[k]
        if not isinstance(el,xmlParse.OrderedDict):
            defvalue,ktype,txt,subdef=el
            if subdef is None:
                final_keys.append(k)
    # put simple elements first
    for k in keys:
        el=defaults[k]
        if isinstance(el,xmlParse.OrderedDict):
            final_keys.append(k)
        else:
            defvalue,ktype,txt,subdef=el
            if subdef is not None:
                final_keys.append(k)

    for k in final_keys:
        el=defaults[k]
        if isinstance(el,xmlParse.OrderedDict):  #sub-dictionary
            outstrarr.append("%s%s:"%(indent,k)+"\n"+defdict2string(el,indent+"\t",width))
        else:
            #print el
            defvalue,ktype,txt,subdef=el
            wrap_indent=indent+string.ljust("",len("%s(%s) - "%(k,ktype)))
            if subdef is not None:
                if isinstance(defvalue,xmlParse.OrderedDict):
                    dict_subdef=copy.deepcopy(subdef)
                    dict_subdef["name"]=(None,"name","Name",None)
                    outstrarr.append(col_wrap("%s%s(%s) - %s:"%(indent,k,ktype,txt),width,wrap_indent)+"\n"+defdict2string(dict_subdef,indent+"\t",width))
                else:
                    outstrarr.append(col_wrap("%s%s(%s) - %s:"%(indent,k,ktype,txt),width,wrap_indent)+"\n"+defdict2string(subdef,indent+"\t",width))
            else:
                outstrarr.append(col_wrap("%s%s(%s) - %s [%s]"%(indent,k,ktype,txt,defvalue),width,wrap_indent))
    return string.join(outstrarr,"\n")
    
