#from __future__ import with_statement
from icp_compat import prefilter_ICP
from SimpleXMLRPCServer import SimpleXMLRPCServer
from SimpleXMLRPCServer import SimpleXMLRPCRequestHandler
#from SimpleXMLRPCServer import SimpleXMLRPCDispatcher
from BaseHTTPServer import BaseHTTPRequestHandler
import threading, sys
import socket

from InstrumentController_unmixed import InstrumentController
import pyrecs.mixins

AVAILABLE_MIXINS = pyrecs.mixins.__all__

#import xmlrpclib

DEBUG = True

WHITELIST = ['129.6.123.195', # bbm's desktop
             '129.6.120.90', # magik
             '129.6.120.84', # pbr
             '129.6.120.94', # bt4
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


ic = InstrumentController()
# Create server in a new thread
mixins = {}
for mixin_module in AVAILABLE_MIXINS:
    _temp = __import__('pyrecs.mixins', fromlist=[mixin_module])
    mixin_class = _temp.__getattribute__(mixin_module).__getattribute__('mixin_class')
    mixin_name = mixin_class.__name__
    mixins[mixin_name] = mixin_class

active_mixins = set()

def update_mixins():
    InstrumentController.__bases__ = tuple(active_mixins)
    for mixin in active_mixins:
        mixin.__init__(ic)
    icp_conversions = ic.GetICPConversions()
    prefilter_ICP.icpt.register_icp_conversions(icp_conversions)
    
def activate_mixin(mixin_name):
    if mixin_name in mixins:
        active_mixins.add(mixins[mixin_name])
        update_mixins()
    else:
        return "not a valid mixin class"
        
def deactivate_mixin(mixin_name):
    try: 
        active_mixins.remove(mixins[mixin_name])
        update_mixins()
    except KeyError:
        return "not an active mixin"

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

commandserver.register_function(commandserver.system_listMethods, '__dir__')

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

icp_conversions = ic.GetICPConversions()
prefilter_ICP.icpt.register_icp_conversions(icp_conversions)
prefilter_ICP.icpt.echo = True
prefilter_ICP.activate_prefilter(None, log_unfiltered = False) # no callbacks in this client


#####################################################################################
#  Experimental stuff to enable access from XMLHttpGet, which might not be a 
#  good idea, anyway... leaving it here below, for now
#####################################################################################

# Restrict to a particular path.
__version__ = "0.3"

#__all__ = ["SimpleXMLRPCServer", "SimpleXMLRPCRequestHandler"]


