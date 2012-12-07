#from IPython import InteractiveShell
from icp_compat import prefilter_ICP
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


#prefilter_ICP.activate_prefilter(None, log_unfiltered = False) # no callbacks in this client
# make connections to the server
#try: 
if DEBUG: print "starting signaling connection"
icsig = xmlrpclib.ServerProxy('%s:%d' % (PYRECS_SERVER_ADDR, PYRECS_SIGNAL_PORT))
if DEBUG: print "starting command connection"
ic = xmlrpclib.ServerProxy('%s:%d' % (PYRECS_SERVER_ADDR, PYRECS_CONTROL_PORT))
if DEBUG: print "connected!"

icp_conversions = ic.GetICPConversions()
    
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

if DEBUG: print "connections restarted."

####################################################################################################################

# decorators that automatically add functions to the ICP prefilter,
# based on the function name and number of arguments.
#def arg_command(func):
#    """ register a command that takes arguments with the prefilter """
#    argspec = inspect.getargspec(func)
#    opt_args_num = len(argspec.defaults) if argspec.defaults is not None else 0
#    base_num = len(argspec.args) - 1 - opt_args_num # remove the "self" argument and keywords
#    argnums = [base_num + i for i in range(opt_args_num+1)] # one choice for each optional keyword
#    prefilter_ICP.icpt.arg_commands.add(func.__name__, argnums)
#    return func
#    
#def en_dis_command(func):
#    """ register an enable/disable command with the prefilter """
#    prefilter_ICP.icpt.en_dis_commands.add(func.__name__)
#    return func
#    
#def increment_command(func):
#    """ register an increment command with the prefilter
#    syntax is 'd4i=2' to increment motor 4 by 2 deg. """
#    prefilter_ICP.icpt.increment_commands.add(func.__name__)
#    return func
#    
#def tied_command(func):
#     """ register an tied-motor command with the prefilter
#    syntax is 'd4t=2' to drive motor 4 to 2.0 and motor 3 (4-1) to 1.0 """
#    argspec = inspect.getargspec(func)
#    opt_args_num = len(argspec.defaults) if argspec.defaults is not None else 0
#    base_num = len(argspec.args) - 1 - opt_args_num # remove the "self" argument and keywords
#    argnums = [base_num + i for i in range(opt_args_num+1)] # one choice for each optional keyword
#    prefilter_ICP.icpt.tied_commands.add(func.__name__, argnums)
#    return func

#class ICPPyrecsConnect(object):
#    """ a local server proxy that translates commands to Pyrecs API. 
#    
#    This class should contain a method with the same name as the 
#    equivalent ICP command for every ICP command you want to map.
#    
#    Using the decorators for arg_command, en_dis_command and 
#    increment_command you can register these methods with the IPython
#    prefilter, which will intercept commands in the ICP syntax and
#    convert them to calls to this class' methods
#    
#    e.g. 
#    @arg_command
#    def pa(self, motornum=None):
#        if motornum is None:
#            for n in self.viper_to_name:
#                self.pa(n)
#        else:
#            name = self.viper_to_name[motornum]
#            soft = self.api.readValue(name + '.softPosition')
#            hard = self.api.readValue(name + '.hardPosition')
#            self.write('motor %d soft: % .4f\tmotor %d hard: % .4f\n' % (motornum, soft, motornum, hard))
#    
#    The decorator registers a function named 'pa' with the prefilter, expecting either 0 or 1 arguments,
#    because of the keyword (they are optional)
#    If the prefilter catches a command of the form "pa 1" or "pa1" or "pa,1" or "pa=1"
#    it will call this class' pa method as "ic.pa(1)", while "pa" would become "ic.pa()"
#    where "ic" is an instance of this class.
#    
#    """
#    def __init__(self, api_connection):
#        self.api = api_connection
#        self.logging_enabled = True
#        self._tc = [] # temperature controllers        
#        
#    def write(self, msg):
#        import sys
#        sys.stdout.write(msg)
#    
#    @en_dis_command
#    def p(self, enable):
#        """ enable = True will turn on polarization_enabled """
#        self.api.polarization_enabled = bool(enable)
#    
#    @arg_command    
#    def pa(self, motornum=None):
#        self.api.PrintCounts(motornum)
#    
#    @increment_command
#    @arg_command
#    def d(self, motornum, position, relative=False):
#        self.api.DriveMotor(motornum, position, increment=relative)
#        
#    @arg_command
#    def set(self, motornum, position):
#        self.api.SetHardMotorPos(motornum, position)
#        
#    @arg_command
#    def init(self, motornum, position):
#        self.api.SetSoftMotorPos(motornum, position)
#    
#    @arg_command
#    def wl(self, new_wavelength=None):
#        if new_wavelength is None:
#            current_wavelength = self.api.GetWavelength()
#            self.write('current wavelength: %.5f (Angstroms)' % (current_wavelength,))
#        else:
#            self.api.SetWavelength(new_wavelength)
#            
#    @arg_command    
#    def ct(self, duration=-1):
#        self.api.PrintCounts(duration)
#    
#    @arg_command    
#    def fp(self, motornum, mrange, mstep, duration=-1):
#        self.api.FindPeak(motornum, mrange, mstep, duration)
#        
#    @arg_command    
#    def rapid(self, motornum, mstart, mstop, speed_ratio=1.0, step_time=0.2):
#        self.api.RapidScan_new(motornum, mstart, mstop, speed_ratio=speed_ratio, step_time=step_time)
#        
#    def putline_reverse(self, msg):
#        self.write(self.reverse_colors(msg))
#        
#    def reverse_colors(self, msg):
#        return '\x1b[7m' + msg + '\x1b[0m'
#    
#    @arg_command
#    def statline(self):
#        mesg = 'Status Flags              '
#        if self.logging_enabled:
#            mesg += 'W+  '
#        else:
#            mesg += 'W-  '
#        if self._tc == []:
#            mesg += 'T-  '
#        else: 
#            mesg += 'T+  '
#        if self.api.polarization_enabled:
#            mesg += 'P+  '
#        else:
#            mesg += 'P-  '
#        
#        mesg += 'F:'
#        #for motornum in self.viper_to_name:
#        #    mesg += '% 2d' % motornum
#        padding = ' '
#        pad_length = 80 - len(mesg)
#        mesg += pad_length * padding
#        #mesg += '\n'
#        
#        self.putline_reverse(mesg)

    
def get_cmds():
    #icp_conversions = ic.GetICPConversions()
    if DEBUG: print "icp_conversions: ", icp_conversions
    prefilter_ICP.icpt.register_icp_conversions(icp_conversions)

if DEBUG: print "ready to roll..."
get_cmds()
prefilter_ICP.activate_prefilter(None, log_unfiltered = False) # no callbacks in this client


                
