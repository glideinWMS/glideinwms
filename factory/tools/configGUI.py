#!/usr/bin/env python
#
# Project:
#   glideinWMS
#
# File Version: 
#
# Description:
#   This program implements a GUI
#   for the configuration of the glideinWMS factory
#
# Author:
#   Robert Chen @UCSD
#

#import wxWidgets
import wx
import wx.grid

#import system libraries
import sys
import os.path
import copy

STARTUP_DIR=sys.path[0]

# import glideinWMS libraries
sys.path.append(os.path.join(STARTUP_DIR,"../../.."))
from glideinwms.creation.lib import cgWParams

# current entry for site
currentSiteEntry = ""

#configuration file, temporary one
cfg = None
rowToRemove = ""
defaultSite = ""
offline = 0

class MyGrid(wx.grid.Grid):

    def __init__(self, parent):
        wx.grid.Grid.__init__(self, parent, -1)

        self.CreateGrid(0, 8)
        self.RowLabelSize = 20
        self.ColLabelSize = 20

        self.Bind(wx.grid.EVT_GRID_CELL_LEFT_DCLICK, self.onToggle)
        self.Bind(wx.grid.EVT_GRID_CELL_CHANGE, self.onEdit)
        
    # user edited the grid   values
    
    def onEdit(self, evt):
        global currentSiteEntry
        
        row = evt.GetRow()
        column  = evt.GetCol()
        property = self.GetColLabelValue(column)
        attribute = self.GetCellValue(row, 0).encode('ascii', 'ignore')
        
        cfg.data["entries"][currentSiteEntry]['attrs'][attribute][property] = self.GetCellValue(row, column)
        
    def onToggle(self, evt):
        global currentSiteEntry, cfg
        
        row = evt.GetRow()
        column  = evt.GetCol()
        
        # color toggling only works on non data cells
        if(column < 3):
            return
        
        attribute = self.GetCellValue(row, 0)
        property = self.GetColLabelValue(column)
        
        # in case of Unicode wxWidgets
        attribute = attribute.encode('ascii','ignore')
        


        # was set to True, now make it False
        if(self.GetCellBackgroundColour(row, column) ==  wx.Colour(204, 255, 153) ):
            cfg.data["entries"][currentSiteEntry]['attrs'][attribute][ property] =  False
            self.SetCellValue(row, column, "False")
            self.SetCellBackgroundColour(row, column, wx.Colour(255, 204, 153))
            
            # dirty hack to make changes immediately visible
            self.MoveCursorDown(False)
            self.MoveCursorUp(False)
        # was set to False, now make it True
        else:
            cfg.data["entries"][currentSiteEntry]['attrs'][attribute][ property] =  True
            self.SetCellValue(row, column, "True")
            self.SetCellBackgroundColour(row, column, wx.Colour(204, 255, 153) )
            
            self.MoveCursorDown(False)
            self.MoveCursorUp(False)
        

