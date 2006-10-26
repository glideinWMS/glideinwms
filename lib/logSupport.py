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
                fd.write(self.format_msg(now,msg)+"\n")
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

# this class is used for cleanup
class DirCleanup:
    def __init__(self,dirname,maxlife,
                 activity_log,warning_log): # if null, no logging
        self.dirname=dirname
        self.maxlife=maxlife
        self.activity_log=activity_log
        self.warning_log=warning_log
        return

    def cleanup(self):
        treshold_time=time.time()-self.maxlife
        fnames=os.listdir(self.dirname)
        count removes=0
        for fname in fnames:
            fpath=os.path.join(self.dirname,fname)
            fstat=os.lstat(fpath)
            fmode=fstat[stat.ST_MODE]
            isdir=stat.S_ISDIR(fmode)
            if isdir:
                continue #ignore directories
            update_time=fstat[stat.ST_MTIME]
            if update_time<treshold_time:
                try:
                    os.unlink(fpath)
                except:
                   if self.warning_log:
                       self.warning_log.write("Could not remove %s"%fpath)
                count_removes=count_removes+1
        if count_removes>0:
            if self.activity_log:
                self.activity_log.write("Removed %i files."%count_removes)

        return

