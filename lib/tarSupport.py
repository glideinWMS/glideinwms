import os
import sys
import tarfile
import cStringIO

class GlideinTar:
    """
        potential exception needs to be caught by calling routine
    """
    def __init__(self):
        self.strings = {}
        self.files = []

    def add_file(self, filename, arc_dirname):
        if os.path.exists(filename):
            self.files.append((filename, dirname))

    def add_string(self, name, string_data):
        self.strings[name] = string_data

    def create_tar(self, tf):
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

    def create_tar_file(self, fd):
        tf = tarfile.open(fileobj=fd, mode="w:gz")
        self.create_tar(tf)
        tf.close()

    def create_tar_blob(self):
        from cStringIO import StringIO
        file_out = StringIO()
        tf = tarfile.open(fileobj=file_out, mode="w:gz")
        self.create_tar(tf)
        tf.close()
        return file_out.getvalue()

