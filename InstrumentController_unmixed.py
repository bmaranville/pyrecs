from __future__ import with_statement
import time, sys, glob, copy, os
sys.path.append(os.path.join(os.environ['HOME'],'bin'))
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

import itertools
import functools
from ordered_dict import OrderedDict
from prefilter_ICP import prefilterICPString
from ICPSequenceFile import PyICPSequenceFile, PyICPSequenceStringIO
from pyrecs.icp_compat import ibuffer
from InstrumentParameters import InstrumentParameters
from pyrecs.drivers.VME import VME
from pyrecs.publishers import update_xpeek
from pyrecs.publishers import ICPDataFile


FLOAT_ERROR = 1.0e-7
DEBUG = False
AUTO_MOTOR_DISABLE = False
        
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
 
class Fitter:
    """ generic fitting.  Give a function (string) and parameter names with default values """
    def __init__(self, xdata, ydata, params):
        self.params = params
        
    def do_fit(self):
        """ do the fitting and return result (dict) where result[pn] = val, result[pn_err] = val_err """
        result = {}
        return result
        

class GnuplotPublisher(Publisher):
    def __init__(self):
        self.plot = Popen("gnuplot", shell=True, stdin=PIPE, stdout=PIPE, stderr=PIPE, close_fds=True)
        (self.tmp_fd, self.tmp_path) = tempfile.mkstemp() #temporary file for plotting
        
    def publish_datapoint(self, state, scan_def):
        outstr = ''
        for movable in scan_def['vary']:
            outstr += '%10.4f    ' % state[movable]
        outstr += '%14g' % state['result']['counts']
        with open(self.tmp_path, 'a') as f:
            f.write(outstr)            
        title = scan_def['filename']
        self.plot.stdin.write('plot \'%s\' u 1:2:(1+sqrt(2)) title \'%s\' w errorbars lt 2 ps 1 pt 7 lc rgb "red"\n' % (self.tmp_path,title))
        
    def publish_end(self, state, scan_def):
        title = scan_def['filename']
        if state.has_key('fit_result'):
            fit_params = state['fit_result']
            self.plot.stdin.write('f(x) = %s \n' % fit_params['fit_func'])
            for pn in fit_params['pname']:
                self.plot.stdin.write('%s = %f \n' % (pn, fit_params['result'][pn]))
            self.plot.stdin.write('plot \'%s\' u 1:2:(1+sqrt(2))title \'%s\' w errorbars lt 2 ps 1 pt 7 lc rgb "green",' % (self.tmp_path,title))
            self.plot.stdin.write('f(x) w lines lt 2 lc rgb "red"\n')
        else:
            self.plot.stdin.write('plot \'%s\' u 1:2:(1+sqrt(2)) title \'%s\' w errorbars lt 2 ps 1 pt 7 lc rgb "red"\n' % (self.tmp_path,title))
            
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
        self.motor_names = ['a%d' % i for i in range(1, self.num_motors+1)]
        self.motor_lookup = dict(zip(self.motor_names, range(1, self.num_motors+1)))
        
        num_pol_ps = int(self.ip.InstrCfg['#pol_ps'])
        self.ps_names = ['ps%d' %i for i in range(1, num_pol_ps+1)]
        self.ps_lookup = dict(zip(self.ps_names, range(1, num_pol_ps+1)))
        
        PC_mot_line = int(self.ip.InstrCfg['PC_mot_line'])
        vme = VME(port = self.ip.GetSerialPort(PC_mot_line)) # initialize the VME box (motors, scaler)
        
        self.scaler = vme # counter controller
        self.mc = vme # motor controller, happens to be same as counter controller right now
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
        self.loopdelay = 0.03
        self.psd_data = None
        self.plot = None
        self.writers = set([StdoutWriter()]) # handles screen output (and logging?)
        #self.fitter = FitGnuplot
        self.gauss_fitter = FitGaussGnuplot
        self.cossquared_fitter = FitCosSquaredGnuplot
        #self.quadratic_fitter = FitQuadraticGnuplot
        #self.publishers = [xpeek_broadcast()]
        #self.default_publishers = [update_xpeek.XPeekPublisher()]
        self.default_publishers = []
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
        
        # command alias list: these commands will come in from the filter
        # ICP commands:
        self.pa = self.PrintMotorPos
        self.pt = self.PrintTemperature
        self.pu = self.PrintUpperLimits
        self.pl = self.PrintLowerLimits
        self.init = self.SetHardMotorPos
        self.set = self.SetSoftMotorPos
        self.st = self.SetTemperature
        self.d = self.DriveMotor
        self.di = functools.partial(self.DriveMotor, increment=True)
        self.ct = self.PrintCounts
        self.mon = self.PrintMonitor
        self.w = self.setLogging
        self.fp = self.FindPeak
        self.l = self.SetLowerLimit
        self.u = self.SetUpperLimit
        self.ri = self.RunIBuffer
        self.rsf = self.RunICPSequenceFile
        self.rs = self.RunSequence
        self.dp = self.DrivePeak #New!
        
        self.device_registry = {'motor': 
                                {'names': self.motor_names, 'updater': self.DriveMotorByName },
                                'scaler':
                                {'names': ['scaler'], 'updater': self.scaler }}
        
        self.state = {}
        self.getState()
        
        # lastly, initialize any base classes (mixins) that aren't initialized yet
        #for base in self.__class__.__bases__:
        #    base.__init__(self)
  
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
        self._suspended = not self._suspended
        
    def Break(self, signum=None, frame=None):
        #print "Break: (stop scan and fit)"
        self._break = True
    
    def exit(self):
        """ Convenience function to make it possible to exit with 'exit' instead of 'exit()' 
        This is specific to IPython """
        #_ip.magic('exit')
        exit()
        
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
            
    
    def getNextFilename(self, prefix, suffix, path = None):
        """ find the highest filenumber with prefix and suffix
        and return 'prefix + (highest+1) + suffix' """
        if path is None: path = self.datafolder 
        fl = glob.glob1(path, prefix+'*'+suffix)
        fl.sort()
        if len(fl) == 0:
            # first scan!
            biggest = 0
        else:
            biggest = fl[-1][len(prefix):-len(suffix)]
        new_filenum = int(biggest) + 1
        new_filenum_str = '%03d' % new_filenum
        new_filename = prefix + new_filenum_str + suffix
        return new_filename
    
    def getState(self):
        """ get a dictionary representing the current instrument state """
        # first grab the motors and collimation etc. from the backend
        self.state.update(self.ip.getState())
        # then augment the state definition with stuff only the InstrumentController knows
        self.state.setdefault('scaler_gating_mode', "'TIME'")
        self.state.setdefault('scaler_time_preset', 1.0)
        self.state.setdefault('scaler_monitor_preset', 1000)
        self.state.setdefault('polarization_enabled', self.polarization_enabled)
        #self.state.setdefault('psd_enabled', self.getPSDActive() )
        #self.state.setdefault('flipper1', self.flipperstate[0])
        #self.state.setdefault('flipper2', self.flipperstate[1])
        self.state.setdefault('project_path', self.datafolder)
        self.state.setdefault('measurement_id', None) # this is like a filename, perhaps.  we're not in a measurement
        self.state.setdefault('result', {}) # needs to be filled by a measurement!
        self.state.setdefault('magnet_defined', (len(self._magnet) > 0))
        self.state.setdefault('temp_controller_defined', (len(self._tc) > 0))
        self.state['timestamp'] = time.time()
        return self.state.copy()
    
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
            new_state.pop(device)
        self.state.update(new_state)
        return deepcopy(self.state)
        
    def setLogging(self, enable):
        """ console command accessed via equivalent ICP command 'w+' or 'w-':
        Enable/Disable logging """
        self.logwriter.logging_enabled = enable
                
    def PrintCounts(self, duration):
        """ console command accessed via equivalent ICP command 'ct':
        get counts for a given duration using the active counter """
        result = self.Count(duration)
        msg = 'count time: %.4f  counts: %d' % (result['count_time'], result['counts'])
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
    
    
    def GetHardMotorPos(self, motornum):
        hard_pos = self.mc.GetMotorPos(motornum)
        self.ip.SetHardMotorPos(motornum, hard_pos)
        return hard_pos
        
    def GetMotorPos(self, motornum):
        # default to retrieving the soft motor pos: 
        # this is what we need for writing data files, driving motors etc.
        return self.GetSoftMotorPos(motornum)
        
        
    def GetSoftMotorPos(self, motornum, use_stored = False):
        if use_stored:
            hard_pos = self.ip.GetHardMotorPos(motornum)
        else:
            hard_pos = self.GetHardMotorPos(motornum)
        offset = self.ip.GetSoftMotorOffset(motornum)
        soft_pos = hard_pos - offset
        return soft_pos
  
    
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
            self.write(' Soft: A%02d=%8.3f\n Hard: A%02d=%8.3f\n' % (motornum, soft_pos, motornum, hard_pos))
        else:  # no motor specified - get them all
            self.PrintAllMotorPos()
       
    def GetStoredSoftMotorPos(self, motornum):
        """ get motor position (soft) from stored backend value """
        hard_pos = self.ip.GetHardMotorPos(motornum)
        offset = self.ip.GetSoftMotorOffset(motornum)
        soft_pos = hard_pos - offset
        return soft_pos
         
        
    def SetHardMotorPos(self, motornum, pos):
        """ initialize the hardware motor position """
        self.mc.SetMotorPos(motornum, pos) # update the motor controller
        self.ip.SetHardMotorPos(motornum, pos) # update the MOTORS.BUF file
        
    
    def SetSoftMotorPos(self, motornum, pos):
        """ initialize the soft motor position """
        hard_pos = self.GetHardMotorPos(motornum)
        new_offset = hard_pos - pos
        self.ip.SetSoftMotorOffset(motornum, new_offset) # update the MOTORS.BUF file
    
    def fix(self, motornum):
        """ set the motor to "fixed", which means it won't be moved during an ibuffer scan """
        self.ip.SetMotorFixed(motornum)
        #self.fixed_motors.add(motornum)
        
    def rel(self, motornum):
        """ release a previously "fixed" motor """
        self.ip.SetMotorReleased(motornum)
        #self.fixed_motors.remove(motornum)
    
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


    
    def moveMultiMotor(self, motornum_list, soft_position_list, check_limits = True, reraise_exceptions = True, disable=AUTO_MOTOR_DISABLE):
        """ send motor move command to VME and wait for it to complete motion """
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
            pos = hard_position_list.pop() # pull the top position off the list (reduces list length)
            softpos = soft_position_list.pop()
            self.mc.EnableMotor(motnum)
            self.mc.MoveMotor(motnum, pos)
            self.ip.SetHardMotorPos(motnum, pos) # update MOTORS.BUF
            self.state[self.motor_names[motnum-1]] = softpos # update state dictionary
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
            # and it doesn't exit until all sub-calls have returned (all motors are stopped and disabled)
            return
            
        recursive_motor_move(motornum_list, hard_position_list, soft_position_list)
        #if not reraise_exceptions: # reset the abort flag
        #    self._aborted = False

       
    def DriveMotor(self, motornum, position, do_backlash = True, check_limits = True, reraise_exceptions = False, increment=False):
        if increment:
            position = self.GetMotorPos(motornum) + position
        self.DriveMultiMotor([motornum], [position], do_backlash, check_limits, reraise_exceptions)
    
    def DriveMotorByName(self, motors_to_move, position_list, do_backlash = True, check_limits = True, reraise_exceptions = False):
        motor_list = [self.motor_lookup[s] for s in motors_to_move]
        # i.e. 'a3' is motor 3
        self.DriveMultiMotor(motor_list, position_list, do_backlash, check_limits, reraise_exceptions) 
    
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
            new_mot_list = []
            new_pos_list = []
            for motnum, target_pos in zip(motlist, poslist):
                current_pos[motnum] = self.GetMotorPos(motnum)
                if abs(current_pos[motnum] - target_pos) > tolerance[motnum]:
                    new_mot_list.append(motnum)
                    new_pos_list.append(target_pos)
            return new_mot_list, new_pos_list
            
        motors_to_move, position_list = remove_finished_motors(motors_to_move, position_list) # if they're already there, take them off the list
        
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
            motors_to_move, positions1 = remove_finished_motors(motors_to_move, positions1)
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
            motors_to_backlash, positions1 = remove_finished_motors(motors_to_backlash, positions2)
            # silently continues if still outside tolerance after motor_retries!
            
        # can check for problems here:  if the lists aren't empty, they didn't meet tolerances:
        # if len(motors_to_move) > 0 : print "error!"
        # if len(motors_to_backlas) > 0 : print "error!"
            
        return
        
            
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
    
    
    def RapidScan(self, motornum = None, start_angle = None, stop_angle = None, client_plotter = None, reraise_exceptions = False, disable=AUTO_MOTOR_DISABLE):
        """ new, non-ICP function: count while moving.
                returns: (position, counts, elapsed_time) """
        
        (tmp_fd, tmp_path) = tempfile.mkstemp() #temporary file for plotting
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
            tmp_file = open(tmp_path, 'a')
            tmp_file.write(out_str + '\n')
            tmp_file.close()
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
        for i in range(1,self.num_motors+1):
            if self._aborted: break
            if use_stored:
                hard_pos = self.ip.GetHardMotorPos(i)
            else:
                hard_pos = self.GetHardMotorPos(i)
                self.ip.SetHardMotorPos(i, hard_pos) # update, because we can!
            offset = self.ip.GetSoftMotorOffset(i)
            soft_pos = hard_pos - offset
            soft_line += 'A%02d=%8.3f ' % (i, soft_pos)
            hard_line += 'A%02d=%8.3f ' % (i, hard_pos)
            #self.write(' Soft: A%02d=%7.3f\n Hard: A%02d=%7.3f' % (motornum, soft_pos, motornum, hard_pos))
            #self.write('A%02d: %.4f\t' % (i, pos))
            if ( i % 5 == 0) or (i == self.num_motors):
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
                self.write('temp controller %d: setpoint = %.4f, tnow = %4f' % (i+1, tc.getSetpoint(), tc.getTemperature()))           
    
    def SetTemperature(self, temperature):
        if self._tc == []:
            self.write(" Error: no temperature controller defined ")
        else: 
            self._tc[0].SetTemperature(temperature)
            
        
    def PrintLowerLimits(self):
        result = self.ip.GetLowerLimits()
        for i in range(self.num_motors):
            self.write('L%d: %.4f\t' % (i+1, result[i]))
    
    
    def PrintUpperLimits(self):
        result = self.ip.GetUpperLimits()
        for i in range(self.num_motors):
            self.write('U%d: %.4f\t' % (i+1, result[i]))
        
    
    def SetLowerLimit(self, motornum, position):
        self.ip.SetLowerLimit(motornum, position)
        
        
    def SetUpperLimit(self, motornum, position):
        self.ip.SetUpperLimit(motornum, position)
             
    
    def measure(self, params = {}):
        params.setdefault('scaler_gating_mode', 'TIME')
        params.setdefault('scaler_time_preset', 1.0)
        params.setdefault('scaler_monitor_preset', 1000)
        if params['scaler_gating_mode'] == 'TIME':
            return self.updateState({'result': self.Count(-1.0 * params['scaler_time_preset'])} )
        elif params['scaler_gating_mode'] == 'NEUT':
            return self.updateState({'result': self.Count(params['scaler_monitor_preset'])} )
        
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
    def oneDimScan(self, scan_definition, publishers = [], extra_dicts = [], publish_end=True):
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
        scan_definition['vary'] = OrderedDict(scan_definition['vary'])
        scan_definition['init_state'] = OrderedDict(scan_definition['init_state'])
        scan_definition.setdefault('namestr', self.ip.GetNameStr().upper())
        new_state = self.updateState(scan_definition['init_state'])
        for pub in publishers:
            pub.publish_start(new_state, scan_definition)
        iterations = scan_definition['iterations']
        scan_expr = scan_definition['vary']
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
                
            new_state = self.updateState(scan_state.copy())
            output_state = self.measure(new_state)
            result = output_state['result']
            scan_state['result'] = output_state['result'].copy()
            data.append(result['counts'])
                
            # send immediate feedback to writers:
            out_str  = ''.join(['%11.4f\t' % scan_state[d] for d in scan_expr])
            out_str += '%11g\n' % (result['counts'],)
            self.write(out_str)
                
            # publish datapoint
            for pub in publishers:
                pub.publish_datapoint(output_state, scan_definition)
            all_states.append(scan_state)
            yield output_state, scan_state
        
        if publish_end:
            for pub in publishers:
                pub.publish_end(output_state, scan_definition)               
        return
    
    
    def RunScan(self, scan_definition):
        """runs a scan_definition with default publishers and FindPeak publisher """
        publishers = self.default_publishers + [ICPDataFile.ICPFindPeakPublisher()]
        scan = self.oneDimScan(scan_definition, publishers = publishers)
        self.ResetAbort()
        for datapoint in scan:
            pass # everything gets done in the iterator
    
    def PeakScan(self, movable, numsteps, mstart, mstep, duration, mprevious, comment=None, Fitter=None, auto_drive_fit=False):
        suffix = '.' + self.ip.GetNameStr().lower()
        new_filename = self.getNextFilename('fp_%s' % movable, suffix)

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
        fitter.do_fit()
        #print fitter.error
        #self.fitter_error = fitter.error
        self.fitter = fitter
        try:       
            fit_params = fitter.params_out
            fit_result = fit_params.get('fit_result', {})
            fit_str = ''
            for pn in fit_params.get('pname', []):
                fit_str += '%s: %11f  +/-  %.1f\n' % (pn, fit_result[pn], fit_result['%s_err' % pn])
            self.write(fit_str)
            end_state = self.getState()
            end_state['result'] = { 'TYPE': comment, 'fit_result': fit_result, 'fit_func': fit_params['fit_func']}
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
        self.PeakScan(movable, numsteps, mstart, mstep, duration, val_now, comment, Fitter, auto_drive_fit)
         
    def DrivePeak(self):
        """ Drive to stored peak (self.last_fitted_peak)
        This value is created when FindPeak is run! """
        self.updateState(self.last_fitted_peak)
    
    def getLastFittedPeak(self):
        return self.last_fitted_peak
                  
    def updateGnuplot(self, filename, title, gaussfit_params = None):
        if not self.plot:
            # we haven't plotted yet - create the gnuplot window
            self.plot = Popen("gnuplot_andr", shell=True, stdin=PIPE, stdout=PIPE, stderr=PIPE, close_fds=True)
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
            self.plot.stdin.write('plot \'%s\' u 1:2:(1+sqrt(2))title \'%s\' w errorbars lt 2 ps 1 pt 7 lc rgb "green",' % (filename,title))
            self.plot.stdin.write('gauss(x) w lines lt 2 lc rgb "red"\n')
        else:
            self.plot.stdin.write('plot \'%s\' u 1:2:(1+sqrt(2)) title \'%s\' w errorbars lt 2 ps 1 pt 7 lc rgb "red"\n' % (filename,title))
            
    def GetIBufHeader(self, bufnum):
        return self.dataOutput.GenerateIBufferHeader(bufnum)
    
    def RunICPSequenceFile(self, filename, datafolder = None):
        if datafolder is None:
            datafolder = self.datafolder
        icp_seq = PyICPSequenceFile(os.path.join(datafolder, filename))
        for command in icp_seq:
            if self._aborted: break
            filtered_command = prefilterICPString(command)
            self.write('Sequence: ' + filtered_command + '\n')
            eval(filtered_command, self.__dict__)
    
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
        
            
    def RunIBuffer(self, bufnum):
        """ Execute the scan defined in the IBUFFER with number bufnum """
        ################################################
        ### THIS HAS NOT BEEN DEBUGGED OR TESTED YET ###
        ################################################
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
            init_state.append((motname, '%f' % motstart))
            if motstep > FLOAT_ERROR: # floating-point errors!
                scan_expr.append((motname, '%f + (i * %f)' % (motstart, motstep)))
        scan_expr.append(('t0', '%f + (i * %f)' % (ibuf.data['T0'], ibuf.data['IncT'])))
        scan_expr.append(('h0', '%f + (i * %f)' % (ibuf.data['H0'], ibuf.data['Hinc'])))
            
        scan_definition = {'namestr': self.ip.GetNameStr(), 
                           'comment': ibuf.data['description'],
                           'iterations': ibuf.data['numpoints'],
                           'init_state': init_state,
                           'vary': scan_expr }
        
        file_seedname = ibuf.data['description'][:5]
        #scan_definition['ibuf_data'] = deepcopy(ibuf.data)
            
        generic_suffix = '.' + self.ip.GetNameStr().lower()
        ibuf_pol_flags = [ ibuf.data['p1exec'], ibuf.data['p2exec'], ibuf.data['p3exec'], ibuf.data['p4exec'] ]
        pol_states = []
        pol_defined = any(ibuf_pol_flags)
        
        scan_defs = []
        if pol_defined and self.polarization_enabled:
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
                    scan_defs.append(new_scan_def)
                    # this changes, for example, cg1 to ca1, cb1 etc. and ng1 to na1...
        else:
            # if there's no polarization defined, or if it's overriden by the "polarization_enabled" flag set to false
            new_scan_def = scan_definition.copy()
            new_scan_def['filename'] = self.getNextFilename(file_seedname, generic_suffix)
            scan_defs.append(new_scan_def)
            
        publishers = self.default_publishers + [ICPDataFile.ICPDataFilePublisher()]         
        scans = [self.oneDimScan(scan_def, publishers = publishers, extra_dicts = [] ) for scan_def in scan_defs]

        locked_scans = itertools.izip_longest(*scans) #joins the scans so it steps through them all at the same time
        for scan_step in locked_scans:
            pass # all the work is done in the oneDimScan
        
        #for scan_def in scan_defs:
        #    print scan_def
        #    for pub in publishers:
        #        pub.publish_end(self.getState(), scan_def)
            
    
    
        
