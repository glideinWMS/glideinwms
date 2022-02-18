# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

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

import copy
import io
import os  # string
import os.path
import re
import shutil
import socket

from glideinwms.lib import hashCrypto
from glideinwms.lib.defaults import BINARY_ENCODING
from glideinwms.lib.util import chmod

########################################
#
# File dictionary classes
#
########################################


class DictFileError(RuntimeError):
    def __init__(self, msg):
        super().__init__(msg)


# TODO: DictFile could implement a standard interface, e.g. mutable mapping or extend dict,
#  to have a more standard behavior
#  Method naming could also be changes to comply w/ std interfaces and similar classes in the std library

# TODO: DictFile could include encoding information (default being BINARY_ENCODING, latin-1) and have 2 childs,
#  DictBytesFile and DictTextFiles, saving respectively binary and text files, to optimize and reduce some back
#  and forth encoding


class DictFile:
    """Dictionaries serialized in files, one line per item

    Comments start w/ '#' at the beginning of the line
    Empty lines are nor tolerated by the parser in the glidein (bash)

    Files have to be compatible across GlideinWMS versions running in different Python versions
    In this Python 3 version: using binary files and 'latin-1' encoding to preserve
    bytes (0x80...0xff) through round-tripping from byte streams to Unicode and back
    """

    def __init__(self, dir, fname, sort_keys=False, order_matters=False, fname_idx=None):
        """DictFile Constructor

        Args:
            dir (str): folder containing the dictionary
            fname (str): file name (the file path is the concatenation of dir and fname)
            sort_keys (bool): True if keys should be sorted
            order_matters (bool): True if it should remember the insertion order
            fname_idx (str): ID file name (fname if None)

        Raises:
            DictFileError: if both sort_keys and order_matters are True

        """
        self.dir = dir
        self.fname = fname

        if fname_idx is None:
            fname_idx = fname
        self.fname_idx = fname_idx

        if sort_keys and order_matters:
            raise DictFileError("Cannot preserve the order and sort the keys")
        self.sort_keys = sort_keys
        self.order_matters = order_matters

        self.is_readonly = False
        self.changed = True

        self.keys = []
        self.vals = {}

    def has_key(self, key):
        return key in self.keys

    def __contains__(self, key):
        return key in self.keys

    def __getitem__(self, key):
        return self.vals[key]

    # MM .get() added 5345, check no trouble
    def get(self, key):
        return self.vals.get(key)

    def get_fname(self):
        return self.fname

    def get_dir(self):
        return self.dir

    def get_filepath(self):
        return os.path.join(self.dir, self.fname)

    def erase(self):
        self.keys = []
        self.vals = {}
        self.changed = True

    def set_readonly(self, readonly=True):
        self.is_readonly = readonly

    def add(self, key, val, allow_overwrite=False):
        """Add a key, value pair to the dictionary (self) if not already there

        Changes the content of the dictionary and set self.changed to True if the value was added.

        Args:
            key (str): dictionary key
            val: Any value stored in the dictionary, usually a tuple (e.g. attributes and value)
            allow_overwrite (bool): Allow to overwrite an exising value if True (default: False)

        Raises:
            DictFileError: when trying to modify a read only DictFile or overriding an existing item when prohibited
                or using an incompatible value

        """
        if key in self.keys:
            if self.vals[key] == val:
                return  # already exists, nothing to do

        if self.is_readonly:
            raise DictFileError(f"Trying to modify a readonly object ({key}, {val})!")

        if key in self.keys:
            if not allow_overwrite:
                raise DictFileError("Key '%s' already exists" % key)
            elif not self.is_compatible(self.vals[key], val):
                raise DictFileError(f"Key '{key}': Value {val} not compatible with old value {self.vals[key]}")
            # Already exists, covered above
            # if self.vals[key]==val:
            #     return # nothing to do
        else:
            self.keys.append(key)
        self.vals[key] = val
        self.changed = True

    def remove(self, key, fail_if_missing=False):
        if not (key in self.keys):
            if not fail_if_missing:
                raise RuntimeError("Key '%s' does not exist" % key)
            else:
                return  # nothing to do

        self.keys.remove(key)
        del self.vals[key]
        self.changed = True

    def save(
        self,
        dir=None,
        fname=None,
        sort_keys=None,
        set_readonly=True,
        reset_changed=True,
        save_only_if_changed=True,
        want_comments=True,
    ):
        """Save the dictionary into a binary file encoded w/ BINARY_ENCODING (dump function)

        save_into_fd() is the actual function writing to file
        DictFile.save_into_fd() receives str from .format_val() and is encoding them using BINARY_ENCODING
        File permission is 644, to avoid accidental execution of configuration files

        If dir and/or fname are not specified, use the defaults specified in __init__

        Args:
            dir (str): folder containing the dictionary, override the object value
            fname (str): file name (the file path is the concatenation of dir and fname), override the object value
            sort_keys (bool): True if keys should be sorted, override the object value
            set_readonly (bool): if True, set read only after saving it
            reset_changed (bool): if False, do not reset self.changed
            save_only_if_changed (bool): if False, save also if it was not changed
            want_comments (bool): if True, comments are saved as well

        """
        if save_only_if_changed and (not self.changed):
            return  # no change -> don't save

        if dir is None:
            dir = self.dir
        if fname is None:
            fname = self.fname
        if sort_keys is None:
            sort_keys = self.sort_keys

        if not os.path.exists(dir):
            os.makedirs(dir)
        filepath = os.path.join(dir, fname)
        try:
            with open(filepath, "wb") as fd:
                self.save_into_fd(fd, sort_keys, set_readonly, reset_changed, want_comments)
        except OSError as e:
            raise DictFileError(f"Error creating or writing to {filepath}: {e}")

        # ensure that the file permissions are 644
        # This is to minimize a security risk where we load python code from
        # a config file and exec it.  We want to ensure that the only user that
        # can write to the config file is the factory or frontend user.  If
        # either of those user accounts is compromised, then there are much
        # bigger problems than a simple exec security hole.
        chmod(filepath, 0o644)

        return

    def save_into_fd(
        self,
        fd,
        sort_keys=None,
        set_readonly=True,
        reset_changed=True,
        want_comments=True,
    ):
        """Save into a BINARY_ENCODING (latin-1) encoded binary file

        Args:
            fd: binary file
            sort_keys (bool): whether the keys should be sorted before writing the
                dictionary (default: None, use the object setting)
            set_readonly (bool): False to set the DictFile read-write
            reset_changed (bool): False not to record the save (self.changed remains True)
            want_comments (bool): False to disable comments

        """
        if sort_keys is None:
            sort_keys = self.sort_keys

        header = self.file_header(want_comments)
        if sort_keys:
            keys = sorted(self.keys[0:])  # makes a copy
        else:
            keys = self.keys
        footer = self.file_footer(want_comments)  # pylint: disable=assignment-from-none
        try:
            if header is not None:
                fd.write(b"%s\n" % header.encode(BINARY_ENCODING))
            for k in keys:
                val = self.format_val(k, want_comments)
                # TODO: format_val should always return strings (also binary blobs?)
                #       remove this if verified
                # if type(val) == str:
                #    val = val.encode(BINARY_ENCODING)
                #    val = val.encode(BINARY_ENCODING)
                fd.write(b"%s\n" % val.encode(BINARY_ENCODING))
            if footer is not None:
                fd.write(b"%s\n" % footer.encode(BINARY_ENCODING))
        except AttributeError as e:
            # .encode() attribute may be missing because bytes are passed
            raise DictFileError(f"str received while writing {self.fname} ({type(self).__name__}): {e}")

        if set_readonly:
            self.set_readonly(True)

        if reset_changed:
            self.changed = False
        return

    def save_into_bytes(self, sort_keys=None, set_readonly=True, reset_changed=True, want_comments=True):
        """Save the dictionary into a bytes array

        Args:
            sort_keys (bool):
            set_readonly (bool): if True (default) set also the dictionary as read-only
            reset_changed (bool): if True (default) set also the dictionary as not changed (all changes have been saved)
            want_comments (bool): False if you want to skip the comments

        Returns:
            bytes: the content of the dictionary

        """
        fd = io.BytesIO()
        self.save_into_fd(fd, sort_keys, set_readonly, reset_changed, want_comments)
        fd.seek(0)
        data = fd.read()
        fd.close()
        return data

    def save_into_str(self, sort_keys=None, set_readonly=True, reset_changed=True, want_comments=True):
        """Save the dictionary into a string

        Same as save_into_bytes, but returns a string

        Args:
            sort_keys (bool):
            set_readonly (bool): if True (default) set also the dictionary as read-only
            reset_changed (bool): if True (default) set also the dictionary as not changed (all changes have been saved)
            want_comments (bool): False if you want to skip the comments

        Returns:
            str: the content of the dictionary

        """
        data = self.save_into_bytes(sort_keys, set_readonly, reset_changed, want_comments).decode(BINARY_ENCODING)
        return data

    def load(
        self,
        dir=None,
        fname=None,
        change_self=True,
        erase_first=True,
        set_not_changed=True,
    ):
        """

        if dir and/or fname are not specified, use the defaults specified in __init__,
        if they are, and change_self is True, change the self.

        Args:
            dir:
            fname:
            change_self:
            erase_first (bool): if True, delete old content first
            set_not_changed (bool): if True, set self.changed to False

        Returns:

        """
        if dir is None:
            dir = self.dir
        if fname is None:
            fname = self.fname

        filepath = os.path.join(dir, fname)
        try:
            fd = open(filepath, "rb")
        except OSError as e:
            print(f"Error opening {filepath}: {e}")
            print("Assuming blank, and re-creating...")
            return
        try:
            with fd:
                self.load_from_fd(fd, erase_first, set_not_changed)
        except RuntimeError as e:
            raise DictFileError(f"File {filepath}: {str(e)}")

        if change_self:
            self.dir = dir
            self.fname = fname

        return

    def load_from_fd(self, fd, erase_first=True, set_not_changed=True):
        """Load a dictionary in memory from a binary file encoded w/ BINARY_ENCODING

        Values (on lines) are loaded into the dictionary using parse_val, which expects str

        Args:
            fd: file descriptor to load the dictionary from
            erase_first (bool): if True, delete old content of the dictionary first
            set_not_changed (bool): if True, set self.changed to False

        Raises:
            DictFileError: problem parsong a line

        """
        if erase_first:
            self.erase()

        lines = fd.readlines()

        idx = 0
        for line in lines:
            idx += 1
            if line[-1:] == b"\n":
                # strip newline, colon is needed, otherwise the number 10 is returned for \n
                line = line[:-1]
            try:
                self.parse_val(line.decode(BINARY_ENCODING))
            except RuntimeError as e:
                raise DictFileError("Line %i: %s" % (idx, str(e)))

        if set_not_changed:
            self.changed = False  # the memory copy is now same as the one on disk
        return

    def load_from_str(self, data, erase_first=True, set_not_changed=True):
        """Load data from a string into the object (self)

        Args:
            data (str): string to load from
            erase_first (bool): if True, delete old content of the dictionary first
            set_not_changed (bool): if True, set self.changed to False

        """
        with io.BytesIO() as fd:
            # TODO: there may be an optimization here adding a load_from_strfd() method to avoid the encode+decode steps
            fd.write(data.encode(BINARY_ENCODING))
            fd.seek(0)
            try:
                self.load_from_fd(fd, erase_first, set_not_changed)
            except RuntimeError as e:
                raise DictFileError("Memory buffer: %s" % (str(e)))
        return

    def is_equal(self, other, compare_dir=False, compare_fname=False, compare_keys=None):
        """Parametrised comparison of DictFile objects

        Args:
            other (DictFile): second object in the comparison, must be of the same class
            compare_dir (bool): if True, compare also the directories of the files
            compare_fname (bool): if True, compare also the file names
            compare_keys (bool):  if True, compare the order of the keys. If None, use order_matters

        Returns:
            bool: True if self and other have the same representation

        """
        if compare_dir and (self.dir != other.dir):
            return False
        if compare_fname and (self.fname != other.fname):
            return False
        if compare_keys is None:
            compare_keys = self.order_matters
        if compare_keys and (self.keys != other.keys):
            return False
        res = self.save_into_str(
            sort_keys=None, set_readonly=False, reset_changed=False, want_comments=False
        ) == other.save_into_str(sort_keys=None, set_readonly=False, reset_changed=False, want_comments=False)
        return res

    # PRIVATE
    def is_compatible(self, old_val, new_val):
        return True  # everything is compatible

    def file_header(self, want_comments):
        """Return the file header line (file name) as comment, None is want_comments is False

        Args:
            want_comments (bool): If True print also comment lines (lines w/o values)

        Returns:
            str: The file header, a comment containing the file name
        """
        if want_comments:
            return "# File: %s\n#" % self.fname
        else:
            return None

    def file_footer(self, want_comments):
        """Return the file footer as comment (None for this class)

        Args:
            want_comments (bool): If True print also comment lines (lines w/o values)

        Returns:
            None
        """
        return None  # no footer

    def format_val(self, key, want_comments):
        """Return a string with the formatted (space+tab separated) key, value

        Args:
            key: key of the key, value pair to format
            want_comments (bool): If True print also comment lines (lines w/o values)

        Returns:
            str: formatted key, value

        """
        return f"{key} \t{self.vals[key]}"

    def parse_val(self, line):
        """Parse a line and add it to the dictionary

        Changes the dictionary and self.changed via self.add()

        Args:
            line (str): splitting w/ the default separator should yeld the key and the value

        Raises:
            DictFileError, from self.add()
        """
        if not line or line[0] == "#":
            return  # ignore comments
        arr = line.split(None, 1)
        if len(arr[0]) == 0:
            return  # empty key (empty line)

        key = arr[0]
        if len(arr) == 1:
            val = ""
        else:
            val = arr[1]
        return self.add(key, val)


