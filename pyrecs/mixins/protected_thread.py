import threading
import functools
import signal
import time

DEBUG = False
TO_PROTECT = [
    "updateState",
    "PrintCounts",
    "PrintMonitor",
    "PencilCount",
    "GetHardMotorPos",
    "GetMotorPos",
    "GetSoftMotorPos",
    "PrintMotorPos",
    "SetHardMotorPos",
    "SetSoftMotorPos",
    "fix",
    "rel",
    "moveMotor",
    "moveMultiMotor",
    "DriveMotor",
    "DriveMotorIncrement",
    "DriveMotorTied",
    "DriveMotorByName",
    "GetMotorByName",
    "DriveMultiMotor",
    "DragCount",
    "RapidScan_new",
    "RapidScan",
    "PrintAllMotorPos",
    "PrintTemperature",
    "SetTemperature",
    "PrintField",
    "PrintLowerLimits",
    "PrintUpperLimits",
    "SetLowerLimit",
    "SetUpperLimit",
    "measure",
    "oneDimScan",
    "RunScan",
    "RunScanFile",
    "PeakScan",
    "FindPeak",
    "FindLine",
    "FindPeakTied",
    "DrivePeak",
    "RunICPSequenceFile",
    "RunSequence",
    "RunIBuffer",
]
    
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

def inthread(func):
    """ decorator to make a function run in a separate thread:
    it watches the thread in a non-blocking way (looping) so that
    we can still make interrupts with ctrl-c, ctrl-z and ctrl-\ """
    
    @functools.wraps(func)
    def new_func(self, *args, **kw):
        if DEBUG: print threading.currentThread()
        # this is a bit of a cheat, but the first arg is always "self", so use it:
        if not self.threading_enabled: # bail out!
            return func(self, *args, **kw)
        if self._inthread_running == True: # we're already in a protected thread
            return func(self, *args, **kw) # execute function unchanged
        else: # start a new thread and set all the flags
            self._inthread_running = True
            self._aborted = False
            self._suspended = False
            self._break = False
            # store old handlers
            orig_handlers = {}
            for sig in [signal.SIGINT, signal.SIGQUIT, signal.SIGTSTP]:
                orig_handlers[sig] = signal.getsignal(sig)
            # register new handlers                
            signal.signal(signal.SIGTSTP, self.Suspend)
            signal.signal(signal.SIGINT, self.Abort)
            signal.signal(signal.SIGQUIT, self.Break)
            
            thr = InThread(func, self, *args, **kw)
            thr.start()
            while not thr.isFinished():
                time.sleep(0.001) # fast loop?
                
            # done with thread
            # restore handlers
            for sig in [signal.SIGINT, signal.SIGQUIT, signal.SIGTSTP]:
                signal.signal(sig, orig_handlers[sig])
            # reset flags
            self._inthread_running = False
            self._aborted = False
            self._suspended = False
            self._break = False
            return thr.retrieve()
          
    return new_func

class ProtectedThreadMixin:
    """ Mixin to protect instrument-control functions in a separate thread, that need
    to be interrupted in a graceful way.  Overrides the standard signal handlers 
    when the function is called, and restores them when the function is finished.
        
    Use as a Mixin class (needs methods from InstrumentController), i.e.
    via Multiple Inheritance mechanism:
    
    class NewIC(InstrumentController, ProtectedThreadMixin):
        def __init__(self):
            InstrumentController.__init__(self)
            FlipperControlMixin.__init__(self)
        
    or use helper function Mixin:
    MixIn(InstrumentController, ProtectedThreadMixin)
    """
    
    def __init__(self):
        self._inthread_running = False
        self.threading_enabled = True
        # now, wrap all the functions that need to be protected.
        for funcname in TO_PROTECT:
            func = getattr(self.__class__, funcname)
            new_func = inthread(func)
            setattr(self.__class__, funcname, new_func)   
             
# for compatibility and easy mixing:
mixin_class = ProtectedThreadMixin
        
    
