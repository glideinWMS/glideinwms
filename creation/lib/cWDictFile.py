from __future__ import print_function
#
# Project:
#   glideinWMS
#
# File Version:
#
# Description:
#   Classes needed to handle dictionary files
#   And other support functions
#

import os, os.path  # string
import shutil
import copy
import socket
import cStringIO
from glideinwms.lib import hashCrypto


########################################
#
# File dictionary classes
#
########################################

class DictFile:
    """Dictionaries serialized in files, one line per item

    Comments start w/ '#' at the beginning of the line
    Empty lines are nor tolerated by the parser in the glidein (bash)
    """
    def __init__(self,dir,fname,sort_keys=False,order_matters=False,
                 fname_idx=None):      # if none, use fname
        self.dir=dir
        self.fname=fname
        if fname_idx is None:
            fname_idx=fname
        self.fname_idx=fname_idx

        if sort_keys and order_matters:
            raise RuntimeError("Cannot preserve the order and sort the keys")
        self.sort_keys=sort_keys
        self.order_matters=order_matters

        self.is_readonly=False
        self.changed=True

        self.keys=[]
        self.vals={}

    def has_key(self, key):
        return key in self.keys

    def __contains__(self, key):
        return key in self.keys

    def __getitem__(self, key):
        return self.vals[key]

    def get_fname(self):
        return self.fname

    def get_dir(self):
        return self.dir

    def get_filepath(self):
        return os.path.join(self.dir, self.fname)

    def erase(self):
        self.keys=[]
        self.vals={}
        self.changed=True

    def set_readonly(self,readonly=True):
        self.is_readonly=readonly

    def add(self, key, val, allow_overwrite=False):
        if key in self.keys:
            if self.vals[key] == val:
                return  # already exists, nothing to do

        if self.is_readonly:
            raise RuntimeError("Trying to modify a readonly object (%s, %s)!" % (key, val))

        if key in self.keys:
            if not allow_overwrite:
                raise RuntimeError("Key '%s' already exists" % key)
            elif not self.is_compatible(self.vals[key], val):
                raise RuntimeError("Key '%s': Value %s not compatible with old value %s" % (key, val, self.vals[key]))
            # Already exists, covered above
            # if self.vals[key]==val:
            #     return # nothing to do
        else:
            self.keys.append(key)
        self.vals[key] = val
        self.changed = True

    def remove(self,key,fail_if_missing=False):
        if not (key in self.keys):
            if not fail_if_missing:
                raise RuntimeError("Key '%s' does not exist"%key)
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
            return  # no change -> don't save

        if dir is None:
            dir=self.dir
        if fname is None:
            fname=self.fname
        if sort_keys is None:
            sort_keys=self.sort_keys

        if not os.path.exists(dir):
            os.makedirs(dir)
        filepath=os.path.join(dir, fname)
        try:
            fd=open(filepath, "w")
        except IOError as e:
            raise RuntimeError("Error creating %s: %s"%(filepath, e))
        try:
            self.save_into_fd(fd, sort_keys, set_readonly, reset_changed, want_comments)
        finally:
            fd.close()

        # ensure that the file permissions are 644
        # This is to minimize a security risk where we load python code from
        # a config file and exec it.  We want to ensure that the only user that
        # can write to the config file is the factory or frontend user.  If
        # either of those user accounts is compromised, then there are much
        # bigger problems than a simple exec security hole.
        os.chmod(filepath, 0o644)

        return

    def save_into_fd(self, fd,
                     sort_keys=None,set_readonly=True,reset_changed=True,
                     want_comments=True):
        if sort_keys is None:
            sort_keys=self.sort_keys

        header=self.file_header(want_comments)
        if header is not None:
            fd.write("%s\n"%header)
        if sort_keys:
            keys=sorted(self.keys[0:])  # makes a copy
        else:
            keys=self.keys
        for k in keys:
            fd.write("%s\n"%self.format_val(k, want_comments))
        footer=self.file_footer(want_comments)
        if footer is not None:
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
        self.save_into_fd(fd, sort_keys, set_readonly, reset_changed, want_comments)
        fd.seek(0)
        data=fd.read()
        fd.close()
        return data

    def load(self, dir=None, fname=None,
             change_self=True,        # if dir and/or fname are not specified, use the defaults specified in __init__, if they are, and change_self is True, change the self.
             erase_first=True,        # if True, delete old content first
             set_not_changed=True):   # if True, set self.changed to False
        if dir is None:
            dir = self.dir
        if fname is None:
            fname = self.fname

        filepath = os.path.join(dir, fname)
        try:
            fd = open(filepath, "r")
        except IOError as e:
            print("Error opening %s: %s" % (filepath, e))
            print("Assuming blank, and re-creating...")
            return
        try:
            try:
                self.load_from_fd(fd, erase_first, set_not_changed)
            except RuntimeError as e:
                raise RuntimeError("File %s: %s" % (filepath, str(e)))
        finally:
            fd.close()

        if change_self:
            self.dir = dir
            self.fname = fname

        return

    def load_from_fd(self, fd,
                     erase_first=True,        # if True, delete old content first
                     set_not_changed=True):   # if True, set self.changed to False
        if erase_first:
            self.erase()

        lines = fd.readlines()

        idx = 0
        for line in lines:
            idx += 1
            if line[-1] == '\n':
                # strip newline
                line = line[:-1]
            try:
                self.parse_val(line)
            except RuntimeError as e:
                raise RuntimeError("Line %i: %s" % (idx, str(e)))

        if set_not_changed:
            self.changed = False  # the memory copy is now same as the one on disk
        return

    def load_from_str(self, data,
                      erase_first=True,        # if True, delete old content first
                      set_not_changed=True):   # if True, set self.changed to False
        fd = cStringIO.StringIO()
        fd.write(data)
        fd.seek(0)
        try:
            self.load_from_fd(fd, erase_first, set_not_changed)
        except RuntimeError as e:
            raise RuntimeError("Memory buffer: %s" % (str(e)))
        fd.close()
        return

    def is_equal(self, other,         # other must be of the same class
                 compare_dir=False, compare_fname=False,
                 compare_keys=None):  # if None, use order_matters
        if compare_dir and (self.dir != other.dir):
            return False
        if compare_fname and (self.fname != other.fname):
            return False
        if compare_keys is None:
            compare_keys = self.order_matters
        if compare_keys and (self.keys != other.keys):
            return False
        res = (self.save_into_str(sort_keys=None, set_readonly=False, reset_changed=False, want_comments=False) ==
               other.save_into_str(sort_keys=None, set_readonly=False, reset_changed=False, want_comments=False))
        return res

    # PRIVATE
    def is_compatible(self, old_val, new_val):
        return True  # everything is compatible

    def file_header(self, want_comments):
        if want_comments:
            return "# File: %s\n#" % self.fname
        else:
            return None

    def file_footer(self, want_comments):
        return None  # no footer

    def format_val(self, key, want_comments):
        return "%s \t%s" % (key, self.vals[key])

    def parse_val(self, line):
        if not line or line[0] == '#':
            return  # ignore comments
        arr = line.split(None, 1)
        if len(arr[0]) == 0:
            return  # empty key

        key = arr[0]
        if len(arr) == 1:
            val = ''
        else:
            val = arr[1]
        return self.add(key, val)


