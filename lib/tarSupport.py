import os
import sys
import tarfile
import cStringIO

class FileDoesNotExist(Exception):
    """File does not exist exception

    @note: Include the file name in the full_path
    @ivar full_path: The full path to the missing file.  Includes the file name
    """
    def __init__(self, full_path):
        message = "The file, %s, does not exist." % full_path
        # Call the base class constructor with the parameters it needs
        Exception.__init__(self, message)

class GlideinTar:
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
        if os.path.exists(filename):
            self.files.append((filename, arc_dirname))
        else:
            raise FileDoesNotExist(filename)

    def add_string(self, name, string_data):
        self.strings[name] = string_data

    def create_tar(self, tf):
        """Takes the provided tar file object and adds all the specified data
        to it.  The strings dictionary is parsed such that the key name is the
        file name and the value is the file data in the tar file.
        """
        for file in self.files:
            file, dirname = file
            if dirname:
                tf.add(file, arcname=os.path.join(dirname, os.path.split(file)[-1]))
            else:
                tf.add(file)

        for filename, string in self.strings.items():
            fd_str = cStringIO.StringIO(string)
            fd_str.seek(0)
            ti = tarfile.TarInfo()
            ti.size = len(string)
            ti.name = filename
            ti.type = tarfile.REGTYPE
            tf.addfile(ti, fd_str)

    def create_tar_file(self, fd, compression="gz"):
        """Creates a tarball and writes it out to the file specified in fd

        @Note: we don't have to worry about ReadError, since we don't allow
            appending.  We only write to a tarball on create.

        @param fd: The file that the tarball will be written to
        @param compression: The type of compression that should be used

        @raise tarfile.CompressionError: This exception can be raised is an
            invalid compression type has been passed in
        """
        tar_mode = "w:%s" % compression
        tf = tarfile.open(fileobj=fd, mode=tar_mode)
        self.create_tar(tf)
        tf.close()

    def create_tar_blob(self, compression="gz"):
        """Creates a tarball and writes it out to memory

        @Note: we don't have to worry about ReadError, since we don't allow
            appending.  We only write to a tarball on create.

        @param fd: The file that the tarball will be written to
        @param compression: The type of compression that should be used

        @raise tarfile.CompressionError: This exception can be raised is an
            invalid compression type has been passed in
        """
        from cStringIO import StringIO
        tar_mode = "w:%s" % compression
        file_out = StringIO()
        tf = tarfile.open(fileobj=file_out, mode="w:gz")
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
        return tarfile.is_tarfile(full_path)
