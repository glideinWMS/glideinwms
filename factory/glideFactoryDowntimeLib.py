#
# Project:
#   glideinWMS
#
# File Version: 
#   $Id: glideFactoryDowntimeLib.py,v 1.3.28.1 2010/08/31 18:49:16 parag Exp $
#
# Description:
#   This module implements the functions needed to
#   handle the downtimes
#
# Author:
#   Igor Sfiligoi (July 7th 2008)
#

import time
import fcntl
import os.path
import timeConversion

#
# Handle a downtime file
#
# Each line in the file has two entries
# start_time   end_time
# expressed in utime
# if end_time is None, the downtime does not have a set expiration
#  (i.e. it runs forever)
class DowntimeFile:
    def __init__(self,fname):
        self.fname=fname

    # return a list of downtime periods (utimes)
    # a value of None idicates "forever"
    # for example: [(1215339200,1215439170),(1215439271,None)]
    def read(self, raise_on_error=False):
        return read(self.fname,raise_on_error)

    # if check_time==None, use current time
    def checkDowntime(self,check_time=None):
        return checkDowntime(self.fname,check_time)

    # add a scheduled downtime
    def addPeriod(self,start_time,end_time,create_if_empty=True):
        return addPeriod(self.fname,start_time,end_time,create_if_empty)

    # start a downtime that we don't know when it will end
    # if start_time==None, use current time
    def startDowntime(self,start_time=None,create_if_empty=True):
        if start_time==None:
            start_time=long(time.time())
        return self.addPeriod(start_time,None,create_if_empty)

    # end a downtime (not a scheduled one)
    # if end_time==None, use current time
    def endDowntime(self,end_time=None):
        return endDowntime(self.fname,end_time)

    # if cut time<0, use current_time-abs(cut_time)
    def purgeOldPeriods(self,cut_time=None, raise_on_error=False):
        return purgeOldPeriods(self.fname,cut_time, raise_on_error)


#############################
# INTERNAL - Do not use
#############################

# return a list of downtime periods (utimes)
# a value of None idicates "forever"
# for example: [(1215339200,1215439170),(1215439271,None)]
def read(fname, raise_on_error=False):
        try:
            fd=open(fname,'r')
            try:
                fcntl.flock(fd,fcntl.LOCK_SH)
                lines=fd.readlines()
            finally:
                fd.close()
        except IOError, e:
            if raise_on_error:
                raise
            else:
                return [] # no file -> no downtimes

        out=[]
        lnr=0
        for long_line in lines:
            lnr+=1
            line=long_line.strip()
            if len(line)==0:
                continue # ignore empty lines
            if line[0:1]=='#':
                continue # ignore comments
            arr=line.split()
            if len(arr)!=2:
                if raise_on_error:
                    raise ValueError, "%s:%i: Expected pair, got '%s'"%(fname,lnr,line)
                else:
                    continue # ignore malformed lines
            try:
                start_time=timeConversion.extractISO8601_Local(arr[0])
            except ValueError,e:
                if raise_on_error:
                    raise ValueError, "%s:%i: 1st element: %s"%(fname,lnr,e)
                else:
                    continue #ignore errors

            try:
                if arr[1]=='None':
                    end_time=None
                else:
                    end_time=timeConversion.extractISO8601_Local(arr[1])
            except ValueError,e:
                if raise_on_error:
                    raise ValueError, "%s:%i: 2nd element: %s"%(fname,lnr,e)
                else:
                    continue #ignore errors
            out.append((start_time,end_time))
            # end for long_line in lines:
            
        return out

# if check_time==None, use current time
def checkDowntime(fname,check_time=None):
        if check_time==None:
            check_time=long(time.time())
        time_list=read(fname)
        for time_tuple in time_list:
            if check_time<time_tuple[0]:
                continue # check_time before start
            if time_tuple[1]==None:
                return True # downtime valid until the end of times, so here we go
            if check_time<=time_tuple[1]:
                return True # within limit

        return False # not found a downtime window
        
