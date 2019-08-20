from __future__ import print_function
import time
import fcntl
import os.path

from glideinwms.lib import timeConversion

# Handle a downtime file
#
# Each line in the file has two entries
# start_time   end_time
# expressed in utime
# if end_time is None, the downtime does not have a set expiration
#  (i.e. it runs forever)
class DowntimeFile:
    def __init__(self, fname):
        self.fname=fname

    # if check_time==None, use current time
    def checkDowntime( self, check_time=None ):
        rtn = checkDowntime(self.fname, check_time)
        return rtn

    # add a scheduled downtime
    def addPeriod(self, start_time, end_time, create_if_empty=True):
        return addPeriod(self.fname, start_time, end_time, create_if_empty)

    # start a downtime that we don't know when it will end    # if start_time==None, use current time
    def startDowntime(self, start_time=None, end_time=None, create_if_empty=True):
        if start_time is None:
            start_time=long(time.time())
        return self.addPeriod(start_time, end_time, create_if_empty)

    # end a downtime (not a scheduled one)    # if end_time==None, use current time
    def endDowntime(self, end_time=None):
        return endDowntime( self.fname, end_time)


    def printDowntime(self, check_time=None):
        return printDowntime(self.fname, check_time)

    # return a list of downtime periods (utimes) a value of None idicates "forever" for example: [(1215339200,1215439170),(1215439271,None)]
    def read(self, raise_on_error=False):
        return read(self.fname, raise_on_error)


#############################
# INTERNAL - Do not use
#############################

# return a list of downtime periods (utimes)
# a value of None idicates "forever"
# for example: [(1215339200,1215439170),(1215439271,None)]
def read(fname, raise_on_error=False):
        try:
            with open(fname, 'r') as fd:
                fcntl.flock( fd, fcntl.LOCK_SH | fcntl.LOCK_NB )
                lines = fd.readlines()
        except IOError as e:
            if raise_on_error:
                raise
            else:
                return [] # no file -> no downtimes
#############################################################################
        out=[]
        lnr=0
        for long_line in lines:
            lnr += 1
            line = long_line.strip()

            if len(line)==0:
                continue # ignore empty lines
            if line[0:1]=='#':
                continue # ignore comments

            arr = line.split()

            # Read in lines of the downtime file
            # Start End Entry Security_Class Comment
            if len(arr) < 2:
                if raise_on_error:
                    raise ValueError("%s:%i: Expected pair, got '%s'"%(fname, lnr, line))
                else:
                    continue # ignore malformed lines

            try:
                start_time = timeConversion.extractISO8601_Local(arr[0])
            except ValueError as e:
                if raise_on_error:
                    raise ValueError("%s:%i: 1st element: %s"%(fname, lnr, e))
                else:
                    continue #ignore errors

            try:
                if arr[1]=='None':
                    end_time=None
                else:
                    end_time = timeConversion.extractISO8601_Local(arr[1])
            except ValueError as e:
                if raise_on_error:
                    raise ValueError("%s:%i: 2nd element: %s"%(fname, lnr, e))
                else:
                    continue #ignore errors

            out.append((start_time, end_time))
        return out # out is a list


# if check_time==None, use current time
def checkDowntime(fname, check_time=None):
        if check_time is None:
            check_time = long(time.time())

        time_list = read(fname)

        for time_tuple in time_list:

            if check_time < time_tuple[0]:  # check_time before start
                continue

            if time_tuple[1] is None: # downtime valid until the end of times, so here we go
                return True

            if check_time <= time_tuple[1]:  # within limit
                return True

        return False # not found a downtime window


# just insert a new line with start time and end time
def addPeriod( fname, start_time, end_time,  create_if_empty=True):
        exists = os.path.isfile(fname)
        if (not exists) and (not create_if_empty):
            raise IOError("[Errno 2] No such file or directory: '%s'"%fname)
       
        with open(fname, 'a+') as fd:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB )

            if not exists: # new file, create header
                fd.write("#%-29s %-30s\n"%("Start", "End"))

            if end_time is not None:
                fd.write("%-30s %-20s\n" % (timeConversion.getISO8601_Local(start_time), timeConversion.getISO8601_Local(end_time)))
            else:
                fd.write("%-30s %-30s\n" % (timeConversion.getISO8601_Local(start_time), "None"))
        
        return 0


# end a downtime (not a scheduled one)
# if end_time==None, use current time
def endDowntime(fname, end_time=None):

        if end_time is None:
            end_time = long(time.time())
    
        try:
            with open(fname, 'r+') as fd:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                # read the old info
                inlines = fd.readlines()

                outlines=[]
                lnr=0
                closed_nr=0


                for long_line in inlines:
                    lnr+=1
                    line = long_line.strip()

                    if len(line)==0:
                        outlines.append(long_line)
                        continue # pass on empty lines
                    if line[0:1]=='#':
                        outlines.append(long_line)
                        continue # pass on comments

                    arr = line.split()
                    if len(arr)<2:
                        outlines.append(long_line)
                        continue # pass on malformed lines

                    #make sure this is for the right entry
                    #if ((entry!="All")and(len(arr)>2)and(entry!=arr[2])):
                    #    outlines.append(long_line)
                    #    continue
                    #if ((entry=="All")and(len(arr)>2)and("factory"==arr[2])):
                    #    outlines.append(long_line)
                    #    continue
                    #if ((frontend!="All")and(len(arr)>3)and(frontend!=arr[3])):
                    #    outlines.append(long_line)
                    #    continue
                    #make sure that this time tuple applies to this security_class
                    #if ((security_class!="All")and(len(arr)>4)and(security_class!=arr[4])):
                    #    outlines.append(long_line)
                    #    continue

                    cur_start_time = 0
                    cur_end_time = 0
                    if arr[0] != 'None':
                        cur_start_time = timeConversion.extractISO8601_Local(arr[0])
                    if arr[1] != 'None':
                        cur_end_time   = timeConversion.extractISO8601_Local(arr[1])
                    # open period -> close
                    if arr[1] == 'None' or ((cur_start_time < long(time.time())) and (cur_end_time > end_time)):
                        outlines.append("%-30s %-30s" % (arr[0], timeConversion.getISO8601_Local(end_time)))
                        outlines.append("\n")
                        closed_nr += 1
                    else:
                        outlines.append(long_line) # closed just pass on

                    #Keep parsing file, since there may be multiple downtimes
                    #pass # end for

                # go back to start to rewrite
                fd.seek(0)
                fd.writelines(outlines)
                fd.truncate()
        except IOError:
            return 0 # no file -> nothing to end

        return closed_nr


def printDowntime(fname, check_time=None):
        if check_time is None:
            check_time = long(time.time())

        time_list=read(fname)

        for time_tuple in time_list:
            if check_time < time_tuple[0]:
                continue
            if (time_tuple[1] is not None) and (check_time>time_tuple[1]):
                continue
            print("%-30s Down"%("Frontend"))
