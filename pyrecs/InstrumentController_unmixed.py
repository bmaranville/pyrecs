from __future__ import with_statement
import time, sys, glob, copy, os
sys.path.append(os.path.join(os.environ['HOME'],'bin'))
sys.path.append(os.path.join(os.environ['HOME'],'bbm','python'))
#import numpy # not really using for much except float32 and int32
import signal # need this to make sure interrupts only go to main thread!
import tempfile
import pprint
import inspect
from subprocess import Popen, PIPE
#from PSD import BrookhavenDetector
from FitGnuplot import *
from StringIO import StringIO
import math
from copy import deepcopy, copy
import simplejson

import itertools
import functools
#from ordered_dict import OrderedDict
import collections
if hasattr(collections, 'OrderedDict'):
    from collections import OrderedDict
else:
    from ordered_dict import OrderedDict
from prefilter_ICP import prefilterICPString
from ICPSequenceFile import PyICPSequenceFile, PyICPSequenceStringIO
from pyrecs.icp_compat import ibuffer
from pyrecs.icp_compat.icp_to_pyrecs_table import ICP_CONVERSIONS
from InstrumentParameters import InstrumentParameters
import pyrecs.drivers
from pyrecs.publishers import update_xpeek
from pyrecs.publishers import ICPDataFile, publisher
from pyrecs.publishers.gnuplot_publisher import GnuplotPublisher

FLOAT_ERROR = 1.0e-7
DEBUG = False
AUTO_MOTOR_DISABLE = True
FPT_OFFSET = 1
        
class Publisher:
    """ generic measurement publisher.  inherit and override the classes 
    for specific publishers (file, Xpeek, manifest, etc.) """
    def __init__(self, *args, **kwargs):
        pass
       
    def publish_start(self, state, scan_definition, **kwargs):
        """ called to record the start time of the measurement """
        pass
    
    def publish_archive_creation(self, state, scan_definition, **kwargs):
        """ called to record the creation of the data archive
        (needed in the MONITOR.REC file) """
        pass
    
    def publish_datapoint(self, state, scan_definition, **kwargs):
        """ called to record a new datapoint """
        pass
    
    def publish_end(self, state, scan_definition, **kwargs):
        """ called when measurement complete - archive finished """
        pass

class GenericScaler(object):
    """ generic counter/scaler """
    def __init__(self, *args, **kwargs):
        self.CountByMonitor = self.notImplemented
        self.CountByTime = self.notImplemented
        self.IsCounting = self.notImplemented
        self.GetElapsed = self.notImplemented
        self.AbortCount = self.notImplemented
        self.ResetScaler = self.notImplemented
                
    def notImplemented(self, *args, **kwargs):
        print("fake scaler: does nothing")
        return 0
   
    def GetCounts(self, *args, **kwargs):
        print("fake scaler: does nothing")
        return 0,0,0
        
    def CountByTime(self, preset, **kwargs):
        time.sleep(abs(preset))
        print("fake scaler: does nothing")
        
    def Count(self, preset, **kwargs):
        time.sleep(abs(preset))
        print("fake scaler: does nothing")
        result = {'count_time': preset, 'monitor': preset, 'counts': 1, 'elapsed_time': preset, 'psd_data': 0}
        return result
        
class GenericMotorController(object):
    def __init__(self):
        self.MoveMotor = self.notImplemented
        self.GetMotorPos = self.notImplemented
        self.SetMotorPos = self.notImplemented
        self.CheckMoving = self.notImplemented
        self.CheckHardwareLimits = self.notImplemented
        self.DisableMotor = self.notImplemented
        self.EnableMotor = self.notImplemented
        self.StopMotor = self.notImplemented

    def notImplemented(self, *args, **kwargs):
        print("fake motor controller: does nothing")
        return 0      
 
class Fitter:
    """ generic fitting.  Give a function (string) and parameter names with default values """
    def __init__(self, xdata, ydata, params):
        self.params = params
        
    def do_fit(self):
        """ do the fitting and return result (dict) where result[pn] = val, result[pn_err] = val_err """
        result = {}
        return result
            
class StdoutWriter:
    """ writes output to sys.stdout and flushes """
    import sys
    def write(self, msg):
        sys.stdout.write(msg)
        sys.stdout.flush()

class LogWriter:
    """ class for writing to log file """
    def __init__(self, logfilename, logging_enabled = True, log_timestamp = True):
        self.logging_enabled = logging_enabled
        self.logfilename = logfilename
        self.log_timestamp = log_timestamp
    
    def enable_logging(self):
        self.logging_enabled = True
        
    def disable_logging(self):
        self.logging_enabled = False
        
    def write(self, msg):
        outstr = ''
        if self.log_timestamp:
            outstr += time.ctime() + ': '
        outstr += inspect.stack()[2][3] + ': '
        outstr += msg + '\n'
        with open(self.logfilename, 'a') as log:
            log.write(outstr)

class ExpressionTrajectory:
    """ the FOR loop for doing scans... 
    evaluate the expression for each movable at each point """
    def __init__(self, iterations = 1, expressions = [], state = {}):
        """ expressions should be of the form [('movable_id', 'text expression')]
        for example, [('a3', 'i * 0.01 + 0.2'), ('a4',  '2.0 * a3')]
        they will be evaluated in order so keep that in mind when specifying 
        relationships between state variables """
        self.state = state
        self.expressions = expressions
        self.iterations = iterations 
        self.i = 0 # for loop starts here!
        
    def __getitem__(self, index):
        target_state = copy(self.state)
        target_state['i'] = int(index)
        target_list = []
        for expr in self.expressions:
            if isinstance(expr, ExpressionTrajectory):
                target_list.append(expr.get_all())
            else:
                movable = expr[0]
                target_state[movable] = eval(expr[1], globals(), target_state)
                target_list.append((movable, target_state[movable]))
        return target_list
    
    def get_all(self):
        all_targets = []
        for i in range(self.iterations):
            all_targets.append(self.get_target(i))
        return all_targets
  
    def __iter__(self):
        return self
    
    def next(self):
        if self.i >= self.iterations:
            raise StopIteration
        else:
            return_val = self.get_target(self.i)
            self.i += 1
            return return_val
        
class ListTrajectory:
    """ this one defines a recipe for moving from one state to another,
    along a predefined path.  Pick up data along the way.
    Base class is most general - defines a list of steps.
    Should this be an iterator, in the programmatic sense?
    This only changes a subset of state variables, but needs 
    to know all of them in case they are related. 
    Positions is a 2-d list of strings, each entry an
    expression defining the new state based on itself or other state variable."""
    def __init__(self, state, things_to_move, positions):
        """ things_to_move should be a list of dictionaries """
        self.state = state
        self.things_to_move = things_to_move
        self.positions = positions
        self.index = 0
        
    def diff(self, index1, index2):
        diff = {}
        for i, movable in enumerate(self.things_to_move):
            diff[movable] = eval(self.positions[i][index1], self.state) - eval(self.positions[i][index2], self.state)
    
    def get_target(self, index):
        target = []
        for i, movable in enumerate(self.things_to_move):
            target[movable] = eval(self.positions[i][index], self.state)
            
    def get_states(self):
        num_movables = len(self.things_to_move)
        num_states = len(self.positions[0])
        states = []
        new_state = dict(self.state)
        for i in range(num_states):
             for j in range(num_movables):
                 new_state[self.things_to_move[j]] = eval(positions[j][i], new_state)
             states.append(new_state)          

