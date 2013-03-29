from motorpanel import *
from PlotPanel import *
import wx
import xmlrpclib
import numpy
import threading, time

MOTORNAMES = [
            'slit 1 aperture', 
            'slit 2 aperture',
            'theta',
            'two-theta',
            'slit 3 aperture',
            'slit 4 aperture',
            'translation x',
            'tilt (beam axis)',
            'polarizer 1 angle',
            'polarizer 2 angle',
            ]

myEVT_COUNT = wx.NewEventType()
EVT_COUNT = wx.PyEventBinder(myEVT_COUNT, 1)
class CountEvent(wx.PyCommandEvent):
    """Event to signal that a count value is ready"""
    def __init__(self, etype, eid, motnum=None, position=None):
        """Creates the event object"""
        wx.PyCommandEvent.__init__(self, etype, eid)
        self._motnum = motnum
        self._position = position

    def GetValue(self):
        """Returns the value from the event.
        @return: the value of this event

        """
        return self._motnum, self._position

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
        time.sleep(3) # our simulated calculation time
        evt = CountEvent(myEVT_COUNT, -1, self._motnums, self._positions)
        wx.PostEvent(self._parent, evt)


class TestMotorPanel(MotorPanel):
    def __init__(self, *args, **kwargs):
        MotorPanel.__init__(self, *args, **kwargs)
        self.Bind(EVT_COUNT, self.OnCount)
    
    def drive_motor(self, motnum, position):
        self.TopLevelParent.disable_all_buttons()
        worker = MoverThread(self, [motnum], [position])
        worker.start()
        print "working"
    
    def OnCount(self, evt):
        motnums, positions = evt.GetValue()
        for motnum, pos in zip(motnums, positions):
            print "moving motor %d to position %f" % (motnum, pos)
        self.TopLevelParent.restore_button_state()
        
    def get_motor_pos(self, motnum):
        return 0.0
        
    def drive_multi_motor(self, motnums, positions):
        self.TopLevelParent.disable_all_buttons()
        worker = MoverThread(self, motnums, positions)
        worker.start()
        print "working"
        
       
    
class TestAbortPanel(AbortPanel):
    
    def Abort(self, event=None):
        print "I'm shuttin 'er down"



class MyFrame(wx.Frame):
    def __init__(self, *args, **kwds):
        # begin wxGlade: MyFrame.__init__
        kwds["style"] = wx.DEFAULT_FRAME_STYLE
        wx.Frame.__init__(self, *args, **kwds)
        self.buttons = []
        self.button_state = []
        self.abort_panel = TestAbortPanel(self, -1)
        self.panel_1 = TestMotorPanel(self, -1, MOTORNAMES)
        self.menubar = wx.MenuBar()
        if len(self.panel_1.menus) > 0:
            for menu in self.panel_1.menus:
                self.menubar.Append(menu[0], menu[1])
        self.buttons.extend(self.panel_1.buttons)
        self.plot_panel = PlotPanel(self, -1)
        
        self.__set_properties()
        self.__do_layout()
        # end wxGlade

    def __set_properties(self):
        # begin wxGlade: MyFrame.__set_properties
        self.SetTitle("Motor Control Panel")
        self.SetMenuBar(self.menubar)
        # end wxGlade

    def __do_layout(self):
        # begin wxGlade: MyFrame.__do_layout
        sizer_1 = wx.BoxSizer(wx.HORIZONTAL)
        sizer_1.Add(self.panel_1, 0, wx.EXPAND, 0)
        sizer_1.Add(self.abort_panel, 0, wx.EXPAND, 0)
        sizer_1.Add(self.plot_panel, 0, wx.EXPAND, 0)
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
        self.button_state = old_button_state
        return old_button_state
    
    def restore_button_state(self):
        for i, state in enumerate(self.button_state):
            self.buttons[i].Enable(state)
    
# end of class MyFrame


if __name__ == "__main__":
    app = wx.PySimpleApp(0)
    wx.InitAllImageHandlers()
    frame_1 = MyFrame(None, -1, "")
    app.SetTopWindow(frame_1)
    frame_1.Show()
    ax = frame_1.plot_panel.figure.add_subplot(111)
    ax.plot(numpy.random.random(10))
    app.MainLoop()
