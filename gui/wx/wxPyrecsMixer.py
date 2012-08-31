#!/usr/bin/python

# spinctrl.py
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
# pyrecs root is three levels up!
import wx
import os
from SimpleXMLRPCServer import SimpleXMLRPCServer
from SimpleXMLRPCServer import SimpleXMLRPCRequestHandler
from BaseHTTPServer import BaseHTTPRequestHandler
import socket
import threading, sys
from numpy import float, abs

from pyrecs.InstrumentController_unmixed import InstrumentController
import pyrecs.mixins

AVAILABLE_MIXINS = pyrecs.mixins.__all__

DEBUG = True
EVT_MESSAGE_ID = wx.NewId()
EVT_ABORT_ID = wx.NewId()
EVT_RESET_ABORT_ID = wx.NewId()

def EVT_MESSAGE(win, func):
    """Define Result Event."""
    win.Connect(-1, -1, EVT_MESSAGE_ID, func)
    
def EVT_ABORT(win, func):
    """Define Abort Event"""
    win.Connect(-1,-1, EVT_ABORT_ID, func)

def EVT_RESET_ABORT(win, func):
    """Define Reset Abort Event"""
    win.Connect(-1,-1, EVT_RESET_ABORT_ID, func)

class MessageEvent(wx.PyEvent):
    """Simple event to carry arbitrary message data."""
    def __init__(self, data):
        """Init Result Event."""
        wx.PyEvent.__init__(self)
        self.SetEventType(EVT_MESSAGE_ID)
        self.data = data
        
class AbortEvent(wx.PyEvent):
    """Simple event to set Abort flag"""
    def __init__(self):
        """Init Abort Event."""
        wx.PyEvent.__init__(self)
        self.SetEventType(EVT_ABORT_ID)
        
class ResetAbortEvent(wx.PyEvent):
    """Simple event to set Abort flag"""
    def __init__(self):
        """Init Reset Abort Event."""
        wx.PyEvent.__init__(self)
        self.SetEventType(EVT_RESET_ABORT_ID)


class wxWriter:
    def __init__(self, notify_window):
        self._notify_window = notify_window

    def write(self, msg):
        wx.PostEvent(self._notify_window, MessageEvent(msg))

WHITELIST = ['129.6.123.108',
             '129.6.120.84',
             '129.6.120.90',
             '127.0.0.1',
             'localhost']

class WhitelistXMLRPCServer(SimpleXMLRPCServer):
    def verify_request(self, request, client_address):
        self.connected_peer = client_address
        return client_address[0] in WHITELIST

class UDPWriter:
    import socket
    """ output goes here. """
    def __init__(self, hostname, port):
        self.hostname = hostname
        self.port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
         
    def write(self, msg):
        self.sock.sendto(msg, (self.hostname, self.port))
        
    def flush(self):
        pass

class XMLRPCWriter:
    """ output goes here. """
    import xmlrpclib
    def __init__(self, hostname, port):
        self.hostname = hostname
        self.port = port
        self.sock = self.xmlrpclib.ServerProxy('http://%s:%d' % (hostname, port))
         
    def write(self, msg):
        try:
            self.sock.localprint(msg)
        except:
            pass # ignore if the print command doesn't work
        
    def get_input(self, prompt):
        try:
            return self.sock.get_input(prompt)
        except:
            return
        
    def flush(self):
        pass


class wxInstrumentController(InstrumentController):
    _notify_window = None
    def Abort(self, signum=None, frame=None):
        """ when trapped, the abort just sets a flag """
        self._aborted = True
        wx.PostEvent(self._notify_window, AbortEvent())
        
    def ResetAbort(self):
        """ call this when you're ready to start taking commands again """
        self._aborted = False
        wx.PostEvent(self._notify_window, ResetAbortEvent())   
            