class InstrumentController:
    """called once, holds all the methods for moving motors, counting etc.
    with functionality similar to the ICP program"""
    def __init__(self, datafolder = None):
        #### First, the base modules
        self.ip = InstrumentParameters() # handles all configuration files
        
        self.num_motors = int(self.ip.num_motors)
        self.motor_numbers = [m['M'] for m in self.ip.InstrCfg['motors'].values()]
        self.motor_names = ['a%d' % i for i in self.motor_numbers]
        self.motor_lookup = dict(zip(self.motor_names, self.motor_numbers))
        self._auto_motor_disable = AUTO_MOTOR_DISABLE
        
        
        VIPER_mot_line = int(self.ip.InstrCfg['VIPER_mot_line'])
        #vme = VME(port = self.ip.GetSerialPort(VIPER_mot_line)) # initialize the VME box (motors, scaler)
        
        self.scaler = GenericScaler() # counter controller
        self.mc = GenericMotorController() # motor controller, happens to be same as counter controller right now
        self.psd = None
        term_line = int(self.ip.InstrCfg['term_line,'])
            
        if datafolder is None:
            datafolder = os.getcwd()
        self.datafolder = datafolder # where data will be stored
        os.chdir(self.datafolder)
        #### Now, for the optional modules:
        self._tc = [] # temperature controller(s)
        self._magnet = [] # magnet power supply(s)
        #self.fixed_motors = set() # none start out fixed
        self.gpib = None
        self.loopdelay = 0.1
        self.psd_data = None
        self.plot = None
        self.writers = set([StdoutWriter()]) # handles screen output (and logging?)
        #self.fitter = FitGnuplot
        self.gauss_fitter = FitGaussGnuplot
        self.line_fitter = FitLineAlternate
        self.cossquared_fitter = FitCosSquaredGnuplot
        self.quadratic_fitter = FitQuadraticGnuplot
        #self.publishers = [xpeek_broadcast()]
        #self.default_publishers = [update_xpeek.XPeekPublisher(), GnuplotPublisher(auto_poisson_errorbars=False)]
        self.default_publishers = [update_xpeek.XPeekPublisher()]
        #self.default_publishers = [GnuplotPublisher(auto_poisson_errorbars=False)]
        self.logfilename = self.getNextFilename(time.strftime('%b%d%Y_'), '.LOG')
        self.logwriter = LogWriter(self.logfilename)
        self.get_input = raw_input #defaults to local prompt - override in server
        #self.writers.add(LogWriter(self.logfilename))
        self.polarization_enabled = True
        #self.setPSDActive(False) #start with pencil detector by default
        self._suspended = False # clear suspend flag at the beginning
        self._break = False
        self._aborted = False
        self.station_number = int(self.ip.InstrCfg['sta#'])
        self.num_scalers = int(self.ip.InstrCfg['#scl'])
        self.id = self.ip.GetNameStr()
        self.motor_retries = 1 #should be 5?
        self.last_fitted_peak = {} # this will be filled after FindPeak
        #self.dataOutput = ICPDataFile.ICPDataFile(self) # initialize output handler (writes ICP-style data files)
        #self.fileManifest = FileManifest()
        
        #setup of signal handlers: taking over ctrl-c, ctrl-z and ctrl-\
        #signal.signal(signal.SIGTSTP, self.Suspend)
        #signal.signal(signal.SIGINT, self.Abort)
        #signal.signal(signal.SIGQUIT, self.Break)

        self.sequence = StringIO() # empty sequence to start
        
        self.Count = self.scaler.Count
        # command alias list: these commands will come in from the filter
        # ICP commands:
        
        self.pwl = self.GetWavelength
        self.wl = self.SetWavelength
        self.pa = self.PrintMotorPos
        self.pt = self.PrintTemperature
        self.pu = self.PrintUpperLimits
        self.pl = self.PrintLowerLimits
        self.init = self.SetHardMotorPos
        self.set = self.SetSoftMotorPos
        self.st = self.SetTemperature
        self.d = self.DriveMotor
        self.di = functools.partial(self.DriveMotor, relative=True)
        self.ct = self.PrintCounts
        self.mon = self.PrintMonitor
        self.w = self.setLogging
        self.fp = self.FindPeak
        self.fpt = self.FindPeakTied
        self.l = self.SetLowerLimit
        self.u = self.SetUpperLimit
        self.ri = self.RunIBuffer
        self.rsf = self.RunICPSequenceFile
        self.rs = self.RunSequence
        self.dp = self.DrivePeak #New!
        
        
        self.icp_conversions = ICP_CONVERSIONS
        
        self.device_registry = {'motor': 
                                {'names': self.motor_names, 'updater': self.DriveMotorByName, 'getter': self.GetMotorByName },
                                #'scaler':
                                #{'names': ['scaler'], 'updater': self.scaler, 'getter': self.GetCountSettings },
                                'temperature':
                                {'names': [], 'updater': self.SetTemperatureByName, 'getter': self.GetTemperatureByName },
                                'magnet':
                                {'names': [], 'updater': self.SetMagnetByName, 'getter': self.GetMagnetByName } }
        
        self.state = {}
        self.getState()
        
        # lastly, initialize any base classes (mixins) that aren't initialized yet
        #for base in self.__class__.__bases__:
        #    base.__init__(self)
  
    def GetICPConversions(self):
        return self.icp_conversions
        
    def Abort(self, signum=None, frame=None):
        """ when trapped, the abort just sets a flag """
        self._aborted = True
        
    def ResetAbort(self):
        """ call this when you're ready to start taking commands again """
        self._aborted = False
        
    def Suspend(self, signum=None, frame=None):
        """ this one is a toggle - hit it again to unsuspend """
        #if self._suspended:
        #    print "Resuming (Suspend flag cleared)"
        #else:
        #    print "Suspend: program will pause"
        if not self._suspended: self.write('Suspending...')
        self._suspended = not self._suspended
        
    def Break(self, signum=None, frame=None):
        #print "Break: (stop scan and fit)"
        self._break = True
    
    def exit(self):
        """ Convenience function to make it possible to exit with 'exit' instead of 'exit()' 
        This is specific to IPython """
        #_ip.magic('exit')
        exit()
    
    def validate_motor(func):
        """ check to see if motor is in the range of addressable motors """
        @functools.wraps(func)
        def wrapper(*args, **kwds):
            motornum = args[1] if len(args) > 1 else None
            me = args[0]
            #num_motors = me.num_motors # self!!
            motor_numbers = me.motor_numbers
            if (motornum is not None) and (motornum not in motor_numbers):
                me.write('requested motor is out of range')
                return
            else:
                return func(*args, **kwds)
        return wrapper
        
    def register_writer(self, writer):
        self.writers.add(writer)
        
    def write(self, screen_msg, file_msg = None, timestamp = False):
        """ Dual printing to screen and file.  
        Default behavior (if no separate file msg specified) is to print the same message to both. """
        screen_msg = str(screen_msg)
        if file_msg == None:
            file_msg = screen_msg
        for writer in self.writers:
            writer.write(screen_msg)
        self.logwriter.write(file_msg)
    
    def register_publisher(self, publisher):
        self.default_publishers.add(publisher)
        
    def putline_reverse(self, msg):
        for writer in self.writers:
            writer.write(self.reverse_colors(msg))
        
    def reverse_colors(self, msg):
        return '\x1b[7m' + msg + '\x1b[0m'
    
    def statline(self):
        mesg = 'Status Flags              '
        if self.logwriter.logging_enabled:
            mesg += 'W+  '
        else:
            mesg += 'W-  '
        if self._tc == []:
            mesg += 'T-  '
        else: 
            mesg += 'T+  '
        if self.polarization_enabled:
            mesg += 'P+  '
        else:
            mesg += 'P-  '
        
        mesg += 'F:'
        for motornum in self.ip.GetFixedMotors():
            mesg += '% 2d' % motornum
        padding = ' '
        pad_length = 80 - len(mesg)
        mesg += pad_length * padding
        #mesg += '\n'
        
        self.putline_reverse(mesg)
            
    def GetWavelength(self):
        return self.ip.GetWavelength()
        
    def SetWavelength(self, wl):
        self.ip.SetWavelength(wl)
    
    def RemoveTemperatureDevice(self, device_num=None):
        if device_num is None:
            self.write('enter \'rtdev i\' to remove temperature controller \'i\'\n')
            self.write('(valid i values are between 1 and %d)\n' % (int(device_num), len(self._tc)))
        if device_num<1 or device_num>len(self._tc):
            self.write('%d is Not a valid temperature device (valid values are between 1 and %d)\n' % (int(device_num), len(self._tc)))
            return
        else:
            _ = self._tc.pop(device_num-1) # remove the key
            self.device_registry['temperature']['names'] = ['t%d' % (i+1) for i in range(len(self._tc))]
            
    def NewTemperatureDevice(self, driver_num=None, port=None, **kwargs):
        tdevices = pyrecs.drivers.temperature_controllers
        #print "Choose a driver for device %s:" % (str(devicename))
        if driver_num is None:
            self.write('Please specify a driver number from 1 to %d:\n (e.g. \'atdev 1\')\n' % (len(tdevices),))
            for i, td in enumerate(tdevices):
                self.write("%d: %s\n" % (i+1, td[0])) # label
            return         
        elif (int(driver_num) < 1 or int(driver_num)>len(tdevices)):
            self.write('invalid driver.\n')
            self.write('Please specify a driver number from 1 to %d:\n (e.g. \'atdev 1\')\n' % (len(tdevices),))
            for i, td in enumerate(tdevices):
                self.write("%d: %s\n" % (i+1, td[0])) # label
            return
        selection = tdevices[int(driver_num)-1]    
        #driver = __import__('pyrecs.drivers.'+selection[1], fromlist=selection[2])
        if len(self._tc) == 0:
            if port is None:
                # then use the default port
                port = self.ip.GetSerialPort(int(self.ip.InstrCfg['tmp_line']))
            else: 
                port = self.ip.GetSerialPort(int(port))
        else: # we already have a defined tc, adding another
            if port is None:
                self.write('Must specify a port for any additional (>1) temperature controllers, as\n')
                self.write('\'atdev [driver number] [port]\', e.g. \'atdev 1 5\',\n which corresponds to /dev/ttyUSB4 on the multiport adapter\n')  
                return
            else:
                port = self.ip.GetSerialPort(int(port))
        driver_module = __import__('pyrecs.drivers.'+selection[1], fromlist=['not_empty'])
        driver = getattr(driver_module, selection[2])
        new_tempcontroller = driver(port, **kwargs)
        self._tc.append(new_tempcontroller)
        dev_id = len(self._tc)
        settings = new_tempcontroller.getSettings()
        #settings_str = pprint.pformat(settings)
        settings_str = str(settings)
        self.write('device added: \n')
        self.write("%d: driver=%s, port=%s, settings=%s" % (dev_id, new_tempcontroller.label, new_tempcontroller.port,  settings_str))
        self.write('\nTo change settings for this driver, type e.g. \'tdev %d sample_sensor A\'\n' % (dev_id,))
        self.device_registry['temperature']['names'] = ['t%d' % (i+1) for i in range(len(self._tc))]
    
    def ConfigureTemperatureDevice(self, device_num, keyword=None, value=None):
        if (int(device_num) < 1 or int(device_num) > len(self._tc)):
            self.write('%d is Not a valid temperature device (valid values are between 1 and %d)\n' % (int(device_num), len(self._tc)))
            return
        elif value is None:
            tc = self._tc[device_num-1]
            settings = tc.getSettings()
            settings_str = pprint.pformat(settings)
            self.write("%d: driver=%s, port=%s, settings=\n  %s\n" % (device_num+1, tc.label, tc.port, settings_str))
            self.write('To remove, type \'rtdev %d\'\n' % (device_num+1))
            self.write('To change settings, type e.g. \'tdev %d sample_sensor A\'\n' % (device_num+1,))
        self.write(self._tc[int(device_num) -1].configure(keyword, value))
        
    def TemperatureDevice(self, device_num=None, keyword=None, value=None):
        if device_num is None:
            if len(self._tc) > 0: # there are temperature controllers defined
                print "Defined temperature controllers:"
                for i, tc in enumerate(self._tc):
                    settings = tc.getSettings()
                    settings_str = pprint.pformat(settings)
                    self.write("%d: driver=%s, port=%s, settings=\n  %s\n" % (i+1, tc.label, tc.port, settings_str))
                    self.write('To remove, type \'rtdev %d\'\n' % (i+1))
                self.write('To change settings, type e.g. \'tdev %d sample_sensor A\'\n' % (i+1,))
            else: 
                self.write('No defined temperature controllers.\n')
            self.write('To add a new (additional) temperature controller: \'atdev\'\n')
        else: # we're adding or reconfiguring a device
            self.ConfigureTemperatureDevice(device_num, keyword, value)
    
    def RemoveMagnetDevice(self, device_num=None):
        if device_num is None:
            self.write('enter \'rhdev i\' to remove magnet controller \'i\'\n')
            self.write('(valid i values are between 1 and %d)\n' % (int(device_num), len(self._magnet)))
        if device_num<1 or device_num>len(self._magnet):
            self.write('%d is Not a valid magnet device (valid values are between 1 and %d)\n' % (int(device_num), len(self._magnet)))
            return
        else:
            _ = self._magnet.pop(device_num-1) # remove the key
            self.device_registry['magnet']['names'] = ['h%d' % (i+1) for i in range(len(self._magnet))]
    
    def NewMagnetDevice(self, driver_num=None):
        hdevices = pyrecs.drivers.magnet_controllers
        #print "Choose a driver for device %s:" % (str(devicename))
        if driver_num is None:
            self.write('Please specify a driver number from 1 to %d:\n (e.g. \'ahdev 1\')\n' % (len(hdevices),))
            for i, hd in enumerate(hdevices):
                self.write("%d: %s\n" % (i+1, hd[0])) # label
            return         
        elif (int(driver_num) < 1 or int(driver_num)>len(hdevices)):
            self.write('invalid driver.\n')
            self.write('Please specify a driver number from 1 to %d:\n (e.g. \'ahdev 1\')\n' % (len(hdevices),))
            for i, hd in enumerate(hdevices):
                self.write("%d: %s\n" % (i+1, hd[0])) # label
            return
        selection = hdevices[int(driver_num)-1]    
        driver_module = __import__('pyrecs.drivers.'+selection[1], fromlist=['not_empty'])
        driver = getattr(driver_module, selection[2])
        new_magcontroller = driver()
        self._magnet.append(new_magcontroller)
        dev_id = len(self._magnet)
        settings = new_magcontroller.getSettings()
        #settings_str = pprint.pformat(settings)
        settings_str = str(settings)
        self.write('device added: \n')
        self.write("%d: driver=%s, settings=%s" % (dev_id, new_magcontroller.label, settings_str))
        self.write('\nTo change settings for this driver, type e.g. \'hdev %d comm_mode=gpib\'\n' % (dev_id,))
        self.device_registry['magnet']['names'] = ['h%d' % (i+1) for i in range(len(self._magnet))]
            
    def MagnetDevice(self, device_num=None, keyword=None, value=None):
        if device_num is None:
            if len(self._magnet) > 0: # there are temperature controllers defined
                print "Defined magnet controllers:"
                for i, mag in enumerate(self._magnet):
                    settings = mag.getSettings()
                    settings_str = pprint.pformat(settings)
                    self.write("%d: driver=%s, port=%s, settings=\n  %s\n" % (i+1, mag.label, mag.port, settings_str))
                    self.write('To remove, type \'rhdev %d\'\n' % (i+1))
                self.write('To change settings, type e.g. \'hdev %d sample_sensor A\'\n' % (i+1,))
            else: 
                self.write('No defined magnet controllers.\n')
            self.write('To add a new (additional) magnet controller: \'ahdev\'\n')
        else: # we're adding or reconfiguring a device
            self.ConfigureMagnetDevice(device_num, keyword, value)
    
    def ConfigureMagnetDevice(self, device_num, keyword=None, value=None):
        if (int(device_num) < 1 or int(device_num) > len(self._magnet)):
            self.write('%d is Not a valid magnet device (valid values are between 1 and %d)\n' % (int(device_num), len(self._magnet)))
            return
        self.write(self._magnet[int(device_num) -1].configure(keyword, value))
    
    def SetMagnetByName(self, magcontrollers, fields):
        """ pass a list of magnet controllers and fields to set """
        # device mapping: from "h1" to 0, "h10" to 9, etc...
        for mcname, field in zip(magcontrollers, fields):
            mc = self._magnet[int(mcname[1:]) - 1]
            mc.setField(field)
            
    def GetMagnetByName(self, mc_name, poll=False):
        mcnum = int(mc_name[1:])-1
        if poll==True:
            field = self._magnet[mcnum].getField()
            self.state[mc_name] = field
            return field
        else:
            return self.state.get(mc_name, '')
            
    def SetTemperatureByName(self, tempcontrollers, temps):
        """ pass a list of temperature controllers and temperatures to set """
        # device mapping: from "t1" to 0, "t10" to 9, etc...
        for tcname, temp in zip(tempcontrollers, temps):
            tc = self._tc[int(tcname[1:]) - 1]
            tc.setTemp(temp)
            
    def GetTemperatureByName(self, tc_name, poll=False):
        tcnum = int(tc_name[1:])-1
        if poll==True:
            tc_state = self._tc[tcnum].getState()
            self.state[tc_name] = tc_state
            return tc_state
        else:
            return self.state.get(tc_name, {})
    
    def getNextFilename(self, prefix, suffix, path = None):
        """ find the highest filenumber with prefix and suffix
        and return 'prefix + (highest+1) + suffix' """
        if path is None: path = self.datafolder 
        fl = glob.glob1(path, prefix+'*'+suffix)
        fl.sort(key=lambda fn: fn[len(prefix):-len(suffix)])
        if len(fl) == 0:
            # first scan!
            biggest = 0
        else:
            biggest = fl[-1][len(prefix):-len(suffix)]
        new_filenum = int(biggest) + 1
        new_filenum_str = '%03d' % new_filenum
        new_filename = prefix + new_filenum_str + suffix
        return new_filename
    
    def getState(self, poll=False):
        """ get a dictionary representing the current instrument state
        If poll==True, grab a current reading from all hardware """
        # first grab the motors and collimation etc. from the backend
        self.state.update(self.ip.getState())
        # then augment the state definition with stuff only the InstrumentController knows
        self.state.setdefault('scaler_gating_mode', 'TIME')
        self.state.setdefault('scaler_time_preset', 1.0)
        self.state.setdefault('scaler_monitor_preset', 1000)
        #self.state.setdefault('polarization_enabled', self.polarization_enabled)
        #self.state.setdefault('psd_enabled', self.getPSDActive() )
        #self.state.setdefault('flipper1', self.flipperstate[0])
        #self.state.setdefault('flipper2', self.flipperstate[1])
        for groupname in self.device_registry:
            device_group = self.device_registry[groupname]
            for devicename in device_group['names']:
                if device_group['getter'] is not None:
                    self.state.update({devicename: device_group['getter'](devicename, poll=poll)})
        self.state.setdefault('project_path', self.datafolder)
        self.state.setdefault('measurement_id', None) # this is like a filename, perhaps.  we're not in a measurement
        self.state.setdefault('result', {}) # needs to be filled by a measurement!
        self.state['magnets_defined'] = len(self._magnet)
        #for i, mc in enumerate(self._magnet):
        #    self.state['h%d' % (i+1)] = mc.getField()
        self.state['temp_controllers_defined'] = len(self._tc)
        #for i, tc in enumerate(self._tc):
        #    self.state['t%d' % (i+1)] = tc.getTemp()
        self.state['timestamp'] = time.time()
        return self.state.copy()
    
    def GetCountSettings(self, scaler_name):
        counter_state = {
            'scaler_gating_mode': self.state.get('scaler_gating_mode', 'TIME'),
            'scaler_time_preset': self.state.get('scaler_time_preset', 1.0),
            'scaler_monitor_preset': self.state.get('scaler_monitor_preset', 1000) }
        return counter_state
    
    def updateState(self, target_state):
        new_state = target_state.copy()
        devices_moved = set()
        for device_type in self.device_registry:
            device_cfg = self.device_registry[device_type]
            devices_to_move = [d for d in new_state if (d in device_cfg['names'])]
            positions = [new_state[d] for d in devices_to_move]
            if len(devices_to_move) > 0:
                updater = device_cfg['updater'] # should return a function
                updater(devices_to_move, positions)
            devices_moved.update(devices_to_move)
        for device in devices_moved:
            new_state.pop(device) # remove the moved devices from the new information to be added to state
        self.state.update(new_state) # add all the non-movable updates to state (count type, etc.)
        return deepcopy(self.state)
        
    def setLogging(self, enable):
        """ console command accessed via equivalent ICP command 'w+' or 'w-':
        Enable/Disable logging """
        self.logwriter.logging_enabled = enable
                
    def PrintCounts(self, duration):
        """ console command accessed via equivalent ICP command 'ct':
        get counts for a given duration using the active counter """
        result = self.Count(duration)
        msg = 'count time: %.4f monitor: %g counts: %g' % (result['count_time'], result['monitor'], result['counts'])
        self.write(msg, file_msg = ('Count: '+ msg))
        
    def PrintMonitor(self, duration=-5):
        """ console command accessed via equivalent ICP command 'mon':
        get monitor counts for a given duration (defaults to 5s) using the active counter """
        result = self.Count(duration)
        self.write('count time: %.4f  counts: %d' % (result['count_time'], result['monitor']))
        
    def PencilCount(self, duration, reraise_exceptions = False):
        """ PencilCount(self, duration, reraise_exceptions = False):
        Count with the pencil detector.  All interaction is through self.scaler object """
        duration = float(duration)
        self.scaler.ResetScaler()
        if duration < 0: # count by time
            duration *= -1.0 # reset the negative sign
            self.scaler.CountByTime(duration)
        else: # count vs. monitor
            self.scaler.CountByMonitor(duration)
        
        while self.scaler.IsCounting(): 
            if self._aborted:
                print "\nAborting"
                self.scaler.AbortCount()
                #if not reraise_exceptions:
                #    self._aborted = False
                break
            time.sleep(self.loopdelay)                
            
        count_time, monitor, counts = self.scaler.GetCounts()
        elapsed_time = self.scaler.GetElapsed()
        psd_data = None
        result = {'count_time': count_time, 'monitor': monitor, 'counts': counts, 'elapsed_time': elapsed_time, 'psd_data': psd_data}
        self.state['result'].update(result)
        return result
    
        
