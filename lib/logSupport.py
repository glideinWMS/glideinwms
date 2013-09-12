#
# Project:
#   glideinWMS
#
# File Version: 
#
# Description: log support module
#
# Author:
#  Igor Sfiligoi (Oct 25th 2006)
#
import os,os.path,stat
import timeConversion
import time
import re

# this class can be used instead of a file for writing
class DayLogFile:
    def __init__(self,base_fname,extension="log"):
        self.base_fname=base_fname
        self.extension=extension
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
            raise
        try:
            try:
                fd.write(self.format_msg(now,msg)+"\n")
            except:
                self.write_on_exception("Cannot open %s"%fname,msg)
                raise
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
        return "%s.%s.%s"%(self.base_fname,time.strftime("%Y%m%d",time.localtime(timestamp)),self.extension)

    def format_msg(self,timestamp,msg):
        return "[%s %s] %s"%(self.format_time(timestamp),os.getpid(),msg)

    def format_time(self,timestamp):
        return timeConversion.getISO8601_Local(timestamp)

# this class is used for cleanup
class DirCleanup:
    def __init__(self,
                 dirname,
                 fname_expression, # regular expression, used with re.match
                 maxlife,
                 activity_log,warning_log): # if None, no logging
        self.dirname=dirname
        self.fname_expression=fname_expression
        self.fname_expression_obj=re.compile(fname_expression)
        self.maxlife=maxlife
        self.activity_log=activity_log
        self.warning_log=warning_log
        return

    def cleanup(self):
        count_removes=0

        treshold_time=time.time()-self.maxlife
        files_wstats=self.get_files_wstats()

        for fpath in files_wstats.keys():
            fstat=files_wstats[fpath]

            update_time=fstat[stat.ST_MTIME]
            if update_time<treshold_time:
                try:
                    self.delete_file(fpath)
                    count_removes+=1
                except:
                   if self.warning_log is not None:
                       self.warning_log.write("Could not remove %s"%fpath)

        if count_removes>0:
            if self.activity_log is not None:
                self.activity_log.write("Removed %i files."%count_removes)

        return

    # INTERNAL
    # return a dictionary of fpaths each havinf the os.lstat output
    def get_files_wstats(self):
        out_data={}

        fnames=os.listdir(self.dirname)
        for fname in fnames:
            if self.fname_expression_obj.match(fname) is None:
                continue # ignore files that do not match
            
            fpath=os.path.join(self.dirname,fname)
            fstat=os.lstat(fpath)
            fmode=fstat[stat.ST_MODE]
            isdir=stat.S_ISDIR(fmode)
            if isdir:
                continue #ignore directories
            out_data[fpath]=fstat

        return out_data

    # this may reimplemented by the children
    def delete_file(self,fpath):
        os.unlink(fpath)

# this class is used for cleanup
class DirCleanupWSpace(DirCleanup):
    def __init__(self,
                 dirname,
                 fname_expression, # regular expression, used with re.match
                 maxlife,          # max lifetime after which it is deleted
                 minlife,maxspace, # max space allowed for the sum of files, unless they are too young
                 activity_log,warning_log): # if None, no logging
        DirCleanup.__init__(self,dirname,fname_expression,maxlife,activity_log,warning_log)
        self.minlife=minlife
        self.maxspace=maxspace
        return

    def cleanup(self):
        count_removes=0
        count_removes_bytes=0L
        
        min_treshold_time=time.time()-self.minlife
        treshold_time=time.time()-self.maxlife

        now = time.time()
        files_wstats=self.get_files_wstats()
        self.activity_log.write("Directory stat (%s) took %ss" % (self.dirname, time.time()-now))
        fpaths=files_wstats.keys()
        # order based on time (older first)
        fpaths.sort(lambda i,j:cmp(files_wstats[i][stat.ST_MTIME],files_wstats[j][stat.ST_MTIME]))

        # first calc the amount of space currently used
        used_space=0L        
        now = time.time()
        for fpath in fpaths:
            fstat=files_wstats[fpath]
            fsize=fstat[stat.ST_SIZE]
            used_space+=fsize

        for fpath in fpaths:
            fstat=files_wstats[fpath]

            update_time=fstat[stat.ST_MTIME]
            fsize=fstat[stat.ST_SIZE]

            if ((update_time<treshold_time) or
                ((update_time<min_treshold_time) and (used_space>self.maxspace))):
                try:
                    self.delete_file(fpath)
                    count_removes+=1
                    count_removes_bytes+=fsize
                    used_space-=fsize
                except:
                   if self.warning_log is not None:
                       self.warning_log.write("Could not remove %s"%fpath)

        self.activity_log.write("Deleting %i files took %ss" % (count_removes, time.time() - now))
                
        if count_removes>0:
            if self.activity_log is not None:
                self.activity_log.write("Removed %i files for %.2fMB."%(count_removes,count_removes_bytes/(1024.0*1024.0)))
        return