class DictFileTwoKeys(DictFile):
    """DictFile double keyed: both key and val are keys
    """
    def __init__(self, dir, fname, sort_keys=False, order_matters=False,
                 fname_idx=None):
        """constructor

        :param dir: directory
        :param fname: file name
        :param sort_keys: should the keys be sorted? (Default: False)
        :param order_matters: order is important (Default: False)
        :param fname_idx: fname ID, use fname if None (Default: None)
        :return:
        """
        DictFile.__init__(self, dir, fname, sort_keys, order_matters, fname_idx)
        self.keys2 = []
        self.vals2 = {}

    def has_key2(self, key):
        """Check reverse dictionary keys

        :param key: reverse key (value)
        :return: reverse key in value list
        """
        return key in self.keys2

    def get_val2(self, key):
        """Retrieve value associated with reverse key

        :param key: reverse key (value)
        :return: value associated with reverse key (key)
        """
        return self.vals2[key]

    def erase(self):
        DictFile.erase(self)
        self.keys2 = []
        self.vals2 = {}

    def add(self, key, val, allow_overwrite=False):
        if key in self.keys:
            if self.vals[key] == val:
                return  # already exists, nothing to do

        if self.is_readonly:
            raise RuntimeError("Trying to modify a readonly object (%s, %s)!" % (key, val))

        if key in self.keys:
            old_val = self.vals[key]
            if not allow_overwrite:
                raise RuntimeError("Key '%s' already exists" % key)
            elif not self.is_compatible(old_val, val):
                raise RuntimeError("Key '%s': Value %s not compatible with old value %s" % (key, val, old_val))
            # if old_val == val:   # no need to check again, would have hit the check above
            #    return  # nothing to be changed
            # the second key (value) changed, need to delete the old one
            self.keys2.remove(old_val)
            del self.vals2[old_val]
        else:
            self.keys.append(key)
        self.vals[key] = val

        if val in self.keys2:
            old_key = self.vals2[val]
            if not allow_overwrite:
                raise RuntimeError("Value '%s' already exists" % val)
            elif not self.is_compatible2(old_key, key):
                raise RuntimeError("Value '%s': Key %s not compatible with old key %s" % (val, key, old_key))
            # if old_key==key: # no need to check again, would have hit the check above
            #    return # nothing to be changed
            # the first key changed, need to delete the old one
            self.keys.remove(old_key)
            del self.vals[old_key]
        else:
            self.keys2.append(val)
        self.vals2[val] = key
        self.changed = True

    def remove(self, key, fail_if_missing=False):
        if key not in self.keys:
            if fail_if_missing:
                raise RuntimeError("Key '%s' does not exist" % key)
            else:
                return  # nothing to do

        val = self.vals[key]

        self.keys.remove(key)
        del self.vals[key]
        self.keys2.remove(val)
        del self.vals2[val]
        self.changed = True

    def is_equal(self, other,
                 compare_dir=False, compare_fname=False,
                 compare_keys=None):
        """Compare two DictFileDoubleKey objects (and optionally their file)

        :param other: other dictionary, object of the same class
        :param compare_dir: if True compare also the file directory (Default: False)
        :param compare_fname: if True compare also the file name (Default: False)
        :param compare_keys: if True compare also the keys lists. If None, use order_matters (Default: False)
        :return:
        """
        if compare_dir and (self.dir != other.dir):
            return False
        if compare_fname and (self.fname != other.fname):
            return False
        if compare_keys is None:
            compare_keys = self.order_matters
        if compare_keys and ((self.keys != other.keys) or (self.keys2 != other.keys2)):
            return False
        res = (self.save_into_str(sort_keys=None, set_readonly=False, reset_changed=False, want_comments=False) ==
               other.save_into_str(sort_keys=None, set_readonly=False, reset_changed=False, want_comments=False))
        return res

    # PRIVATE
    def is_compatible2(self, old_val2, new_val2):
        return True  # everything is compatible


# descriptions
class DescriptionDictFile(DictFileTwoKeys):
    def format_val(self, key, want_comments):
        return "%s \t%s" % (self.vals[key], key)

    def parse_val(self, line):
        if not line or line[0] == '#':
            return  # ignore comments
        arr = line.split(None, 1)
        if len(arr) == 0:
            return  # empty line
        if len(arr) != 2:
            raise RuntimeError("Not a valid description line: '%s'" % line)

        return self.add(arr[1], arr[0])


# gridmap file
class GridMapDict(DictFileTwoKeys):
    def file_header(self, want_comments):
        return None

    def format_val(self, key, want_comments):
        return '"%s" %s' % (key, self.vals[key])

    def parse_val(self, line):
        if not line or line[0] == '#':
            return  # ignore comments
        arr=line.split()
        if len(arr) == 0:
            return  # empty line
        if len(arr[0]) == 0:
            return  # empty key

        if line[0:1] != '"':
            raise RuntimeError('Not a valid gridmap line; not starting with ": %s' % line)

        user = arr[-1]

        if line[-len(user)-2:-len(user)-1] != '"':
            raise RuntimeError('Not a valid gridmap line; DN not ending with ": %s' % line)

        dn = line[1:-len(user)-2]
        return self.add(dn, user)


##################################
# signatures
class SHA1DictFile(DictFile):
    def add_from_file(self,filepath,allow_overwrite=False,
                      key=None): # if key==None, use basefname
        sha1=hashCrypto.extract_sha1(filepath)
        if key is None:
            key=os.path.basename(filepath)
        self.add(key, sha1, allow_overwrite)

    def format_val(self, key, want_comments):
        return "%s  %s"%(self.vals[key], key)

    def parse_val(self, line):
        if not line or line[0]=='#':
            return # ignore comments
        arr=line.split(None, 1)
        if len(arr)!=2:
            raise RuntimeError("Not a valid SHA1 line: '%s'"%line)

        return self.add(arr[1], arr[0])


# summary signatures
# values are (sha1,fname2)
class SummarySHA1DictFile(DictFile):
    def add(self,key,val,allow_overwrite=False):
        if not (type(val) in (type(()), type([]))):
            raise RuntimeError("Values '%s' not a list or tuple"%val)
        if len(val)!=2:
            raise RuntimeError("Values '%s' not (sha1,fname)"%val)
        return DictFile.add(self, key, val, allow_overwrite)

    def add_from_file(self,filepath,
                      fname2=None, # if fname2==None, use basefname
                      allow_overwrite=False,
                      key=None):   # if key==None, use basefname
        sha1=hashCrypto.extract_sha1(filepath)
        if key is None:
            key=os.path.basename(filepath)
        if fname2 is None:
            fname2=os.path.basename(filepath)
        DictFile.add(self, key, (sha1, fname2), allow_overwrite)

    def format_val(self, key, want_comments):
        return "%s  %s  %s"%(self.vals[key][0], self.vals[key][1], key)

    def parse_val(self, line):
        if not line or line[0]=='#':
            return # ignore comments
        arr=line.split(None, 2)
        if len(arr)!=3:
            raise RuntimeError("Not a valid summary signature line (expected 4, found %i elements): '%s'"%(len(arr), line))

        key=arr[2]
        return self.add(key, (arr[0], arr[1]))


