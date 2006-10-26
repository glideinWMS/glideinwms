#
# Description: log support module
#
# Author:
#  Igor Sfiligoi (Oct 25th 2006)
#
import os
import time

# this class can be used instead of a file for writing
class DayLogFile:
    def __init__(self,base_fname):
        self.base_fname=base_fname
        return

    def close(self):
        return # nothing to do, just a placeholder

    def write(self,msg):
        now=time.time()
        fname=self.get_fname(now)
        try:
            fd=open(fname,"a")
        except:
            self.write_on_exception("Cannot open %s"%fname,msg)
        try:
            try:
                fd.write(self.format_msg(now,msg))
            except:
                self.write_on_exception("Cannot open %s"%fname,msg)
        finally:
            fd.close()
        
        return

    ##########################
    # these can be customized
    ##########################

    def write_on_exception(self,exception_msg,msg):
        print "%s: %s" % (exception_msg,msg)
        return 

    def get_fname(self,timestamp):
        return "%s.%s.log"%(self.base_fname,time.strftime("%Y%m%d",time.localtime(timestamp)))

    def format_msg(self,timestamp,msg):
        return "[%s %s] %s"%(self.format_time(timestamp),os.getpid(),msg)

    def format_time(self,timestamp):
        return "%li"%timestamp

