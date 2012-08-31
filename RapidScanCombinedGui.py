#!/usr/bin/python
from motorpanel import *
import wx
import xmlrpclib
import threading
import socket

HOSTNAME = socket.getfqdn()

myEVT_DONE = wx.NewEventType()
EVT_DONE = wx.PyEventBinder(myEVT_DONE, 1)
class DoneEvent(wx.PyCommandEvent):
    """Event to signal that a remote move operation is done"""
    def __init__(self, etype, eid, msg = None):
        """Creates the event object"""
        wx.PyCommandEvent.__init__(self, etype, eid)
        self._msg = msg

    def GetValue(self):
        """Returns the value from the event.
        @return: the value of this event

        """
        return self._msg

class MoverThread(threading.Thread):
    def __init__(self, parent, motnums, positions):
        """
        @param parent: The gui object that should recieve the value
        @param value: value to 'calculate' to
        """
        threading.Thread.__init__(self)
        self._parent = parent
        self._motnums = motnums
        self._positions = positions

    def run(self):
        """Overrides Thread.run. Don't call this directly its called internally
        when you call Thread.start().
        """
        self._parent.ic.DriveMultiMotor(self._motnums, self._positions)
        evt = DoneEvent(myEVT_DONE, -1, None)
        wx.PostEvent(self._parent, evt)
        
class RapidScanThread(threading.Thread):
    def __init__(self, parent, motnum, start_position, dest_position):
        """
        @param parent: The gui object that should recieve the value
        @param value: value to 'calculate' to
        """
        threading.Thread.__init__(self)
        self._parent = parent
        self._motnum = motnum
        self._start_position = start_position
        self._dest_position = dest_position

    def run(self):
        """Overrides Thread.run. Don't call this directly its called internally
        when you call Thread.start().
        """
        self._parent.ic.RapidScan(self._motnum, self._start_position, self._dest_position)
        evt = DoneEvent(myEVT_DONE, -1, None)
        wx.PostEvent(self._parent, evt)


class XMLRPCMotorPanel(MotorPanel):
    def __init__(self, *args, **kwargs):
        self.ic = xmlrpclib.ServerProxy('http://'+HOSTNAME + ':8001')
        MotorPanel.__init__(self, *args, **kwargs)
        self.Bind(EVT_DONE, self.onDone)
    
    def motor_go(self, event = None, motnum = None):
        if motnum is None:
            return
        try:
            dest = float(self.motor_dest[motnum-1].GetValue())
        except ValueError:
            # improperly formatted destination!
            return
        self.drive_motor(motnum, dest)
        #self.update_all_motors() # this comes later in the threaded version!
    
    def get_num_mots(self):
        return self.ic.getState()['num_mots']
    
    def drive_motor(self, motnum, position):
        self.TopLevelParent.disable_all_buttons()
        worker = MoverThread(self, [motnum], [position])
        worker.start()
    
    def drive_multi_motor(self, motnums, positions): 
        self.TopLevelParent.disable_all_buttons()
        worker = MoverThread(self, motnums, positions)
        worker.start()
        
    def onDone(self, evt):
        self.update_all_motors()
        self.TopLevelParent.restore_button_state()
        
    def get_motor_pos(self, motnum):
        return self.ic.GetStoredSoftMotorPos(motnum)

class XMLRPCRapidScanPanel(RapidScanPanel):
    def __init__(self, *args, **kwargs):
        self.ic = xmlrpclib.ServerProxy('http://'+HOSTNAME + ':8001')
        RapidScanPanel.__init__(self, *args, **kwargs)
        self.Bind(EVT_DONE, self.onDone)
        
    def onDone(self, evt):
        self.update_all_motors()
        self.TopLevelParent.restore_button_state()
        
    def get_motor_pos(self, motnum):
        return self.ic.GetStoredSoftMotorPos(motnum)
        
    def RapidScan(self, motnum, start_pos, dest_pos):
        self.TopLevelParent.disable_all_buttons()
        worker = RapidScanThread(self, motnum, start_pos, dest_pos)
        worker.start()
        