class SimpleFileDictFile(DictFile):
    """Dictionary of files that holds also the content of the file as the last element in the values. Value is a tuple.

    The dictionary is serialized using a file (dictionary file), one item per line.
    Each item is a file, identified by a file name, with an optional attribute (value) and the file content.
    File names are key. All files are in the same directory of the dictionary (self.dir).
    The values are a tuple and the last item is the file content.
    Only the file name and the first element of the value are saved in the dictionary file (serialized dictionary).
    SimpleFileDictFile is used for file lists.
    """
    def get_immutable_files(self):
        return self.keys  # keys are files, and all are immutable in this implementation

    def get_file_fname(self, key):
        return key

    def add(self, key, val, allow_overwrite=False):
        """Add an entry to the dictionary, e.g. a file to the list

        :param key: file name (dictionary key)
        :param val: parameters (not the file content), usually file attributes
        :param allow_overwrite: (Default: False)
        :return:
        """
        return self.add_from_file(key, val, os.path.join(self.dir, self.get_file_fname(key)), allow_overwrite)

    def add_from_str(self, key, val, data, allow_overwrite=False):
        """Add an entry to the dictionary, parameters and content are both available

        :param key: file name (key)
        :param val: parameters (not the file content), usually file attributes
        :param data: string with the file content added to the dictionary
        :param allow_overwrite:
        :return:
        """
        # make it generic for use by children
        if not (type(val) in (type(()), type([]))):
            DictFile.add(self, key, (val, data), allow_overwrite)
        else:
            DictFile.add(self, key, tuple(val)+(data,), allow_overwrite)

    def add_from_fd(self, key, val, fd, allow_overwrite=False):
        """Add an entry to the dictionary using a file object - has a read() method that provides the content

        :param key: file name (key)
        :param val: parameters (not the file content), usually file attributes
        :param fd: file object - has a read() method
        :param allow_overwrite:
        :return:
        """
        data = fd.read()
        self.add_from_str(key, val, data, allow_overwrite)

    def add_from_file(self, key, val, filepath, allow_overwrite=False):
        """add data from a file

        :param key: file name (key)
        :param val: parameters (not the file content), usually file attributes
        :param filepath: full path of the file (
        :param allow_overwrite:
        :return:
        """
        try:
            with open(filepath, "r") as fd:
                self.add_from_fd(key, val, fd, allow_overwrite)
        except IOError as e:
            raise RuntimeError("Could not open file %s" % filepath)

    def format_val(self, key, want_comments):
        """Print lines: only the file name (key) the first item of the value tuple if not None

        :param key: file name (dictionary key)
        :param want_comments:
        :return:
        """
        if self.vals[key][0] is not None:
            return "%s \t%s" % (key, self.vals[key][0])
        else:
            return key

    def parse_val(self, line):
        """Parse line and add value and content to the dictionary

        Skip comments (start with #) or empty lines and do nothing, otherwise add to the dictionary:
        First item is the file name (key), the rest are the parameter, data is read form the file (file name)
        :param line: line to be parsed
        :return: None
        """
        if not line or line[0] == '#':
            return  # ignore comments
        arr = line.split(None, 1)
        if len(arr[0]) == 0:
            return  # empty key - this can never happen

        key = arr[0]
        if len(arr) == 1:
            val = None
        else:
            val = arr[1]
        return self.add(key, val)

    def save_files(self, allow_overwrite=False):
        for key in self.keys:
            fname = self.get_file_fname(key)
            if not fname:
                raise RuntimeError("File name not defined for key %s" % key)
            fdata = self.vals[key][-1]
            filepath = os.path.join(self.dir, fname)
            if (not allow_overwrite) and os.path.exists(filepath):
                raise RuntimeError("File %s already exists" % filepath)
            try:
                with open(filepath, "w") as fd:
                    try:
                        fd.write(fdata)
                    except IOError as e:
                        raise RuntimeError("Error writing into file %s" % filepath)
            except IOError as e:
                raise RuntimeError("Could not create file %s" % filepath)