class GlideFrame(wx.Frame):

    def __init__(self, *args, **kwds):
        
        kwds["style"] = wx.DEFAULT_FRAME_STYLE
        wx.Frame.__init__(self, *args, **kwds)
        self.split_pane = wx.SplitterWindow(self, -1, style=wx.SP_3D | wx.SP_BORDER)
        self.right_pane_panel = wx.Panel(self.split_pane, -1)
        self.config_notebook = wx.Notebook(self.right_pane_panel, -1, style=0)
        self.notebook_pane_2 = wx.Panel(self.config_notebook, -1)
        self.notebook_pane_1 = wx.Panel(self.config_notebook, -1)
        self.max_jobs_divider_staticbox = wx.StaticBox(self.notebook_pane_1, -1, "max_jobs")
        self.sizer_2_staticbox = wx.StaticBox(self.notebook_pane_1, -1, "release")
        self.sizer_3_staticbox = wx.StaticBox(self.notebook_pane_1, -1, "remove")
        self.sizer_4_staticbox = wx.StaticBox(self.notebook_pane_1, -1, "submit")
        self.left_pane_panel = wx.Panel(self.split_pane, -1)
        self.sites_list = wx.ListCtrl(self.left_pane_panel, -1, style=wx.LC_REPORT | wx.SUNKEN_BORDER)
        self.label_1 = wx.StaticText(self.notebook_pane_1, -1, "Held:")
        self.config_max_jobs_held = wx.TextCtrl(self.notebook_pane_1, 1, "")
        self.label_2 = wx.StaticText(self.notebook_pane_1, -1, "Idle:")
        self.config_max_jobs_idle = wx.TextCtrl(self.notebook_pane_1, 2, "")
        self.label_3 = wx.StaticText(self.notebook_pane_1, -1, "Running:")
        self.config_max_jobs_running = wx.TextCtrl(self.notebook_pane_1, 3, "")
        self.label_4 = wx.StaticText(self.notebook_pane_1, -1, "Max Per Cycle:")
        self.config_release_max_per_cycle = wx.TextCtrl(self.notebook_pane_1, 4, "")
        self.label_5 = wx.StaticText(self.notebook_pane_1, -1, "Sleep:")
        self.config_release_sleep = wx.TextCtrl(self.notebook_pane_1, 5, "")
        self.label_6 = wx.StaticText(self.notebook_pane_1, -1, "Max Per Cycle:")
        self.config_remove_max_per_cycle = wx.TextCtrl(self.notebook_pane_1, 6, "")
        self.label_7 = wx.StaticText(self.notebook_pane_1, -1, "Sleep:")
        self.config_remove_sleep = wx.TextCtrl(self.notebook_pane_1, 7, "")
        self.label_8 = wx.StaticText(self.notebook_pane_1, -1, "Cluster Size:")
        self.config_submit_cluster_size = wx.TextCtrl(self.notebook_pane_1, 8, "")
        self.label_9 = wx.StaticText(self.notebook_pane_1, -1, "Max Per Cycle:")
        self.config_submit_max_per_cycle = wx.TextCtrl(self.notebook_pane_1, 9, "")
        self.label_10 = wx.StaticText(self.notebook_pane_1, -1, "Sleep:")
        self.config_submit_sleep = wx.TextCtrl(self.notebook_pane_1, 10, "")
        

        self.attr_grid = MyGrid(self.notebook_pane_2)
        
        
        self.__set_properties()
        self.__do_layout()
        
        self.Bind(wx.EVT_LIST_ITEM_SELECTED, self.do_select, self.sites_list)
        self.Bind(wx.EVT_LIST_ITEM_RIGHT_CLICK, self.do_enableDisable, self.sites_list)
        
        
        self.attr_grid.Bind(wx.grid.EVT_GRID_CELL_RIGHT_CLICK, self.right_cb)
        
        
        global cfg
        global cfg
        global dataFile
        global defaultSite
       
        #self.targetFile = os.path.join(STARTUP_DIR,'glideinWMS.xml')

        self.attr_grid.SetColLabelValue(0, "attribute")
        self.attr_grid.SetColLabelValue(1, "type")
        self.attr_grid.SetColLabelValue(2, "value")
        self.attr_grid.SetColLabelValue(3, "const")
        self.attr_grid.SetColLabelValue(4, "glidein_publish")
        self.attr_grid.SetColLabelValue(5, "job_publish")
        self.attr_grid.SetColLabelValue(6, "parameter")
        self.attr_grid.SetColLabelValue(7, "publish")
        
        # menu actions
        self.QUIT_COMMAND = 0
        self.OPEN_COMMAND = 10
        self.SAVE_COMMAND = 20
        self.SAVEAS_COMMAND = 30
        self.ADD = 40
        self.REMOVE = 50
        self.DISABLE = 60
        self.ENABLE = 70
        
        menubar = wx.MenuBar()
        file = wx.Menu()
        
        file.Append(self.OPEN_COMMAND, 'Open', 'Open a glideWMSGUI file')
        file.Append(self.SAVE_COMMAND, 'Save', 'Save the file being edited')
        file.Append(self.SAVEAS_COMMAND, 'Save As...', 'Save the file being edited')
        
        file.Append(self.QUIT_COMMAND, 'Quit', 'Quit program')
        
        wx.EVT_MENU(self, self.QUIT_COMMAND, self.quit)
        wx.EVT_MENU(self, self.OPEN_COMMAND, self.openFile)
        wx.EVT_MENU(self, self.SAVE_COMMAND, self.ApplyChange)
        wx.EVT_MENU(self, self.SAVEAS_COMMAND, self.ApplyChange)
        
        wx.EVT_MENU(self, self.DISABLE, self.disable)
        wx.EVT_MENU(self, self.ENABLE,  self.enable)
        

        menubar.Append(file, '&File')
        self.SetMenuBar(menubar)

   
        # set to acceptable width, so that attributes can be read
        self.attr_grid.SetColSize(0, 200)
        self.attr_grid.SetColSize(4, 100)
        self.attr_grid.SetColSize(5, 100)
        
    # Create Columns for the Sites List
        siteColumn = wx.ListItem()
        siteColumn.SetText("Entry Name")
        
        # set column width
        siteColumn.SetWidth(500)

        self.sites_list.InsertColumnItem( 0, siteColumn )
  
        # if command line argument is set, load that config file
        if(len(sys.argv) > 1):
            self.targetFile = sys.argv[1]
            cfg=cgWParams.GlideinParams('','',['',self.targetFile])
            self.doTable()
        # parse GlideinWMS XML file

        #cfg=cgWParams.GlideinParams('','',['',self.targetFile])

        # default entry code
        # we're going to use a shortcut hack here and copy the first entry, only changing what we need
        #cfg.data['entries'][u'DEFAULT'] = cfg.data['entries'][cfg.data['entries'].keys()[0]].copy()

