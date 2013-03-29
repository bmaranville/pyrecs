import xmlrpclib
import threading
import time
import socket

class xint(xmlrpclib.ServerProxy):
    def __init__(self, host):
        xmlrpclib.ServerProxy.__init__(self, host)
    def __getattr__(self, *args, **kwargs):
        return xmlrpclib.ServerProxy.__getattr__(self, *args, **kwargs)
        
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
       
class threadedServerProxy(xmlrpclib.ServerProxy):
    #def __init__(self, host, **kwargs):
    #    xmlrpclib.ServerProxy.__init__(self, host, **kwargs)
    def __getattr__(self, *args, **kwargs):
        args = (self,) + args
        getterThread = InThread(xmlrpclib.ServerProxy.__getattr__, *args, **kwargs)
        getterThread.start()
        while getterThread.is_alive():
            time.sleep(0.001) # fast loop?
        return getterThread.retrieve()


class threadedTransport(xmlrpclib.Transport):
    def request(self, *args, **kwargs):
        args = (self,) + args
        getterThread = InThread(xmlrpclib.Transport.request, *args, **kwargs)
        getterThread.setDaemon(1)
        getterThread.start()
        getterThread.join()
        while not getterThread.isFinished():
            time.sleep(0.001) # fast loop?
        return getterThread.retrieve()

class MyTransport2(xmlrpclib.Transport):
    """ run xmlrpc transport, but ignore any system IOError problems """
    def request(self, *args, **kwargs):
        try:
            result = xmlrpclib.Transport.request(self, *args, **kwargs)
        except socket.error as (errno, msg):
            if errno != 4:
                raise
            result = "Interrupted"
        return result

        
ic = xmlrpclib.ServerProxy('http://andr.ncnr.nist.gov:8001', transport = threadedTransport())
print ic.funcs
ic.where_am_I_calling_from()