class FileDictFile(SimpleFileDictFile):
    """Dictionary file for files (file list). Used for list of transferred files.

    It is using a dictionary (key, value) from DictFile, serialized to file.
    The key is the file ID
    The value (line) on file has DATA_LENGTH (7) components: the key and the first DATA_LENGTH-1 attributes below.
    The value in memory has DATA_LENGTH components (real_fname,cache/exec,period,prefix,cond_download,config_out, data),
    the key is used as key for the dictionary and the data (file content) is added reading the file.
    Here the attributes stored as tuple in the dictionary value:
    1. real_fname, i.e file name
    2. cache/exec/... keyword identifying the file type: regular, nocache, exec, untar
    3. period period in seconds at which an executable is re-invoked (only for periodic executables, 0 otherwise)
    4. prefix startd_cron variables prefix (default is GLIDEIN_PS_)
    5. cond_download has a special value of TRUE
    6. config_out has a special value of FALSE
    7. data - String containing the data extracted from the file (real_fname) (not in the serialized dictionary)
    For placeholders, the real_name is empty (and the tuple starts w/ an empty string). Placeholders cannot be
     serialized (saved into file). Empty strings would cause error when parsed back.
    """
    DATA_LENGTH = 7  # Length of value (attributes + data)
    PLACEHOLDER_VALUE = ("", "", 0, "", "", "", "")  # The tuple should be DATA_LENGTH long and have the correct values

    def add_placeholder(self, key, allow_overwrite=True):
        # using DictFile, no file content (FileDictFile or SimpleFileDictFile)
        DictFile.add(self, key, self.PLACEHOLDER_VALUE, allow_overwrite)

    def is_placeholder(self, key):
        return self[key][0] == ""  # empty real_fname can only be a placeholder

    @staticmethod
    def make_val_tuple(file_name, file_type, period=0, prefix='GLIDEIN_PS_', cond_download='TRUE', config_out='FALSE'):
        """Make a tuple with the DATA_LENGTH-1 attributes in the correct order using the defaults

        :param file_name: name of the file (aka real_fname)
        :param file_type: type of the file (regular, nocache, exec, untar)
        :param period: period for periodic executables (ignored otherwise, default: 0)
        :param prefix: prefix for periodic executables (ignored otherwise, default: GLIDEIN_PS_)
        :param cond_download: conditional download (default: 'TRUE')
        :param config_out: config out (default: 'FALSE')
        :return: tuple with the DATA_LENGTH-1 attributes
        See class definition for more information about the attributes
        """
        # TODO: should it do some value checking? valid constant, int, ...
        return file_name, file_type, period, prefix, cond_download, config_out  # python constructs the tuple

    @staticmethod
    def val_to_file_name(val):
        return val[0]

    def get_file_fname(self, key):
        return self.val_to_file_name(self.vals[key])

    def add_from_str(self, key, val,
                     data,
                     allow_overwrite=False,
                     allow_overwrite_placeholder=True):

        if key in self and allow_overwrite_placeholder:
            if self.is_placeholder(key):
                # since the other functions know nothing about placeholders, need to force overwrite
                allow_overwrite = True
        return SimpleFileDictFile.add_from_str(self, key, val, data, allow_overwrite)

    def add(self, key,
            val,     # will if len(val)==5, use the last one as data (for placeholders), else load from val[0]
            allow_overwrite=False,
            allow_overwrite_placeholder=True):
        """Add a file to the list
        invokes add_from_str if the content is provided (6th component of val), add_from_file otherwise
        :param key: file ID
        :param val: lists of 6 or 7 components (see class definition)
        :param allow_overwrite: if True the existing files can be replaced (default: False)
        :param allow_overwrite_placeholder: if True, placeholder files can be replaced even if allow_overwrite
            is False (default: True)
        :return:
        """
        if not (type(val) in (type(()), type([]))):
            raise RuntimeError("Values '%s' not a list or tuple" % val)

        if key in self and allow_overwrite_placeholder:
            if self.is_placeholder(key):
                # since the other functions from base class know nothing about placeholders, need to force overwrite
                allow_overwrite = True

        # This will help identify calls not migrated to the new format
        # TODO: check parameters!!
        try:
            int(val[2])  # to check if is integer. Period must be int or convertible to int
        except (ValueError, IndexError):
            raise RuntimeError("Values '%s' not (real_fname,cache/exec,period,prefix,cond_download,config_out)" % val)

        if len(val) == self.DATA_LENGTH:
            # Alt: return self.add_from_str(key, val[:self.DATA_LENGTH-1], val[self.DATA_LENGTH-1], allow_overwrite)
            return DictFile.add(self, key, tuple(val), allow_overwrite)
        elif len(val) == self.DATA_LENGTH-1:
            # Added a safety check that the last element is an attribute and not the value
            # Maybe check also string length or possible values?
            if '\n' in val[-1]:
                raise RuntimeError("Values '%s' not (real_fname,cache/exec,period,prefix,cond_download,config_out)" % val)
            return self.add_from_file(key, val, os.path.join(self.dir, self.val_to_file_name(val)), allow_overwrite)
        else:
            raise RuntimeError("Values '%s' not (real_fname,cache/exec,period,prefix,cond_download,config_out)" % val)

    def format_val(self, key, want_comments):
        return "%s \t%s \t%s \t%s \t%s \t%s \t%s" % (key, self.vals[key][0], self.vals[key][1], self.vals[key][2],
                                                     self.vals[key][3], self.vals[key][4], self.vals[key][5])

    def file_header(self, want_comments):
        if want_comments:
            return (DictFile.file_header(self, want_comments) + "\n" +
                    ("# %s \t%s \t%s \t%s \t%s \t%s \t%s\n" %
                     ('Outfile', 'InFile        ', 'Cache/exec', 'Period', 'Prefix', 'Condition', 'ConfigOut')) +
                    ("#"*89))
        else:
            return None

    def parse_val(self, line):
        """Parse a line of serialized FileDictFile files and add it to the dictionary

        Each line is a tab separated tuple w/ the key and the attributes describing the entry (see class description )
        :param line: string with the line content
        :return: tuple with DATA_LENGTH-1 values
        """
        if not line or line[0] == '#':
            return  # ignore empty lines and comments
        arr = line.split(None, self.DATA_LENGTH-1)  # split already eliminates multiple spaces (no need for strip)
        if len(arr) == 0:
            return  # empty line (only separators)
        if len(arr[0]) == 0:
            return  # empty key

        if len(arr) != self.DATA_LENGTH:
            # compatibility w/ old formats
            # 3.2.13 (no prefix): key, fname, type, period, cond_download, config_out
            # 3.2.10 (no period, prefix): key, fname, type, cond_download, config_out
            # TODO: remove in 3.3 or after a few version (will break upgrade)
            if len(arr) == self.DATA_LENGTH-1:
                # For upgrade from 3.2.13 to 3.2.11
                return self.add(arr[0], [arr[1], arr[2], arr[3], "GLIDEIN_PS_", arr[4], arr[5]])
            elif len(arr) == self.DATA_LENGTH-2:
                # For upgrade from 3.2.10 or earlier
                return self.add(arr[0], [arr[1], arr[2], 0, "GLIDEIN_PS_", arr[3], arr[4]])
            raise RuntimeError("Not a valid file line (expected %i, found %i elements): '%s'" %
                               (self.DATA_LENGTH, len(arr), line))

        return self.add(arr[0], arr[1:])

    def get_immutable_files(self):
        mkeys = []
        for k in self.keys:
            val = self.vals[k][1]
            if val != "nocache":
                mkeys.append(self.vals[k][0])  # file name is not the key, but the first entry

        return mkeys

    def reuse(self, other,
              compare_dir=False, compare_fname=False,
              compare_files_fname=False):
        """Reuse the entry value (and file) if an item in the "other" dictionary shares the same attributes and content

        :param other: other dictionary
        :param compare_dir: reuse only if the serialized dictionary is in the same directory (Default: False)
        :param compare_fname: reuse only if the serialized dictionary has the same name (Default: False)
        :param compare_files_fname: reuse only if the item file name is the same (Default: False)
        :return: None
        """
        if compare_dir and (self.dir != other.dir):
            return  # nothing to do, different dirs
        if compare_fname and (self.fname != other.fname):
            return  # nothing to do, different fnames

        for k in self.keys:
            if k in other.keys:
                # the other has the same key, check if they are the same
                if compare_files_fname:
                    # The value is already the same, why deepcopy?
                    # The item are the same but not the nested ones?
                    # could return - no need for deepcopy
                    is_equal = (self.vals[k] == other.vals[k])
                else:  # ignore file name (first element)
                    is_equal = (self.vals[k][1:] == other.vals[k][1:])

                if is_equal:
                    self.vals[k] = copy.deepcopy(other.vals[k])
                # else they are different and there is nothing to be done

        return


# will convert values into python format before writing them out
#   given that it does not call any parent methods, implement an interface first
class ReprDictFileInterface:
    def format_val(self, key, want_comments):
        return "%s \t%s"%(key, repr(self.vals[key]))

    def parse_val(self, line):
        if not line or line[0]=='#':
            return # ignore comments
        arr=line.split(None, 1)
        if len(arr[0])==0:
            return # empty key

        key=arr[0]
        if len(arr)==1:
            val=''
        else:
            val=arr[1]
        return self.add(key, eval(val))

    # fake init to make pylint happy
    def interface_fake_init(self):
        self.vals={}
        self.add=lambda x, y:True
        raise NotImplementedError("This function must never be called")


#   this one actually has the full semantics
class ReprDictFile(ReprDictFileInterface, DictFile):
    pass


# will hold only strings
class StrDictFile(DictFile):
    def add(self, key, val, allow_overwrite=False):
        DictFile.add(self, key, str(val), allow_overwrite)