class XMLRPCAbortPanel(AbortPanel):
    icsig = xmlrpclib.ServerProxy('http://'+HOSTNAME+':8000')
    
    def Abort(self, event=None):
        self.icsig.Abort()     

class XMLRPCMotorConfiguration(MotorConfiguration):
    ic = xmlrpclib.ServerProxy('http://'+HOSTNAME+':8001')
    def get_num_mots(self):
        return self.ic.getState()['num_mots']

class MyFrame(wx.Frame):
    def __init__(self, *args, **kwds):
        # begin wxGlade: MyFrame.__init__
        kwds["style"] = wx.DEFAULT_FRAME_STYLE
        wx.Frame.__init__(self, *args, **kwds)
        self.buttons = []
        self.panels = []
        
        self.motors_cfg = XMLRPCMotorConfiguration(self)
        self.menubar = wx.MenuBar()
        self.menubar.Append(self.motors_cfg.motormenu, self.motors_cfg.motormenu_title)
        self.SetMenuBar(self.menubar)
        
        self.abort_panel = XMLRPCAbortPanel(self, -1)
        self.panel_1 = XMLRPCMotorPanel(self, -1, self.motors_cfg.motors)
        self.panel_2 = XMLRPCRapidScanPanel(self, -1, self.motors_cfg.motors)
        # buttons to disable when moving:
        self.buttons.extend(self.panel_1.buttons) 
        self.buttons.extend(self.panel_2.buttons)
        self.panels.append(self.panel_1)
        self.panels.append(self.panel_2)
        if len(self.panel_1.menus) > 0:
            self.menubar = wx.MenuBar()
            for menu, title in self.panel_1.menus:
                self.menubar.Append(menu, title)
            self.SetMenuBar(self.menubar)
            
        # (this specifically excludes the Abort button, which is NOT disabled)
        #self.plot_panel = PlotPanel(self, -1)      
        self.__set_properties()
        self.__do_layout()
        # end wxGlade

    def __set_properties(self):
        # begin wxGlade: MyFrame.__set_properties
        self.SetTitle("Motor Control Panel")
        # end wxGlade        
    
    def __do_layout(self):
        # begin wxGlade: MyFrame.__do_layout
        sizer_1 = wx.BoxSizer(wx.HORIZONTAL)
        sizer_2 = wx.BoxSizer(wx.VERTICAL)
        sizer_1.Add(self.panel_1, 0, wx.EXPAND, 0)
        
        sizer_1.Add(self.abort_panel, 0, wx.EXPAND, 0)
        sizer_2.Add(sizer_1)
        rs_label = wx.StaticText(self, -1, 'RAPID SCAN:')
        rs_label.SetFont(wx.Font(10, wx.DEFAULT, wx.NORMAL, wx.BOLD, 0, ""))
        sizer_2.Add(rs_label, 0,0,0)
        sizer_2.Add(self.panel_2, 0, wx.EXPAND, 0)
        #sizer_1.Add(self.plot_panel, 0, wx.EXPAND, 0)
        self.SetSizer(sizer_2)
        sizer_2.Fit(self)
        self.Layout()
        # end wxGlade

    def disable_all_buttons(self):
        """ disables all buttons except the abort button """
        old_button_state = []
        for button in self.buttons:
            old_button_state.append(button.IsEnabled())
            button.Disable()
        self._stored_button_state = old_button_state
        return old_button_state
    
    def restore_button_state(self, button_state=None):
        for panel in self.panels:
            panel.update_all_motors()
        if button_state==None: button_state = self._stored_button_state
        for i, state in enumerate(button_state):
            self.buttons[i].Enable(state)
    
    def update_motors(self, motors):
        for panel in self.panels:
            panel.motors = motors
            panel.update_all_motors()
            
    def change_enabled_motors(self, motors_enabled):
        for panel in self.panels:
            panel.motors_enabled = motors_enabled
            panel.__do_layout()     
        

# end of class MyFrame


if __name__ == "__main__":
    app = wx.PySimpleApp(0)
    wx.InitAllImageHandlers()
    frame_1 = MyFrame(None, -1, "")
    app.SetTopWindow(frame_1)
    frame_1.Show()
    app.MainLoop()