def addPeriod(fname,start_time,end_time,create_if_empty=True):
        exists=os.path.isfile(fname)
        if (not exists) and (not create_if_empty):
            raise IOError, "[Errno 2] No such file or directory: '%s'"%fname
        
        fd=open(fname,'a+')
        try:
            fcntl.flock(fd,fcntl.LOCK_EX)
            if not exists: # new file, create header
                fd.write("# Downtime file\n#Start\t\t\t\tEnd\n")
            if end_time!=None:
                fd.write("%s\t%s\n"%(timeConversion.getISO8601_Local(start_time),timeConversion.getISO8601_Local(end_time)))
            else:
                fd.write("%s\tNone\n"%timeConversion.getISO8601_Local(start_time))
        finally:
            fd.close()

# if cut_time==None or 0, use current time
# if cut time<0, use current_time-abs(cut_time)
def purgeOldPeriods(fname,cut_time=None, raise_on_error=False):
        if cut_time==None:
            cut_time=long(time.time())
        elif cut_time<=0:
            cut_time=long(time.time())+cut_time

        try:
            fd=open(fname,'r+')
        except IOError, e:
            if raise_on_error:
                raise
            else:
                return 0 # no file -> nothing to purge
        
        try:
            fcntl.flock(fd,fcntl.LOCK_EX)
            # read the old info
            inlines=fd.readlines()

            outlines=[]
            lnr=0
            cut_nr=0
            for long_line in inlines:
                lnr+=1
                line=long_line.strip()
                if len(line)==0:
                    outlines.append(long_line)
                    continue # pass on empty lines
                if line[0:1]=='#':
                    outlines.append(long_line)
                    continue # pass on comments
                arr=line.split()
                if len(arr)!=2:
                    if raise_on_error:
                        raise ValueError, "%s:%i: Expected pair, got '%s'"%(fname,lnr,line)
                    else:
                        outlines.append(long_line)
                        continue # pass on malformed lines

                try:
                    if arr[1]=='None':
                        end_time=None
                    else:
                        end_time=timeConversion.extractISO8601_Local(arr[1])
                except ValueError,e:
                    if raise_on_error:
                        raise ValueError, "%s:%i: 2nd element: %s"%(fname,lnr,e)
                    else:
                        outlines.append(long_line)
                        continue #unknown, pass on
                
                if end_time==None:
                    outlines.append(long_line)
                    continue #valid forever, pass on
                
                if end_time>=cut_time:
                    outlines.append(long_line)
                    continue # end_time after cut_time, have to keep it

                # if we got here, the period ended before the cut date... cut it
                cut_nr+=1
                pass # end for
            
            # go back to start to rewrite
            fd.seek(0)
            fd.writelines(outlines)
            fd.truncate()
        finally:
            fd.close()

        return cut_nr

# end a downtime (not a scheduled one)
# if end_time==None, use current time
def endDowntime(fname,end_time=None):
        if end_time==None:
            end_time=long(time.time())
    
        try:
            fd=open(fname,'r+')
        except IOError, e:
            return 0 # no file -> nothing to end

        try:
            fcntl.flock(fd,fcntl.LOCK_EX)
            # read the old info
            inlines=fd.readlines()

            outlines=[]
            lnr=0
            closed_nr=0
            for long_line in inlines:
                lnr+=1
                line=long_line.strip()
                if len(line)==0:
                    outlines.append(long_line)
                    continue # pass on empty lines
                if line[0:1]=='#':
                    outlines.append(long_line)
                    continue # pass on comments
                arr=line.split()
                if len(arr)!=2:
                    outlines.append(long_line)
                    continue # pass on malformed lines
                
                if arr[1]=='None':
                    # open period -> close
                    outlines.append("%s\t%s\n"%(arr[0],timeConversion.getISO8601_Local(end_time)))
                    closed_nr+=1
                else:
                    # closed just pass on
                    outlines.append(long_line)
                pass # end for
            
            # go back to start to rewrite
            fd.seek(0)
            fd.writelines(outlines)
            fd.truncate()
        finally:
            fd.close()

        return closed_nr