# will save only strings
# while populating, it may hold other types
# not guaranteed to have typed values on (re-)load
class StrWWorkTypeDictFile(StrDictFile):
    def __init__(self, dir, fname, sort_keys=False, order_matters=False,
                 fname_idx=None):      # if none, use fname
        StrDictFile.__init__(self, dir, fname, sort_keys, order_matters, fname_idx)
        self.typed_vals = {}

    def erase(self):
        StrDictFile.erase(self)
        self.typed_vals = {}

    def remove(self, key, fail_if_missing=False):
        StrDictFile.remove(self, key, fail_if_missing)
        if key in self.typed_vals:
            del self.typed_vals[key]

    def get_typed_val(self, key):
        return self.typed_vals[key]

    def add(self, key, val, allow_overwrite=False):
        StrDictFile.add(self, key, val, allow_overwrite)
        self.typed_vals[key] = val


# values are (Type,Default,CondorName,Required,Export,UserName)
class VarsDictFile(DictFile):
    def is_compatible(self, old_val, new_val):
        return ((old_val[0]==new_val[0]) and (old_val[4]==new_val[4]))# at least the type and the export must be preserved

    def file_header(self, want_comments):
        if want_comments:
            return (DictFile.file_header(self, want_comments)+"\n"+
                    "# VarName               Type    Default         CondorName                     Req.     Export  UserName           \n"+
                    "#                       S=Quote - = No Default  + = VarName                             Condor   - = Do not export \n"+
                    "#                                                                                                + = Use VarName   \n"+
                    "#                                                                                                @ = Use CondorName\n"
                    "###################################################################################################################")
        else:
            return None

    def add(self, key, val, allow_overwrite=0):
        if not (type(val) in (type(()), type([]))):
            raise RuntimeError("Values '%s' not a list or tuple" % val)
        if len(val) != 6:
            raise RuntimeError("Values '%s' not (Type,Default,CondorName,Required,Export,UserName)" % str(val))
        if not (val[0] in ('C', 'S', 'I')):
            raise RuntimeError("Invalid var type '%s', should be either C, S or I in val: %s" % (val[1], str(val)))
        for i, t in ((3, "Required"), (4, "Export")):
            if not (val[i] in ('Y', 'N')):
                raise RuntimeError("Invalid var %s '%s', should be either Y or N in val: %s" % (t, val[i], str(val)))

        return DictFile.add(self, key, val, allow_overwrite)

    def add_extended(self,key,
                     type,
                     val_default,  # None or False==No default (i.e. -)
                     condor_name,  # if None or false, Varname (i.e. +)
                     required,
                     export_condor,
                     user_name,    # If None or false, do not export (i.e. -)
                                   # if True, set to VarName (i.e. +)
                     allow_overwrite=0):
        if type == "string":
            type_str = 'S'
        elif type == "expr":
            type_str = 'C'
        else:
            type_str = 'I'

        if (val_default is None) or (val_default == False):
            val_default = '-'

        if (condor_name is None) or (condor_name == False):
            condor_name = "+"

        if required:
            req_str = 'Y'
        else:
            req_str = 'N'

        if export_condor:
            export_condor_str = 'Y'
        else:
            export_condor_str = 'N'

        if (user_name is None) or (user_name == False):
            user_name = '-'
        elif user_name == True:
            user_name = '+'

        self.add(key, (type_str, val_default, condor_name, req_str, export_condor_str, user_name), allow_overwrite)

    def format_val(self, key, want_comments):
        return "%s \t%s \t%s \t\t%s \t%s \t%s \t%s" % (key, self.vals[key][0], self.vals[key][1], self.vals[key][2],
                                                       self.vals[key][3], self.vals[key][4], self.vals[key][5])

    def parse_val(self, line):
        if not line or line[0] == '#':
            return  # ignore comments
        arr=line.split(None, 6)
        if len(arr) == 0:
            return  # empty line
        if len(arr) != 7:
            raise RuntimeError("Not a valid var line (expected 7, found %i elements): '%s'" % (len(arr), line))

        key = arr[0]
        return self.add(key, arr[1:])


# This class holds the content of the whole file in the single val
# with key 'content'
# Any other key is invalid
class SimpleFile(DictFile):
    def add(self, key, val, allow_overwrite=False):
        if key != 'content':
            raise RuntimeError("Invalid key '%s'!='content'" % key)
        return DictFile.add(self, key, val, allow_overwrite)

    def file_header(self, want_comments):
        return None  # no comment, anytime

    def format_val(self, key, want_comments):
        if key == 'content':
            return self.vals[key]
        else:
            raise RuntimeError("Invalid key '%s'!='content'"%key)

    def load_from_fd(self, fd,
                     erase_first=True,        # if True, delete old content first
                     set_not_changed=True):   # if True, set self.changed to False
        if erase_first:
            self.erase()

        data = fd.read()

        # remove final newline, since it will be added at save time
        if data[-1:] == '\n':
            data = data[:-1]

        self.add('content', data)

        if set_not_changed:
            self.changed = False  # the memory copy is now same as the one on disk
        return

    def parse_val(self, line):
        raise RuntimeError("Not defined in SimpleFile")


# This class holds the content of the whole file in the single val
# with key 'content'
# Any other key is invalid
# When saving, it will make it executable
class ExeFile(SimpleFile):
    def save(self, dir=None, fname=None,        # if dir and/or fname are not specified, use the defaults specified in __init__
             sort_keys=None,set_readonly=True,reset_changed=True,
             save_only_if_changed=True,
             want_comments=True):
        if save_only_if_changed and (not self.changed):
            return # no change -> don't save

        if dir is None:
            dir=self.dir
        if fname is None:
            fname=self.fname
        if sort_keys is None:
            sort_keys=self.sort_keys


        filepath=os.path.join(dir, fname)
        try:
            fd=open(filepath, "w")
        except IOError as e:
            raise RuntimeError("Error creating %s: %s"%(filepath, e))
        try:
            self.save_into_fd(fd, sort_keys, set_readonly, reset_changed, want_comments)
        finally:
            fd.close()
        os.chmod(filepath, 0o755)

        return

########################################################################################################################

# abstract class for a directory creation
class dirSupport:
    # returns a bool: True if the dir was created, false else
    def create_dir(self,fail_if_exists=True):
        raise RuntimeError("Undefined")

    def delete_dir(self):
        raise RuntimeError("Undefined")


class simpleDirSupport(dirSupport):
    def __init__(self, dir, dir_name):
        self.dir=dir
        self.dir_name=dir_name

    def create_dir(self,fail_if_exists=True):
        if os.path.isdir(self.dir):
            if fail_if_exists:
                raise RuntimeError("Cannot create %s dir %s, already exists."%(self.dir_name, self.dir))
            else:
                return False # already exists, nothing to do

        try:
            os.mkdir(self.dir)
        except OSError as e:
            raise RuntimeError("Failed to create %s dir: %s"%(self.dir_name, e))
        return True

    def delete_dir(self):
        shutil.rmtree(self.dir)

