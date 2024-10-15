# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

import io
import os
import tarfile


class FileDoesNotExist(Exception):
    """Exception raised when a specified file does not exist.

    Attributes:
        full_path (str): The full path to the missing file.
    """

    def __init__(self, full_path):
        """Initializes FileDoesNotExist with the full path of the missing file.

        Args:
            full_path (str): The full path to the missing file.
        """
        message = f"The file, {full_path}, does not exist."
        super().__init__(message)


class GlideinTar:
    """Container for creating tarballs.

    This class provides methods to add files and string data to a tarball.
    The tarball can be written to a file on disk or stored in memory.
    """

    def __init__(self):
        """Initializes GlideinTar with empty strings and files containers.

        The `strings` dict holds string data to be added to the tar file, where
        the key is the file name and the value is the file content.
        The `files` list contains file paths that will be added to the tar file.
        """
        self.strings = {}
        self.files = []

    def add_file(self, filename, arc_dirname):
        """Adds a file path to the files list.

        Args:
            filename (str): The file path to be added to the tarball.
            arc_dirname (str): The directory path within the tarball where the file will be stored.

        Raises:
            FileDoesNotExist: If the specified file does not exist.
        """
        if os.path.exists(filename):
            self.files.append((filename, arc_dirname))
        else:
            raise FileDoesNotExist(filename)

    def add_string(self, name, string_data):
        """Adds a string as a file within the tarball.

        Args:
            name (str): The filename within the tarball.
            string_data (str): The string content to be written as a file in the tarball.
        """
        self.strings[name] = string_data

    def create_tar(self, tf):
        """Adds files and string data to the provided tarfile object.

        Args:
            tf (tarfile.TarFile): The tarfile object to which files and strings will be added.
        """
        for file, dirname in self.files:
            if dirname:
                tf.add(file, arcname=os.path.join(dirname, os.path.split(file)[-1]))
            else:
                tf.add(file)

        for filename, string in self.strings.items():
            string_encoding = string.encode("utf-8")
            fd_str = io.BytesIO(string_encoding)
            fd_str.seek(0)
            ti = tarfile.TarInfo()
            ti.size = len(string_encoding)
            ti.name = filename
            ti.type = tarfile.REGTYPE
            ti.mode = 0o400
            tf.addfile(tarinfo=ti, fileobj=fd_str)

    def create_tar_file(self, archive_full_path, compression="gz"):
        """Creates a tarball and writes it to a file.

        Args:
            archive_full_path (str): The full path to the file where the tarball will be written.
            compression (str, optional): The compression format to use (default is "gz").

        Raises:
            CompressionError: If an invalid compression type is passed in.
        """
        tar_mode = f"w:{compression}"
        tf = tarfile.open(archive_full_path, mode=tar_mode)
        self.create_tar(tf)
        tf.close()

    def create_tar_blob(self, compression="gz"):
        """Creates a tarball and stores it in memory.

        Args:
            compression (str, optional): The compression format to use (default is "gz").

        Returns:
            bytes: The tarball data stored in memory.

        Raises:
            CompressionError: If an invalid compression type is passed in.
        """
        from io import BytesIO

        tar_mode = f"w:{compression}"
        file_out = BytesIO()
        tf = tarfile.open(fileobj=file_out, mode=tar_mode)
        self.create_tar(tf)
        tf.close()
        return file_out.getvalue()

    def is_tarfile(self, full_path):
        """Checks if the specified file is a valid tar file.

        Args:
            full_path (str): The full path to the tar file, including the file name.

        Returns:
            bool: True if the file is a valid tar file and can be read, False otherwise.
        """
        return tarfile.is_tarfile(full_path)
