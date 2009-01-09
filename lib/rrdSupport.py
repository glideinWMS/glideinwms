#
# Description:
#   This module implements the basic functions needed
#   to interface to rrdtool
#
# Author:
#   Igor Sfiligoi
#

import string,time

class BaseRRDSupport:
    #############################################################
    def __init__(self,rrd_obj):
        self.rrd_obj=rrd_obj

    #############################################################
    # The default will do nothing
    # Children should overwrite it, if needed
    def get_disk_lock(self):
        return dummy_disk_lock()

    #############################################################
    def create_rrd(self,
                   rrdfname,
                   rrd_step,rrd_archives,
                   rrd_ds):
        """
        Create a new RRD archive

        Arguments:
          rrdfname     - File path name of the RRD archive
          rrd_step     - base interval in seconds
          rrd_archives - list of tuples, each containing the following fileds (in order)
            CF    - consolidation function (usually AVERAGE)
            xff   - xfiles factor (fraction that can be unknown)
            steps - how many of these primary data points are used to build a consolidated data point
            rows  - how many generations of data values are kept
          rrd_ds       - a tuple containing the following fields (in order)
            ds-name   - attribute name
            DST       - Data Source Type (usually GAUGE)
            heartbeat - the maximum number of seconds that may pass between two updates before it becomes unknown
            min       - min value
            max       - max value
          
        For more details see
          http://oss.oetiker.ch/rrdtool/doc/rrdcreate.en.html
        """
        if None==self.rrd_obj:
            return # nothing to do in this case

        start_time=(long(time.time()-1)/rrd_step)*rrd_step # make the start time to be aligned on the rrd_step boundary - needed for optimal resoultion selection 
        #print (rrdfname,start_time,rrd_step)+rrd_ds
        args=[str(rrdfname),'-b','%li'%start_time,'-s','%i'%rrd_step,'DS:%s:%s:%i:%s:%s'%rrd_ds]
        for archive in rrd_archives:
            args.append("RRA:%s:%g:%i:%i"%archive)

        lck=self.get_disk_lock()
        try:
            self.rrd_obj.create(*args)
        finally:
            lck.close()
        return

    #############################################################
    def create_rrd_multi(self,
                         rrdfname,
                         rrd_step,rrd_archives,
                         rrd_ds_arr):
        """
        Create a new RRD archive

        Arguments:
          rrdfname     - File path name of the RRD archive
          rrd_step     - base interval in seconds
          rrd_archives - list of tuples, each containing the following fileds (in order)
            CF    - consolidation function (usually AVERAGE)
            xff   - xfiles factor (fraction that can be unknown)
            steps - how many of these primary data points are used to build a consolidated data point
            rows  - how many generations of data values are kept
          rrd_ds_arr   - list of tuples, each containing the following fields (in order)
            ds-name   - attribute name
            DST       - Data Source Type (usually GAUGE)
            heartbeat - the maximum number of seconds that may pass between two updates before it becomes unknown
            min       - min value
            max       - max value
          
        For more details see
          http://oss.oetiker.ch/rrdtool/doc/rrdcreate.en.html
        """
        if None==self.rrd_obj:
            return # nothing to do in this case

        start_time=(long(time.time()-1)/rrd_step)*rrd_step # make the start time to be aligned on the rrd_step boundary - needed for optimal resoultion selection 
        #print (rrdfname,start_time,rrd_step)+rrd_ds
        args=[str(rrdfname),'-b','%li'%start_time,'-s','%i'%rrd_step]
        for rrd_ds in rrd_ds_arr:
            args.append('DS:%s:%s:%i:%s:%s'%rrd_ds)
        for archive in rrd_archives:
            args.append("RRA:%s:%g:%i:%i"%archive)

        lck=self.get_disk_lock()
        try:
            self.rrd_obj.create(*args)
        finally:
            lck.close()
        return

    #############################################################
    def update_rrd(self,
                   rrdfname,
                   time,val):
        """
        Create an RRD archive with a new value

        Arguments:
          rrdfname - File path name of the RRD archive
          time     - When was the value taken
          val      - What vas the value
        """
        if None==self.rrd_obj:
            return # nothing to do in this case

        lck=self.get_disk_lock()
        try:
            self.rrd_obj.update(str(rrdfname),'%li:%i'%(time,val))
        finally:
            lck.close()

        return

    #############################################################
    def update_rrd_multi(self,
                         rrdfname,
                         time,val_dict):
        """
        Create an RRD archive with a set of values (possibly all of the supported)

        Arguments:
          rrdfname - File path name of the RRD archive
          time     - When was the value taken
          val_dict - What was the value
        """
        if None==self.rrd_obj:
            return # nothing to do in this case

        args=[str(rrdfname)]
        ds_names=val_dict.keys()
        ds_names.sort()

        ds_vals=[]
        for ds_name in ds_names:
            ds_vals.append("%i"%val_dict[ds_name])

        args.append('-t')
        args.append(string.join(ds_names,':'))
        args.append(('%li:'%time)+string.join(ds_vals,':'))
    
        lck=self.get_disk_lock()
        try:
            print args
            self.rrd_obj.update(*args)
        finally:
            lck.close()
            
        return


