from __future__ import absolute_import
from builtins import object
from future import standard_library
standard_library.install_aliases()
import os
from . import glideinwms_tarfile
import io

class FileDoesNotExist(Exception):
    """File does not exist exception

    @note: Include the file name in the full_path
    @ivar full_path: The full path to the missing file.  Includes the file name
    """
    def __init__(self, full_path):
        message = "The file, %s, does not exist." % full_path
        # Call the base class constructor with the parameters it needs
        Exception.__init__(self, message)

class GlideinTar(object):
    """This class provides a container for creating tarballs.  The class provides
    methods to add files and string data (ends up as a file in the tarball).
    The tarball can be written to a file on disk or written to memory.
    """
    def __init__(self):
        """Set up the strings dict and the files list

        The strings dict will hold string data that is to be added to the tar
        file.  The key will be the file name and the value will be the file
        data.  The files list contains a list of file paths that will be added
        to the tar file.
        """
        self.strings = {}
        self.files = []

    def add_file(self, filename, arc_dirname):
        """
        Add a filepath to the files list
        
        @type filename: string
        @param filename: The file path to the file that will eventually be 
        written to the tarball.
        @type arc_dirname: string
        @param arc_dirname: This is the directory that the file will show up 
        under in the tarball
        """
        if os.path.exists(filename):
            self.files.append((filename, arc_dirname))
        else:
            raise FileDoesNotExist(filename)

    def add_string(self, name, string_data):
        """
        Add a string to the string dictionary.
        
        @type name: string
        @param name: A string specifying the "filename" within the tarball that 
        the string_data will be written to.
        @type string_data: string
        @param string_data: The contents that will be written to a "file" within
        the tarball.
        """
        self.strings[name] = string_data

    def create_tar(self, tf):
        """Takes the provided tar file object and adds all the specified data
        to it.  The strings dictionary is parsed such that the key name is the
        file name and the value is the file data in the tar file.
        
        @type tf: Tar File
        @param tf: The Tar File Object that will be written to
        """
        for file in self.files:
            file, dirname = file
            if dirname:
                tf.add(file, arcname=os.path.join(dirname, os.path.split(file)[-1]))
            else:
                tf.add(file)

        for filename, string in list(self.strings.items()):
            fd_str = io.StringIO(string)
            fd_str.seek(0)
            ti = glideinwms_tarfile.TarInfo()
            ti.size = len(string)
            ti.name = filename
            ti.type = glideinwms_tarfile.REGTYPE
            ti.mode = 0o400
            tf.addfile(ti, fd_str)

    def create_tar_file(self, archive_full_path, compression="gz"):
        """Creates a tarball and writes it out to the file specified in fd

        @Note: we don't have to worry about ReadError, since we don't allow
            appending.  We only write to a tarball on create.

        @param fd: The file that the tarball will be written to
        @param compression: The type of compression that should be used

        @raise glideinwms_tarfile.CompressionError: This exception can be raised is an
            invalid compression type has been passed in
        """
        tar_mode = "w:%s" % compression
        tf = glideinwms_tarfile.open(archive_full_path, mode=tar_mode)
        self.create_tar(tf)
        tf.close()

    def create_tar_blob(self, compression="gz"):
        """Creates a tarball and writes it out to memory

        @Note: we don't have to worry about ReadError, since we don't allow
            appending.  We only write to a tarball on create.

        @param fd: The file that the tarball will be written to
        @param compression: The type of compression that should be used

        @raise glideinwms_tarfile.CompressionError: This exception can be raised is an
            invalid compression type has been passed in
        """
        from io import StringIO
        tar_mode = "w:%s" % compression
        file_out = StringIO()
        tf = glideinwms_tarfile.open(fileobj=file_out, mode=tar_mode)
        self.create_tar(tf)
        tf.close()
        return file_out.getvalue()

    def is_tarfile(self, full_path):
        """Checks to see if the tar file specified is valid and can be read.
        Returns True if the file is a valid tar file and it can be read.
        Returns False if not valid or it cannot be read.

        @param full_path: The full path to the tar file.  Includes the file name

        @return: True/False
        """
        return glideinwms_tarfile.is_tarfile(full_path)