class DictFileTwoKeys(DictFile):
    """DictFile double keyed: both key and val are keys"""

    def __init__(self, dir, fname, sort_keys=False, order_matters=False, fname_idx=None):
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
        """

        Args:
            key:
            val:
            allow_overwrite:

        Raises:
            DictFileError

        """
        if key in self.keys:
            if self.vals[key] == val:
                return  # already exists, nothing to do

        if self.is_readonly:
            raise DictFileError(f"Trying to modify a readonly object ({key}, {val})!")

        if key in self.keys:
            old_val = self.vals[key]
            if not allow_overwrite:
                raise DictFileError("Key '%s' already exists" % key)
            elif not self.is_compatible(old_val, val):
                raise DictFileError(f"Key '{key}': Value {val} not compatible with old value {old_val}")
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
                raise DictFileError("Value '%s' already exists" % val)
            elif not self.is_compatible2(old_key, key):
                raise DictFileError(f"Value '{val}': Key {key} not compatible with old key {old_key}")
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
        """

        Args:
            key:
            fail_if_missing:

        Raises:
            DictFileError: KeyError, the key does not exist

        """
        if key not in self.keys:
            if fail_if_missing:
                raise DictFileError("Key '%s' does not exist" % key)
            else:
                return  # nothing to do

        val = self.vals[key]

        self.keys.remove(key)
        del self.vals[key]
        self.keys2.remove(val)
        del self.vals2[val]
        self.changed = True

    def is_equal(self, other, compare_dir=False, compare_fname=False, compare_keys=None):
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
        res = self.save_into_str(
            sort_keys=None, set_readonly=False, reset_changed=False, want_comments=False
        ) == other.save_into_str(sort_keys=None, set_readonly=False, reset_changed=False, want_comments=False)
        return res

    # PRIVATE
    def is_compatible2(self, old_val2, new_val2):
        return True  # everything is compatible


# descriptions
class DescriptionDictFile(DictFileTwoKeys):
    def format_val(self, key, want_comments):
        return f"{self.vals[key]} \t{key}"

    def parse_val(self, line):
        if not line or line[0] == "#":
            return  # ignore comments
        arr = line.split(None, 1)
        if len(arr) == 0:
            return  # empty line
        if len(arr) != 2:
            raise DictFileError("Not a valid description line: '%s'" % line)

        return self.add(arr[1], arr[0])


# gridmap file
class GridMapDict(DictFileTwoKeys):
    def file_header(self, want_comments):
        return None

    def format_val(self, key, want_comments):
        return f'"{key}" {self.vals[key]}'

    def parse_val(self, line):
        if not line or line[0] == "#":
            return  # ignore comments
        arr = line.split()
        if len(arr) == 0:
            return  # empty line
        if len(arr[0]) == 0:
            return  # empty key

        if line[0:1] != '"':
            raise DictFileError('Not a valid gridmap line; not starting with ": %s' % line)

        user = arr[-1]

        if line[-len(user) - 2 : -len(user) - 1] != '"':
            raise DictFileError('Not a valid gridmap line; DN not ending with ": %s' % line)

        dn = line[1 : -len(user) - 2]
        return self.add(dn, user)