class chmodDirSupport(simpleDirSupport):
    def __init__(self, dir, chmod, dir_name):
        simpleDirSupport.__init__(self, dir, dir_name)
        self.chmod=chmod

    def create_dir(self,fail_if_exists=True):
        if os.path.isdir(self.dir):
            if fail_if_exists:
                raise RuntimeError("Cannot create %s dir %s, already exists."%(self.dir_name, self.dir))
            else:
                return False # already exists, nothing to do

        try:
            os.mkdir(self.dir, self.chmod)
        except OSError as e:
            raise RuntimeError("Failed to create %s dir: %s"%(self.dir_name, e))
        return True

class symlinkSupport(dirSupport):
    def __init__(self, target_dir, symlink, dir_name):
        self.target_dir=target_dir
        self.symlink=symlink
        self.dir_name=dir_name

    def create_dir(self,fail_if_exists=True):
        if os.path.islink(self.symlink):
            if fail_if_exists:
                raise RuntimeError("Cannot create %s symlink %s, already exists."%(self.dir_name, self.symlink))
            else:
                return False # already exists, nothing to do

        try:
            os.symlink(self.target_dir, self.symlink)
        except OSError as e:
            raise RuntimeError("Failed to create %s symlink: %s"%(self.dir_name, e))
        return True

    def delete_dir(self):
        os.unlink(self.symlink)

# class for many directory creation
class dirsSupport:
    def __init__(self):
        self.dir_list=[]

    # dir obj must support create_dir and delete_dir
    def add_dir_obj(self, dir_obj):
        self.dir_list.append(dir_obj)

    def create_dirs(self,fail_if_exists=True):
        created_dirs=[]
        try:
            for dir_obj in self.dir_list:
                res=dir_obj.create_dir(fail_if_exists)
                if res:
                    created_dirs.append(dir_obj)
        except:
            # on error, remove the dirs in reverse order
            created_dirs.reverse()
            for dir_obj in created_dirs:
                dir_obj.delete_dir()
            # then rethrow exception
            raise

        return len(created_dirs)!=0

    def delete_dirs(self):
        idxs=range(len(self.dir_list))
        idxs.reverse()
        for i in idxs:
            self.dir_list[i].delete_dir()

# multiple simple dirs
class multiSimpleDirSupport(dirSupport, dirsSupport):
    def __init__(self, list_of_dirs, dir_name):
        dirsSupport.__init__(self)
        self.list_of_dirs=list_of_dirs
        self.dir_name=dir_name

        for dir in list_of_dirs:
            self.add_dir_obj(simpleDirSupport(dir, self.dir_name))

    def create_dir(self,fail_if_exists=True):
        return self.create_dirs(fail_if_exists)

    def delete_dir(self):
        self.delete_dirs()

###########################################

class workDirSupport(multiSimpleDirSupport):
    def __init__(self, work_dir, workdir_name):
        multiSimpleDirSupport.__init__(self,
                                       (work_dir, os.path.join(work_dir, 'lock')),
                                       workdir_name)

# similar to workDirSupport but without lock subdir
class simpleWorkDirSupport(simpleDirSupport):
    pass

class logDirSupport(simpleDirSupport):
    def __init__(self,log_dir,dir_name='log'):
        simpleDirSupport.__init__(self, log_dir, dir_name)

class logSymlinkSupport(symlinkSupport):
    def __init__(self,log_dir,work_dir,symlink_subdir='log',dir_name='log'):
        symlinkSupport.__init__(self, log_dir, os.path.join(work_dir, symlink_subdir), dir_name)

class stageDirSupport(simpleDirSupport):
    def __init__(self,stage_dir,dir_name='stage'):
        simpleDirSupport.__init__(self, stage_dir, dir_name)

class monitorDirSupport(dirSupport, dirsSupport):
    def __init__(self,monitor_dir,dir_name="monitor"):
        dirsSupport.__init__(self)

        self.dir_name=dir_name
        self.monitor_dir=monitor_dir
        self.add_dir_obj(simpleDirSupport(self.monitor_dir, self.dir_name))
        self.add_dir_obj(simpleDirSupport(os.path.join(self.monitor_dir, 'lock'), self.dir_name))

    def create_dir(self,fail_if_exists=True):
        return self.create_dirs(fail_if_exists)

    def delete_dir(self):
        self.delete_dirs()

class monitorWLinkDirSupport(monitorDirSupport):
    def __init__(self,monitor_dir,work_dir,work_subdir="monitor",monitordir_name="monitor"):
        monitorDirSupport.__init__(self, monitor_dir, monitordir_name)

        self.work_dir=work_dir
        self.monitor_symlink=os.path.join(self.work_dir, work_subdir)

        self.add_dir_obj(symlinkSupport(self.monitor_dir, self.monitor_symlink, self.dir_name))

################################################
#
# Dictionaries of files classes
# Only abstract classes defined here
#
################################################

# helper class, used below
class fileCommonDicts:
    def __init__(self):
        self.dicts = {}

    def keys(self):
        return self.dicts.keys()

    def has_key(self, key):
        return key in self.dicts

    def __contains__(self, key):
        return key in self.dicts

    def __getitem__(self, key):
        return self.dicts[key]

    def set_readonly(self,readonly=True):
        for el in self.dicts.values():
            #condor_jdl are lists. Iterating over its elements in this case
            if isinstance(el, list):
                for cj in el:
                    cj.set_readonly(readonly)
            else:
                el.set_readonly(readonly)

################################################
#
# This Class contains the main dicts
#
################################################

class fileMainDicts(fileCommonDicts, dirsSupport):
    def __init__(self,
                 work_dir,stage_dir,
                 workdir_name,
                 simple_work_dir=False,     # if True, do not create the lib and lock work_dir subdirs
                 log_dir=None):             # used only if simple_work_dir=False

        self.active_sub_list = []
        self.disabled_sub_list = []
        self.monitor_dir = ''

        fileCommonDicts.__init__(self)
        dirsSupport.__init__(self)

        self.work_dir=work_dir
        self.stage_dir=stage_dir
        self.workdir_name=workdir_name

        self.simple_work_dir=simple_work_dir
        if simple_work_dir:
            self.log_dir=None
            self.add_dir_obj(simpleWorkDirSupport(self.work_dir, self.workdir_name))
        else:
            self.log_dir=log_dir
            self.add_dir_obj(workDirSupport(self.work_dir, self.workdir_name))
            self.add_dir_obj(logDirSupport(self.log_dir))
            # make it easier to find; create a symlink in work
            self.add_dir_obj(logSymlinkSupport(self.log_dir, self.work_dir))

            # in order to keep things clean, put daemon process logs into a separate dir
            self.add_dir_obj(logDirSupport(self.get_daemon_log_dir(log_dir)))

        self.add_dir_obj(stageDirSupport(self.stage_dir))

        self.erase()

    def get_summary_signature(self): # you can discover most of the other things from this
        return self.dicts['summary_signature']

    def erase(self):
        self.dicts=self.get_main_dicts()

    def populate(self, params=None):
        raise NotImplementedError("populate() not implemented in child!")

    # child must overwrite this
    def load(self):
        raise RuntimeError("Undefined")

    # child must overwrite this
    def save(self,set_readonly=True):
        raise RuntimeError("Undefined")

    def is_equal(self,other,             # other must be of the same class
                 compare_work_dir=False,compare_stage_dir=False,
                 compare_fnames=False):
        if compare_work_dir and (self.work_dir!=other.work_dir):
            return False
        if compare_stage_dir and (self.stage_dir!=other.stage_dir):
            return False
        for k in self.dicts.keys():
            if not self.dicts[k].is_equal(other.dicts[k], compare_dir=False, compare_fname=compare_fnames):
                return False
        return True

    # reuse as much of the other as possible
    def reuse(self, other):             # other must be of the same class
        if self.work_dir!=other.work_dir:
            raise RuntimeError("Cannot change main %s base_dir! '%s'!='%s'"%(self.workdir_name, self.work_dir, other.work_dir))
        if self.stage_dir!=other.stage_dir:
            raise RuntimeError("Cannot change main stage base_dir! '%s'!='%s'"%(self.stage_dir, other.stage_dir))
        return # nothing else to be done in this

    ####################
    # Internal
    ####################

    # Child should overwrite this
    def get_daemon_log_dir(self, base_dir):
        return os.path.join(base_dir, "main")

    # Child must overwrite this
    def get_main_dicts(self):
        raise RuntimeError("Undefined")

