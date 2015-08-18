#
# Project:
#   glideinWMS
#
# File Version: 
#
# Description:
#   This module implements the basic functions needed
#   to interface to rrdtool
#
# Author:
#   Igor Sfiligoi
#

import string
import time
try:
    import rrdtool #@UnresolvedImport
except:
    pass
import subprocess
import shlex
import subprocessSupport

class BaseRRDSupport:
    #############################################################
    def __init__(self, rrd_obj):
        self.rrd_obj = rrd_obj

    def isDummy(self):
        return (self.rrd_obj is None)

    #############################################################
    # The default will do nothing
    # Children should overwrite it, if needed
    def get_disk_lock(self, fname):
        return dummy_disk_lock()

    #############################################################
    # The default will do nothing
    # Children should overwrite it, if needed
    def get_graph_lock(self, fname):
        return dummy_disk_lock()

    #############################################################
    def create_rrd(self,
                   rrdfname,
                   rrd_step, rrd_archives,
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
        self.create_rrd_multi(rrdfname,
                              rrd_step, rrd_archives,
                              (rrd_ds,))
        return

    #############################################################
    def create_rrd_multi(self,
                         rrdfname,
                         rrd_step, rrd_archives,
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
        if None == self.rrd_obj:
            return # nothing to do in this case

        # make the start time to be aligned on the rrd_step boundary
        # This is needed for optimal resoultion selection 
        start_time = (long(time.time() - 1)/rrd_step) * rrd_step 
        #print (rrdfname,start_time,rrd_step)+rrd_ds
        args = [str(rrdfname), '-b', '%li' % start_time, '-s', '%i' % rrd_step]
        for rrd_ds in rrd_ds_arr:
            args.append('DS:%s:%s:%i:%s:%s' % rrd_ds)
        for archive in rrd_archives:
            args.append("RRA:%s:%g:%i:%i" % archive)

        lck = self.get_disk_lock(rrdfname)
        try:
            self.rrd_obj.create(*args)
        finally:
            lck.close()
        return

    #############################################################
    def update_rrd(self,
                   rrdfname,
                   time, val):
        """
        Create an RRD archive with a new value

        Arguments:
          rrdfname - File path name of the RRD archive
          time     - When was the value taken
          val      - What vas the value
        """
        if None == self.rrd_obj:
            # nothing to do in this case
            return

        lck = self.get_disk_lock(rrdfname)
        try:
            self.rrd_obj.update(str(rrdfname),'%li:%s'%(time,val))
        finally:
            lck.close()

        return

    #############################################################
    def update_rrd_multi(self,
                         rrdfname,
                         time, val_dict):
        """
        Create an RRD archive with a set of values (possibly all of the supported)

        Arguments:
          rrdfname - File path name of the RRD archive
          time     - When was the value taken
          val_dict - What was the value
        """
        if self.rrd_obj is None:
            return # nothing to do in this case

        args = [str(rrdfname)]
        ds_names = val_dict.keys()
        ds_names.sort()

        ds_names_real = []
        ds_vals = []
        for ds_name in ds_names:
            if val_dict[ds_name] is not None:
                ds_vals.append("%s"%val_dict[ds_name])
                ds_names_real.append(ds_name)

        if len(ds_names_real) == 0:
            return

        args.append('-t')
        args.append(string.join(ds_names_real, ':'))
        args.append(('%li:' % time) + string.join(ds_vals, ':'))
    
        lck = self.get_disk_lock(rrdfname)
        try:
            #print args
            self.rrd_obj.update(*args)
        finally:
            lck.close()
            
        return

    #############################################################
    def rrd2graph(self, fname,
                  rrd_step, ds_name, ds_type,
                  start, end,
                  width, height,
                  title, rrd_files, cdef_arr=None, trend=None,
                  img_format='PNG'):
        """
        Create a graph file out of a set of RRD files

        Arguments:
          fname         - File path name of the graph file
          rrd_step      - Which step should I use in the RRD files
          ds_name       - Which attribute should I use in the RRD files
          ds_type       - Which type should I use in the RRD files
          start,end     - Time points in utime format
          width,height  - Size of the graph
          title         - Title to put in the graph
          rrd_files     - list of RRD files, each being a tuple of (in order)
                rrd_id      - logical name of the RRD file (will be the graph label)
                rrd_fname   - name of the RRD file
                graph_type  - Graph type (LINE, STACK, AREA)
                grpah_color - Graph color in rrdtool format
          cdef_arr      - list of derived RRD values
                          if present, only the cdefs will be plotted
                          each elsement is a tuple of (in order)
                rrd_id        - logical name of the RRD file (will be the graph label)
                cdef_formula  - Derived formula in rrdtool format
                graph_type    - Graph type (LINE, STACK, AREA)
                grpah_color   - Graph color in rrdtool format
          trend         - Trend value in seconds (if desired, None else)
          
        For more details see
          http://oss.oetiker.ch/rrdtool/doc/rrdcreate.en.html
        """
        if None == self.rrd_obj:
            return # nothing to do in this case

        multi_rrd_files = []
        for rrd_file in rrd_files:
            multi_rrd_files.append((rrd_file[0], rrd_file[1], ds_name, ds_type, rrd_file[2], rrd_file[3]))
        return self.rrd2graph_multi(fname, rrd_step, start, end, width, height, title, multi_rrd_files, cdef_arr, trend, img_format)

    #############################################################
    def rrd2graph_now(self, fname,
                      rrd_step, ds_name, ds_type,
                      period, width, height,
                      title, rrd_files, cdef_arr=None, trend=None,
                      img_format='PNG'):
        """
        Create a graph file out of a set of RRD files

        Arguments:
          fname         - File path name of the graph file
          rrd_step      - Which step should I use in the RRD files
          ds_name       - Which attribute should I use in the RRD files
          ds_type       - Which type should I use in the RRD files
          period        - start=now-period, end=now
          width,height  - Size of the graph
          title         - Title to put in the graph
          rrd_files     - list of RRD files, each being a tuple of (in order)
                rrd_id      - logical name of the RRD file (will be the graph label)
                rrd_fname   - name of the RRD file
                graph_type  - Graph type (LINE, STACK, AREA)
                grpah_color - Graph color in rrdtool format
          cdef_arr      - list of derived RRD values
                          if present, only the cdefs will be plotted
                          each elsement is a tuple of (in order)
                rrd_id        - logical name of the RRD file (will be the graph label)
                cdef_formula  - Derived formula in rrdtool format
                graph_type    - Graph type (LINE, STACK, AREA)
                grpah_color   - Graph color in rrdtool format
          trend         - Trend value in seconds (if desired, None else)
          
        For more details see
          http://oss.oetiker.ch/rrdtool/doc/rrdcreate.en.html
        """
        now = long(time.time())
        start = ((now-period)/rrd_step)*rrd_step
        end = ((now-1)/rrd_step)*rrd_step
        return self.rrd2graph(fname, rrd_step, ds_name, ds_type, start, end, width, height, title, rrd_files, cdef_arr, trend, img_format)

    #############################################################
    def rrd2graph_multi(self, fname,
                        rrd_step,
                        start, end,
                        width, height,
                        title, rrd_files, cdef_arr=None, trend=None,
                        img_format='PNG'):
        """
        Create a graph file out of a set of RRD files

        Arguments:
          fname         - File path name of the graph file
          rrd_step      - Which step should I use in the RRD files
          start,end     - Time points in utime format
          width,height  - Size of the graph
          title         - Title to put in the graph
          rrd_files     - list of RRD files, each being a tuple of (in order)
                rrd_id      - logical name of the RRD file (will be the graph label)
                rrd_fname   - name of the RRD file
                ds_name     - Which attribute should I use in the RRD files
                ds_type     - Which type should I use in the RRD files
                graph_type  - Graph type (LINE, STACK, AREA)
                graph_color - Graph color in rrdtool format
          cdef_arr      - list of derived RRD values
                          if present, only the cdefs will be plotted
                          each elsement is a tuple of (in order)
                rrd_id        - logical name of the RRD file (will be the graph label)
                cdef_formula  - Derived formula in rrdtool format
                graph_type    - Graph type (LINE, STACK, AREA)
                grpah_color   - Graph color in rrdtool format
          trend         - Trend value in seconds (if desired, None else)
          img_format    - format of the graph file (default PNG)
          
        For more details see
          http://oss.oetiker.ch/rrdtool/doc/rrdcreate.en.html
        """
        if None == self.rrd_obj:
            return # nothing to do in this case

        args = [str(fname), '-s', '%li' % start, '-e', '%li' % end, '--step', '%i' % rrd_step, '-l', '0', '-w', '%i' % width, '-h', '%i' % height, '--imgformat', str(img_format), '--title', str(title)]
        for rrd_file in rrd_files:
            ds_id = rrd_file[0]
            ds_fname = rrd_file[1]
            ds_name = rrd_file[2]
            ds_type = rrd_file[3]
            if trend is None:
                args.append(str("DEF:%s=%s:%s:%s" % (ds_id, ds_fname, ds_name, ds_type)))
            else:
                args.append(str("DEF:%s_inst=%s:%s:%s" % (ds_id, ds_fname, ds_name, ds_type)))
                args.append(str("CDEF:%s=%s_inst,%i,TREND" % (ds_id, ds_id, trend)))

        plot_arr = rrd_files
        if cdef_arr is not None:
            # plot the cdefs not the files themselves, when we have them
            plot_arr = cdef_arr

            for cdef_el in cdef_arr:
                ds_id = cdef_el[0]
                cdef_formula = cdef_el[1]
                ds_graph_type = rrd_file[2]
                ds_color = rrd_file[3]
                args.append(str("CDEF:%s=%s" % (ds_id, cdef_formula)))
        else:
            plot_arr = []
            for rrd_file in rrd_files:
                plot_arr.append((rrd_file[0], None, rrd_file[4], rrd_file[5]))


        if plot_arr[0][2] == "STACK":
            # add an invisible baseline to stack upon
            args.append("AREA:0")

        for plot_el in plot_arr:
            ds_id = plot_el[0]
            ds_graph_type = plot_el[2]
            ds_color = plot_el[3]
            args.append("%s:%s#%s:%s" % (ds_graph_type, ds_id, ds_color, ds_id))
            

        args.append("COMMENT:Created on %s" % time.strftime("%b %d %H\:%M\:%S %Z %Y"))

    
        try:
            lck = self.get_graph_lock(fname)
            try:
                self.rrd_obj.graph(*args)
            finally:
                lck.close()
        except:
            print "Failed graph: %s" % str(args)

        return args

    #############################################################
    def rrd2graph_multi_now(self, fname,
                            rrd_step,
                            period, width, height,
                            title, rrd_files, cdef_arr=None, trend=None,
                            img_format='PNG'):
        """
        Create a graph file out of a set of RRD files

        Arguments:
          fname         - File path name of the graph file
          rrd_step      - Which step should I use in the RRD files
          period        - start=now-period, end=now
          width,height  - Size of the graph
          title         - Title to put in the graph
          rrd_files     - list of RRD files, each being a tuple of (in order)
                rrd_id      - logical name of the RRD file (will be the graph label)
                rrd_fname   - name of the RRD file
                ds_name     - Which attribute should I use in the RRD files
                ds_type     - Which type should I use in the RRD files
                graph_type  - Graph type (LINE, STACK, AREA)
                graph_color - Graph color in rrdtool format
          cdef_arr      - list of derived RRD values
                          if present, only the cdefs will be plotted
                          each elsement is a tuple of (in order)
                rrd_id        - logical name of the RRD file (will be the graph label)
                cdef_formula  - Derived formula in rrdtool format
                graph_type    - Graph type (LINE, STACK, AREA)
                grpah_color   - Graph color in rrdtool format
          trend         - Trend value in seconds (if desired, None else)
          img_format    - format of the graph file (default PNG)
          
        For more details see
          http://oss.oetiker.ch/rrdtool/doc/rrdcreate.en.html
        """
        now = long(time.time())
        start = ((now-period)/rrd_step)*rrd_step
        end = ((now-1)/rrd_step)*rrd_step
        return self.rrd2graph_multi(fname, rrd_step, start, end, width, height, title, rrd_files, cdef_arr, trend, img_format)

    ###################################################
    def fetch_rrd(self, filename, CF, resolution = None, start = None,
                  end = None, daemon = None):
        """
        Fetch will analyze the RRD and try to retrieve the data in the
        resolution requested.

        Arguments:
          filename      -the name of the RRD you want to fetch data from
          CF            -the consolidation function that is applied to the data
                         you want to fetch (AVERAGE, MIN, MAX, LAST)
          resolution    -the interval you want your values to have
                         (default 300 sec)
          start         -start of the time series (default end - 1day)
          end           -end of the time series (default now)
          daemon        -Address of the rrdcached daemon. If specified, a flush
                         command is sent to the server before reading the RRD
                         files. This allows rrdtool to return fresh data even
                         if the daemon is configured to cache values for a long
                         time.

        For more details see
          http://oss.oetiker.ch/rrdtool/doc/rrdcreate.en.html
        """
        if None == self.rrd_obj:
            return # nothing to do in this case

        if CF in ('AVERAGE', 'MIN', 'MAX', 'LAST'):
            consolFunc = str(CF)
        else:
            raise RuntimeError,"Invalid consolidation function %s"%CF
        args = [str(filename), consolFunc]
        if resolution is not None:
            args.append('-r')
            args.append(str(resolution))
        if end is not None:
            args.append('-e')
            args.append(str(end))
        if start is not None:
            args.append('-s')
            args.append(str(start))
        if daemon is not None:
            args.append('--daemon')
            args.append(str(daemon))

        return self.rrd_obj.fetch(*args)
        
    def verify_rrd(self, filename, expected_dict):
        """
        Verifies that an rrd matches a dictionary of datastores.
        This will return a tuple of arrays ([missing],[extra]) attributes
    
        @param filename: filename of the rrd to verify
        @param expected_dict: dictionary of expected values
        @return: A two-tuple of arrays ([missing attrs],[extra attrs])
    
        """
        rrd_info=self.rrd_obj.info(filename)
        rrd_dict={}
        for key in rrd_info.keys():
            #rrdtool 1.3
            if key[:3]=="ds[":
                rrd_dict[key[3:].split("]")[0]]=None
            #rrdtool 1.2
            if key=="ds":
                for dskey in rrd_info[key].keys():
                    rrd_dict[dskey]=None
        missing=[]
        extra=[]
        for t in expected_dict.keys():
            if t not in rrd_dict.keys():
                missing.append(t)
        for t in rrd_dict.keys():
            if t not in expected_dict.keys():
                extra.append(t)
        return (missing,extra)

# This class uses the rrdtool module for rrd_obj
class ModuleRRDSupport(BaseRRDSupport):
    def __init__(self):
        BaseRRDSupport.__init__(self, rrdtool)

# This class uses rrdtool cmdline for rrd_obj
class ExeRRDSupport(BaseRRDSupport):
    def __init__(self):
        BaseRRDSupport.__init__(self, rrdtool_exe())

# This class tries to use the rrdtool module for rrd_obj
# then tries the rrdtool cmdline
# will use None if needed
class rrdSupport(BaseRRDSupport):
    def __init__(self):
        try:
            rrd_obj = rrdtool
        except ImportError:
            try:
                rrd_obj = rrdtool_exe()
            except:
                rrd_obj = None
        BaseRRDSupport.__init__(self, rrd_obj)


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
    l2 = []
    for e in arglist:
        l2.append('"%s"' % e)
    return string.join(l2)

#################################
# this class is used in place of the rrdtool
# python module, if that one is not available
class rrdtool_exe:
    def __init__(self):
        self.rrd_bin = (subprocessSupport.iexe_cmd("which rrdtool").split('\n')[0]).strip()

    def create(self,*args):
        cmdline = '%s create %s'%(self.rrd_bin,string_quote_join(args))
        outstr = subprocessSupport.iexe_cmd(cmdline)
        return

    def update(self,*args):
        cmdline = '%s update %s'%(self.rrd_bin,string_quote_join(args))
        outstr = subprocessSupport.iexe_cmd(cmdline)
        return
    
    def info(self,*args):
        cmdline = '%s info %s'%(self.rrd_bin,string_quote_join(args))
        outstr = subprocessSupport.iexe_cmd(cmdline).split('\n')
        outarr = {}
        for line in outstr:
            linearr = line.split('=')
            outarr[linearr[0]] = linearr[1]
        return outarr
    
    def dump(self,*args):
        """
        Run rrd_tool dump

        Input is usually just the file name.
        Output is a list of lines, as returned from rrdtool.
        """
        cmdline = '%s dump %s' % (self.rrd_bin, string_quote_join(args))
        outstr = subprocessSupport.iexe_cmd(cmdline).split('\n')
        return outstr
    
    def restore(self,*args):
        cmdline = '%s restore %s'%(self.rrd_bin,string_quote_join(args))
        outstr = subprocessSupport.iexe_cmd(cmdline)
        return

    def graph(self,*args):
        cmdline = '%s graph %s'%(self.rrd_bin, string_quote_join(args))
        outstr = subprocessSupport.iexe_cmd(cmdline)
        return

def addDataStore(filenamein, filenameout, attrlist):
    """
    Add a list of data stores to a rrd export file
    This will essentially add attributes to the end of a rrd row

    @param filenamein: filename path of a rrd exported with rrdtool dump
    @param filenameout: filename path of output xml with datastores added
    @param attrlist: array of datastores to add
    """
    f=open(filenamein,"r")
    out=open(filenameout,"w")
    parse=False
    writenDS=False
    for line in f:
        if ("<rra>" in line) and (not writenDS):
            for a in attrlist:
                out.write("<ds>\n")
                out.write("<name> %s </name>\n"%a)
                out.write("<type> GAUGE </type>\n")
                out.write("<minimal_heartbeat> 1800 </minimal_heartbeat>\n")
                out.write("<min> NaN </min>\n")
                out.write("<max> NaN </max>\n")
                out.write("<!-- PDP Status -->\n")
                out.write("<last_ds> UNKN </last_ds>\n")
                out.write("<value> 0 </value>\n")
                out.write("<unknown_sec> 0 </unknown_sec>\n")
                out.write("</ds>\n")
            writenDS=True
        if "</cdp_prep>" in line:
            for a in attrlist:
                out.write("<ds><value> NaN </value>\n")
                out.write("<unknown_datapoints> 0 </unknown_datapoints></ds>\n")
        if "</database>" in line:
            parse=False
        if parse:
            out.write(line[:-7])
            for a in attrlist:
                out.write("<v> NaN </v>")
            out.write(line[-7:])
        else:
            out.write(line)
        if "<database>" in line:
            parse=True