##################################
# signatures
class SHA1DictFile(DictFile):
    """Dictionary of SHA1 signatures
    Saved as "SHA1   FNAME" lines
    """

    def add_from_file(self, filepath, allow_overwrite=False, key=None):
        """Add the SHA1 digest of the file to the dictionary (keyed by the file name)

        Args:
            filepath (str): path of the file to calculate the digest
            allow_overwrite (bool): allow overwrite if True
            key (str): if key==None, use basefname (file name extracted form filepath)

        Returns:

        """
        sha1 = hashCrypto.extract_sha1(filepath)
        if key is None:
            key = os.path.basename(filepath)
        self.add(key, sha1, allow_overwrite)

    def format_val(self, key, want_comments):
        """Format values into a line

        Args:
            key (str): key
            want_comments (bool): not used

        Returns:
            str: line for the file

        """
        return f"{self.vals[key]}  {key}"

    def parse_val(self, line):
        """Parse a line into values for the dictionary

        Comments are ignored

        Args:
            line (str): file line

        Returns:

        """
        if not line or line[0] == "#":
            return  # ignore comments
        arr = line.split(None, 1)
        if len(arr) != 2:
            raise DictFileError("Not a valid SHA1 line: '%s'" % line)
        return self.add(arr[1], arr[0])


# summary signatures
# values are (sha1,fname2)
class SummarySHA1DictFile(DictFile):
    """Summary dictionary w/ SHA1 signatures, values are (sha1, fname2)
    Saved as "SHA1   FNAME2   FNAME" lines
    """

    def add(self, key, val, allow_overwrite=False):
        """Add a SHA1 signature to the dictionary

        Args:
            key (str): key, file name
            val (tuple): (sha1, fname2) tuples
            allow_overwrite:

        Returns:

        """
        if not (type(val) in (type(()), type([]))):
            raise DictFileError("Values '%s' not a list or tuple" % val)
        if len(val) != 2:
            raise DictFileError("Values '%s' not (sha1, fname)" % val)
        return DictFile.add(self, key, val, allow_overwrite)

    def add_from_file(self, filepath, fname2=None, allow_overwrite=False, key=None):
        """Add a file and its SHA1 signature to a summary dictionary

        Args:
            filepath (str): full path of the file to add to the dictionary
            fname2 (str): if fname2==None, use basefname
            allow_overwrite (bool): allow overwrite if True
            key (str): if key==None, use basefname (file name extracted form filepath)

        Returns:

        """
        sha1 = hashCrypto.extract_sha1(filepath)
        if key is None:
            key = os.path.basename(filepath)
        if fname2 is None:
            fname2 = os.path.basename(filepath)
        DictFile.add(self, key, (sha1, fname2), allow_overwrite)

    def format_val(self, key, want_comments):
        """Format the dictionary elements into a line

        Args:
            key (str): key, file name
            want_comments (bool): not used

        Returns:

        """
        return f"{self.vals[key][0]}  {self.vals[key][1]}  {key}"

    def parse_val(self, line):
        """Parse a line and add the values to the dictionary

        Args:
            line (str): line to parse

        Returns:

        """
        if not line or line[0] == "#":
            return  # ignore comments
        arr = line.split(None, 2)
        if len(arr) != 3:
            raise DictFileError(
                "Not a valid summary signature line (expected 4, found %i elements): '%s'" % (len(arr), line)
            )
        key = arr[2]
        return self.add(key, (arr[0], arr[1]))


class SimpleFileDictFile(DictFile):
    """Dictionary of files that holds also the content of the file as the last element in the values. Value is a tuple.

    The dictionary is serialized using a file (dictionary file), one item per line.
    Each item is a file, identified by a file name, with an optional attribute (value) and the file content.
    File names are key. All files are in the same directory of the dictionary (self.dir).
    The values are a tuple and the last item is the file content.
    The file content in the value can be a binary blob (bytes) so it should read accordingly w/o attempting a decode.
    Only the file name and the first element of the value are saved in the dictionary file (serialized dictionary).
    SimpleFileDictFile is used for file lists.

    Dictionary saved as "FNAME VALUE", where FNAME is the key and VALUE the file attributes,
    and a series of separate files w/ the content
    """

    def get_immutable_files(self):
        return self.keys  # keys are files, and all are immutable in this implementation

    def get_file_fname(self, key):
        return key

    def add(self, key, val, allow_overwrite=False):
        """Add an entry to the dictionary, e.g. a file to the list

        Args:
            key (str): file name (dictionary key)
            val: parameters (not the file content), usually file attributes
            allow_overwrite (bool): if True, allows to override existing content in the dictionary (Default: False)
        """
        return self.add_from_file(key, val, os.path.join(self.dir, self.get_file_fname(key)), allow_overwrite)

    def add_from_bytes(self, key, val, data, allow_overwrite=False):
        """Add an entry to the dictionary, parameters and content are both available

        Same as add_from_str(), but the value is here is binary, BINARY_ENCODING encoded if it was text

        Args:
            key (str): file name (key)
            val: parameters (not the file content), usually file attributes (tuple, list or scalar)
            data (bytes): bytes string with the file content added to the dictionary
                (this is binary or BINARY_ENCODING encoded text)
            allow_overwrite (bool): if True, allows to override existing content in the dictionary
        """
        # make it generic for use by children
        # TODO: make sure that DictFile.add() is compatible w/ binary data
        if not isinstance(data, (bytes, bytearray)):
            raise DictFileError(f"Using add_from_bytes to add a string to DictFile ({key}, {data})")
        if not (type(val) in (type(()), type([]))):
            DictFile.add(self, key, (val, data), allow_overwrite)
        else:
            DictFile.add(self, key, tuple(val) + (data,), allow_overwrite)

    def add_from_str(self, key, val, data, allow_overwrite=False):
        """Add an entry to the dictionary, parameters and content are both available

        Same as add_from_bytes(), but the value is here is text, will be BINARY_ENCODING encoded before calling add_from_bytes()

        Args:
            key (str): file name (key)
            val: parameters (not the file content), usually file attributes (tuple, list or scalar)
            data (str): string with the file content added to the dictionary (this is decoded, not bytes)
                It will be encoded using BINARY_ENCODING
            allow_overwrite (bool): if True, allows to override existing content in the dictionary
        """
        # make it generic for use by children
        bindata = data.encode(BINARY_ENCODING)
        self.add_from_bytes(key, val, bindata, allow_overwrite)

    def add_from_fd(self, key, val, fd, allow_overwrite=False):
        """Add an entry to the dictionary using a file object - has a read() method that provides the content

        Args:
            key (str): file name (key)
            val: parameters (not the file content), usually file attributes (tuple, list or scalar)
            fd: file object - has a read() method, opened in binary mode not to try a decode of the content
            allow_overwrite (bool): if True, allows to override existing content in the dictionary
        """
        data = fd.read()
        self.add_from_bytes(key, val, data, allow_overwrite)

    def add_from_file(self, key, val, filepath, allow_overwrite=False):
        """Add data from a file. Add an entry to the dictionary using a file path

        The file could be either a text or a binary file. Opened as binary file.

        Args:
            key (str): file name (key)
            val: parameters (not the file content), usually file attributes (tuple, list or scalar)
            filepath (str): full path of the file
            allow_overwrite (bool): if True, allows to override existing content in the dictionary

        Raises:
            DictFileError: if the file could not be opened (IOError from the system)
        """
        try:
            with open(filepath, "rb") as fd:
                self.add_from_fd(key, val, fd, allow_overwrite)
        except OSError as e:
            raise DictFileError("Could not open file or read from it: %s" % filepath)

    def format_val(self, key, want_comments):
        """Print lines: only the file name (key) the first item of the value tuple if not None

        Args:
            key: file name (dictionary key)
            want_comments: NOT USED, required by inheritance

        Returns:
            str: Formatted string with key (file name) and values (tuple of options for that file)
                Only the file name if there are no values

        """
        if self.vals[key][0] is not None:
            return f"{key} \t{self.vals[key][0]}"
        else:
            return key

    def parse_val(self, line):
        """Parse line and add value and content to the dictionary

        Skip comments (start with #) or empty lines and do nothing, otherwise add to the dictionary:
        First item is the file name (key), the rest are the parameter, data is read form the file (file name)
        Used to parse the line of a file list and add the files to a DictFile object

        Args:
            line (str): line to be parsed

        """
        if not line or line[0] == "#":
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
        """Write the content of the files referred in the dictionary

        For each item self.vals[key][-1] is the content of the file
        It should be bytes, if it is not it will be encoded using BINARY_ENCODING
        This methos is not saving the dictionary itself (key, values)

        Args:
            allow_overwrite (bool): if True allow to over write existing files

        Raises:
            DictFileError: if an error occurred in writing into the file or the file data (last element) is str
                instead of bytes

        """
        for key in self.keys:
            fname = self.get_file_fname(key)
            if not fname:
                raise DictFileError("File name not defined for key %s" % key)
            fdata = self.vals[key][-1]
            # The file content should be already a binary blob (bytes); if it is a string,
            # then raise an error or convert it
            if isinstance(fdata, str):
                raise DictFileError(f"File content received as str instead of bytes: {key} (in {filepath})")
                # Use this instead of 'raise' to silently change the data and be more tolerant
                # fdata = bytes(fdata, encoding=BINARY_ENCODING)
            filepath = os.path.join(self.dir, fname)
            if (not allow_overwrite) and os.path.exists(filepath):
                raise DictFileError("File %s already exists" % filepath)
            try:
                fd = open(filepath, "wb")
            except OSError as e:
                raise DictFileError("Could not create file %s" % filepath)
            try:
                with fd:
                    fd.write(fdata)
            except OSError as e:
                raise DictFileError("Error writing into file %s" % filepath)