# This class uses the rrdtool module for rrd_obj
class ModuleRRDSupport(BaseRRDSupport):
    def __init__(self):
        import rrdtool
        BaseRRDSupport.__init__(self,rrdtool)

# This class uses rrdtool cmdline for rrd_obj
class ExeRRDSupport(BaseRRDSupport):
    def __init__(self):
        BaseRRDSupport.__init__(self,rrdtool_exe())

# This class tries to use the rrdtool module for rrd_obj
# then tries the rrdtool cmdline
# will use None if needed
class rrdSupport(BaseRRDSupport):
    def __init__(self):
        try:
            import rrdtool
            rrd_obj=rrdtool
        except ImportError,e:
            try:
                rrd_obj=rrdtool_exe()
            except:
                rrd_obj=None
        BaseRRDSupport.__init__(self,rrd_obj)


##################################################################
# INTERNAL, do not use directly
##################################################################


##################################
# Dummy, do nothing
# Used just to get a object
class DummyDiskLock:
    def close(self):
        return

def dummy_disk_lock():
    return DummyDiskLock()

#################################
def string_quote_join(arglist):
    l2=[]
    for e in arglist:
        l2.append('"%s"'%e)
    return string.join(l2)

#################################
# this class is used in place of the rrdtool
# python module, if that one is not available
class rrdtool_exe:
    def __init__(self):
        import popen2
        self.popen2_obj=popen2
        self.rrd_bin=self.iexe_cmd("which rrdtool")[0][:-1]

    def create(self,*args):
        cmdline='%s create %s'%(self.rrd_bin,string_quote_join(args))
        outstr=self.iexe_cmd(cmdline)
        return

    def update(self,*args):
        cmdline='%s update %s'%(self.rrd_bin,string_quote_join(args))
        outstr=self.iexe_cmd(cmdline)
        return

    def graph(self,*args):
        cmdline='%s graph %s'%(self.rrd_bin,string_quote_join(args))
        outstr=self.iexe_cmd(cmdline)
        return

    ##########################################
    def iexe_cmd(cmd):
        child=self.popen2_obj.Popen3(cmd,True)
        child.tochild.close()
        tempOut = child.fromchild.readlines()
        child.fromchild.close()
        tempErr = child.childerr.readlines()
        child.childerr.close()
        try:
            errcode=child.wait()
        except OSError, e:
            if len(tempOut)!=0:
                # if there was some output, it is probably just a problem of timing
                # have seen a lot of those when running very short processes
                errcode=0
            else:
                raise RuntimeError, "Error running '%s'\nStdout:%s\nStderr:%s\nException OSError: %s"%(cmd,tempOut,tempErr,e)
        if (errcode!=0):
            raise RuntimeError, "Error running '%s'\ncode %i:%s"%(cmd,errcode,tempErr)
        return tempOut