################################################
#
# This Class contains the sub dicts
#
################################################

class fileSubDicts(fileCommonDicts, dirsSupport):
    def __init__(self,base_work_dir,base_stage_dir,sub_name,
                 summary_signature,workdir_name,
                 simple_work_dir=False,           # if True, do not create the lib and lock work_dir subdirs
                 base_log_dir=None):              # used only if simple_work_dir=False
        fileCommonDicts.__init__(self)
        dirsSupport.__init__(self)

        self.sub_name=sub_name

        work_dir=self.get_sub_work_dir(base_work_dir)
        stage_dir=self.get_sub_stage_dir(base_stage_dir)

        self.work_dir=work_dir
        self.stage_dir=stage_dir
        self.workdir_name=workdir_name

        self.simple_work_dir=simple_work_dir
        if simple_work_dir:
            self.log_dir=None
            self.add_dir_obj(simpleWorkDirSupport(self.work_dir, self.workdir_name))
        else:
            self.log_dir=self.get_sub_log_dir(base_log_dir)
            self.add_dir_obj(workDirSupport(self.work_dir, self.workdir_name))
            self.add_dir_obj(logDirSupport(self.log_dir))

        self.add_dir_obj(stageDirSupport(self.stage_dir))

        self.summary_signature=summary_signature
        self.erase()

    def erase(self):
        self.dicts=self.get_sub_dicts()

    # child must overwrite this
    def load(self):
        raise ValueError("Undefined")

    # child must overwrite this
    def save(self,set_readonly=True):
        raise ValueError("Undefined")

    # child can overwrite this
    def save_final(self,set_readonly=True):
        pass # not always needed, use default of empty

    def is_equal(self,other,             # other must be of the same class
                 compare_sub_name=False,
                 compare_fnames=False):
        if compare_sub_name and (self.sub_name!=other.sub_name):
            return False
        for k in self.dicts.keys():
            if not self.dicts[k].is_equal(other.dicts[k], compare_dir=False, compare_fname=compare_fnames):
                return False
        return True

    # reuse as much of the other as possible
    def reuse(self, other):             # other must be of the same class
        if self.work_dir!=other.work_dir:
            raise RuntimeError("Cannot change sub %s base_dir! '%s'!='%s'"%(self.workdir_name, self.work_dir, other.work_dir))
        if self.stage_dir!=other.stage_dir:
            raise RuntimeError("Cannot change sub stage base_dir! '%s'!='%s'"%(self.stage_dir, other.stage_dir))

        return # nothing more to be done here


    ####################
    # Internal
    ####################

    # Child should overwrite this
    def get_sub_work_dir(self, base_dir):
        return base_dir+"/sub_"+self.sub_name

    # Child should overwrite this
    def get_sub_log_dir(self, base_dir):
        return base_dir+"/sub_"+self.sub_name

    # Child should overwrite this
    def get_sub_stage_dir(self, base_dir):
        return base_dir+"/sub_"+self.sub_name

    # Child must overwrite this
    def get_sub_dicts(self):
        raise RuntimeError("Undefined")

    # Child must overwrite this
    def reuse_nocheck(self, other):
        raise RuntimeError("Undefined")

################################################
#
# This Class contains both the main and
# the sub dicts
#
################################################

class fileDicts:
    def __init__(self,work_dir,stage_dir,sub_list=[],workdir_name="work",
                 simple_work_dir=False, # if True, do not create the lib and lock work_dir subdirs
                 log_dir=None):         # used only if simple_work_dir=False
        self.work_dir=work_dir
        self.workdir_name=workdir_name
        self.stage_dir=stage_dir
        self.simple_work_dir=simple_work_dir
        self.log_dir=log_dir

        self.main_dicts=self.new_MainDicts()
        self.sub_list=sub_list[:]
        self.sub_dicts={}
        for sub_name in sub_list:
            self.sub_dicts[sub_name]=self.new_SubDicts(sub_name)
        return

    def set_readonly(self,readonly=True):
        self.main_dicts.set_readonly(readonly)
        for el in self.sub_dicts.values():
            el.set_readonly(readonly)

    def erase(self,destroy_old_subs=True): # if false, the sub names will be preserved
        self.main_dicts.erase()
        if destroy_old_subs:
            self.sub_list=[]
            self.sub_dicts={}
        else:
            for sub_name in self.sub_list:
                self.sub_dicts[sub_name].erase()
        return

    def load(self,destroy_old_subs=True): # if false, overwrite the subs you load, but leave the others as they are
        self.main_dicts.load()
        if destroy_old_subs:
            self.sub_list=[]
            self.sub_dicts={}
        # else just leave as it is, will rewrite just the loaded ones

        for sign_key in self.main_dicts.get_summary_signature().keys:
            if sign_key!='main': # main is special, not an sub
                sub_name=self.get_sub_name_from_sub_stage_dir(sign_key)
                if not(sub_name in self.sub_list):
                    self.sub_list.append(sub_name)
                self.sub_dicts[sub_name]=self.new_SubDicts(sub_name)
                self.sub_dicts[sub_name].load()


    def save(self,set_readonly=True):
        for sub_name in self.sub_list:
            self.sub_dicts[sub_name].save(set_readonly=set_readonly)
        self.main_dicts.save(set_readonly=set_readonly)
        for sub_name in self.sub_list:
            self.sub_dicts[sub_name].save_final(set_readonly=set_readonly)

    def create_dirs(self,fail_if_exists=True):
        self.main_dicts.create_dirs(fail_if_exists)
        try:
            for sub_name in self.sub_list:
                self.sub_dicts[sub_name].create_dirs(fail_if_exists)
        except:
            self.main_dicts.delete_dirs() # this will clean up also any created subs
            raise

    def delete_dirs(self):
        self.main_dicts.delete_dirs() # this will clean up also all subs

    def is_equal(self,other,             # other must be of the same class
                 compare_work_dir=False,compare_stage_dir=False,
                 compare_fnames=False):
        if compare_work_dir and (self.work_dir!=other.work_dir):
            return False
        if compare_stage_dir and (self.stage_dir!=other.stage_dir):
            return False
        if not self.main_dicts.is_equal(other.main_dicts, compare_work_dir=False, compare_stage_dir=False, compare_fnames=compare_fnames):
            return False
        my_subs=self.sub_list[:]
        other_subs=other.sub_list[:]
        if len(my_subs)!=len(other_subs):
            return False

        my_subs.sort()
        other_subs.sort()
        if my_subs!=other_subs: # need to be in the same order to make a comparison
            return False

        for k in my_subs:
            if not self.sub_dicts[k].is_equal(other.sub_dicts[k], compare_sub_name=False,
                                              compare_fname=compare_fnames):
                return False
        return True

    # reuse as much of the other as possible
    def reuse(self, other):             # other must be of the same class
        if self.work_dir!=other.work_dir:
            raise RuntimeError("Cannot change %s base_dir! '%s'!='%s'"%(self.workdir_name, self.work_dir, other.work_dir))
        if self.stage_dir!=other.stage_dir:
            raise RuntimeError("Cannot change stage base_dir! '%s'!='%s'"%(self.stage_dir, other.stage_dir))

        # compare main dictionaires
        self.main_dicts.create_dirs(fail_if_exists=False)
        self.main_dicts.reuse(other.main_dicts)

        # compare sub dictionaires
        for k in self.sub_list:
            if k in other.sub_list:
                self.sub_dicts[k].create_dirs(fail_if_exists=False)
                self.sub_dicts[k].reuse(other.sub_dicts[k])
            else:
                # nothing to reuse, but must create dir
                self.sub_dicts[k].create_dirs(fail_if_exists=False)

    ###########
    # PRIVATE
    ###########

    # this should be redefined by the child
    # and return a child of fileMainDicts
    def new_MainDicts(self):
        return fileMainDicts(self.work_dir, self.stage_dir, self.workdir_name, self.simple_work_dir, self.log_dir)

    # this should be redefined by the child
    # and return a child of fileSubDicts
    def new_SubDicts(self, sub_name):
        return fileSubDicts(self.work_dir, self.stage_dir, sub_name, self.main_dicts.get_summary_signature(), self.workdir_name, self.simple_work_dir, self.log_dir)

    # this should be redefined by the child
    def get_sub_name_from_sub_stage_dir(self, sign_key):
        raise RuntimeError("Undefined")