#        print cfg.data['entries'][u'DEFAULT']

        # open condor_vars.lst and condor_vars.lst.entry for parsing  
        #fcondor_vars = open("../../creation/web_base/condor_vars.lst")
        #fcondor_vars_lst = open("../../creation/web_base/condor_vars.lst.entry")

        #condor_vars = fcondor_vars.readlines()
        #condor_vars_lst = fcondor_vars_lst.readlines()
        
        #merge the two lists
        #for line in condor_vars_lst:
        #    condor_vars.append(line)

        #print condor_vars
        #for i in condor_vars:
            # ignore comments
        #    if i[0]!= "#":
        #        defaultentr = i.split("\t")[0].strip()
        #        if(defaultentr!=""):
        #            cfg.data['entries'][u'DEFAULT']['attrs'][defaultentr] = cgWParams.cWParams.SubParams({
        #                u"comment":u"None",
        #                u"const":u"False",
        #                u"glidein_publish":u"False",
        #                u"job_publish":u"False",
        #                u"parameter":u"False",
        #                u"publish":u"False",
        #                u"type":u"None",
        #                u"value":u"None"
        #                })
     

        # reload file       
        #cfg.save_into_file_wbackup(self.targetFile)
    
        #del cfg
        #cfg = cgWParams.GlideinParams('','',['', self.targetFile])

        # get only entries
        #self.doTable()
        
    def __set_properties(self):
        
        self.SetTitle("GlideWMS Configuration")
        self.SetSize((1296, 816))
        self.sites_list.SetMinSize((490, 417))
        self.left_pane_panel.SetMinSize((668, 769))
        self.label_1.SetForegroundColour(wx.Colour(204, 50, 50))
        self.config_max_jobs_held.SetBackgroundColour(wx.Colour(255, 255, 153))
        self.label_2.SetForegroundColour(wx.Colour(204, 50, 50))
        self.config_max_jobs_idle.SetBackgroundColour(wx.Colour(255, 255, 153))
        self.label_3.SetForegroundColour(wx.Colour(204, 50, 50))
        self.config_max_jobs_running.SetBackgroundColour(wx.Colour(255, 255, 153))
        self.label_4.SetForegroundColour(wx.Colour(204, 50, 50))
        self.config_release_max_per_cycle.SetBackgroundColour(wx.Colour(255, 255, 153))
        self.label_5.SetForegroundColour(wx.Colour(204, 50, 50))
        self.config_release_sleep.SetBackgroundColour(wx.Colour(255, 255, 153))
        self.label_6.SetForegroundColour(wx.Colour(204, 50, 50))
        self.config_remove_max_per_cycle.SetBackgroundColour(wx.Colour(255, 255, 153))
        self.label_7.SetForegroundColour(wx.Colour(204, 50, 50))
        self.config_remove_sleep.SetBackgroundColour(wx.Colour(255, 255, 153))
        self.label_8.SetForegroundColour(wx.Colour(204, 50, 50))
        self.config_submit_cluster_size.SetBackgroundColour(wx.Colour(255, 255, 153))
        self.label_9.SetForegroundColour(wx.Colour(204, 50, 50))
        self.config_submit_max_per_cycle.SetBackgroundColour(wx.Colour(255, 255, 153))
        self.label_10.SetForegroundColour(wx.Colour(204, 50, 50))
        self.config_submit_sleep.SetBackgroundColour(wx.Colour(255, 255, 153))
        

    def __do_layout(self):
        
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        right_pane_sizer = wx.BoxSizer(wx.HORIZONTAL)
        sizer_1 = wx.BoxSizer(wx.HORIZONTAL)
        config_category_sizer = wx.BoxSizer(wx.VERTICAL)
        sizer_4 = wx.StaticBoxSizer(self.sizer_4_staticbox, wx.HORIZONTAL)
        grid_sizer_4 = wx.GridSizer(3, 2, 0, 0)
        sizer_3 = wx.StaticBoxSizer(self.sizer_3_staticbox, wx.HORIZONTAL)
        grid_sizer_3 = wx.GridSizer(2, 2, 0, 0)
        sizer_2 = wx.StaticBoxSizer(self.sizer_2_staticbox, wx.HORIZONTAL)
        grid_sizer_2 = wx.GridSizer(2, 2, 0, 0)
        max_jobs_divider = wx.StaticBoxSizer(self.max_jobs_divider_staticbox, wx.HORIZONTAL)
        grid_sizer_1 = wx.GridSizer(3, 2, 0, 0)
        left_pane_sizer = wx.BoxSizer(wx.HORIZONTAL)
        left_pane_sizer.Add(self.sites_list, 1, wx.EXPAND, 0)
        self.left_pane_panel.SetSizer(left_pane_sizer)
        grid_sizer_1.Add(self.label_1, 0, 0, 0)
        grid_sizer_1.Add(self.config_max_jobs_held, 0, 0, 0)
        grid_sizer_1.Add(self.label_2, 0, 0, 0)
        grid_sizer_1.Add(self.config_max_jobs_idle, 0, 0, 0)
        grid_sizer_1.Add(self.label_3, 0, 0, 0)
        grid_sizer_1.Add(self.config_max_jobs_running, 0, 0, 0)
        max_jobs_divider.Add(grid_sizer_1, 1, wx.EXPAND, 0)
        config_category_sizer.Add(max_jobs_divider, 1, wx.EXPAND, 0)
        grid_sizer_2.Add(self.label_4, 0, 0, 0)
        grid_sizer_2.Add(self.config_release_max_per_cycle, 0, 0, 0)
        grid_sizer_2.Add(self.label_5, 0, 0, 0)
        grid_sizer_2.Add(self.config_release_sleep, 0, 0, 0)
        sizer_2.Add(grid_sizer_2, 1, wx.EXPAND, 0)
        config_category_sizer.Add(sizer_2, 1, wx.EXPAND, 0)
        grid_sizer_3.Add(self.label_6, 0, 0, 0)
        grid_sizer_3.Add(self.config_remove_max_per_cycle, 0, 0, 0)
        grid_sizer_3.Add(self.label_7, 0, 0, 0)
        grid_sizer_3.Add(self.config_remove_sleep, 0, 0, 0)
        sizer_3.Add(grid_sizer_3, 1, wx.EXPAND, 0)
        config_category_sizer.Add(sizer_3, 1, wx.EXPAND, 0)
        grid_sizer_4.Add(self.label_8, 0, 0, 0)
        grid_sizer_4.Add(self.config_submit_cluster_size, 0, 0, 0)
        grid_sizer_4.Add(self.label_9, 0, 0, 0)
        grid_sizer_4.Add(self.config_submit_max_per_cycle, 0, 0, 0)
        grid_sizer_4.Add(self.label_10, 0, 0, 0)
        grid_sizer_4.Add(self.config_submit_sleep, 0, 0, 0)
        sizer_4.Add(grid_sizer_4, 1, wx.EXPAND, 0)
        config_category_sizer.Add(sizer_4, 1, wx.EXPAND, 0)
        
        self.notebook_pane_1.SetSizer(config_category_sizer)
        
        
        sizer_1.Add(self.attr_grid, 1, wx.EXPAND, 0)
        
        self.notebook_pane_2.SetSizer(sizer_1)
        self.config_notebook.AddPage(self.notebook_pane_1, "Configuration")
        self.config_notebook.AddPage(self.notebook_pane_2, "Attributes")
        right_pane_sizer.Add(self.config_notebook, 1, wx.EXPAND, 0)
        self.right_pane_panel.SetSizer(right_pane_sizer)
        self.split_pane.SplitVertically(self.left_pane_panel, self.right_pane_panel)
        main_sizer.Add(self.split_pane, 1, wx.EXPAND, 0)
        self.SetSizer(main_sizer)
        self.Layout()
    
    def right_cb(self, event):
        global rowToRemove
        
        menu = wx.Menu()
        menu.Append( self.ADD, "Add Attribute","" )
        menu.AppendSeparator()
        menu.Append( self.REMOVE, "Remove Attribute","" )
        
        wx.EVT_MENU( menu, self.ADD, self.MenuSelect )
        wx.EVT_MENU( menu, self.REMOVE, self.MenuSelect )
        rowToRemove = event.GetRow()
        self.PopupMenu( menu, event.GetPosition() +(650,50) )
        
        menu.Destroy()

        
    def MenuSelect(self,event):
        global currentSiteEntry
        global rowToRemove
        global cfg
        
        if(event.GetId() == self.ADD):
            input = wx.GetTextFromUser("Please enter name of new attribute","New Attribute", "");
            if(input == ""):
                pass
            else:
                newRowNumber = self.attr_grid.GetNumberRows()
                self.attr_grid.InsertRows(newRowNumber,1)
                self.attr_grid.SetCellValue(newRowNumber, 0, input)
                
                # initialize new cfg entry
                cfg.data['entries'][currentSiteEntry]['attrs'][input] = cgWParams.cWParams.SubParams({
                u"comment":u"None",
                u"const":u"False",
                u"glidein_publish":u"False",
                u"job_publish":u"False",
                u"parameter":u"False",
                u"publish":u"False",
                u"type":u"None",
                u"value":u"None"
                })
                
                #print cfg.data['entries'][currentSiteEntry]['attrs']['GLEXEC_BIN']
                #print cfg.data['entries'][currentSiteEntry]['attrs'][input]
                
                for i in range(3, 8):
                    self.attr_grid.SetCellBackgroundColour(newRowNumber, i, wx.Colour(255, 204, 153 ))
                    self.attr_grid.SetCellValue(newRowNumber, i, "False")
                    self.attr_grid.SetReadOnly(newRowNumber, i )
                    
        if(event.GetId() == self.REMOVE):
                attribute = self.attr_grid.GetCellValue(rowToRemove, 0)
                self.attr_grid.DeleteRows(int(rowToRemove), 1)
                cfg.data['entries'][currentSiteEntry]['attrs'][attribute]=None
                
    def doTable(self):
        global cfg
        global offline
        # clear all entries
        self.sites_list.DeleteAllItems()
        # get only entries
        for entry in cfg.data["entries"].keys():
            # put enabled servers on top
            if cfg.data["entries"][entry]["enabled"] == "True":
                self.sites_list.InsertStringItem(self.sites_list.GetItemCount() - offline, entry)
                self.sites_list.SetItemBackgroundColour(self.sites_list.GetItemCount()-offline-1, wx.Color(204, 255, 153))
            else:
                self.sites_list.InsertStringItem(self.sites_list.GetItemCount(), entry)
                self.sites_list.SetItemBackgroundColour(self.sites_list.GetItemCount()-1, wx.Color(255, 204, 153))
                offline +=1
        
        
        
    def enable(self, event):
        answer = wx.MessageBox("Enable entry and apply changes?", "Confirm",
                            wx.YES_NO, self);
        if answer == wx.YES:
            cfg.data["entries"][currentSiteEntry]["enabled"] = True
            self.ApplyChange(None)
            self.sites_list.DeleteAllItems()
            self.doTable()
            
    def disable(self, event):
        answer = wx.MessageBox("Disable entry and apply changes?", "Confirm",
                            wx.YES_NO, self);
        if answer == wx.YES:
            cfg.data["entries"][currentSiteEntry]["enabled"] = False
            self.ApplyChange(None)
            self.sites_list.DeleteAllItems()
            self.doTable()
            
    def do_enableDisable(self, event):
        global currentSiteEntry
        
        menu = wx.Menu()
        menu.Append( self.ENABLE, "Enable entry","" )
        menu.AppendSeparator()
        menu.Append( self.DISABLE, "Disable entry","" )
    
        wx.EVT_MENU( menu, self.DISABLE, self.disable )
        wx.EVT_MENU( menu, self.ENABLE, self.enable )
        
        # set currentSiteEntry to the site that was selected
        currentSiteEntry = event.GetText().encode("ascii", "ignore")
        
        self.PopupMenu( menu, event.GetPosition() )
        
        menu.Destroy()
        
    def quit(self, event):
        answer = wx.MessageBox("Are you sure you want to quit?", "Confirm",
                            wx.YES_NO, self);
        if answer == wx.YES:
           answer = wx.MessageBox("Do you want to save?", "Confirm",
                            wx.YES_NO, self);

           if answer == wx.YES:
               cfg.data["entries"][u'DEFAULT'] = None
               cfg.save_into_file_wbackup(self.targetFile)
               sys.exit(1)           

    def openFile(self, event):
        global cfg
        filename = wx.FileSelector("Choose a configuration to load.");
        if(filename == ""):
            pass
        else:
            self.targetFile = filename
            cfg = cgWParams.GlideinParams('','',['',self.targetFile])
            self.doTable()
            
    def do_select(self, event): 
        global currentSiteEntry
        # set currentSiteEntry to the site that was selected
        currentSiteEntry = event.GetText().encode("ascii", "ignore")
        
        # so, for this particular entry, load its config, and get all configuration tags, 
        self.config_max_jobs_held.SetValue(cfg.data["entries"][event.GetText()]["config"]["max_jobs"]["held"])
        self.config_max_jobs_held.Bind(wx.EVT_TEXT, self.onChange)
        
        self.config_max_jobs_idle.SetValue(cfg.data["entries"][event.GetText()]["config"]["max_jobs"]["idle"])
        self.config_max_jobs_idle.Bind(wx.EVT_TEXT, self.onChange)
        self.config_max_jobs_running.SetValue(cfg.data["entries"][event.GetText()]["config"]["max_jobs"]["running"])
        self.config_max_jobs_running.Bind(wx.EVT_TEXT, self.onChange)
        
        self.config_release_max_per_cycle.SetValue(cfg.data["entries"][event.GetText()]["config"]["release"]["max_per_cycle"])
        self.config_release_max_per_cycle.Bind(wx.EVT_TEXT, self.onChange)
        self.config_release_sleep.SetValue(cfg.data["entries"][event.GetText()]["config"]["release"]["sleep"])
        self.config_release_sleep.Bind(wx.EVT_TEXT, self.onChange)
        
        self.config_remove_max_per_cycle.SetValue(cfg.data["entries"][event.GetText()]["config"]["remove"]["max_per_cycle"])
        self.config_remove_max_per_cycle.Bind(wx.EVT_TEXT, self.onChange)
        self.config_remove_sleep.SetValue(cfg.data["entries"][event.GetText()]["config"]["remove"]["sleep"])
        self.config_remove_sleep.Bind(wx.EVT_TEXT, self.onChange)
        
        self.config_submit_cluster_size.SetValue(cfg.data["entries"][event.GetText()]["config"]["submit"]["cluster_size"])
        self.config_submit_cluster_size.Bind(wx.EVT_TEXT, self.onChange)
        self.config_submit_max_per_cycle.SetValue(cfg.data["entries"][event.GetText()]["config"]["submit"]["max_per_cycle"])
        self.config_submit_max_per_cycle.Bind(wx.EVT_TEXT, self.onChange)
        self.config_submit_sleep.SetValue(cfg.data["entries"][event.GetText()]["config"]["submit"]["sleep"])
        self.config_submit_sleep.Bind(wx.EVT_TEXT, self.onChange)
        
        self.SetTitle("GlideinWMS Configuration - " + event.GetText())
        #counter
        # parse attributes and load it
        # clear all existing entries first
        self.attr_grid.ClearGrid()
        self.attr_grid.DeleteRows(0, self.attr_grid.GetNumberRows())
        row = 0
        
        # insert attributes
        for attributes in cfg.data["entries"][event.GetText()]["attrs"].keys():
            # attribute
            self.attr_grid.InsertRows(row,1)
            self.attr_grid.SetCellValue(row, 0, attributes)
            self.attr_grid.SetReadOnly(row, 0)
            
            # properties
            # assumes that the order of the values is correct in the xml file: const, glidein_publish, job_publish, parameter, publish
            for value in cfg.data["entries"][event.GetText()]["attrs"][attributes].keys():
                if(value == "value"):
                    self.attr_grid.SetCellValue(row, 2, cfg.data["entries"][event.GetText()]["attrs"][attributes][value] )
                elif(value == "type"):
                    self.attr_grid.SetCellValue(row, 1, cfg.data["entries"][event.GetText()]["attrs"][attributes][value] )
                elif(value == "const"):
                    if(cfg.data["entries"][event.GetText()]["attrs"][attributes][value] == "True"):
                        self.attr_grid.SetCellBackgroundColour(row, 3, wx.Colour(204, 255, 153) )
                        self.attr_grid.SetCellValue(row, 3, "True")
                    else:
                        self.attr_grid.SetCellBackgroundColour(row, 3, wx.Colour(255, 204, 153 ))
                        self.attr_grid.SetCellValue(row, 3, "False")
                    self.attr_grid.SetReadOnly(row, 3)  
                elif(value == "glidein_publish"):
                    if(cfg.data["entries"][event.GetText()]["attrs"][attributes][value] == "True"):
                        self.attr_grid.SetCellBackgroundColour(row, 4, wx.Colour(204, 255, 153) )
                        self.attr_grid.SetCellValue(row, 4, "True")
                    else:
                        self.attr_grid.SetCellBackgroundColour(row, 4, wx.Colour(255, 204, 153 ))
                        self.attr_grid.SetCellValue(row, 4, "False")
                    self.attr_grid.SetReadOnly(row, 4)  
                
                elif(value == "job_publish"):
                    if(cfg.data["entries"][event.GetText()]["attrs"][attributes][value] == "True"):
                        self.attr_grid.SetCellBackgroundColour(row, 5, wx.Colour(204, 255, 153) )
                        self.attr_grid.SetCellValue(row, 5, "True")
                    else:
                        self.attr_grid.SetCellBackgroundColour(row, 5, wx.Colour(255, 204, 153 ))
                        self.attr_grid.SetCellValue(row, 5, "False")
                    self.attr_grid.SetReadOnly(row, 5)  
                elif(value == "parameter"):
                    if(cfg.data["entries"][event.GetText()]["attrs"][attributes][value] == "True"):
                        self.attr_grid.SetCellBackgroundColour(row, 6, wx.Colour(204, 255, 153) )
                        self.attr_grid.SetCellValue(row, 6, "True")
                    else:
                        self.attr_grid.SetCellBackgroundColour(row, 6, wx.Colour(255, 204, 153 ))
                        self.attr_grid.SetCellValue(row, 6, "False")
                    self.attr_grid.SetReadOnly(row, 6)  
                elif(value == "publish"):
                    if(cfg.data["entries"][event.GetText()]["attrs"][attributes][value] == "True"):
                        self.attr_grid.SetCellBackgroundColour(row, 7, wx.Colour(204, 255, 153) )
                        self.attr_grid.SetCellValue(row, 7, "True")
                    else:
                        self.attr_grid.SetCellBackgroundColour(row, 7, wx.Colour(255, 204, 153 ))
                        self.attr_grid.SetCellValue(row, 7, "False")
                    self.attr_grid.SetReadOnly(row, 7)  
                    
                
            row+=1
    
    # when user updates config text boxes
    def onChange(self, evt):
        global cfg

        # max_jobs held
        if(evt.GetId() == 1):
            cfg.data["entries"][currentSiteEntry]["config"]["max_jobs"]["held"] = evt.GetString()
         #  max_jobs  idle
        elif(evt.GetId() == 2):
            cfg.data["entries"][currentSiteEntry]["config"]["max_jobs"]["idle"] = evt.GetString()
            
        #  max_jobs  running
        elif(evt.GetId() == 3):
            cfg.data["entries"][currentSiteEntry]["config"]["max_jobs"]["running"] = evt.GetString()
            
        # release max_per_cycle
        elif(evt.GetId() == 4):
            cfg.data["entries"][currentSiteEntry]["config"]["release"]["max_per_cycle"] = evt.GetString()
        # release sleep
        elif(evt.GetId() == 5):
            cfg.data["entries"][currentSiteEntry]["config"]["release"]["sleep"] = evt.GetString()
            
        #remove max per cycle
        elif(evt.GetId() == 6):
            cfg.data["entries"][currentSiteEntry]["config"]["remove"]["max_per_cycle"] = evt.GetString()
        #remove sleep
        elif(evt.GetId() == 7):
            cfg.data["entries"][currentSiteEntry]["config"]["remove"]["sleep"] = evt.GetString()
            
        #submit cluster size
        elif(evt.GetId() == 8):
            cfg.data["entries"][currentSiteEntry]["config"]["submit"]["cluster_size"] = evt.GetString()
            
        #submit max_per_cycle
        elif(evt.GetId() == 9):
            cfg.data["entries"][currentSiteEntry]["config"]["submit"]["max_per_cycle"] = evt.GetString()
        
        #submit sleep
        elif(evt.GetId() == 10):
            cfg.data["entries"][currentSiteEntry]["config"]["submit"]["sleep"] = evt.GetString()
        
        
    def ApplyChange(self, event): 
        global cfg
        
        # save config changes
        
        if(event != None and event.GetId() == self.SAVEAS_COMMAND):
            filename =  wx.FileSelector("Save As...", flags=wx.SAVE|wx.OVERWRITE_PROMPT);
            if(filename==""):
                return
            else:
                self.targetFile =filename




        print "Changes Applied..."
        
        cfg.save_into_file_wbackup(self.targetFile)
        
        # deallocate
        
        del cfg
        
        #reinitialize
        cfg = cgWParams.GlideinParams('','',['', self.targetFile])
        
        wx.MessageBox("Changes Applied.", "",wx.OK, self);
        
    def apply_attributes(self, event): 
        print "Event handler `apply_attributes' not implemented"
        event.Skip()
    

    def attr_select(self, event):
        print event.GetData()


class ConfigMain(wx.App):

    def OnInit(self):
        wx.InitAllImageHandlers()
        frame_1 = GlideFrame(None, -1, "")
        self.SetTopWindow(frame_1)
        frame_1.Show()
        return 1

if __name__ == "__main__":
    ConfigMain = ConfigMain(0)
    ConfigMain.MainLoop()
