#!/usr/bin/python

import site, os
dirname = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
print dirname
site.addsitedir(dirname) 

from pyrecs.gui.wx.motorpanel import AbortPauseFinishPanel
# this is to implement key grabbing on function keys:
from pyrecs.lib import pyxhook 
import wx
import xmlrpclib
import threading
import socket
from pyrecs.ordered_dict import OrderedDict

HOSTNAME = socket.getfqdn()
HOTKEYS = {
    "F9": 'Abort',
    "F10": 'Suspend',
    "F11": 'Finish'
}

class XMLRPCSignalPanel(AbortPauseFinishPanel):
    icsig = xmlrpclib.ServerProxy('http://'+HOSTNAME+':8000')
    
    def Abort(self, event=None):
        self.icsig.Abort()
    
    def Pause(self, event=None):
        self.icsig.Suspend()
    
    def Finish(self, event=None):
        self.icsig.Break()   

class MyFrame(wx.Frame):
    def __init__(self, *args, **kwds):
        # begin wxGlade: MyFrame.__init__
        kwds["style"] = wx.DEFAULT_FRAME_STYLE
        wx.Frame.__init__(self, *args, **kwds)
        self.buttons = []
        self.panels = OrderedDict()
        
        self.abort_panel = XMLRPCSignalPanel(self, -1)
            
        # (this specifically excludes the Abort button, which is NOT disabled)
        #self.plot_panel = PlotPanel(self, -1)      
        self.__set_properties()
        self.__do_layout()
        # end wxGlade
        hm = pyxhook.HookManager()
        hm.HookKeyboard()
        hm.KeyDown = self.handleKey
        hm.start()

        self.keylistener = hm
        self.Bind(wx.EVT_CLOSE, self.onClose)

    def __set_properties(self):
        # begin wxGlade: MyFrame.__set_properties
        self.SetTitle("Abort Control")
        # end wxGlade        
    
    def __do_layout(self):
        # begin wxGlade: MyFrame.__do_layout
        sizer_1 = wx.BoxSizer(wx.HORIZONTAL)
        sizer_2 = wx.BoxSizer(wx.VERTICAL)
        for panel in self.panels.values():
            sizer_2.Add(wx.StaticLine(self, -1), 0, wx.EXPAND)
            sizer_2.Add(panel, 0, wx.EXPAND, 0)
        #sizer_1.Add(self.panel_1, 0, wx.EXPAND, 0)
        sizer_1.Add(sizer_2)
        sizer_1.Add(self.abort_panel, 0, wx.EXPAND, 0)
        #sizer_2.Add(sizer_1)
        #rs_label = wx.StaticText(self, -1, 'RAPID SCAN:')
        #rs_label.SetFont(wx.Font(10, wx.DEFAULT, wx.NORMAL, wx.BOLD, 0, ""))
        #sizer_2.Add(rs_label, 0,0,0)
        #sizer_2.Add(self.panel_2, 0, wx.EXPAND, 0)
        #sizer_2.Add(self.panel_3, 0, wx.EXPAND, 0)
        #sizer_1.Add(self.plot_panel, 0, wx.EXPAND, 0)
        self.SetSizer(sizer_1)
        sizer_1.Fit(self)
        self.Layout()
        # end wxGlade

    def onClose(self, event):
        """ cleanup any threads that might have been opened """
        self.keylistener.cancel()
        #print "closing self"
        event.Skip()
        
    def handleKey(self, event):
        if event.Key in HOTKEYS.keys():
            #print "processing %s" % (event.Key)
            try:
                getattr(self.abort_panel, HOTKEYS[event.Key])()
            except:
                print "communication with server failed"
            
    def disable_all_buttons(self):
        """ disables all buttons except the abort button """
        old_button_state = []
        for button in self.buttons:
            old_button_state.append(button.IsEnabled())
            button.Disable()
        self._stored_button_state = old_button_state
        return old_button_state
    
    def restore_button_state(self, button_state=None):
        for panel in self.panels.values():
            panel.update_all_motors()
        if button_state==None: button_state = self._stored_button_state
        for i, state in enumerate(button_state):
            self.buttons[i].Enable(state)
    
    def update_motors(self, motors):
        for panel in self.panels.values():
            panel.motors = motors
            panel.update_all_motors()
            
    def change_enabled_motors(self, motors_enabled):
        for panel in self.panels.values():
            panel.motors_enabled = motors_enabled
            panel.__do_layout()     

# end of class MainFrame
class MyApp(wx.App):
    def OnInit(self):
        wx.InitAllImageHandlers()
        frame_1 = MyFrame(None, -1, "")
        self.SetTopWindow(frame_1)
        frame_1.Show()
        return 1
        
    

# end of class MyApp

if __name__ == "__main__":
    SigButtons = MyApp(0)
    SigButtons.MainLoop()