class FileDictFile(SimpleFileDictFile):
    """Dictionary file for files (file list). Used for list of transferred files.

    It is using a dictionary (key, value) from DictFile, serialized to file.
    The key is the file ID
    The value (line) on file has DATA_LENGTH (7) components: the key and the first DATA_LENGTH-1 attributes below.
    The value in memory has DATA_LENGTH components (real_fname,cache/exec,period,prefix,cond_download,config_out, data),
    the key is used as key for the dictionary and the data (file content) is added reading the file.
    Here the attributes stored as tuple in the dictionary value:
    1. real_fname, i.e file name
    2. cache/exec/... keyword identifying the file type: regular, nocache, exec (:s modifier to run in singularity), untar, wrapper
    3. period period in seconds at which an executable is re-invoked (only for periodic executables, 0 otherwise)
    4. prefix startd_cron variables prefix (default is GLIDEIN_PS_)
    5. cond_download has a special value of TRUE
    6. config_out has a special value of FALSE
    7. data - String containing the data extracted from the file (real_fname) (not in the serialized dictionary)
    For placeholders, the real_name is empty (and the tuple starts w/ an empty string). Placeholders cannot be
    serialized (saved into file). Empty strings would cause error when parsed back.
    """

    DATA_LENGTH = 7  # Length of value (attributes + data)
    PLACEHOLDER_VALUE = (
        "",
        "",
        0,
        "",
        "",
        "",
        "",
    )  # The tuple should be DATA_LENGTH long and have the correct values

    def add_placeholder(self, key, allow_overwrite=True):
        # using DictFile, no file content (FileDictFile or SimpleFileDictFile)
        DictFile.add(self, key, self.PLACEHOLDER_VALUE, allow_overwrite)

    def is_placeholder(self, key):
        return self[key][0] == ""  # empty real_fname can only be a placeholder

    @staticmethod
    def make_val_tuple(
        file_name,
        file_type,
        period=0,
        prefix="GLIDEIN_PS_",
        cond_download="TRUE",
        config_out="FALSE",
    ):
        """Make a tuple with the DATA_LENGTH-1 attributes in the correct order using the defaults

        :param file_name: name of the file (aka real_fname)
        :param file_type: type of the file (regular, nocache, exec, untar, wrapper). 'exec allows modifiers like ':s'
        :param period: period for periodic executables (ignored otherwise, default: 0)
        :param prefix: prefix for periodic executables (ignored otherwise, default: GLIDEIN_PS_)
        :param cond_download: conditional download (default: 'TRUE')
        :param config_out: config out (default: 'FALSE')
        :return: tuple with the DATA_LENGTH-1 attributes
        See class definition for more information about the attributes
        """
        # TODO: should it do some value checking? valid constant, int, ...
        return (
            file_name,
            file_type,
            period,
            prefix,
            cond_download,
            config_out,
        )  # python constructs the tuple

    @staticmethod
    def val_to_file_name(val):
        return val[0]

    def get_file_fname(self, key):
        return self.val_to_file_name(self.vals[key])

    def add_from_bytes(self, key, val, data, allow_overwrite=False, allow_overwrite_placeholder=True):
        """Add a file to the list, the content is provided separately (not in the val tuple)

        Args:
            key (str): file ID
            val (tuple): lists of 6 or 7 components (see class definition)
            data (bytes): bytes string w/ data to add
            allow_overwrite (bool): if True the existing files can be replaced (default: False)
            allow_overwrite_placeholder (bool): if True, placeholder files can be replaced even if allow_overwrite
                is False (default: True)

        Raises:
            DictFileError

        """
        if key in self and allow_overwrite_placeholder:
            if self.is_placeholder(key):
                # since the other functions know nothing about placeholders, need to force overwrite
                allow_overwrite = True
        return SimpleFileDictFile.add_from_bytes(self, key, val, data, allow_overwrite)

    def add_from_str(self, key, val, data, allow_overwrite=False, allow_overwrite_placeholder=True):
        """Add a file to the list, the content is provided separately (not in the val tuple)

        Args:
            key (str): file ID
            val (tuple): lists of 6 or 7 components (see class definition)
            data (str): string w/ data to add
            allow_overwrite (bool): if True the existing files can be replaced (default: False)
            allow_overwrite_placeholder (bool): if True, placeholder files can be replaced even if allow_overwrite
                is False (default: True)

        Raises:
            DictFileError

        """
        if key in self and allow_overwrite_placeholder:
            if self.is_placeholder(key):
                # since the other functions know nothing about placeholders, need to force overwrite
                allow_overwrite = True
        return SimpleFileDictFile.add_from_str(self, key, val, data, allow_overwrite)

    def add(
        self,
        key,
        val,  # will if len(val)==5, use the last one as data (for placeholders), else load from val[0]
        allow_overwrite=False,
        allow_overwrite_placeholder=True,
    ):
        """Add a file to the list

        Invoke add_from_str if the content is provided (6th component of val), add_from_file otherwise

        Args:
            key (str): file ID
            val (tuple): lists of 6 or 7 components (see class definition)
            allow_overwrite (bool): if True the existing files can be replaced (default: False)
            allow_overwrite_placeholder (bool): if True, placeholder files can be replaced even if allow_overwrite
                is False (default: True)

        Raises:
            DictFileError

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
            raise DictFileError("Values '%s' not (real_fname,cache/exec,period,prefix,cond_download,config_out)" % val)

        if len(val) == self.DATA_LENGTH:
            # Alt: return self.add_from_str(key, val[:self.DATA_LENGTH-1], val[self.DATA_LENGTH-1], allow_overwrite)
            return DictFile.add(self, key, tuple(val), allow_overwrite)
        elif len(val) == self.DATA_LENGTH - 1:
            # Added a safety check that the last element is an attribute and not the value
            # Maybe check also string length or possible values?
            if "\n" in val[-1]:
                raise DictFileError(
                    "Values '%s' not (real_fname,cache/exec,period,prefix,cond_download,config_out)" % val
                )
            return self.add_from_file(
                key,
                val,
                os.path.join(self.dir, self.val_to_file_name(val)),
                allow_overwrite,
            )
        else:
            raise DictFileError("Values '%s' not (real_fname,cache/exec,period,prefix,cond_download,config_out)" % val)

    def format_val(self, key, want_comments):
        return "{} \t{} \t{} \t{} \t{} \t{} \t{}".format(
            key,
            self.vals[key][0],
            self.vals[key][1],
            self.vals[key][2],
            self.vals[key][3],
            self.vals[key][4],
            self.vals[key][5],
        )

    def file_header(self, want_comments):
        if want_comments:
            return (
                DictFile.file_header(self, want_comments)
                + "\n"
                + (
                    "# %s \t%s \t%s \t%s \t%s \t%s \t%s\n"
                    % (
                        "Outfile",
                        "InFile        ",
                        "Cache/exec",
                        "Period",
                        "Prefix",
                        "Condition",
                        "ConfigOut",
                    )
                )
                + ("#" * 89)
            )
        else:
            return None

    def parse_val(self, line):
        """Parse a line of serialized FileDictFile files and add it to the dictionary

        Each line is a tab separated tuple w/ the key and the attributes describing the entry (see class description )
        :param line: string with the line content
        :return: tuple with DATA_LENGTH-1 values
        """
        if not line or line[0] == "#":
            return  # ignore empty lines and comments
        arr = line.split(None, self.DATA_LENGTH - 1)  # split already eliminates multiple spaces (no need for strip)
        if len(arr) == 0:
            return  # empty line (only separators)
        if len(arr[0]) == 0:
            return  # empty key

        if len(arr) != self.DATA_LENGTH:
            # compatibility w/ old formats
            # 3.2.13 (no prefix): key, fname, type, period, cond_download, config_out
            # 3.2.10 (no period, prefix): key, fname, type, cond_download, config_out
            # TODO: remove in 3.3 or after a few version (will break upgrade)
            if len(arr) == self.DATA_LENGTH - 1:
                # For upgrade from 3.2.13 to 3.2.11
                return self.add(arr[0], [arr[1], arr[2], arr[3], "GLIDEIN_PS_", arr[4], arr[5]])
            elif len(arr) == self.DATA_LENGTH - 2:
                # For upgrade from 3.2.10 or earlier
                return self.add(arr[0], [arr[1], arr[2], 0, "GLIDEIN_PS_", arr[3], arr[4]])
            raise RuntimeError(
                "Not a valid file line (expected %i, found %i elements): '%s'" % (self.DATA_LENGTH, len(arr), line)
            )

        return self.add(arr[0], arr[1:])

    def get_immutable_files(self):
        mkeys = []
        for k in self.keys:
            val = self.vals[k][1]
            if val != "nocache":
                mkeys.append(self.vals[k][0])  # file name is not the key, but the first entry

        return mkeys

    def reuse(self, other, compare_dir=False, compare_fname=False, compare_files_fname=False):
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
                    is_equal = self.vals[k] == other.vals[k]
                else:  # ignore file name (first element)
                    is_equal = self.vals[k][1:] == other.vals[k][1:]

                if is_equal:
                    self.vals[k] = copy.deepcopy(other.vals[k])
                # else they are different and there is nothing to be done

        return


# will convert values into python format before writing them out
#   given that it does not call any parent methods, implement an interface first
class ReprDictFileInterface:
    def format_val(self, key, want_comments):
        return f"{key} \t{repr(self.vals[key])}"

    def parse_val(self, line):
        if not line or line[0] == "#":
            return  # ignore comments
        arr = line.split(None, 1)
        if len(arr[0]) == 0:
            return  # empty key

        key = arr[0]
        if len(arr) == 1:
            val = ""
        else:
            val = arr[1]
        return self.add(key, eval(val))

    # fake init to make pylint happy
    def interface_fake_init(self):
        self.vals = {}
        self.add = lambda x, y: True
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
    """will save only strings
    while populating, it may hold other types
    not guaranteed to have typed values on (re-)load
    """

    def __init__(self, dir, fname, sort_keys=False, order_matters=False, fname_idx=None):  # if none, use fname
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


class VarsDictFile(DictFile):
    """DictFile class, values are (Type,Default,CondorName,Required,Export,UserName)"""

    def is_compatible(self, old_val, new_val):
        return (old_val[0] == new_val[0]) and (
            old_val[4] == new_val[4]
        )  # at least the type and the export must be preserved

    def file_header(self, want_comments):
        if want_comments:
            return (
                DictFile.file_header(self, want_comments)
                + "\n"
                + "# VarName               Type    Default         CondorName                     Req.     Export  UserName           \n"
                + "#                       S=Quote - = No Default  + = VarName                             Condor   - = Do not export \n"
                + "#                                                                                                + = Use VarName   \n"
                + "#                                                                                                @ = Use CondorName\n"
                "###################################################################################################################"
            )
        else:
            return None

    def add(self, key, val, allow_overwrite=0):
        if not (type(val) in (type(()), type([]))):
            raise RuntimeError("Values '%s' not a list or tuple" % val)
        if len(val) != 6:
            raise RuntimeError("Values '%s' not (Type,Default,CondorName,Required,Export,UserName)" % str(val))
        if not (val[0] in ("C", "S", "I")):
            raise RuntimeError(f"Invalid var type '{val[1]}', should be either C, S or I in val: {str(val)}")
        for i, t in ((3, "Required"), (4, "Export")):
            if not (val[i] in ("Y", "N")):
                raise RuntimeError(f"Invalid var {t} '{val[i]}', should be either Y or N in val: {str(val)}")

        return DictFile.add(self, key, val, allow_overwrite)

    # valid types are "string", "expr" and "integer" (anything different from the first 2 strings is considered integer)
    def add_extended(
        self,
        key,
        type,
        val_default,  # None or False==No default (i.e. -)
        condor_name,  # if None or false, Varname (i.e. +)
        required,
        export_condor,
        user_name,  # If None or false, do not export (i.e. -)
        # if True, set to VarName (i.e. +)
        allow_overwrite=0,
    ):
        if type == "string":
            type_str = "S"
        elif type == "expr":
            type_str = "C"
        else:
            type_str = "I"

        if (val_default is None) or (val_default == False):
            val_default = "-"

        if (condor_name is None) or (condor_name == False):
            condor_name = "+"

        if required:
            req_str = "Y"
        else:
            req_str = "N"

        if export_condor:
            export_condor_str = "Y"
        else:
            export_condor_str = "N"

        if (user_name is None) or (user_name == False):
            user_name = "-"
        elif user_name == True:
            user_name = "+"

        self.add(
            key,
            (type_str, val_default, condor_name, req_str, export_condor_str, user_name),
            allow_overwrite,
        )

    def format_val(self, key, want_comments):
        return "{} \t{} \t{} \t\t{} \t{} \t{} \t{}".format(
            key,
            self.vals[key][0],
            self.vals[key][1],
            self.vals[key][2],
            self.vals[key][3],
            self.vals[key][4],
            self.vals[key][5],
        )

    def parse_val(self, line):
        if not line or line[0] == "#":
            return  # ignore comments
        arr = line.split(None, 6)
        if len(arr) == 0:
            return  # empty line
        if len(arr) != 7:
            raise RuntimeError("Not a valid var line (expected 7, found %i elements): '%s'" % (len(arr), line))

        key = arr[0]
        return self.add(key, arr[1:])


class SimpleFile(DictFile):
    """DictFile with the content of a file

    This class holds the content of the whole file in the single bytes value with key 'content'.
    Any other key is invalid.
    """

    def add(self, key, val, allow_overwrite=False):
        if key != "content":
            raise RuntimeError("Invalid key '%s'!='content'" % key)
        return DictFile.add(self, key, val, allow_overwrite)

    def file_header(self, want_comments):
        return None  # no comment, anytime

    def format_val(self, key, want_comments):
        """Format the content of the file. Only the 'content' key is accepted

        Args:
            key:
            want_comments (bool): not used

        Returns:
            str: content of the file

        Raises:
            RuntimeError: if the key is not 'content'

        """
        if key == "content":
            data = self.vals[key]
            return data.decode(BINARY_ENCODING)
        else:
            raise RuntimeError("Invalid key '%s'!='content'" % key)

    def load_from_fd(self, fd, erase_first=True, set_not_changed=True):
        """Load the content from a binary file (binary mode used also for text files)

        Args:
            fd: binary file to read the data from
            erase_first (bool): if True, default, delete the old content first
            set_not_changed (bool): if True, set self.changed to False

        Returns:

        """
        if erase_first:
            self.erase()

        data = fd.read()

        # remove final newline, since it will be added at save time
        if data[-1:] == b"\n":
            # strip newline, colon is needed, otherwise the number 10 is returned for \n
            data = data[:-1]

        self.add("content", data)

        if set_not_changed:
            self.changed = False  # the memory copy is now same as the one on disk
        return

    def parse_val(self, line):
        raise RuntimeError("Not defined in SimpleFile")


class ExeFile(SimpleFile):
    """DictFile with the content of an executable file

    This class holds the content of the whole file in the single bytes value with key 'content'.
    Any other key is invalid.
    When saving the content to the file, it will set the permissions to make it executable
    """

    def save(
        self,
        dir=None,
        fname=None,
        # if dir and/or fname are not specified, use the defaults specified in __init__
        sort_keys=None,
        set_readonly=True,
        reset_changed=True,
        save_only_if_changed=True,
        want_comments=True,
    ):
        """

        Args:
            dir:
            fname:
            sort_keys:
            set_readonly:
            reset_changed:
            save_only_if_changed:
            want_comments:

        Returns:

        """
        if save_only_if_changed and (not self.changed):
            return  # no change -> don't save

        if dir is None:
            dir = self.dir
        if fname is None:
            fname = self.fname
        if sort_keys is None:
            sort_keys = self.sort_keys

        filepath = os.path.join(dir, fname)
        try:
            with open(filepath, "wb") as fd:
                self.save_into_fd(fd, sort_keys, set_readonly, reset_changed, want_comments)
        except OSError as e:
            raise RuntimeError(f"Error creating or writing to {filepath}: {e}")
        chmod(filepath, 0o755)

        return


########################################################################################################################
#
# Classes to manage directories and symlinks to directories
#
###########################################################


class dirSupport:
    """abstract class for a directory creation"""

    def create_dir(self, fail_if_exists=True):
        """Create the directory

        Args:
            fail_if_exists (bool): fail with RuntimeError if the directory exists already

        Returns:
            bool: True if the dir was created, false else

        Raises:
            RuntimeError: if failed the operation failed and the dircetory is not already there
                or if it is there and fail_if_exists is True
        """
        raise RuntimeError("Undefined")

    def delete_dir(self):
        raise RuntimeError("Undefined")


class simpleDirSupport(dirSupport):
    def __init__(self, dir, dir_name):
        """Constructor

        Args:
            dir: the path of the directory
            dir_name: name of the directory to be used in error messages
        """
        self.dir = dir
        self.dir_name = dir_name

    def create_dir(self, fail_if_exists=True):
        if os.path.isdir(self.dir):
            if fail_if_exists:
                raise RuntimeError(f"Cannot create {self.dir_name} dir {self.dir}, already exists.")
            else:
                return False  # already exists, nothing to do

        try:
            os.mkdir(self.dir)
        except OSError as e:
            raise RuntimeError(f"Failed to create {self.dir_name} dir: {e}")
        return True

    def delete_dir(self):
        shutil.rmtree(self.dir)


class chmodDirSupport(simpleDirSupport):
    def __init__(self, dir, chmod, dir_name):
        simpleDirSupport.__init__(self, dir, dir_name)
        self.chmod = chmod

    def create_dir(self, fail_if_exists=True):
        if os.path.isdir(self.dir):
            if fail_if_exists:
                raise RuntimeError(f"Cannot create {self.dir_name} dir {self.dir}, already exists.")
            else:
                return False  # already exists, nothing to do

        try:
            os.mkdir(self.dir, self.chmod)
        except OSError as e:
            raise RuntimeError(f"Failed to create {self.dir_name} dir: {e}")
        return True


class symlinkSupport(dirSupport):
    """Symlink to a directory"""

    def __init__(self, target_dir, symlink, dir_name):
        self.target_dir = target_dir
        self.symlink = symlink
        self.dir_name = dir_name

    def create_dir(self, fail_if_exists=True):
        if os.path.islink(self.symlink):
            if fail_if_exists:
                raise RuntimeError(f"Cannot create {self.dir_name} symlink {self.symlink}, already exists.")
            else:
                return False  # already exists, nothing to do

        try:
            os.symlink(self.target_dir, self.symlink)
        except OSError as e:
            raise RuntimeError(f"Failed to create {self.dir_name} symlink: {e}")
        return True

    def delete_dir(self):
        os.unlink(self.symlink)


# class for many directory creation
class dirsSupport:
    def __init__(self):
        self.dir_list = []

    # dir obj must support create_dir and delete_dir
    def add_dir_obj(self, dir_obj):
        self.dir_list.append(dir_obj)

    def create_dirs(self, fail_if_exists=True):
        created_dirs = []
        try:
            for dir_obj in self.dir_list:
                res = dir_obj.create_dir(fail_if_exists)
                if res:
                    created_dirs.append(dir_obj)
        except:
            # on error, remove the dirs in reverse order
            created_dirs.reverse()
            for dir_obj in created_dirs:
                dir_obj.delete_dir()
            # then rethrow exception
            raise

        return len(created_dirs) != 0

    def delete_dirs(self):
        idxs = list(range(len(self.dir_list)))
        idxs.reverse()
        for i in idxs:
            self.dir_list[i].delete_dir()


# multiple simple dirs
class multiSimpleDirSupport(dirSupport, dirsSupport):
    def __init__(self, list_of_dirs, dir_name):
        dirsSupport.__init__(self)
        self.list_of_dirs = list_of_dirs
        self.dir_name = dir_name

        for dir in list_of_dirs:
            self.add_dir_obj(simpleDirSupport(dir, self.dir_name))

    def create_dir(self, fail_if_exists=True):
        return self.create_dirs(fail_if_exists)

    def delete_dir(self):
        self.delete_dirs()


###########################################


class workDirSupport(multiSimpleDirSupport):
    def __init__(self, work_dir, workdir_name):
        multiSimpleDirSupport.__init__(self, (work_dir, os.path.join(work_dir, "lock")), workdir_name)


# similar to workDirSupport but without lock subdir
class simpleWorkDirSupport(simpleDirSupport):
    pass


class logDirSupport(simpleDirSupport):
    def __init__(self, log_dir, dir_name="log"):
        simpleDirSupport.__init__(self, log_dir, dir_name)


class logSymlinkSupport(symlinkSupport):
    def __init__(self, log_dir, work_dir, symlink_subdir="log", dir_name="log"):
        symlinkSupport.__init__(self, log_dir, os.path.join(work_dir, symlink_subdir), dir_name)


class stageDirSupport(simpleDirSupport):
    def __init__(self, stage_dir, dir_name="stage"):
        simpleDirSupport.__init__(self, stage_dir, dir_name)


class monitorDirSupport(dirSupport, dirsSupport):
    def __init__(self, monitor_dir, dir_name="monitor"):
        dirsSupport.__init__(self)

        self.dir_name = dir_name
        self.monitor_dir = monitor_dir
        self.add_dir_obj(simpleDirSupport(self.monitor_dir, self.dir_name))
        self.add_dir_obj(simpleDirSupport(os.path.join(self.monitor_dir, "lock"), self.dir_name))

    def create_dir(self, fail_if_exists=True):
        return self.create_dirs(fail_if_exists)

    def delete_dir(self):
        self.delete_dirs()


class monitorWLinkDirSupport(monitorDirSupport):
    def __init__(self, monitor_dir, work_dir, work_subdir="monitor", monitordir_name="monitor"):
        monitorDirSupport.__init__(self, monitor_dir, monitordir_name)

        self.work_dir = work_dir
        self.monitor_symlink = os.path.join(self.work_dir, work_subdir)

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
        return list(self.dicts.keys())

    def has_key(self, key):
        return key in self.dicts

    def __contains__(self, key):
        return key in self.dicts

    def __getitem__(self, key):
        return self.dicts[key]

    def set_readonly(self, readonly=True):
        for el in list(self.dicts.values()):
            # condor_jdl are lists. Iterating over its elements in this case
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
    """This Class contains the main dicts (dicts is a dict of DictFiles)"""

    def __init__(self, work_dir, stage_dir, workdir_name, simple_work_dir=False, log_dir=None):
        """Constructor

        Args:
            work_dir:
            stage_dir:
            workdir_name:
            simple_work_dir (bool): if True, do not create the lib and lock work_dir subdirs
            base_log_dir (str): used only if simple_work_dir=False

        """
        self.active_sub_list = []
        self.disabled_sub_list = []
        self.monitor_dir = ""

        fileCommonDicts.__init__(self)
        dirsSupport.__init__(self)

        self.work_dir = work_dir
        self.stage_dir = stage_dir
        self.workdir_name = workdir_name

        self.simple_work_dir = simple_work_dir
        if simple_work_dir:
            self.log_dir = None
            self.add_dir_obj(simpleWorkDirSupport(self.work_dir, self.workdir_name))
        else:
            self.log_dir = log_dir
            self.add_dir_obj(workDirSupport(self.work_dir, self.workdir_name))
            self.add_dir_obj(logDirSupport(self.log_dir))
            # make it easier to find; create a symlink in work
            self.add_dir_obj(logSymlinkSupport(self.log_dir, self.work_dir))

            # in order to keep things clean, put daemon process logs into a separate dir
            self.add_dir_obj(logDirSupport(self.get_daemon_log_dir(log_dir)))

        self.add_dir_obj(stageDirSupport(self.stage_dir))

        self.erase()

    def get_summary_signature(
        self,
    ):  # you can discover most of the other things from this
        return self.dicts["summary_signature"]

    def erase(self):
        self.dicts = self.get_main_dicts()

    def populate(self, params=None):
        raise NotImplementedError("populate() not implemented in child!")

    # child must overwrite this
    def load(self):
        raise RuntimeError("Undefined")

    # child must overwrite this
    def save(self, set_readonly=True):
        raise RuntimeError("Undefined")

    def is_equal(
        self,
        other,  # other must be of the same class
        compare_work_dir=False,
        compare_stage_dir=False,
        compare_fnames=False,
    ):
        if compare_work_dir and (self.work_dir != other.work_dir):
            return False
        if compare_stage_dir and (self.stage_dir != other.stage_dir):
            return False
        for k in list(self.dicts.keys()):
            if not self.dicts[k].is_equal(other.dicts[k], compare_dir=False, compare_fname=compare_fnames):
                return False
        return True

    # reuse as much of the other as possible
    def reuse(self, other):  # other must be of the same class
        if self.work_dir != other.work_dir:
            raise RuntimeError(
                f"Cannot change main {self.workdir_name} base_dir! '{self.work_dir}'!='{other.work_dir}'"
            )
        if self.stage_dir != other.stage_dir:
            raise RuntimeError(f"Cannot change main stage base_dir! '{self.stage_dir}'!='{other.stage_dir}'")
        return  # nothing else to be done in this

    ####################
    # Internal
    ####################

    # Child should overwrite this
    def get_daemon_log_dir(self, base_dir):
        return os.path.join(base_dir, "main")

    # Child must overwrite this
    def get_main_dicts(self):
        """Interface

        Returns:
            dict of DictFile: keys are standard depending on the dictionary

        """
        raise RuntimeError("Undefined")


################################################
#
# This Class contains the sub dicts
#
################################################


class fileSubDicts(fileCommonDicts, dirsSupport):
    """This Class contains the sub dicts"""

    def __init__(
        self,
        base_work_dir,
        base_stage_dir,
        sub_name,
        summary_signature,
        workdir_name,
        simple_work_dir=False,
        base_log_dir=None,
    ):
        """Constructor

        Args:
            base_work_dir (str):
            base_stage_dir (str):
            sub_name (str):
            summary_signature (str):
            workdir_name (str):
            simple_work_dir (bool): if True, do not create the lib and lock work_dir subdirs
            base_log_dir (str): used only if simple_work_dir=False
        """
        fileCommonDicts.__init__(self)
        dirsSupport.__init__(self)

        self.sub_name = sub_name

        work_dir = self.get_sub_work_dir(base_work_dir)
        stage_dir = self.get_sub_stage_dir(base_stage_dir)

        self.work_dir = work_dir
        self.stage_dir = stage_dir
        self.workdir_name = workdir_name

        self.simple_work_dir = simple_work_dir
        if simple_work_dir:
            self.log_dir = None
            self.add_dir_obj(simpleWorkDirSupport(self.work_dir, self.workdir_name))
        else:
            self.log_dir = self.get_sub_log_dir(base_log_dir)
            self.add_dir_obj(workDirSupport(self.work_dir, self.workdir_name))
            self.add_dir_obj(logDirSupport(self.log_dir))

        self.add_dir_obj(stageDirSupport(self.stage_dir))

        self.summary_signature = summary_signature
        self.erase()

    def erase(self):
        self.dicts = self.get_sub_dicts()

    # child must overwrite this
    def load(self):
        raise ValueError("Undefined")

    # child must overwrite this
    def save(self, set_readonly=True):
        raise ValueError("Undefined")

    # child can overwrite this
    def save_final(self, set_readonly=True):
        pass  # not always needed, use default of empty

    def is_equal(
        self,
        other,  # other must be of the same class
        compare_sub_name=False,
        compare_fnames=False,
    ):
        """

        Args:
            other: other must be of the same class (child of fileSubDicts)
            compare_sub_name (bool):
            compare_fnames (bool):

        Returns:

        """
        if compare_sub_name and (self.sub_name != other.sub_name):
            return False
        for k in list(self.dicts.keys()):
            if not self.dicts[k].is_equal(other.dicts[k], compare_dir=False, compare_fname=compare_fnames):
                return False
        return True

    # reuse as much of the other as possible
    def reuse(self, other):  # other must be of the same class
        if self.work_dir != other.work_dir:
            raise RuntimeError(f"Cannot change sub {self.workdir_name} base_dir! '{self.work_dir}'!='{other.work_dir}'")
        if self.stage_dir != other.stage_dir:
            raise RuntimeError(f"Cannot change sub stage base_dir! '{self.stage_dir}'!='{other.stage_dir}'")

        return  # nothing more to be done here

    ####################
    # Internal
    ####################

    # Child should overwrite this
    def get_sub_work_dir(self, base_dir):
        return base_dir + "/sub_" + self.sub_name

    # Child should overwrite this
    def get_sub_log_dir(self, base_dir):
        return base_dir + "/sub_" + self.sub_name

    # Child should overwrite this
    def get_sub_stage_dir(self, base_dir):
        return base_dir + "/sub_" + self.sub_name

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
    """This Class contains both the main and the sub dicts"""

    def __init__(
        self,
        work_dir,
        stage_dir,
        sub_list=[],
        workdir_name="work",
        simple_work_dir=False,
        log_dir=None,
    ):
        """

        Args:
            work_dir:
            stage_dir:
            sub_list:
            workdir_name:
            simple_work_dir: if True, do not create the lib and lock work_dir subdirs
            log_dir: used only if simple_work_dir=False
        """
        self.work_dir = work_dir
        self.workdir_name = workdir_name
        self.stage_dir = stage_dir
        self.simple_work_dir = simple_work_dir
        self.log_dir = log_dir

        self.main_dicts = self.new_MainDicts()
        self.sub_list = sub_list[:]
        self.sub_dicts = {}

        for sub_name in sub_list:
            self.sub_dicts[sub_name] = self.new_SubDicts(sub_name)
        return

    def set_readonly(self, readonly=True):
        self.main_dicts.set_readonly(readonly)
        for el in list(self.sub_dicts.values()):
            el.set_readonly(readonly)

    def erase(self, destroy_old_subs=True):  # if false, the sub names will be preserved
        self.main_dicts.erase()
        if destroy_old_subs:
            self.sub_list = []
            self.sub_dicts = {}
        else:
            for sub_name in self.sub_list:
                self.sub_dicts[sub_name].erase()
        return

    def load(self, destroy_old_subs=True):  # if false, overwrite the subs you load, but leave the others as they are
        self.main_dicts.load()
        if destroy_old_subs:
            self.sub_list = []
            self.sub_dicts = {}
        # else just leave as it is, will rewrite just the loaded ones

        for sign_key in self.main_dicts.get_summary_signature().keys:
            if sign_key != "main":  # main is special, not an sub
                sub_name = self.get_sub_name_from_sub_stage_dir(sign_key)
                if not (sub_name in self.sub_list):
                    self.sub_list.append(sub_name)
                self.sub_dicts[sub_name] = self.new_SubDicts(sub_name)
                self.sub_dicts[sub_name].load()

    def save(self, set_readonly=True):
        for sub_name in self.sub_list:
            self.sub_dicts[sub_name].save(set_readonly=set_readonly)
        self.main_dicts.save(set_readonly=set_readonly)
        for sub_name in self.sub_list:
            self.sub_dicts[sub_name].save_final(set_readonly=set_readonly)

    def create_dirs(self, fail_if_exists=True):
        self.main_dicts.create_dirs(fail_if_exists)
        try:
            for sub_name in self.sub_list:
                self.sub_dicts[sub_name].create_dirs(fail_if_exists)
        except:
            self.main_dicts.delete_dirs()  # this will clean up also any created subs
            raise

    def delete_dirs(self):
        self.main_dicts.delete_dirs()  # this will clean up also all subs

    def is_equal(
        self,
        other,  # other must be of the same class
        compare_work_dir=False,
        compare_stage_dir=False,
        compare_fnames=False,
    ):
        if compare_work_dir and (self.work_dir != other.work_dir):
            return False
        if compare_stage_dir and (self.stage_dir != other.stage_dir):
            return False
        if not self.main_dicts.is_equal(
            other.main_dicts,
            compare_work_dir=False,
            compare_stage_dir=False,
            compare_fnames=compare_fnames,
        ):
            return False
        my_subs = self.sub_list[:]
        other_subs = other.sub_list[:]
        if len(my_subs) != len(other_subs):
            return False

        my_subs.sort()
        other_subs.sort()
        if my_subs != other_subs:  # need to be in the same order to make a comparison
            return False

        for k in my_subs:
            if not self.sub_dicts[k].is_equal(other.sub_dicts[k], compare_sub_name=False, compare_fname=compare_fnames):
                return False
        return True

    # reuse as much of the other as possible
    def reuse(self, other):  # other must be of the same class
        if self.work_dir != other.work_dir:
            raise RuntimeError(f"Cannot change {self.workdir_name} base_dir! '{self.work_dir}'!='{other.work_dir}'")
        if self.stage_dir != other.stage_dir:
            raise RuntimeError(f"Cannot change stage base_dir! '{self.stage_dir}'!='{other.stage_dir}'")

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
        return fileMainDicts(
            self.work_dir,
            self.stage_dir,
            self.workdir_name,
            self.simple_work_dir,
            self.log_dir,
        )

    # this should be redefined by the child
    # and return a child of fileSubDicts
    def new_SubDicts(self, sub_name):
        return fileSubDicts(
            self.work_dir,
            self.stage_dir,
            sub_name,
            self.main_dicts.get_summary_signature(),
            self.workdir_name,
            self.simple_work_dir,
            self.log_dir,
        )

    # this should be redefined by the child
    def get_sub_name_from_sub_stage_dir(self, sign_key):
        raise RuntimeError("Undefined")


class MonitorFileDicts:
    def __init__(
        self,
        work_dir,
        stage_dir,
        sub_list=[],
        workdir_name="work",
        simple_work_dir=False,
    ):  # if True, do not create the lib and lock work_dir subdirs
        self.work_dir = work_dir
        self.workdir_name = workdir_name
        self.stage_dir = stage_dir
        self.simple_work_dir = simple_work_dir

        self.main_dicts = self.new_MainDicts()
        self.sub_list = sub_list[:]
        self.sub_dicts = {}
        for sub_name in sub_list:
            self.sub_dicts[sub_name] = self.new_SubDicts(sub_name)
        return

    def new_MainDicts(self):
        raise NotImplementedError("new_MainDicts() not implemented in child!")

    def new_SubDicts(self, sub_name):
        raise NotImplementedError("new_SubDicts() not implemented in child!")

    def get_sub_name_from_sub_stage_dir(self, sign_key):
        raise NotImplementedError("get_sub_name_from_sub_stage_dir() not implemented in child!")

    def set_readonly(self, readonly=True):
        self.main_dicts.set_readonly(readonly)
        for el in list(self.sub_dicts.values()):
            el.set_readonly(readonly)

    def erase(self, destroy_old_subs=True):  # if false, the sub names will be preserved
        self.main_dicts.erase()
        if destroy_old_subs:
            self.sub_list = []
            self.sub_dicts = {}
        else:
            for sub_name in self.sub_list:
                self.sub_dicts[sub_name].erase()
        return

    def load(self, destroy_old_subs=True):  # if false, overwrite the subs you load, but leave the others as they are

        self.main_dicts.load()
        if destroy_old_subs:
            self.sub_list = []
            self.sub_dicts = {}
        # else just leave as it is, will rewrite just the loaded ones

        for sign_key in self.main_dicts.get_summary_signature().keys:
            if sign_key != "main":  # main is special, not an sub
                sub_name = self.get_sub_name_from_sub_stage_dir(sign_key)
                if not (sub_name in self.sub_list):
                    self.sub_list.append(sub_name)
                self.sub_dicts[sub_name] = self.new_SubDicts(sub_name)
                self.sub_dicts[sub_name].load()

    def save(self, set_readonly=True):
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

# Some valid addresses to test validate_node with (using fermicloudui to avoid DNS errors):
# ['fermicloudui.fnal.gov:9618-9620', 'fermicloudui.fnal.gov:9618?sock=collector30-40',
# 'fermicloudui.fnal.gov:9618-9630', 'fermicloudui.fnal.gov:9618?sock=collector30-50',
# 'fermicloudui.fnal.gov:9618?sock=collector10-20', 'fermicloudui.fnal.gov:9618?sock=collector',
# 'fermicloudui.fnal.gov:9618?sock=collector30-40', 'fermicloudui.fnal.gov:9618?sock=collector30',
# 'fermicloudui.fnal.gov:9618?sock=collector', 'fermicloudui.fnal.gov:9618?sock=collector&key1=val1',
# 'name@fermicloudui.fnal.gov:9618?sock=schedd', 'fermicloudui.fnal.gov:9618?sock=my5alpha0num',
# 'fermicloudui.fnal.gov:9618?key1=val1&sock=collector&key2=val2']


def validate_node(nodestr, allow_range=False):
    """Validate HTCondor endpoint (node) string
    this can be a node, node:port, node:port-range
    or a shared port sinful string node[:port]?[var=val&]sock=collectorN1[-N2][&var=val]
    or a schedd schedd_name@node:port[?sock=collector&var=val]
    'sock' cannot appear more than once
    ranges can be either in ports or in 'sock', not in both at the same time

    @param nodestr: endpoint (node) string
    @param allow_range: True if a port range is allowed (e.g. for secondary collectors or CCBs)
    @return: raise RuntimeError if the validation fails
    """
    # check that ; and , are not in the node string
    if "," in nodestr or ";" in nodestr:
        raise RuntimeError("End-point name can not contain list separators (,;): '%s'" % nodestr)
    eparr = nodestr.split("?")
    if len(eparr) > 2:
        raise RuntimeError("Too many ? in the end-point name: '%s'" % nodestr)
    found_range = False
    if len(eparr) == 2:
        # Validate sinful string
        ss_arr = eparr[1].split("&")
        sock_found = False
        for i in ss_arr:
            if i.startswith("sock="):
                if sock_found:
                    raise RuntimeError("Only one 'sock' element allowed in end-point's sinful string: '%s'" % nodestr)
                sock_found = True
                match = re.match(r"(^\w*[a-zA-Z_]+)(\d+)?(?:-(\d+))?$", i[5:])
                if match is None:
                    raise RuntimeError("Invalid 'sock=' value in in the end-point's sinful string: '%s'" % nodestr)
                if match.groups()[2] is not None:
                    # Check the sock range
                    if not allow_range:
                        raise RuntimeError("'sock' range not allowed for this end-point: '%s'" % nodestr)
                    found_range = True
                    try:
                        if int(match.groups()[1]) >= int(match.groups()[2]):
                            raise RuntimeError(
                                "In the end-point, left value in the sock range must be lower than the right one: '%s'"
                                % nodestr
                            )
                    except (TypeError, ValueError):
                        # match.group can be None (or not an integer?)
                        raise RuntimeError("Invalid 'sock' value in in the end-point's sinful string: '%s'" % nodestr)
    narr = eparr[0].split(":")
    if len(narr) > 2:
        raise RuntimeError("Too many : in the end-point name: '%s'" % nodestr)
    if len(narr) > 1:
        # have ports, validate them
        ports = narr[1]
        parr = ports.split("-")
        if len(parr) > 2:
            raise RuntimeError("Too many - in the end-point ports: '%s'" % nodestr)
        try:
            pleft = int(parr[0])
            if len(parr) > 1:
                # found port range
                if not allow_range:
                    raise RuntimeError("Port range not allowed for this end-point: '%s'" % nodestr)
                if found_range:
                    raise RuntimeError("Cannot have both port range and 'sock' range in end-point: '%s'" % nodestr)
                pright = int(parr[1])
                if pleft >= pright:
                    raise RuntimeError(
                        "Left port must be lower than right port in end-point port range: '%s'" % nodestr
                    )
            else:
                pright = pleft
        except ValueError:
            raise RuntimeError("End-point ports are not integer: '%s'" % nodestr)
        if pleft < 1:
            raise RuntimeError("Ports cannot be less than 1 for end-point ports: '%s'" % nodestr)
        if pright > 65535:
            raise RuntimeError("Ports cannot be more than 64k for end-point ports: '%s'" % nodestr)
    # split needed to handle the multiple schedd naming convention
    nodename = narr[0].split("@")[-1]
    try:
        socket.getaddrinfo(nodename, None)
    except:
        raise RuntimeError("Node name unknown to DNS: '%s'" % nodestr)
    # OK, all looks good
    return
