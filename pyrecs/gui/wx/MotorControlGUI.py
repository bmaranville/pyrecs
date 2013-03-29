from motorpanel import *
import wx
import xmlrpclib

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

class XMLRPCMotorPanel(MotorPanel):
    ic = xmlrpclib.ServerProxy('http://andr.ncnr.nist.gov:8001')
    
    def drive_motor(self, motnum, position):
        self.ic.DriveMotor(motnum, position)
        
    def get_motor_pos(self, motnum):
        return self.ic.GetStoredSoftMotorPos(motnum)
        
class XMLRPCAbortPanel(AbortPanel):
    icsig = xmlrpclib.ServerProxy('http://andr.ncnr.nist.gov:8000')
    
    def Abort(self, event=None):
        self.icsig.Abort()     

class MyFrame(wx.Frame):
    def __init__(self, *args, **kwds):
        # begin wxGlade: MyFrame.__init__
        kwds["style"] = wx.DEFAULT_FRAME_STYLE
        wx.Frame.__init__(self, *args, **kwds)
        self.abort_panel = TestAbortPanel(self, -1)
        self.panel_1 = TestMotorPanel(self, -1, MOTORNAMES)
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
        sizer_1.Add(self.panel_1, 0, wx.EXPAND, 0)
        sizer_1.Add(self.abort_panel, 0, wx.EXPAND, 0)
        #sizer_1.Add(self.plot_panel, 0, wx.EXPAND, 0)
        self.SetSizer(sizer_1)
        sizer_1.Fit(self)
        self.Layout()
        # end wxGlade


# end of class MyFrame


if __name__ == "__main__":
    app = wx.PySimpleApp(0)
    wx.InitAllImageHandlers()
    frame_1 = MyFrame(None, -1, "")
    app.SetTopWindow(frame_1)
    frame_1.Show()
    app.MainLoop()
