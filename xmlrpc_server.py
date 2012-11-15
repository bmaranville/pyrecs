#from __future__ import with_statement
from SimpleXMLRPCServer import SimpleXMLRPCServer
from SimpleXMLRPCServer import SimpleXMLRPCRequestHandler
#from SimpleXMLRPCServer import SimpleXMLRPCDispatcher
from BaseHTTPServer import BaseHTTPRequestHandler
import threading, sys
import socket

from InstrumentController_unmixed import InstrumentController


#import xmlrpclib

DEBUG = True

WHITELIST = ['129.6.123.108',
             '129.6.120.90', 
             '129.6.120.84',
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


#####################################################################################
#  Experimental stuff to enable access from XMLHttpGet, which might not be a 
#  good idea, anyway... leaving it here below, for now
#####################################################################################

# Restrict to a particular path.
__version__ = "0.3"

#__all__ = ["SimpleXMLRPCServer", "SimpleXMLRPCRequestHandler"]

class RequestHandler0(SimpleXMLRPCRequestHandler):
    #global connected_peers
    #connected_peer = None
    rpc_paths = ('/RPC2',)
     # The Python system version, truncated to its first component.
    sys_version = "Python/" + sys.version.split()[0]

    # The server software version.  You may want to override this.
    # The format is multiple whitespace-separated strings,
    # where each string is of the form name[/version].
    server_version = "BaseHTTP/" + __version__

    # The default request version.  This only affects responses up until
    # the point where the request line is parsed, so it mainly decides what
    # the client gets back when sending a malformed request line.
    # Most web servers default to HTTP 0.9, i.e. don't send a status line.
    default_request_version = "HTTP/0.9"
    def parse_request(self):
        """Parse a request (internal).

        The request should be stored in self.raw_requestline; the results
        are in self.command, self.path, self.request_version and
        self.headers.

        Return True for success, False for failure; on failure, an
        error is sent back.

        """
        self.command = None  # set in case of error on the first line
        self.request_version = version = self.default_request_version
        self.close_connection = 1
        requestline = self.raw_requestline
        if DEBUG: print requestline
        if requestline[-2:] == '\r\n':
            requestline = requestline[:-2]
        elif requestline[-1:] == '\n':
            requestline = requestline[:-1]
        self.requestline = requestline
        words = requestline.split()
        if len(words) == 3:
            [command, path, version] = words
            if version[:5] != 'HTTP/':
                self.send_error(400, "Bad request version (%r)" % version)
                return False
            try:
                base_version_number = version.split('/', 1)[1]
                version_number = base_version_number.split(".")
                # RFC 2145 section 3.1 says there can be only one "." and
                #   - major and minor numbers MUST be treated as
                #      separate integers;
                #   - HTTP/2.4 is a lower version than HTTP/2.13, which in
                #      turn is lower than HTTP/12.3;
                #   - Leading zeros MUST be ignored by recipients.
                if len(version_number) != 2:
                    raise ValueError
                version_number = int(version_number[0]), int(version_number[1])
            except (ValueError, IndexError):
                self.send_error(400, "Bad request version (%r)" % version)
                return False
            if version_number >= (1, 1) and self.protocol_version >= "HTTP/1.1":
                self.close_connection = 0
            if version_number >= (2, 0):
                self.send_error(505,
                          "Invalid HTTP Version (%s)" % base_version_number)
                return False
        elif len(words) == 2:
            [command, path] = words
            self.close_connection = 1
            if command != 'GET':
                self.send_error(400,
                                "Bad HTTP/0.9 request type (%r)" % command)
                return False
        elif not words:
            return False
        else:
            self.send_error(400, "Bad request syntax (%r)" % requestline)
            return False
        self.command, self.path, self.request_version = command, path, version

        # Examine the headers and look for a Connection directive
        self.headers = self.MessageClass(self.rfile, 0)

        conntype = self.headers.get('Connection', "")
        if conntype.lower() == 'close':
            self.close_connection = 1
        elif (conntype.lower() == 'keep-alive' and
              self.protocol_version >= "HTTP/1.1"):
            self.close_connection = 0
        return True

    def do_OPTIONS(self):
        """Handles an OPTIONS preflighting (ignores it!)"""
        print "handling OPTIONS"
        print self.headers
        response = "OK!"
        #
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")  
        self.send_header("Access-Control-Allow-Methods", "POST")
        #self.send_header("Access-Control-Allow-Methods", "GET")
        #self.send_header("Access-Control-Allow-Methods", "OPTIONS")  
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Accept", "*/*")
        self.send_header("Access-Control-Max-Age", "1728000")  
        self.send_header("Vary", "Accept-Encoding")  
        self.send_header("Content-Encoding", "gzip")  
        self.send_header("Content-Length", "0")  
        self.send_header("Keep-Alive", "timeout=2, max=100")  
        self.send_header("Connection", "Keep-Alive")  
        self.send_header("Content-type", "text/plain")  
        #self.send_header("Content-type", "text/plain")        
        self.end_headers()
        #self.wfile.write(response)

        # shut down the connection
        #self.wfile.flush()
        self.connection.shutdown(1)
    def do_POST(self):
        """Handles the HTTP POST request.

        Attempts to interpret all HTTP POST requests as XML-RPC calls,
        which are forwarded to the server's _dispatch method for handling.
        """
        print "I am handling a POST"
        # Check that the path is legal
        if not self.is_rpc_path_valid():
            self.report_404()
            return

        try:
            # Get arguments by reading body of request.
            # We read this in chunks to avoid straining
            # socket.read(); around the 10 or 15Mb mark, some platforms
            # begin to have problems (bug #792570).
            max_chunk_size = 10*1024*1024
            size_remaining = int(self.headers["content-length"])
            L = []
            while size_remaining:
                chunk_size = min(size_remaining, max_chunk_size)
                L.append(self.rfile.read(chunk_size))
                size_remaining -= len(L[-1])
            data = ''.join(L)
            print data
            #connected_peers.add(self.connection.getpeername()[0])
            self.server.connected_peer = self.connection.getpeername()[0]

            # In previous versions of SimpleXMLRPCServer, _dispatch
            # could be overridden in this class, instead of in
            # SimpleXMLRPCDispatcher. To maintain backwards compatibility,
            # check to see if a subclass implements _dispatch and dispatch
            # using that method if present.
            response = self.server._marshaled_dispatch(
                    data, getattr(self, '_dispatch', None)
                )
        except Exception, e: # This should only happen if the module is buggy
            # internal error, report as HTTP server error
            self.send_response(500)

            # Send information about the exception if requested
            if hasattr(self.server, '_send_traceback_header') and \
                    self.server._send_traceback_header:
                self.send_header("X-exception", str(e))
                self.send_header("X-traceback", traceback.format_exc())

            self.end_headers()
        else:
            # got a valid XML RPC response
            self.send_response(200)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Type", "text/xml")
            self.send_header("Content-length", str(len(response)))
            self.end_headers()
            self.wfile.write(response)
            print "response: ", response.__repr__()

            # shut down the connection
            self.wfile.flush()
            self.connection.shutdown(1)