class MyDialog(wx.Dialog):
    def __init__(self, parent, id, title, ic, mixins):
        wx.Dialog.__init__(self, parent, id, title, wx.DefaultPosition, wx.Size(450, 310))

        self.ic = ic
        self.mixins = mixins
        #### LOGO STUFF ####
        self.supersizer = wx.BoxSizer(wx.HORIZONTAL)
        PyrecsLogo = wx.Image(os.path.join(os.path.dirname(__file__), 'pyrex.png')).ConvertToBitmap()
        self.logo = wx.StaticBitmap(self, bitmap=PyrecsLogo)
        ####################
        
        self.sizer = wx.BoxSizer(wx.VERTICAL)
        self.buttons_sizer = wx.FlexGridSizer(rows = 1, cols = 3, hgap = 10, vgap = 10 )
        self.mixins_sizer = wx.BoxSizer(wx.VERTICAL)
        
        Title = wx.StaticText(self, -1, 'Python Reflectometry Control Software                          ')
        spacer = wx.StaticText(self, -1, '')      
        
        ABORT_btn = wx.Button(self, 1, 'ABORT')
        Reset_Abort_btn = wx.Button(self, 2, 'Reset Abort')
        self.ABORT_indicator = wx.StaticText(self, -1, 'Not Aborted.')
        self.ABORT_indicator.SetForegroundColour('black')
        
        self.mixin_checkboxes = []
        for mixin_label in mixins:
            mixin_checkbox = wx.CheckBox(self, -1, mixin_label)
            self.Bind(wx.EVT_CHECKBOX, self.update_mixins, mixin_checkbox)
            self.mixin_checkboxes.append(mixin_checkbox)
            self.mixins_sizer.Add(mixin_checkbox)
        
        ResultLabel = wx.StaticText(self, -1, 'Result:')
        self.ResultText = wx.StaticText(self, -1, '', size=(-1, 60))
        self.ResultText.Wrap(400)

        self.buttons_sizer.Add(ABORT_btn)
        self.buttons_sizer.Add(Reset_Abort_btn)
        self.buttons_sizer.Add(self.ABORT_indicator)


        self.Bind(wx.EVT_BUTTON, self.ABORT, id=1)
        self.Bind(wx.EVT_BUTTON, self.Reset_Abort, id=2)
        self.Bind(wx.EVT_CLOSE, self.OnClose)
        
        self.sizer.Add(Title)
        self.sizer.Add(self.buttons_sizer)
        self.sizer.Add(self.mixins_sizer)
        self.sizer.Add(ResultLabel)
        self.sizer.Add(self.ResultText)
        
        #self.SetSizer(self.sizer)
        
        #### LOGO STUFF ####
        self.supersizer.Add(self.sizer)
        self.supersizer.Add(self.logo)
        self.SetSizer(self.supersizer)
        ####################
        EVT_MESSAGE(self,self.OnMessage)
        EVT_ABORT(self, self.OnAbort)
        EVT_RESET_ABORT(self, self.OnResetAbort)
        self.Fit()
    
    def write(self, msg):
        self.ResultText.SetLabel(msg)
        self.ResultText.Wrap(350) 

    def OnMessage(self, event):
        msg = event.data
        self.write(msg)
        
    def ABORT(self, event = None):        
        self.ic.Abort()
        
    def OnAbort(self, event = None):
        self.ABORT_indicator.SetLabel('Aborted!')
        self.ABORT_indicator.SetForegroundColour('red')
        
    def Reset_Abort(self, event=None):
        self.ic.ResetAbort()
        
    def OnResetAbort(self, event=None):
        self.ABORT_indicator.SetLabel('Not Aborted.')
        self.ABORT_indicator.SetForegroundColour('black')
            
    def OnClose(self, event):
        self.Destroy()
        
    def update_mixins(self, event=None):
        active_mixin_names = [checkbox.GetLabelText() for checkbox in self.mixin_checkboxes if checkbox.IsChecked()]
        self.write(str(active_mixin_names))
        active_mixins = [self.mixins[name] for name in active_mixin_names]
        InstrumentController.__bases__ = tuple(active_mixins)
        for mixin in active_mixins:
            mixin.__init__(self.ic)


class MyApp(wx.App):
    def OnInit(self):
        ic = wxInstrumentController()
        self.ic = ic
        mixins = {}
        for mixin_name in AVAILABLE_MIXINS:
            _temp = __import__('pyrecs.mixins', fromlist=[mixin_name])
            mixins[mixin_name] = _temp.__getattribute__(mixin_name).__getattribute__('mixin_class')
        
        # Create server in a new thread

        #signalserver = SimpleXMLRPCServer((socket.getfqdn(), 8000),
        #                        requestHandler=RequestHandler)
        signalserver = WhitelistXMLRPCServer((socket.getfqdn(), 8000))
        #signalserver.timeout = 1.0
        signalserver.register_introspection_functions()
        signalserver.allow_none = True
        signalserver.register_function(ic.Abort)
        signalserver.register_function(ic.Suspend)
        signalserver.register_function(ic.Break)
        signalserver.register_function(signalserver.server_close)

        #commandserver = SimpleXMLRPCServer((socket.getfqdn(), 8001),
        #                        requestHandler=RequestHandler)
        commandserver = WhitelistXMLRPCServer((socket.getfqdn(), 8001))
        #commandserver.timeout = 1.0
        commandserver.register_introspection_functions()
        commandserver.allow_none = True

        # need to define these for tab-completion to work in Ipython clients
        def _getAttributeNames():
            return commandserver.system_listMethods()
        commandserver.register_function(_getAttributeNames)

        def trait_names():
            return commandserver.system_listMethods()
        commandserver.register_function(trait_names)

        def where_am_I_calling_from():
            return commandserver.connected_peer

        def register_xmlrpc_writer(hostname, port):
            writer = XMLRPCWriter(hostname, port)
            ic.register_writer(writer)

        def register_udp_writer(hostname, port):
            writer = UDPWriter(hostname, port)
            ic.register_writer(writer)
            
        commandserver.register_function(register_xmlrpc_writer)
        commandserver.register_function(register_udp_writer)
        commandserver.register_function(where_am_I_calling_from)
        commandserver.register_function(commandserver.server_close)
        commandserver.register_instance(ic)

        def stop():
            signalserver.server_close()
            commandserver.server_close()
            
        signalserver.register_function(stop)

        #server.register_function(adder_function, 'add')
        # Run the server's main loop
        sigserver_thread = threading.Thread(target=signalserver.serve_forever)
        sigserver_thread.setDaemon(1)
        sigserver_thread.start()

        cmdserver_thread = threading.Thread(target=commandserver.serve_forever)
        cmdserver_thread.setDaemon(1)
        cmdserver_thread.start()
        dlg = MyDialog(None, -1, 'PyReCS Server with Mixins', ic, mixins)
        # remove the stdout writer...
        ic.writers = set([wxWriter(dlg)])
        ic._notify_window = dlg
        dlg.Show(True)
        dlg.Centre()
        return True



app = MyApp(0)
app.MainLoop()

