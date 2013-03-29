from motorpanel import *
import wx
import xmlrpclib
import threading
import socket

HOSTNAME = socket.getfqdn()
MOTORNAMES = [
            'slit 1', 
            'slit 2',
            'theta',
            'two-theta',
            'slit 3',
            'slit 4',
            'translation x',
            'tilt (beam axis)',
            'polarizer angle',
            'polarizer trans',
            ]


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
        

class XMLRPCRapidScanPanel(RapidScanPanel):
    def __init__(self, *args, **kwargs):
        RapidScanPanel.__init__(self, *args, **kwargs)
        self.ic = xmlrpclib.ServerProxy('http://'+HOSTNAME + ':8001')
        self.Bind(EVT_DONE, self.onDone)
        
    def onDone(self, evt):
        self.update_all_motors()
        self.TopLevelParent.restore_button_state()
        
    def get_motor_pos(self, motnum):
        return self.ic.GetStoredSoftMotorPos(motnum)
        
    def RapidScan(self, motnum, start_pos, dest_pos):
        self.TopLevelParent.disable_all_buttons()
        worker = MoverThread(self, motnum, start_pos, dest_pos)
        worker.start()

        
class XMLRPCAbortPanel(AbortPanel):
    icsig = xmlrpclib.ServerProxy('http://'+HOSTNAME+':8000')
    
    def Abort(self, event=None):
        self.icsig.Abort()     

class InThread(threading.Thread):
    """ make a function run in a separate thread.
    Mostly needed because it will shield I/O operations from interrupts """
    def __init__(self, func, *args, **kwargs):
        self.func = func
        self.args = args
        self.kwargs = kwargs
        self.result = None
        self.finished = False
        threading.Thread.__init__(self)
        
    def run(self):
        self.result = self.func(*(self.args), **(self.kwargs))        
        self.finished = True
        
    def isFinished(self):
        return self.finished
        
    def retrieve(self):
        return self.result

class MyFrame(wx.Frame):
    def __init__(self, *args, **kwds):
        # begin wxGlade: MyFrame.__init__
        kwds["style"] = wx.DEFAULT_FRAME_STYLE
        wx.Frame.__init__(self, *args, **kwds)
        self.buttons = []      
        self.abort_panel = XMLRPCAbortPanel(self, -1)
        self.panel_1 = XMLRPCRapidScanPanel(self, -1, MOTORNAMES)
        # buttons to disable when moving:
        self.buttons.extend(self.panel_1.buttons) 
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
        self.SetTitle("Rapid Motor Scan (count while moving)")
        # end wxGlade        
    
    def __do_layout(self):
        # begin wxGlade: MyFrame.__do_layout
        sizer_1 = wx.BoxSizer(wx.HORIZONTAL)
        sizer_1.Add(self.panel_1, 0, wx.EXPAND, 0)
        sizer_1.Add(self.abort_panel, 0, wx.EXPAND, 0)
        #sizer_1.Add(self.plot_panel, 0, wx.EXPAND, 0)
        self.SetSizer(sizer_1)
        sizer_1.Fit(self)
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
        if button_state==None: button_state = self._stored_button_state
        for i, state in enumerate(button_state):
            self.buttons[i].Enable(state)
        
            
        

# end of class MyFrame


if __name__ == "__main__":
    app = wx.PySimpleApp(0)
    wx.InitAllImageHandlers()
    frame_1 = MyFrame(None, -1, "")
    app.SetTopWindow(frame_1)
    frame_1.Show()
    app.MainLoop()
