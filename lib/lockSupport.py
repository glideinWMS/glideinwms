import os

class LockSupport:
    def __init__(self, pid_fname=None):
        self.pid_fname = "/tmp/gwms_reload_lock"

    def check(self):
        return os.path.exists( self.pid_fname )

    def create(self):
        fd = open(self.pid_fname, "w")

    def delete(self):
        if os.path.exists( self.pid_fname ):
            os.remove( self.pid_fname )
