from IPython.iplib import InteractiveShell
import prefilter_ICP
import signal
import xmlrpclib
from SimpleXMLRPCServer import SimpleXMLRPCServer
from SimpleXMLRPCServer import SimpleXMLRPCRequestHandler
import socket
import threading
import sys, os
import time

PYRECS_SERVER_ADDR = 'http://' + socket.getfqdn()
#PYRECS_SERVER_ADDR = "http://andr.ncnr.nist.gov"
PYRECS_SIGNAL_PORT = 8000
PYRECS_CONTROL_PORT = 8001

DEBUG = False

UDP_PRINT = False
XMLRPC_PRINT= True

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
        try:
            self.result = self.func(*(self.args), **(self.kwargs))        
        except xmlrpclib.Fault as fault:
            self.result = fault.faultString
        self.finished = True
               
    def retrieve(self):
        return self.result

class threadedTransport(xmlrpclib.Transport):
    def __init__(self, *args, **kwargs):
        self.base_request = xmlrpclib.Transport.request
        xmlrpclib.Transport.__init__(self, *args, **kwargs)
    def request(self, *args, **kwargs):
        #print args
        args = (self,) + args
        getterThread = InThread(self.base_request, *args, **kwargs)
        getterThread.start()
        # non-blocking join() alternative
        while getterThread.is_alive():
            time.sleep(0.001) # fast loop?
        return getterThread.retrieve()

# Receive messages

def localprint(printstr):
    sys.stdout.write(printstr)
    sys.stdout.flush()
        
def get_input(prompt):
    #reply = ''
    #dlg = wx.TextEntryDialog(None, "reply", prompt)
    #if dlg.ShowModal() == wx.ID_OK:
    #    reply = dlg.GetValue()
    #dlg.Destroy()
    #return reply
    print "hit Return then answer the following:"     
    return raw_input(prompt)

def UDP_Printserver():
    global UDPSock
    global UDP_Printer_active
    while UDP_Printer_active:
        data,addr = UDPSock.recvfrom(buf)
        if not data:    
            print "Client has exited!"
            break
        else:
            sys.stdout.write(data)
            sys.stdout.flush()
    #Close socket
    UDPSock.close()


prefilter_ICP.activate_prefilter(None, log_unfiltered = False) # no callbacks in this client
# make connections to the server
#try: 
if DEBUG: print "starting signaling connection"
icsig = xmlrpclib.ServerProxy('%s:%d' % (PYRECS_SERVER_ADDR, PYRECS_SIGNAL_PORT))
if DEBUG: print "starting command connection"
ic = xmlrpclib.ServerProxy('%s:%d' % (PYRECS_SERVER_ADDR, PYRECS_CONTROL_PORT))
if DEBUG: print "connected!"
    
try:
    if DEBUG: print "opening reverse connection"
    #getattr(ic, "where_am_I_calling_from")(,)
    hostname = None
    while hostname is None:
        try:
            print "getting hostname...."
            hostname = ic.where_am_I_calling_from()[0]
        except:
            pass
    if DEBUG: print "calling from %s" % hostname
    if UDP_PRINT:
        UDPSock = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
        UDPSock.bind(('0.0.0.0', 0)) # grab an open port
        udp_listen_port = UDPSock.getsockname()[1]
        UDP_Printer_active = True
        ic.register_udp_writer(hostname, udp_listen_port)
        printserver_thread = threading.Thread(target=UDP_Printserver)
        printserver_thread.setDaemon(1)
        printserver_thread.start()

    if XMLRPC_PRINT:
        class RequestHandler(SimpleXMLRPCRequestHandler):
            rpc_paths = ('/RPC2',)
        XMLPrintserver = SimpleXMLRPCServer((hostname, 0), requestHandler=RequestHandler)
        print "Opening print service on %s at port %d" % XMLPrintserver.socket.getsockname()
        XMLPrintserver.allow_none = True
        XMLPrintserver.logRequests = False
        XMLPrintserver.register_function(localprint)
        XMLPrintserver.register_function(get_input)
        XMLPrintserver_thread = threading.Thread(target=XMLPrintserver.serve_forever)
        XMLPrintserver_thread.setDaemon(1)
        XMLPrintserver_thread.start()
        ic.register_xmlrpc_writer(XMLPrintserver.socket.getsockname()[0], XMLPrintserver.socket.getsockname()[1])
    if DEBUG: print "listener registered."
except:
    print "couldn't make reverse connection for print statement"
    raise


def Abort(signum = None, frame = None):
    icsig.Abort()
    #raise KeyboardInterrupt
    
def Suspend(signum = None, frame = None):
    icsig.Suspend()
    
def Break(signum = None, frame = None):
    icsig.Break()

signal.signal(signal.SIGINT, Abort)
if os.name.lower() == 'posix':
    signal.signal(signal.SIGTSTP, Suspend)
    signal.signal(signal.SIGQUIT, Break)

#restart the connection with protected communication threads
icsig = xmlrpclib.ServerProxy('%s:%d' % (PYRECS_SERVER_ADDR, PYRECS_SIGNAL_PORT), transport = threadedTransport())
ic = xmlrpclib.ServerProxy('%s:%d' % (PYRECS_SERVER_ADDR, PYRECS_CONTROL_PORT), transport = threadedTransport())