#     def AppendPSDResult(self, datafile):
#        """ write a chunk of data (from PSD) to a file, appending it to end """
#        ####################################################
#        ### NOT COMPATIBLE WITH ICP FORMAT AT THE MOMENT ###
#        ### (need to break into length-80 lines)         ###
#        ####################################################
#        f_out = open(datafile, 'a+')
#        templine = StringIO()
#        # writing to local string because it's pretty fast
#        numpy.savetxt(data, templine, fmt='%d', delimiter=',')
#        f_out.write(templine.read() + '\n')
#        f_out.close()
    
    @validate_motor
    def GetHardMotorPos(self, motornum):
        hard_pos = self.mc.GetMotorPos(motornum)
        self.ip.SetHardMotorPos(motornum, hard_pos)
        return hard_pos
        
    @validate_motor
    def GetMotorPos(self, motornum):
        # default to retrieving the soft motor pos: 
        # this is what we need for writing data files, driving motors etc.
        return self.GetSoftMotorPos(motornum)
            
    @validate_motor
    def GetSoftMotorPos(self, motornum, use_stored = False):
        if use_stored:
            hard_pos = self.ip.GetHardMotorPos(motornum)
        else:
            hard_pos = self.GetHardMotorPos(motornum)
        offset = self.ip.GetSoftMotorOffset(motornum)
        soft_pos = hard_pos - offset
        return soft_pos
  
    @validate_motor
    def PrintMotorPos(self, motornum = None, use_stored = False):
        """ retrieve the motor position from the motor controller 
        to mimic the way ICP works, if no argument is given, get all values """
        if motornum:
            if use_stored:
                hard_pos = self.ip.GetHardMotorPos(motornum)
            else:
                hard_pos = self.GetHardMotorPos(motornum)
            offset = self.ip.GetSoftMotorOffset(motornum)
            soft_pos = hard_pos - offset
            self.write(' Soft: A%02d=%8.4f\n Hard: A%02d=%8.4f\n' % (motornum, soft_pos, motornum, hard_pos))
        else:  # no motor specified - get them all
            self.PrintAllMotorPos()
    
    @validate_motor   
    def GetStoredSoftMotorPos(self, motornum):
        """ get motor position (soft) from stored backend value """
        hard_pos = self.ip.GetHardMotorPos(motornum)
        offset = self.ip.GetSoftMotorOffset(motornum)
        soft_pos = hard_pos - offset
        return soft_pos
         
    @validate_motor    
    def SetHardMotorPos(self, motornum, pos):
        """ initialize the hardware motor position """
        self.mc.SetMotorPos(motornum, pos) # update the motor controller
        self.ip.SetHardMotorPos(motornum, pos) # update the MOTORS.BUF file
        
    @validate_motor
    def SetSoftMotorPos(self, motornum, pos):
        """ initialize the soft motor position """
        hard_pos = self.GetHardMotorPos(motornum)
        new_offset = hard_pos - pos
        self.ip.SetSoftMotorOffset(motornum, new_offset) # update the MOTORS.BUF file
    
    @validate_motor
    def fix(self, motornum):
        """ set the motor to "fixed", which means it won't be moved during an ibuffer scan """
        self.ip.SetMotorFixed(motornum)
        #self.fixed_motors.add(motornum)
        
    @validate_motor
    def rel(self, motornum):
        """ release a previously "fixed" motor """
        self.ip.SetMotorReleased(motornum)
        #self.fixed_motors.remove(motornum)
    
    @validate_motor
    def moveMotor(self, motornum, position, check_limits = True, reraise_exceptions = True):
        """ send motor move command to VME and wait for it to complete motion """
        # first, make sure we should move:
        if check_limits:
            ul = self.ip.GetUpperLimits()[motornum-1] # upper limit (array index for limits starts at zero, not 1)
            ll = self.ip.GetLowerLimits()[motornum-1] # lower limit
            if position > ul:
                print 'Error: Moving motor %d to %.4f would violate upper limit of %.4f' % (motornum, position, ul)
                return 'limit error'
            if position < ll:
                print 'Error: Moving motor %d to %.4f would violate lower limit of %.4f' % (motornum, position, ll)
                return 'limit error'
        # then start moving
        self.mc.EnableMotor(motornum)
        self.mc.MoveMotor(motornum, position)
        while 1:
            if self._aborted: break
            if self.mc.CheckMoving(motornum) == False: break
            if self.mc.CheckHardwareLimits(motornum) == True: break
            time.sleep(self.loopdelay)
            
        self.mc.StopMotor(motornum)
        while self.mc.CheckMoving(motornum) == True:
            time.sleep(self.loopdelay)
        self.mc.DisableMotor(motornum)
        #if not reraise_exceptions: # reset the abort flag
        #    self._aborted = False


    def moveMultiMotor(self, motornum_list, soft_position_list, check_limits = True, reraise_exceptions = True, disable=None):
        """ send motor move command to VME and wait for it to complete motion """
        disable = disable if disable is not None else self._auto_motor_disable
        motornum_list = list(motornum_list)
        soft_position_list = list(soft_position_list)
        # convert soft positions to hard positions:
        hard_position_list = []
        for soft_pos, motnum in zip(soft_position_list, motornum_list):
            hard_position_list.append(soft_pos + self.ip.GetSoftMotorOffset(motnum))
            
        if len(motornum_list) == 0:
            # no motors to move: return
            return
        if not len(motornum_list) == len(soft_position_list):
            print "Error: need a position for each motor"
            return
        # first, make sure we should move:
        if check_limits:            
            ul = self.ip.GetUpperLimits() # upper limit (array index for limits starts at zero, not 1)
            ll = self.ip.GetLowerLimits() # lower limit
            for motornum, position in zip(motornum_list, hard_position_list):
                if position > ul[motornum-1]:
                    print 'Error: Moving motor %d to %.4f would violate upper limit of %.4f' % (motornum, position, ul[motornum-1])
                    return 'limit error'
                if position < ll[motornum-1]:
                    print 'Error: Moving motor %d to %.4f would violate lower limit of %.4f' % (motornum, position, ll[motornum-1])
                    return 'limit error'
                    
        # then start moving
        def recursive_motor_move(motornum_list, hard_position_list, soft_position_list):
            if len(motornum_list) == 0: return # when the list is empty, start the while loop
            motnum = motornum_list.pop() # pull the top motor off the list
            motname = 'a%d' % (motnum,)
            pos = hard_position_list.pop() # pull the top position off the list (reduces list length)
            softpos = soft_position_list.pop()
            self.mc.EnableMotor(motnum)
            self.mc.MoveMotor(motnum, pos)
            self.ip.SetHardMotorPos(motnum, pos) # update MOTORS.BUF
            self.state[motname] = softpos # update state dictionary
            recursive_motor_move(motornum_list, hard_position_list, soft_position_list)
            # this part doesn't get run until all motors are enabled and moving:
            while 1:
                if self._aborted: break
                if self.mc.CheckMoving(motnum) == False: break
                if self.mc.CheckHardwareLimits(motnum) == True: break
                time.sleep(self.loopdelay)           
            self.mc.StopMotor(motnum)
            while self.mc.CheckMoving(motnum) == True: # make sure we're stopped before disabling
                time.sleep(self.loopdelay)
            if disable: self.mc.DisableMotor(motnum)
            new_hardpos = self.mc.GetMotorPos(motnum)
            new_softpos = new_hardpos - self.ip.GetSoftMotorOffset(motnum)
            self.ip.SetHardMotorPos(motnum, new_hardpos) # update MOTORS.BUF
            self.state[motname] = new_softpos # update state dictionary
            # and it doesn't exit until all sub-calls have returned (all motors are stopped and disabled)
            return
            
        recursive_motor_move(motornum_list, hard_position_list, soft_position_list)
        #if not reraise_exceptions: # reset the abort flag
        #    self._aborted = False
       
    @validate_motor
    def DriveMotor(self, motornum, position, relative=False, do_backlash = True, check_limits = True, reraise_exceptions = False):
        if relative:
            position = self.GetMotorPos(motornum) + position
        motors_to_move = [motornum,]
        destinations = [position,]
        self.DriveMultiMotor(motors_to_move, destinations, do_backlash, check_limits, reraise_exceptions)
    
    def DriveMotorIncrement(self, motornum, position, do_backlash = True, check_limits = True, reraise_exceptions = False):
        self.DriveMotor(motornum, position, relative=True, do_backlash=do_backlash, check_limits=check_limits, reraise_exceptions=reraise_exceptions)
    
    def DriveMotorTied(self, motornum, position, relative=False, do_backlash = True, check_limits = True, reraise_exceptions = False):
        motors_to_move = [motornum, motornum-1]
        destinations = [position, position/2.0]
        self.DriveMultiMotor(motors_to_move, destinations, do_backlash, check_limits, reraise_exceptions)
    
    def DriveMotorByName(self, motors_to_move, position_list, do_backlash = True, check_limits = True, reraise_exceptions = False):
        motor_list = [self.motor_lookup[s] for s in motors_to_move]
        # i.e. 'a3' is motor 3
        self.DriveMultiMotor(motor_list, position_list, do_backlash, check_limits, reraise_exceptions) 
        
    def GetMotorByName(self, motorname, poll=False):
        motornum = self.motor_lookup[motorname]
        if poll==True: 
            return self.GetSoftMotorPos(motornum)
        else:
            return self.GetStoredSoftMotorPos(motornum)
    
    def DriveMultiMotor(self, motors_to_move, position_list, do_backlash = True, check_limits = True, reraise_exceptions = False):
        """ Drive motor to new position with optional backlash, and tolerance and limit checking """   
        position_list = [float(p) for p in position_list]
        motors_to_move = list(motors_to_move) # make a copy to work with
        if len(motors_to_move) == 0:
            # no motors to move: return
            return
        if not len(motors_to_move) == len(position_list):
            print "Error: need a position for each motor"
            return
        positions = dict(zip(motors_to_move, position_list)) # lookup dictionary for target positions
        tolerance = self.ip.GetAllMotorTolerances() # lookup dictionary for tolerance (by motor number)
        current_pos = {}
        def remove_finished_motors(motlist, poslist):
            # local utility function (obviously)
            #new_mot_list = []
            #new_pos_list = []
            for motnum, target_pos in zip(motlist, poslist):
                current_pos[motnum] = self.GetMotorPos(motnum)
                if abs(current_pos[motnum] - target_pos) < tolerance[motnum]:
                    i = motlist.index(motnum)
                    motlist.pop(i)
                    poslist.pop(i)
                    #new_mot_list.append(motnum)
                    #new_pos_list.append(target_pos)
            #return new_mot_list, new_pos_list
        #motors_to_move, position_list = remove_finished_motors(motors_to_move, position_list) # if they're already there, take them off the list
        remove_finished_motors(motors_to_move, position_list) # if they're already there, take them off the list
        
        if len(motors_to_move) == 0:
            # all the motors are already within tolerance
            return
            
        # otherwise, start the motion:
        motors_to_backlash = []
        if do_backlash:
            backlash = {}
            backlash_pos = {}
            for motornum in motors_to_move:
                backlash[motornum] = self.ip.GetMotorBacklash(motornum)
                backlash_pos[motornum] = positions[motornum] - backlash[motornum] #backlash to negative side
                motor_delta = positions[motornum] - current_pos[motornum]
                if (motor_delta < 0 and backlash[motornum] > 0) or (motor_delta > 0 and backlash[motornum] < 0): # then we need to backlash
                    motors_to_backlash.append(motornum)
                    
        # first round of moves: backlash and forward moves mixed
        positions1 = []
        for motornum in motors_to_move:
            if motornum in motors_to_backlash:
                positions1.append(backlash_pos[motornum])
            else:
                positions1.append(positions[motornum])
            
        # Drive!
        for i in range(self.motor_retries):
            if self._aborted: break
            result = self.moveMultiMotor(motors_to_move, positions1, check_limits, reraise_exceptions)
            if result == 'limit error': break
            #motors_to_move, positions1 = remove_finished_motors(motors_to_move, positions1)
            remove_finished_motors(motors_to_move, positions1)
            # silently continues if still outside tolerance after motor_retries!
                       
        # second round of moves: only move backlashed motors
        positions2 = []
        for motornum in motors_to_backlash:
            positions2.append(positions[motornum])
            
        # Final Drive!
        for i in range(self.motor_retries):
            if self._aborted: break
            result = self.moveMultiMotor(motors_to_backlash, positions2, check_limits, reraise_exceptions)
            if result == 'limit error': break
            #motors_to_backlash, positions1 = remove_finished_motors(motors_to_backlash, positions2)
            remove_finished_motors(motors_to_backlash, positions2)
            # silently continues if still outside tolerance after motor_retries!
            
        # can check for problems here:  if the lists aren't empty, they didn't meet tolerances:
        unfinished_motors = motors_to_move + motors_to_backlash
        unreached_targets = positions1 + positions2
        if len(unfinished_motors) > 0 : 
            self.write('error! these motors did not reach target position:\n')
            for m,p in zip(unfinished_motors, unreached_targets):
                self.write('motor %d target: %.4f\n reached: %.4f\n' % (m, p, current_pos[m]))
            
        return
        
    @validate_motor        
    def DragCount(self, motornum, start_angle, stop_angle, reraise_exceptions = False):
        """ new, non-ICP function: 
        start counting, move detector from start_angle to stop_angle,
        stop counting, and retrieve result.  
        (Useful for detector sensitivity scans with main beam) """
        psd = self.psd
        self.DriveMotor(motornum, start_angle)
        self.scaler.ResetScaler()
        psd.AIM_CLEAR()
        psd.AIM_ARM()
        self.scaler.CountByTime(-1)
        self.mc.EnableMotor(motornum)
        self.mc.MoveMotor(motornum, stop_angle)
        start_time = time.time()
        while self.mc.CheckMoving(motornum) and not self.mc.CheckHardwareLimits(motornum):
            if self._aborted:
                print "aborted with ctrl-c"
                #if not reraise_exceptions:
                #    self._aborted = False
                break
            time_now = time.time() - start_time
            pos_now = self.mc.GetMotorPos(motornum)
            print '%.2f seconds, motor %d = %s' % (time_now, motornum, pos_now)
            time.sleep(self.loopdelay)
        
        self.scaler.AbortCount()
        count_time, monitor, counts = self.scaler.GetCounts()
        self.scaler.GetElapsed()
        print 'count time: %.3f' % count_time
        self.mc.DisableMotor(motornum)
        psd.AIM_DISARM()
        data = psd.AIM_XFER()
        psd.AIM_SAVE('asd.raw')
        return data
    
    @validate_motor
    def RapidScan_new(self, motornum = None, start_angle = None, stop_angle = None, speed_ratio=1.0, step_time=0.2, client_plotter = None, reraise_exceptions = False, disable=None):
        """ new, non-ICP function: count while moving.
                returns: (position, counts, elapsed_time)
        
        This is a better implementation will take advantage of using VIPER's internal clock.
        VIPER command: 'join [list [clock microseconds] [motor position 1] [clock microseconds] [scaler read] [clock microseconds]] ";"'
        will give a better accuracy on motor position (~ 300 microseconds between clock reads in testing)
        
        Alternatively could just do a bracketed read and average motor position:
        'join [list [clock microseconds] [motor position 1] [scaler read] [motor position 1] [clock microseconds]] ";"'
        
        which might take 1 ms total, plus many milliseconds for transmission.
        
        speed_ratio reduces the vscale on the motor for the duration of the scan, then returns it to what it was before the scan.
        """ 
        disable = disable if disable is not None else self._auto_motor_disable
        (tmp_fd, tmp_path) = tempfile.mkstemp() #temporary file for plotting
        os.close(tmp_fd) # we'll open the file by name later
        title = 'ic.RapidScan(%d, %.4f, %.4f)' % (motornum, start_angle, stop_angle)
        
        # edges of bins: where we measure
        position_list = []
        time_list = []
        cum_counts_list = []
        
        # derived quantities per bin:
        counts_list = []
        bin_position_list = []
        bin_time_list = []
        cps_list = []
        
        if speed_ratio > 1.0 or speed_ratio <= 0.0: speed_ratio = 1.0 # protect against speeders and idiots.
        
        start_vscale = self.mc.sendCMD('set mc(%d,vscale)' % (motornum))
        start_bscale = self.mc.sendCMD('set mc(%d,bscale)' % (motornum))
        
        reduced_vscale = speed_ratio * float(start_vscale)
        reduced_bscale = speed_ratio * float(start_bscale)
        
        self.DriveMotor(motornum, start_angle)
        self.scaler.ResetScaler()
        self.scaler.CountByTime(-1)
        self.mc.EnableMotor(motornum)
        start_time = time.time()
        
        tol = self.ip.GetMotorTolerance(motornum)
        motor_offset = self.ip.GetSoftMotorOffset(motornum)
        direction = math.copysign(1.0, (stop_angle - start_angle))
        hard_stop = stop_angle + motor_offset + direction*5.0*tol # drive a little past end position.
        print "hard_stop: ", hard_stop
        # reduce the speed...
        self.mc.sendCMD('set mc(%d,vscale) %.4f' % (motornum, reduced_vscale))
        self.mc.sendCMD('set mc(%d,bscale) %.4f' % (motornum, reduced_bscale))
        self.mc.sendCMD('MotorConfigLoad %d' % (motornum,))
        
        tstr, ctstr, motstr, ackstr = self.mc.sendCMD('join [list [clock microseconds] [scaler read] [motor position %d] [motor move %d %.6f]] ";"' % (motornum,motornum,hard_stop)).split(";")
        start_time = int(tstr)
        old_time = start_time
        time_list.append(start_time)
        cum_count = float(ctstr.split()[2])
        cum_counts_list.append(cum_count)
        pos = float(motstr) 
        soft_pos = pos - motor_offset
        position_list.append(soft_pos)
        #self.mc.MoveMotor(motornum, hard_stop)
        
        #while self.mc.CheckMoving(motornum):
        #soft_pos = start_angle
        
        readout_cmd = 'join [list [clock microseconds] [motor position %d] [scaler read] [motor position %d] [clock microseconds]] ";"' % (motornum, motornum)
        #print "moving?", self.mc.CheckMoving(motornum)
        while 1:
        #while self.mc.CheckMoving(motornum):
            if self._aborted:
                self.write("aborted")
                #if not reraise_exceptions:
                #    self._aborted = False
                break
                
            t_bef, mot_bef, ctstr, mot_aft, t_aft = self.mc.sendCMD(readout_cmd).split(";")
            #print [t_bef, mot_bef, ctstr, mot_aft, t_aft]
            new_cum_count = float(ctstr.split()[2])
            cum_counts_list.append(new_cum_count)
            new_time = (int(t_bef) + int(t_aft))/2.0 - start_time # microseconds
            new_hard_pos = (float(mot_bef) + float(mot_aft))/2.0
            
            self.ip.SetHardMotorPos(motornum, float(mot_aft)) # update MOTORS.BUF
            new_soft_pos = new_hard_pos - motor_offset
            position_list.append(new_soft_pos)
            
            new_count = new_cum_count - cum_count
            counts_list.append(new_count)

            time_list.append(new_time)
            new_delta_time = new_time - old_time
            new_cps = new_count/new_delta_time * 1.0e6 # convert microseconds to seconds
            cps_list.append(new_cps)
            
            new_bin_position = (new_soft_pos + soft_pos)/2.0
            bin_position_list.append(new_bin_position)
            new_bin_time = (new_time + old_time)/2.0
            bin_time_list.append(new_bin_time)
            
            #self.write(str(new_bin_position) + '\t'+ str(new_cps))
            out_str = '%.4f\t%.4f' % (new_bin_position, new_cps)
            with open(tmp_path, 'a') as tmp_file:
                tmp_file.write(out_str + '\n')
                
            self.updateGnuplot(tmp_path, title, error_bars=False) 

            if (direction * (stop_angle - new_soft_pos)) < tol:
                break
            soft_pos = new_soft_pos
            old_time = new_time
            cum_count = new_cum_count
            
            time.sleep(step_time)
        
        self.scaler.AbortCount()
        count_time, monitor, counts = self.scaler.GetCounts()
        self.scaler.GetElapsed()
        self.write('count time: %.3f' % count_time)
        self.mc.StopMotor(motornum)
        while self.mc.CheckMoving(motornum) == True: # make sure we're stopped before disabling
            time.sleep(self.loopdelay)
        if disable: self.mc.DisableMotor(motornum)
        new_pos =  self.mc.GetMotorPos(motornum)
        self.ip.SetHardMotorPos(motornum, new_pos) # update MOTORS.BUF
        # return the motor to original speed.
        self.mc.sendCMD('set mc(%d,vscale) %s' % (motornum, start_vscale))
        self.mc.sendCMD('set mc(%d,bscale) %s' % (motornum, start_bscale))
        self.mc.sendCMD('MotorConfigLoad %d' % (motornum,))
       
        return bin_position_list, cps_list, bin_time_list
        
    @validate_motor
    def RapidScan(self, motornum = None, start_angle = None, stop_angle = None, client_plotter = None, reraise_exceptions = False, disable=AUTO_MOTOR_DISABLE):
        """ new, non-ICP function: count while moving.
                returns: (position, counts, elapsed_time) """
        
        (tmp_fd, tmp_path) = tempfile.mkstemp() #temporary file for plotting
        os.close(tmp_fd) # immediately close the open OS-level file handle.  We'll open the file by name later
        title = 'ic.RapidScan(%d, %.4f, %.4f)' % (motornum, start_angle, stop_angle)
        
        position_list = []
        ptime_list = []
        cum_counts_list = []
        counts_list = []
        cps_list = []
        ctime_list = []
        self.DriveMotor(motornum, start_angle)
        self.scaler.ResetScaler()
        self.scaler.CountByTime(-1)
        self.mc.EnableMotor(motornum)
        start_time = time.time()
        
        motor_offset = self.ip.GetSoftMotorOffset(motornum)
        t1 = time.time() - start_time
        cum_counts_list.append( self.scaler.GetCounts()[2] )
        t2 = time.time() - start_time
        ctime = (t1+t2)/2.0
        ctime_list.append(ctime)
        pos =  self.mc.GetMotorPos(motornum)
        self.ip.SetHardMotorPos(motornum, pos) # update MOTORS.BUF
        soft_pos = pos - motor_offset
        position_list.append(soft_pos)
        t3 = time.time() - start_time
        ptime = ((t2+t3)/2.0)
        
        hard_stop = stop_angle + motor_offset
        self.mc.MoveMotor(motornum, hard_stop)
        
        #while self.mc.CheckMoving(motornum):
        soft_pos = start_angle
        tol = self.ip.GetMotorTolerance(motornum)
        while 1:
            if self._aborted:
                self.write("aborted")
                #if not reraise_exceptions:
                #    self._aborted = False
                break
            t1 = time.time() - start_time
            cum_counts_list.append( self.scaler.GetCounts()[2] )
            t2 = time.time() - start_time
            new_pos =  self.mc.GetMotorPos(motornum)
            self.ip.SetHardMotorPos(motornum, new_pos) # update MOTORS.BUF
            new_soft_pos = new_pos - motor_offset
            t3 = time.time() - start_time
            
            new_count = cum_counts_list[-1] - cum_counts_list[-2]
            counts_list.append(new_count)
            new_ctime = (t1+t2)/2.0
            ctime_list.append(new_ctime)
            new_cps = new_count/(new_ctime - ctime)
            cps_list.append(new_cps)
            
            new_ptime = (t2+t3)/2.0
            pslope = (new_soft_pos - soft_pos) / (new_ptime - ptime)
            estimated_pos = soft_pos + ((new_ctime - ptime) * pslope) # linearly interpolate, 
            # based on count timestamp vs. position timestamp
            position_list.append(estimated_pos)
            
            self.write(str(position_list[-1]) + '\t'+ str(cps_list[-1]))
            out_str = '%.4f\t%.4f' % (estimated_pos, new_cps)
            with open(tmp_path, 'a') as tmp_file:
                tmp_file.write(out_str + '\n')
                
            self.updateGnuplot(tmp_path, title)
            
            if abs(new_soft_pos - soft_pos) <= tol:
                break
            soft_pos = new_soft_pos
            ptime = new_ptime
            ctime = new_ctime
            time.sleep(0.2)
        
        self.scaler.AbortCount()
        count_time, monitor, counts = self.scaler.GetCounts()
        self.scaler.GetElapsed()
        self.write('count time: %.3f' % count_time)
        self.mc.StopMotor(motornum)
        while self.mc.CheckMoving(motornum) == True: # make sure we're stopped before disabling
            time.sleep(self.loopdelay)
        if disable: self.mc.DisableMotor(motornum)
        new_pos =  self.mc.GetMotorPos(motornum)
        self.ip.SetHardMotorPos(motornum, new_pos) # update MOTORS.BUF
       
        return position_list, cps_list, ctime_list
    
        
    def PrintAllMotorPos(self, use_stored = False):
        soft_line = ' Soft: '
        hard_line = ' Hard: '
        for i,m in enumerate(self.motor_numbers):
            ii = i+1
            if self._aborted: break
            if use_stored:
                hard_pos = self.ip.GetHardMotorPos(m)
            else:
                hard_pos = self.GetHardMotorPos(m)
                self.ip.SetHardMotorPos(m, hard_pos) # update, because we can!
            offset = self.ip.GetSoftMotorOffset(m)
            soft_pos = hard_pos - offset
            soft_line += 'A%02d=%8.4f ' % (m, soft_pos)
            hard_line += 'A%02d=%8.4f ' % (m, hard_pos)
            #self.write(' Soft: A%02d=%7.3f\n Hard: A%02d=%7.3f' % (motornum, soft_pos, motornum, hard_pos))
            #self.write('A%02d: %.4f\t' % (i, pos))
            if ( ii % 5 == 0) or (ii >= len(self.motor_numbers)):
                self.write(soft_line + '\n')
                self.write(hard_line + '\n')
                soft_line = ' Soft: '
                hard_line = ' Hard: '
       
    def PrintAllStoredMotorPos(self):
        self.PrintAllMotorPos(use_stored=True)         
                
               
    def PrintTemperature(self):
        if self._tc == []:
            self.write( " Error: No temperature controller defined ")
        else:
            for i, tc in enumerate(self._tc):
                self.write('temp controller %d: setpoint = %.4f, t_sample = %.4f, t_control= %.4f\n' % (i+1, tc.getSetpoint(), tc.getSampleTemp(), tc.getControlTemp()))           
    
    def SetTemperature(self, temperature):
        if self._tc == []:
            self.write(" Error: no temperature controller defined ")
        else: 
            self._tc[0].setTemp(temperature)
            
    def PrintField(self):
        if len(self._magnet) < 1: 
            self.write("No magnet controllers defined")
        else:
            for i, mc in enumerate(self._magnet):
                self.write('magnet controller %d: %s' % (i+1, mc.getFieldString()))
                
    def PrintLowerLimits(self):
        result = self.ip.GetLowerLimits()
        for i in self.motor_numbers:
            self.write('L%d: %.4f\t' % (i, result[i-1]))
    
    
    def PrintUpperLimits(self):
        result = self.ip.GetUpperLimits()
        for i in self.motor_numbers:
            self.write('U%d: %.4f\t' % (i, result[i-1]))
        
    @validate_motor
    def SetLowerLimit(self, motornum, position):
        self.ip.SetLowerLimit(motornum, position)
        
    @validate_motor    
    def SetUpperLimit(self, motornum, position):
        self.ip.SetUpperLimit(motornum, position)
             
    
    def measure(self, params = {}):
        params.setdefault('scaler_gating_mode', 'TIME')
        params.setdefault('scaler_time_preset', 1.0)
        params.setdefault('scaler_monitor_preset', 1000)
        if params['scaler_gating_mode'] == 'TIME':
            count_time = params['scaler_time_preset']
            if 'scaler_prefactor' in params and params['scaler_prefactor'] != 0.0: count_time *= params['scaler_prefactor']
            return self.updateState({'result': self.Count(-1.0 * count_time)} )
        elif params['scaler_gating_mode'] == 'NEUT':
            monitor_target = params['scaler_monitor_preset']
            if 'scaler_prefactor' in params and params['scaler_prefactor'] != 0.0: monitor_target *= params['scaler_prefactor']
            return self.updateState({'result': self.Count(monitor_target)} )
        
    def scanGenerator(self, scan_definition, extra_dicts = []):
        scan_state = {}
        context = {}
        context.update(math.__dict__)
        context.update(self.getState()) # default dictionaries to give context to calculations
        for extra_dict in extra_dicts:
            context.update(extra_dict)
        scan_expr = OrderedDict(scan_definition['vary'])
        for i in range(scan_definition['iterations']):
            scan_state['i'] = i
            for d in scan_expr:
                scan_state[d] = eval(str(scan_expr[d]), context, scan_state)
            yield scan_state.copy()
                
    """ rewrite FindPeak as generic scan over one variable, publishing to XPeek and File, using Fitter """
    def oneDimScan(self, scan_definition, publishers = [], extra_dicts = [], publish_end=True, publish_time=False):
        """ the basic unit of instrument control:  
        initializes the instrument to some known state (scan_definition['init_state']), 
        publishes the start (to files, xpeek, etc in publishers)
        then creates an iterator that takes a step at a time, 
        (increasing the value of 'i' in the local scope)
        and publishing a new datapoint after each measurement
        finally, the end state is published to all publishers """
        self._break = False
        #self._aborted = False
        # these are defined as tuple trees in order to pass easily over xmlrpc, 
        # but internally they are treated as dicts
        #scan_definition['vary'] = OrderedDict(scan_definition['vary'])
        #scan_definition['init_state'] = OrderedDict(scan_definition['init_state'])
        scan_definition.setdefault('namestr', self.ip.GetNameStr().upper())
        new_state = deepcopy(self.getState(poll=True))
        new_state.update(OrderedDict(scan_definition['init_state']))
        for pub in publishers:
            pub.publish_start(new_state, scan_definition)
        iterations = scan_definition['iterations']
        scan_expr = OrderedDict(scan_definition['vary'])
        context = {}
        context.update(math.__dict__)
        context.update(deepcopy(new_state)) # default dictionaries to give context to calculations
        for extra_dict in extra_dicts:
            context.update(extra_dict)
        data = []
        all_states = []
        output_state = deepcopy(new_state)
        scan_state = {}
        # write headers
        self.write(pprint.pformat(scan_definition) + '\n')
        out_str  = ''.join(['% 11s\t' % d for d in scan_expr])
        out_str += '% 11s\n' % ('counts',)
        self.write(out_str)
        for i in range(iterations):
            scan_state['i'] = i
            if self._break: break
            if self._aborted:
                self.write("aborted ")
                break
            if self._suspended:
                self.write( "suspended: press Ctrl-z to resume" )
                while self._suspended:
                    if self._break: break
                    if self._aborted: 
                        return
                    time.sleep(self.loopdelay)
            ##############################################
            #  REPLACE all the above with a "with" block!
            ##############################################
            for d in scan_expr:
                scan_state[d] = eval(str(scan_expr[d]), context, scan_state)
            
            self.updateState(OrderedDict(scan_definition['init_state'])) # load all the initial states!    
            new_state = self.updateState(scan_state.copy()) # load all the varying states
            output_state = self.measure(new_state)
            result = output_state['result']
            scan_state['result'] = output_state['result'].copy()
            data.append(result['counts'])
                
            # send immediate feedback to writers:
            out_str  = ''.join(['%15g\t' % scan_state[d] for d in scan_expr])
            out_str += '%11g\n' % (result['counts'],)
            self.write(out_str)
                
            # publish datapoint
            reported_count_time = None
            if publish_time:
                reported_count_time = result['count_time'] / 60000.0 # from milliseconds to minutes
                
            for pub in publishers:
                pub.publish_datapoint(output_state, scan_definition, count_time=reported_count_time)

            all_states.append(scan_state)
            yield output_state, scan_state
        
        if publish_end:
            for pub in publishers:
                pub.publish_end(output_state, scan_definition)               
        return
    
    
    def DryRunScan(self, scan_definition, extra_dicts = []):
        
        iterations = scan_definition['iterations']
        scan_expr = OrderedDict(scan_definition['vary'])
        new_state = OrderedDict(scan_definition['init_state'])
        context = {}
        context.update(math.__dict__)
        context.update(deepcopy(new_state)) # default dictionaries to give context to calculations
        for extra_dict in extra_dicts:
            context.update(extra_dict)
        
        scan_state = {}
        scan_states = []
        for i in range(iterations):
            scan_state['i'] = i
            for d in scan_expr:
                scan_state[d] = eval(str(scan_expr[d]), context, scan_state)
            scan_states.append(deepcopy(scan_state))
        
        return scan_states
                
    def RunScan(self, scan_definition, auto_increment_file=True, gnuplot=True, this_publisher=None):
        """runs a scan_definition with default publishers and FindPeak publisher """
        if this_publisher is None: this_publisher = ICPDataFile.ICPDataFilePublisher()
        publishers = self.default_publishers + [this_publisher,]
        if gnuplot == True: publishers.append(GnuplotPublisher(auto_poisson_errorbars=False))
        new_scan_def = deepcopy(scan_definition)
        
        if auto_increment_file==True:
            prefix, suffix = os.path.splitext(scan_definition['filename'])
            if suffix == '': suffix = '.' + self.ip.GetNameStr().lower()
            new_filename = self.getNextFilename(prefix, suffix)
            new_scan_def['filename'] = new_filename
        
        scan = self.oneDimScan(new_scan_def, publishers = publishers)
        self.ResetAbort()
        for datapoint in scan:
            pass # everything gets done in the iterator
    
    def RunScanFile(self, json_filename, this_publisher=None):
        """ opens and runs a scan from a definition in a json file """
        with open(json_filename, 'r') as json_file:
            scan_definition = simplejson.loads(json_file.read())
        self.RunScan(scan_definition, this_publisher=this_publisher)
    
    def DryRunScanFile(self, json_filename):
        """ opens and runs a scan from a definition in a json file """
        with open(json_filename, 'r') as json_file:
            scan_definition = simplejson.loads(json_file.read())
        return self.DryRunScan(scan_definition)
    
    def PeakScan(self, movable, numsteps, mstart, mstep, duration, mprevious, t_movable=None, t_scan=False, comment=None, Fitter=None, auto_drive_fit=False, gnuplot=True):
        suffix = '.' + self.ip.GetNameStr().lower()
        if t_scan:
            new_filename = self.getNextFilename('fpt_%s_' % movable, suffix)
            pos_expression = '%f + (i * %f)' % (mstart, mstep)
            if t_movable == None: t_movable = 'a%d' % (int(movable[1:])-FPT_OFFSET,)
            pos_expression_t = str(movable) + ' / 2.0' 
            scan_expr = [(movable, pos_expression), (t_movable, pos_expression_t)]
        else:
            new_filename = self.getNextFilename('fp_%s_' % movable, suffix)
            # put this in terms the scanner understands:
            pos_expression = '%f + (i * %f)' % (mstart, mstep)
            scan_expr = [(movable, pos_expression)]
        
        if duration < 0.0: init_state = [('scaler_gating_mode', 'TIME'), ('scaler_time_preset',-1.0*duration)]
        else: init_state = [('scaler_gating_mode', 'NEUT'), ('scaler_monitor_preset', duration)]
        
        scan_definition = {'namestr': self.ip.GetNameStr(), 
                           'comment': comment,
                           'iterations': numsteps,
                           'filename': new_filename,
                           'init_state': init_state,
                           'vary': scan_expr }
        
        publishers = self.default_publishers + [ICPDataFile.ICPFindPeakPublisher()]
        if gnuplot == True: publishers.append(GnuplotPublisher(auto_poisson_errorbars=False))
        #scan = self.OneDimScan(self, scan_definition, publishers = publishers, extra_dict = {} )
        scan = self.oneDimScan(scan_definition, publishers = publishers, extra_dicts = [], publish_end=False)
        self.ResetAbort()
        # don't publish the end of the scan until we try fitting the peak!
        ydata = []
        xdata = []
        for datapoint in scan:
            output_state, scan_state = datapoint
            ydata.append(scan_state['result']['counts'])
            xdata.append(scan_state[movable])
        
        
        fitter = Fitter(xdata, ydata)
        
        #print fitter.error
        #self.fitter_error = fitter.error
        self.fitter = fitter
        try:
            fitter.do_fit()
            fit_params = fitter.params_out
            fit_result = fit_params.get('fit_result', {})
            fit_str = ''
            for pn in fit_params.get('pname', []):
                fit_str += '%s: %11f  +/-  %.1f\n' % (pn, fit_result[pn], fit_result['%s_err' % pn])
            self.write(fit_str)
            end_state = self.getState()
            end_state['result'] = { 'TYPE': comment, \
                                    'fit_str': fit_str,\
                                    'fit_result': fit_result,\
                                    'fit_func': fit_params['fit_func']}
            for pub in publishers:
                pub.publish_end(end_state, scan_definition)
            
            self.last_fitted_peak = {movable: fit_result['center']}
            if auto_drive_fit:
                self.DrivePeak()
            else:
                self.write('Peak found at %.4f. Issue command \'dp\' (DrivePeak()) to go there!' % fit_result['center'])

        #if fitter.error is not None:         
        except:        
            self.write("fit failed: driving back to start position")
            end_state = self.getState()
            end_state['result'] = {'TYPE': 'NOCONV'}
            for pub in publishers:
                pub.publish_end(end_state, scan_definition)
            self.updateState({movable: mprevious})
            return
        
                  

        return
        # end of FindPeak function
        
    @validate_motor    
    def FindPeak(self, motnum, mrange, mstep, duration=-1, auto_drive_fit = False):
        """the classic ICP function (fp)
        It can be suspended with ctrl-z (ctrl-z again to resume)
        or the 'finishup' routine skips the rest of the points and fits now (ctrl-\)
        Abort (ctrl-c) works the same as usual """
        numsteps = int( abs(float(mrange) / (mstep)) + 1)
        movable = 'a%d' % (motnum,)
        val_now = self.getState()[movable]
        mstart = val_now - ( int(numsteps/2) * mstep)
        comment = 'FP'
        Fitter = self.gauss_fitter  
        self.PeakScan(movable, numsteps, mstart, mstep, duration, val_now, comment=comment, Fitter=Fitter, auto_drive_fit=auto_drive_fit)
        
    @validate_motor    
    def FindLine(self, motnum, mrange, mstep, duration=-1, auto_drive_fit = False):
        """the classic ICP function (fp) but fitting a line
        It can be suspended with ctrl-z (ctrl-z again to resume)
        or the 'finishup' routine skips the rest of the points and fits now (ctrl-\)
        Abort (ctrl-c) works the same as usual """
        numsteps = int( abs(float(mrange) / (mstep)) + 1)
        movable = 'a%d' % (motnum,)
        val_now = self.getState()[movable]
        mstart = val_now - ( int(numsteps/2) * mstep)
        comment = 'FL'
        Fitter = self.line_fitter  
        self.PeakScan(movable, numsteps, mstart, mstep, duration, val_now, comment=comment, Fitter=Fitter, auto_drive_fit=auto_drive_fit)
        
    @validate_motor    
    def FindPeakTied(self, motnum, mrange, mstep, duration=-1, auto_drive_fit = False, t_movable=None):
        """the classic ICP function (fpt)
        It can be suspended with ctrl-z (ctrl-z again to resume)
        or the 'finishup' routine skips the rest of the points and fits now (ctrl-\)
        Abort (ctrl-c) works the same as usual """
        numsteps = int( abs(float(mrange) / (mstep)) + 1)
        movable = 'a%d' % (motnum,)
        val_now = self.getState()[movable]
        mstart = val_now - ( int(numsteps/2) * mstep)
        comment = 'FPT'
        Fitter = self.gauss_fitter  
        self.PeakScan(movable, numsteps, mstart, mstep, duration, val_now, comment=comment, Fitter=Fitter, auto_drive_fit=auto_drive_fit, t_scan=True, t_movable=t_movable)
         
    def DrivePeak(self):
        """ Drive to stored peak (self.last_fitted_peak)
        This value is created when FindPeak is run! """
        self.updateState(self.last_fitted_peak)
    
    def getLastFittedPeak(self):
        return self.last_fitted_peak
                  
    def updateGnuplot(self, filename, title, gaussfit_params = None, error_bars=True):
        if self.plot is None:
            # we haven't plotted yet - create the gnuplot window
            self.plot = Popen("gnuplot", shell=True, stdin=PIPE, stdout=PIPE, stderr=PIPE, close_fds=True)
        else:
            if not self.plot.poll() == None:
                # we've closed the graph window for some reason: open a new one
                self.plot = Popen("gnuplot", shell=True, stdin=PIPE, stdout=PIPE, stderr=PIPE, close_fds=True)
        if gaussfit_params:    
            self.plot.stdin.write('gauss(x) = a + b * exp( - ( x - c )**2 * 4 * log(2) / d**2  )\n')
            self.plot.stdin.write('a = %f \n' % gaussfit_params['y_offset'])
            self.plot.stdin.write('b = %f \n' % gaussfit_params['amplitude'])
            self.plot.stdin.write('c = %f \n' % gaussfit_params['center'])
            self.plot.stdin.write('d = %f \n' % gaussfit_params['FWHM'])
            self.plot.stdin.write('plot \'%s\' u 1:2:(1+sqrt(2))title \'%s\' w errorbars lt 2 ps 3 pt 7 lc rgb "green",' % (filename,title))
            self.plot.stdin.write('gauss(x) w lines lt 2 lc rgb "red"\n')
        else:
            if error_bars == True:
                self.plot.stdin.write('plot \'%s\' u 1:2:(1+sqrt(2)) title \'%s\' w errorbars lt 2 ps 3 pt 7 lc rgb "red",' % (filename,title))
                self.plot.stdin.write(' \'%s\' u 1:2 w l lt 2 lc rgb "red"\n' % (filename,))
            else:
                self.plot.stdin.write('plot \'%s\' u 1:2 title \'%s\' w lp lt 2 lc rgb "red" ps 3 pt 7\n' % (filename,title))
        self.plot.stdin.flush()
            
    def GetIBufHeader(self, bufnum):
        return self.dataOutput.GenerateIBufferHeader(bufnum)
    
    def RunICPSequenceFile(self, filename, datafolder = None):
        from pyrecs.icp_compat.prefilter_ICP import ICPTransformer
        icpt = ICPTransformer('self.')
        icpt.register_icp_conversions(self.icp_conversions)
        if datafolder is None:
            datafolder = self.datafolder
        icp_seq = PyICPSequenceFile(os.path.join(datafolder, filename))
        for command in icp_seq:
            if self._aborted: break
            filtered_command = icpt.transform(command, '')
            self.write('Sequence: ' + filtered_command + '\n')
            eval(filtered_command, locals())
    
    def CreateSequence(self, sequence_string):
        self.sequence = StringIO(sequence_string)
        
    def ReadSequence(self):
        self.sequence.getvalue()
        self.write(self.sequence.getvalue())

    def RunSequence(self, sequence_string = None):
        if sequence_string is None: # then run!
            sequence = self.sequence
            icp_seq = PyICPSequenceStringIO(sequence)
            for command in icp_seq:
                if self._aborted: break
                filtered_command = prefilterICPString(command)
                self.write('Sequence: ' + filtered_command + '\n')
                eval(filtered_command, self.__dict__)         
        else:
            sequence = StringIO(sequence_string)
            self.sequence = sequence
        
    
    def IBufferToScan(self, bufnum, polarization_enabled=True):
        """ convert an IBUFFER scan into the pyrecs scan format:
        if polarization is defined, will return multiple scans
        to be run in parallel """
        state = self.getState()
        ibuffer_obj = ibuffer.IBUFFER(project_path = state['project_path'])
        # loads buffers from default file location
        if (bufnum <= 0) or (bufnum > len(ibuffer_obj.buffers)):
            print "error: ibuffer number out of range"
            return
        ibuf = ibuffer_obj.buffers[bufnum-1]
        
        if ibuf.data['Type'] == 'NEUT':
            init_state = [ ('scaler_gating_mode', 'NEUT'), ('scaler_monitor_preset', ibuf.data['monit'] ) ]
        else: # data['Type'] == 'TIME':
            init_state = [ ('scaler_gating_mode', 'TIME'), ('scaler_time_preset', ibuf.data['monit'] ) ]
        init_state.append(('scaler_prefactor', ibuf.data['Prefac']))
        #IBUFFERS only move motors 1-6
        motnums = set(range(1,7))
        scan_expr = []
        for motnum in range(1,7):
            motstart = ibuf.data['a%dstart' % motnum]
            motstep = ibuf.data['a%dstep' % motnum]
            motname = 'a%d' % motnum            
            if motstep > FLOAT_ERROR: # floating-point errors!
                scan_expr.append((motname, '%f + (i * %f)' % (motstart, motstep)))
            else:
                init_state.append((motname, '%f' % motstart))
                
        if ibuf.data['IncT'] > FLOAT_ERROR:
            scan_expr.append(('t1', '%f + (i * %f)' % (ibuf.data['T0'], ibuf.data['IncT'])))
        elif state.get('temp_controllers_defined', 0) > 0: 
            init_state.append(('t1', ibuf.data['T0']))
            
        if ibuf.data['Hinc'] > FLOAT_ERROR:
            scan_expr.append(('h1', '%f + (i * %f)' % (ibuf.data['H0'], ibuf.data['Hinc'])))
        elif state.get('magnets_defined', 0) > 0:
            init_state.append(('h1', ibuf.data['H0']))
            
        scan_definition = {'namestr': self.ip.GetNameStr(), 
                           'comment': ibuf.data['description'],
                           'iterations': int(ibuf.data['numpoints']),
                           'init_state': init_state,
                           'vary': scan_expr }
        
        file_seedname = ibuf.data['description'][:5]
        #scan_definition['ibuf_data'] = deepcopy(ibuf.data)
            
        generic_suffix = '.' + self.ip.GetNameStr().lower()
        ibuf_pol_flags = [ ibuf.data['p1exec'], ibuf.data['p2exec'], ibuf.data['p3exec'], ibuf.data['p4exec'] ]
        pol_states = []
        pol_defined = any(ibuf_pol_flags)
        
        scan_defs = []
        if pol_defined and polarization_enabled:
            scan_definition['polarization_enabled'] = True
            identifiers = ['a', 'b', 'c', 'd']
            suffixes = [generic_suffix[:-2] + ident + generic_suffix[-1] for ident in identifiers]
            possible_pol_states = [ [False,False], [True,False], [False,True], [True,True] ]
            for s, p, f in zip(suffixes, possible_pol_states, ibuf_pol_flags):
                if f > 0:
                    new_scan_def = deepcopy(scan_definition)
                    new_scan_def['filename'] = self.getNextFilename(file_seedname, s)
                    new_scan_def['namestr'] = s[-3:].upper()
                    new_scan_def['init_state'].extend([('flipper1', p[0]), ('flipper2', p[1])])
                    #new_scan_def['vary'].extend([('flipper1', p[0]), ('flipper2', p[1])])
                    scan_defs.append(new_scan_def)
                    # this changes, for example, cg1 to ca1, cb1 etc. and ng1 to na1...
        else:
            # if there's no polarization defined, or if it's overriden by the "polarization_enabled" flag set to false
            new_scan_def = scan_definition.copy()
            new_scan_def['filename'] = self.getNextFilename(file_seedname, generic_suffix)
            scan_defs.append(new_scan_def)
        return scan_defs
        
    def RunIBuffer(self, bufnum, gnuplot=True):
        """ Execute the scan defined in the IBUFFER with number bufnum """
        polarization_enabled = self.polarization_enabled
        scan_defs = self.IBufferToScan(bufnum, polarization_enabled)
        
        scans = []
        for scan_def in scan_defs:            
            publishers = self.default_publishers + [ICPDataFile.ICPDataFilePublisher()]
            if gnuplot == True: publishers.append(GnuplotPublisher(auto_poisson_errorbars=False))    
            scans.append(self.oneDimScan(scan_def, publishers = publishers, extra_dicts = [], publish_time=True ))

        locked_scans = itertools.izip_longest(*scans) #joins the scans so it steps through them all at the same time
        for scan_step in locked_scans:
            pass # all the work is done in the oneDimScan
        
            
    
    
        