class MonitorFileDicts:
    def __init__(self,work_dir,stage_dir,sub_list=[],workdir_name="work",
                 simple_work_dir=False): # if True, do not create the lib and lock work_dir subdirs
        self.work_dir=work_dir
        self.workdir_name=workdir_name
        self.stage_dir=stage_dir
        self.simple_work_dir=simple_work_dir

        self.main_dicts=self.new_MainDicts()
        self.sub_list=sub_list[:]
        self.sub_dicts={}
        for sub_name in sub_list:
            self.sub_dicts[sub_name]=self.new_SubDicts(sub_name)
        return

    def new_MainDicts(self):
        raise NotImplementedError("new_MainDicts() not implemented in child!")

    def new_SubDicts(self, sub_name):
        raise NotImplementedError("new_SubDicts() not implemented in child!")

    def get_sub_name_from_sub_stage_dir(self, sign_key):
        raise NotImplementedError("get_sub_name_from_sub_stage_dir() not implemented in child!")



    def set_readonly(self,readonly=True):
        self.main_dicts.set_readonly(readonly)
        for el in self.sub_dicts.values():
            el.set_readonly(readonly)

    def erase(self,destroy_old_subs=True): # if false, the sub names will be preserved
        self.main_dicts.erase()
        if destroy_old_subs:
            self.sub_list=[]
            self.sub_dicts={}
        else:
            for sub_name in self.sub_list:
                self.sub_dicts[sub_name].erase()
        return

    def load(self,destroy_old_subs=True): # if false, overwrite the subs you load, but leave the others as they are

        self.main_dicts.load()
        if destroy_old_subs:
            self.sub_list=[]
            self.sub_dicts={}
        # else just leave as it is, will rewrite just the loaded ones

        for sign_key in self.main_dicts.get_summary_signature().keys:
            if sign_key!='main': # main is special, not an sub
                sub_name=self.get_sub_name_from_sub_stage_dir(sign_key)
                if not(sub_name in self.sub_list):
                    self.sub_list.append(sub_name)
                self.sub_dicts[sub_name]=self.new_SubDicts(sub_name)
                self.sub_dicts[sub_name].load()


    def save(self,set_readonly=True):
        for sub_name in self.sub_list:
            self.sub_dicts[sub_name].save(set_readonly=set_readonly)
        self.main_dicts.save(set_readonly=set_readonly)
        for sub_name in self.sub_list:
            self.sub_dicts[sub_name].save_final(set_readonly=set_readonly)

#########################################################
#
# Common functions
#
#########################################################

#####################################################
# Validate HTCondor endpoint (node) string
# this can be a node, node:port, node:port-range
# or a shared port synful string host:port?sock=some_string$ID
# or schedd_name@host:port[?sock=some_string]
def validate_node(nodestr,allow_prange=False):
    eparr = nodestr.split('?')
    if len(eparr) > 2:
        raise RuntimeError("Too many ? in the end point name: '%s'" % nodestr)
    if len(eparr) == 2:
        if not eparr[1].startswith("sock="):
            raise RuntimeError("Unrecognized HTCondor sinful string: %s" % nodestr)
        # check that ; and , are not in the endpoint ID (they are not before ?)
        if ',' in eparr[1] or ';' in eparr[1]:
            raise RuntimeError("HTCondor sinful string should not contain separators (,;): %s" % nodestr)
    narr = eparr[0].split(':')
    if len(narr) > 2:
        raise RuntimeError("Too many : in the node name: '%s'" % nodestr)
    if len(narr)>1:
        # have ports, validate them
        ports = narr[1]
        parr = ports.split('-')
        if len(parr) > 2:
            raise RuntimeError("Too many - in the node ports: '%s'" % nodestr)
        if len(parr) > 1:
            if not allow_prange:
                raise RuntimeError("Port ranges not allowed for this node: '%s'" % nodestr)
            pmin = parr[0]
            pmax = parr[1]
        else:
            pmin = parr[0]
            pmax = parr[0]
        try:
            pmini = int(pmin)
            pmaxi = int(pmax)
        except ValueError as e:
            raise RuntimeError("Node ports are not integer: '%s'" % nodestr)
        if pmini>pmaxi:
            raise RuntimeError("Low port must be lower than high port in node port range: '%s'" % nodestr)

        if pmini<1:
            raise RuntimeError("Ports cannot be less than 1 for node ports: '%s'" % nodestr)
        if pmaxi>65535:
            raise RuntimeError("Ports cannot be more than 64k for node ports: '%s'" % nodestr)

    # split needed to handle the multiple schedd naming convention
    nodename = narr[0].split("@")[-1]
    try:
        socket.getaddrinfo(nodename, None)
    except:
        raise RuntimeError("Node name unknown to DNS: '%s'" % nodestr)

    # OK, all looks good
    return
