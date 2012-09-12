from __future__ import with_statement
import serial,time, sys, wx, glob, copy
import numpy # not really using for much except float32 and int32
import signal # need this to make sure interrupts only go to main thread!
import threading
import tempfile, os
from drivers.VME import VME
from subprocess import Popen, PIPE
from InstrumentParameters import InstrumentParameters
from drivers.rs232gpib import RS232GPIB
from drivers.FlipperDriver import FlipperPS
from drivers.brookhaven_psd import BrookhavenDetector
from fit_gausspeak import FitGauss
from StringIO import StringIO
import exceptions
from IPython import InteractiveShell
from icp_compat import prefilter_ICP, ibuffer
from publishers import ICPDataFile

DEBUG = False

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
        outstr += msg + '\n'
        with open(self.logfilename, 'a') as log:
            log.write(outstr)
            

class InstrumentController:
    """called once, holds all the methods for moving motors, counting etc.
    with functionality similar to the ICP program"""
    def __init__(self):
        #### First, the base modules
        self.ip = InstrumentParameters() # handles all configuration files
        
        self.num_motors = numpy.int32(self.ip.InstrCfg['#mots'])
        vme = VME(port = self.ip.GetSerialPort(1)) # initialize the VME box (motors, scaler)
        self.scaler = vme # counter controller
        self.mc = vme # motor controller, happens to be same as counter controller right now
        self.psd = BrookhavenDetector() # initialize the PSD connection
        self.gpib = rs232GPIB(serial_port = self.ip.GetSerialPort(3)) # initialize our gpib controller
        num_flipper_ps = len(self.ip.GetFcal())
        self.flipper_ps = []
        for i in range(num_flipper_ps): #initialize all the flipper power supplies
            self.flipper_ps.append(FlipperPS(gpib_addr=i+1, gpib_controller = self.gpib))
        
        #### Now, for the optional modules:
        self.tc = None # temperature controller
        self.magnet = None # magnet power supply
        #self.fixed_motors = set() # none start out fixed
        
        self.loopdelay = 0.03
        self.psd_data = None
        self.plot = None
        self.writers = set([StdoutWriter()]) # handles screen output (and logging?)
        self.logfilename = self.getNextFilename(time.strftime('%b%d%Y_'), '.LOG')
        self.logwriter = LogWriter(self.logfilename)
        #self.writers.add(LogWriter(self.logfilename))
        self.polarization_enabled = True
        self.setPSD(False) #start with pencil detector by default
        self._suspended = False # clear suspend flag at the beginning
        self._break = False
        self._aborted = False
        self.station_number = int(self.ip.InstrCfg['sta#'])
        self.num_scalers = int(self.ip.InstrCfg['#scl'])
        self.motor_retries = 5
        self.dataOutput = ICPDataFile.ICPDataFile(self) # initialize output handler (writes ICP-style data files)
        
        #setup of signal handlers: taking over ctrl-c, ctrl-z and ctrl-\
        signal.signal(signal.SIGTSTP, self.Suspend)
        signal.signal(signal.SIGINT, self.Abort)
        signal.signal(signal.SIGQUIT, self.Break)
        self._inthread_running = False
        self.threading_enabled = True

        # command alias list: these commands will come in from the filter
        self.pa = self.PrintMotorPos
        self.pt = self.PrintTemperature
        #self.phf = self.GetMagneticField
        self.pfcal = self.PrintFlipperCalibration
        self.pu = self.PrintUpperLimits
        self.pl = self.PrintLowerLimits
        self.init = self.SetHardMotorPos
        self.set = self.SetSoftMotorPos
        self.st = self.SetTemperature
        #self.sm = self.SetMagneticField
        self.fcal = self.SetFlipperCalibration
        self.flm = self.SetMonochromatorFlipper
        self.fla = self.SetAnalyzerFlipper
        self.d = self.DriveMotor
        self.ct = self.PrintCounts
        self.a = self.setPSD
        self.w = self.setLogging
        self.fp = self.FindPeak
        self.pasd = self.PrintROI
        self.xmin = self.SetXmin
        self.xmax = self.SetXmax
        self.ymin = self.SetYmin
        self.ymax = self.SetYmax
        self.l = self.SetLowerLimit
        self.u = self.SetUpperLimit
        self.ri = self.RunIBuffer
        self.iset = self.SetFlipperPSCurr
        self.vset = self.SetFlipperPSVolt
        
    #### BEGIN Threading stuff
    
    # Note that we're calling functions with instrument I/O in them
    # in separate threads, so that signals don't interrrupt rudely
    # (but we're keeping a close eye on them)
  
    def Abort(self, signum=None, frame=None):
        """ when trapped, the abort just sets a flag """
        self._aborted = True
        
    def Suspend(self, signum=None, frame=None):
        #if self._suspended:
        #    print "Resuming (Suspend flag cleared)"
        #else:
        #    print "Suspend: program will pause"
        self._suspended = not self._suspended
        
    def Break(self, signum=None, frame=None):
        #print "Break: (stop scan and fit)"
        self._break = True
    
    def inthread(func):
        """ decorator to make a function run in a separate thread:
        it watches the thread in a non-blocking way (looping) so that
        we can still make interrupts with ctrl-c, ctrl-z and ctrl-\ """
        
        if func.func_defaults is None:
            kwargcount = 0
        else:
            kwargcount = len(func.func_defaults)            
        argcount = func.func_code.co_argcount - kwargcount
        argnames = func.func_code.co_varnames[:argcount]
        kwargnames = func.func_code.co_varnames[argcount:]
        fname = func.func_name
        usagestr = 'Usage: %s(' % fname
        for argname in argnames[1:]:
            usagestr += ' %s,' % argname
        if kwargcount > 0:
            for kwargname, val in zip(kwargnames, func.func_defaults):
                usagestr += (' %s=' % kwargname + str(val))
        usagestr += ') \n'

        def new_func(*args, **kw):
            if DEBUG: print threading.currentThread()
            # this is a bit of a cheat, but the first arg is always "self", so use it:
            self = args[0]
            if not self.threading_enabled: # bail out!
                return func(*args, **kw)
            if self._inthread_running == True: # we're already in a protected thread
                return func(*args, **kw) # execute function unchanged
            else: # start a new thread and set all the flags
                self._inthread_running = True
                self._aborted = False
                self._suspended = False
                self._break = False
                thr = InThread(func, *args, **kw)
                thr.start()
                while not thr.isFinished():
                    time.sleep(0.001) # fast loop?
                    
                # Now we're done with the thread: reset a bunch of flags
                self._inthread_running = False
                self._aborted = False
                self._suspended = False
                self._break = False
                return thr.retrieve()
        new_func.__doc__ = usagestr 
        if func.__doc__ is not None: new_func.__doc__ += func.__doc__
        new_func.__name__ = func.__name__
        return new_func

    #### END Threading stuff

    #### BEGIN Utility functions
    
    def exit(self):
        """ Convenience function to make it possible to exit with 'exit' instead of 'exit()' 
        This is specific to IPython """
        #_ip.magic('exit')
        exit()
        
    def register_writer(self, writer):
        self.writers.add(writer)
        
    def write(self, screen_msg, file_msg = None, timestamp = False):
        """ Dual printing to screen and file.  
        Default behavior (if no separate file msg specified)is to print the same message to both. """
        screen_msg = str(screen_msg)
        if file_msg == None:
            file_msg = screen_msg
        for writer in self.writers:
            writer.write(screen_msg)
        self.logwriter.write(file_msg)
    
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
        if self.tc == None:
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
            
    
    def getNextFilename(self, prefix, suffix):
        """ find the highest filenumber with prefix and suffix
        and return 'prefix + (highest+1) + suffix' """
        fl = glob.glob(prefix+'*'+suffix)
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
            
    def getPSD(self):
        """ Returns true if the PSD is the active counter """
        return self._psd_active
    
    def setPSD(self, enable):
        """ console command accessed via equivalent ICP command 'a+' or 'a-':
        switch modes to count with the PSD """
        if enable: # enable the PSD, make Count command do PSDCount
            self.Count = self.PSDCount
            self._psd_active = True
        else: # disable it, re-enable pencil detector, make Count do PencilCount
            self.Count = self.PencilCount
            self._psd_active = False
        
    def setLogging(self, enable):
        """ console command accessed via equivalent ICP command 'w+' or 'w-':
        Enable/Disable logging """
        self.logwriter.logging_enabled = enable
                
    def PrintCounts(self, duration):
        """ console command accessed via equivalent ICP command 'ct':
        get counts for a given duration using the active counter """
        result = self.Count(duration)
        self.write('count time: %.4f  counts: %d' % (result['count_time'], result['counts']))
        
    @inthread    
    def PencilCount(self, duration, reraise_exceptions = False):
        """ PencilCount(self, duration, reraise_exceptions = False):
        Count with the pencil detector.  All interaction is through self.scaler object """
        duration = numpy.float32(duration)
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
        return {'count_time': count_time, 'monitor': monitor, 'counts': counts, 'elapsed_time': elapsed_time, 'psd_data': psd_data}
    
    @inthread       
    def PSDCount(self, duration, reraise_exceptions = False):
        """ PSDCount(self, duration, reraise_exceptions = False):
         Count using the PSD.  Specific to Brookhaven PSD """
        psd = self.psd
        duration = numpy.float32(duration)
        self.scaler.ResetScaler()
        psd.AIM_CLEAR()
        psd.AIM_ARM()
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
        psd.AIM_DISARM()
        psd_data = psd.AIM_XFER()
        self.psd_data = psd_data
        psd.AIM_SAVE('asd.raw')
        
        xmin, ymin, xmax, ymax, numx, numy = self.ip.GetROI()
        
        # overwriting the counts from the scaler with the ones from the PSD:
        counts = numpy.sum(psd_data[xmin:xmax+1,ymin:ymax+1])
        return {'count_time': count_time, 'monitor': monitor, 'counts': counts, 'elapsed_time': elapsed_time, 'psd_data': psd_data}
        
    def AppendPSDResult(self, datafile):
        """ write a chunk of data (from PSD) to a file, appending it to end """
        ####################################################
        ### NOT COMPATIBLE WITH ICP FORMAT AT THE MOMENT ###
        ### (need to break into length-80 lines)         ###
        ####################################################
        f_out = open(datafile, 'a+')
        templine = StringIO()
        # writing to local string because it's pretty fast
        numpy.savetxt(data, templine, fmt='%d', delimiter=',')
        f_out.write(templine.read() + '\n')
        f_out.close()
    
    @inthread
    def GetHardMotorPos(self, motornum):
        hard_pos = self.mc.GetMotorPos(motornum)
        self.ip.SetHardMotorPos(motornum, hard_pos)
        return hard_pos
        
    def GetMotorPos(self, motornum):
        # default to retrieving the soft motor pos: 
        # this is what we need for writing data files, driving motors etc.
        return self.GetSoftMotorPos(motornum)
        
    @inthread    
    def GetSoftMotorPos(self, motornum, use_stored = False):
        if use_stored:
            hard_pos = self.ip.GetHardMotorPos(motornum)
        else:
            hard_pos = self.GetHardMotorPos(motornum)
        offset = self.ip.GetSoftMotorOffset(motornum)
        soft_pos = hard_pos - offset
        return soft_pos
  
    @inthread
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
            self.write(' Soft: A%02d=%8.3f\n Hard: A%02d=%8.3f' % (motornum, soft_pos, motornum, hard_pos))
        else:  # no motor specified - get them all
            self.PrintAllMotorPos()
       
    def GetStoredSoftMotorPos(self, motornum):
        """ get motor position (soft) from stored backend value """
        hard_pos = self.ip.GetHardMotorPos(motornum)
        offset = self.ip.GetSoftMotorOffset(motornum)
        soft_pos = hard_pos - offset
        return soft_pos
         
    @inthread    
    def SetHardMotorPos(self, motornum, pos):
        """ initialize the hardware motor position """
        self.mc.SetMotorPos(motornum, pos) # update the motor controller
        self.ip.SetHardMotorPos(motornum, pos) # update the MOTORS.BUF file
        
    @inthread
    def SetSoftMotorPos(self, motornum, pos):
        """ initialize the soft motor position """
        hard_pos = self.GetHardMotorPos(motornum)
        new_offset = hard_pos - pos
        self.ip.SetSoftMotorOffset(motornum, new_offset) # update the MOTORS.BUF file
        
    @inthread
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


    @inthread
    def moveMultiMotor(self, motornum_list, soft_position_list, check_limits = True, reraise_exceptions = True):
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
        def recursive_motor_move(motornum_list, position_list):
            if len(motornum_list) == 0: return # when the list is empty, start the while loop
            motnum = motornum_list.pop() # pull the top motor off the list
            pos = position_list.pop() # pull the top position off the list (reduces list length)
            self.mc.EnableMotor(motnum)
            self.mc.MoveMotor(motnum, pos)
            self.ip.SetHardMotorPos(motnum, pos) # update MOTORS.BUF
            recursive_motor_move(motornum_list, position_list)
            # this part doesn't get run until all motors are enabled and moving:
            while 1:
                if self._aborted: break
                if self.mc.CheckMoving(motnum) == False: break
                if self.mc.CheckHardwareLimits(motnum) == True: break
                time.sleep(self.loopdelay)           
            self.mc.StopMotor(motnum)
            while self.mc.CheckMoving(motnum) == True: # make sure we're stopped before disabling
                time.sleep(self.loopdelay)
            self.mc.DisableMotor(motnum)
            # and it doesn't exit until all sub-calls have returned (all motors are stopped and disabled)
            return
            
        recursive_motor_move(motornum_list, hard_position_list)
        #if not reraise_exceptions: # reset the abort flag
        #    self._aborted = False

    @inthread
    def oldDriveMotor(self, motornum, position, do_backlash = True, check_limits = True, reraise_exceptions = False):
        """ Drive motor to new position with optional backlash, and tolerance and limit checking """
        tolerance = self.ip.GetMotorTolerance(motornum)
        current_pos = self.GetMotorPos(motornum)
        if abs(current_pos - position) <= tolerance:
            # we're already there: return 
            return
 
        # otherwise, start the motion:
        if do_backlash:
            backlash = self.ip.GetMotorBacklash(motornum)
            backlash_pos = position - backlash # backlash to negative side
            if current_pos > position: # then we're driving backward: need to backlash
                for i in range(self.motor_retries):
                    if self._aborted: break 
                    #    if not reraise_exceptions: self._aborted = False
                    #    break
                    if self.moveMotor(motornum, backlash_pos, reraise_exceptions = True) == 'limit error': break
                    pos = self.GetMotorPos(motornum) 
                    if abs(pos - backlash_pos) <= tolerance: break
                # silently continues if still outside tolerance after (number = self.motor_retries) attempts
            else: # we're driving forward... no need to backlash
                pass
            
        # drive to final position: 
        for i in range(self.motor_retries):
            if self._aborted: break
            #    if not reraise_exceptions: self._aborted = False
            #    break
            if self.moveMotor(motornum, position, reraise_exceptions = True) == 'limit error': break
            pos = self.GetMotorPos(motornum) 
            if abs(pos - position) <= tolerance: break
        # silently continues if still outside tolerance after (number = self.motor_retries) attempts    
            
        new_pos = self.GetMotorPos(motornum)
        return new_pos
       
    def DriveMotor(self, motornum, position, do_backlash = True, check_limits = True, reraise_exceptions = False):
        self.DriveMultiMotor([motornum], [position], do_backlash, check_limits, reraise_exceptions)
        
    @inthread
    def DriveMultiMotor(self, motors_to_move, position_list, do_backlash = True, check_limits = True, reraise_exceptions = False):
        """ Drive motor to new position with optional backlash, and tolerance and limit checking """      
        position_list = list(position_list)
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
        
    @inthread        
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
    
    @inthread
    def RapidScan(self, motornum = None, start_angle = None, stop_angle = None, reraise_exceptions = False):
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
        
        t1 = time.time() - start_time
        cum_counts_list.append( self.scaler.GetCounts()[1] )
        t2 = time.time() - start_time
        ctime = (t1+t2)/2.0
        ctime_list.append(ctime)
        pos =  self.mc.GetMotorPos(motornum)
        position_list.append(pos)
        t3 = time.time() - start_time
        ptime = ((t2+t3)/2.0)
        
        self.mc.MoveMotor(motornum, stop_angle)
        
        #while self.mc.CheckMoving(motornum):
        pos = start_angle
        tol = self.ip.GetMotorTolerance(motornum)
        while 1:
            if self._aborted:
                print "aborted with ctrl-c"
                #if not reraise_exceptions:
                #    self._aborted = False
                break
            t1 = time.time() - start_time
            cum_counts_list.append( self.scaler.GetCounts()[1] )
            t2 = time.time() - start_time
            new_pos =  self.mc.GetMotorPos(motornum)
            t3 = time.time() - start_time
            
            new_count = cum_counts_list[-1] - cum_counts_list[-2]
            counts_list.append(new_count)
            new_ctime = (t1+t2)/2.0
            ctime_list.append(new_ctime)
            new_cps = new_count/(new_ctime - ctime)
            cps_list.append(new_cps)
            
            new_ptime = (t2+t3)/2.0
            pslope = (new_pos - pos) / (new_ptime - ptime)
            estimated_pos = pos + ((new_ctime - ptime) * pslope) # linearly interpolate, 
            # based on count timestamp vs. position timestamp
            position_list.append(estimated_pos)
            
            print position_list[-1], cps_list[-1]
            out_str = '%.4f\t%.4f' % (estimated_pos, new_cps)
            tmp_file = open(tmp_path, 'a')
            tmp_file.write(out_str + '\n')
            tmp_file.close()
            self.updatePlot(tmp_path, title)
            
            if (new_pos - pos) <= tol:
                break
            pos = new_pos
            ptime = new_ptime
            ctime = new_ctime
        
        self.scaler.AbortCount()
        count_time, monitor, counts = self.scaler.GetCounts()
        self.scaler.GetElapsed()
        print 'count time: %.3f' % count_time
        self.mc.DisableMotor(motornum)
       
        return position_list, cps_list, ctime_list
    
    @inthread    
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
            if (numpy.mod(i, 5) == 0) or (i == self.num_motors):
                self.write(soft_line + '\n')
                self.write(hard_line + '\n')
                soft_line = ' Soft: '
                hard_line = ' Hard: '
       
    def PrintAllStoredMotorPos(self):
        self.PrintAllMotorPos(use_stored=True)         
                
    @inthread           
    def PrintTemperature(self):
        if self.tc == None:
            print " Error: No temperature controller defined "
        else:
            temp = self.tc.GetTemperature() 
            self.write(str(temp), str(temp))
            
    @inthread
    def SetTemperature(self, temperature):
        if self.tc == None:
            print " Error: no temperature controller defined "
        else: 
            self.tc.SetTemperature(temperature)
            
    @inthread    
    def PrintLowerLimits(self):
        result = self.ip.GetLowerLimits()
        for i in range(self.num_motors):
            self.write('L%d: %.4f\t' % (i+1, result[i]))
    
    @inthread    
    def PrintUpperLimits(self):
        result = self.ip.GetUpperLimits()
        for i in range(self.num_motors):
            self.write('U%d: %.4f\t' % (i+1, result[i]))
        
    @inthread
    def SetLowerLimit(self, motornum, position):
        self.ip.SetLowerLimit(motornum, position)
        
    @inthread    
    def SetUpperLimit(self, motornum, position):
        self.ip.SetUpperLimit(motornum, position)
        
    @inthread    
    def PrintROI(self):
        xmin, ymin, xmax, ymax, numx, numy = self.ip.GetROI()
        self.write('xmin: %d\nxmax: %d\nymin: %d\nymax: %d' % (xmin, xmax, ymin, ymax))
    
    @inthread    
    def SetXmin(self, xmin):
        self.ip.SetROI(xmin, None, None, None)
    
    @inthread
    def SetXmax(self, xmax):
        self.ip.SetROI(None, None, xmax, None)
        
    @inthread    
    def SetYmin(self, ymin):
        self.ip.SetROI(None, ymin, None, None)
    
    @inthread    
    def SetYmax(self, ymax):
        self.ip.SetROI(None, None, None, ymax)
             
    @inthread    
    def FindPeak(self, motornum, mrange, mstep, duration=-1):
        """ the classic ICP function (fp)
It can be suspended with ctrl-z (ctrl-z again to resume)
or the 'finishup' routine skips the rest of the points and fits now (ctrl-\)
Abort (ctrl-c) works the same as usual """
        # set the flags:
        self._break = False
        # get the file ready:
        new_filename = self.getNextFilename('fpx%02d' % motornum, '.cg1')
        title = 'ic.FindPeak(%d, %.4f, %.4f, %.4f)' % (motornum, mrange, mstep, duration)
        
        f_out = open(new_filename, 'w')
        f_out.write('#Motor no. %d\tIntensity\t%s\n' % (motornum, time.ctime()))
        f_out.close()
                
        numsteps = numpy.int32(numpy.floor(numpy.float32(mrange) / numpy.float32(mstep)) + 1)
        centerpos = self.GetMotorPos(motornum)
        startpos = centerpos - (numpy.floor(numsteps/2.0) * mstep)
        endpos = startpos + ((numsteps-1) * mstep)
        positions = numpy.linspace(startpos, endpos, num=numsteps, endpoint = True)
        (tmp_fd, tmp_path) = tempfile.mkstemp() #temporary file for plotting
        data = []
        for i in range(numsteps):
            if self._break: break
            if self._aborted:
                print "aborted"
                return
            if self._suspended:
                print "suspended: press Ctrl-z to resume"
                while self._suspended:
                    if self._break: break
                    if self._aborted: 
                        return
                    time.sleep(self.loopdelay)
                    
            self.DriveMotor(motornum, positions[i], reraise_exceptions = True)
            result = self.Count(duration, reraise_exceptions = True)
            #count_time, monitor, counts, elapsed_time, psd_data = self.Count(duration, reraise_exceptions = True)
            data.append(result['counts'])
            out_str = '%.4f\t%.4f' % (positions[i], result['counts'])
            f_out = open(new_filename, 'a')
            f_out.write(out_str + '\n')
            f_out.close()
            tmp_file = open(tmp_path, 'a')
            tmp_file.write(out_str + '\n')
            tmp_file.close()
            self.write(out_str)
            self.updatePlot(tmp_path, title)
            
        datalen = len(data)
        ydata = numpy.array(data)
        try:
            fr = FitGauss(positions[:datalen], ydata, verbose = True).do_fit()
            self.write('y_offset: %f\namplitude: %f\ncenter: %f\nFWHM: %f' % (fr['y_offset'], fr['amplitude'], fr['center'], fr['FWHM']))
            self.updatePlot(tmp_path, title, fr)
            move_to_result = raw_input('Peak found at %.4f . Drive there? (y/n)' % fr['center'])
            if move_to_result.strip().lower() == 'y':
                self.DriveMotor(motornum, fr['center'])
        except:
            self.write("fit failed")
            
        return # end of FindPeak function
                 
    def updatePlot(self, filename, title, gaussfit_params = None):
        if not self.plot:
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
            self.plot.stdin.write('plot \'%s\' u 1:2:(1+sqrt(2))title \'%s\' w errorbars lt 2 ps 1 pt 7 lc rgb "green",' % (filename,title))
            self.plot.stdin.write('gauss(x) w lines lt 2 lc rgb "red"\n')
        else:
            self.plot.stdin.write('plot \'%s\' u 1:2:(1+sqrt(2)) title \'%s\' w errorbars lt 2 ps 1 pt 7 lc rgb "red"\n' % (filename,title))
            
    def GetIBufHeader(self, bufnum):
        return self.dataOutput.GenerateIBufferHeader(bufnum)
    
    @inthread    
    def RunIBuffer(self, bufnum, ):
        """ Execute the scan defined in the IBUFFER with number bufnum """
        ################################################
        ### THIS HAS NOT BEEN DEBUGGED OR TESTED YET ###
        ################################################
        ibuffer_obj = ibuffer.IBUFFER() # loads buffers from default file location
        if (bufnum <= 0) or (bufnum > len(ibuffer_obj.buffers)):
            print "error: ibuffer number out of range"
            return
        header = self.dataOutput.GenerateIBufferHeader(bufnum)
        ibuf = ibuffer_obj.buffers[bufnum-1]
        #IBUFFERS only move motors 1-6
        motnums = set(range(1,7))
        motors_to_move = []
        initial_pos = {}
        steps = {}
        final_pos = {}
        numpoints = ibuf.data['numpoints']
        duration = ibuf.data['monit']
        if not ibuf.data['Type'] == 'NEUT':
            duration *= -1.0 
        ul = self.ip.GetUpperLimits() # upper limit (array index for limits starts at zero, not 1)
        ll = self.ip.GetLowerLimits() # lower limit
        
        file_seedname = ibuf.data['description'][:5]
                
        generic_suffix = '.' + self.ip.GetNameStr().lower()
        ibuf_polarization_flags = [ ibuf.data['p1exec'], ibuf.data['p2exec'], ibuf.data['p3exec'], ibuf.data['p4exec'] ]
        pol_defined = False
        pol_states = []
        for pol_flag in ibuf_polarization_flags:
            pol_defined = pol_defined or (pol_flag > 0) # test for any "True" flags set in ibuf
        if pol_defined and self.polarization_enabled:
            identifiers = ['a', 'b', 'c', 'd']
            possible_pol_states = [ [False,False], [True,False], [False,True], [True,True] ] 
            file_suffixes = []
            for i, ident in enumerate(identifiers):
                if ibuf_polarization_flags[i] > 0:
                    file_suffixes.append(generic_suffix[:-3] + ident + generic_suffix[-1])
                    pol_states.append(possible_pol_states[i])
                    # this changes, for example, cg1 to ca1, cb1 etc. and ng1 to na1...
        else:
            # if there's no polarization defined, or if it's overriden by the "polarization_enabled" flag set to false
            file_suffixes = [generic_suffix]
            pol_states = [[False,False]]
        
        # ok, we're all set - now set up the output values
        output_params = {}
        output_params.update(ibuf.data) # inject all the ibuffer values
        output_params['collim'], output_params['mosaic'] = self.ip.GetCollimationMosaic()
        output_params['magnet_defined'] = magnet_defined
        output_params['temp_controller_defined'] = temp_controller_defined
        output_params['path'] = self.datafolder
        
        filenames = []
        for pol_state, file_suffix in zip(pol_states, file_suffixes):
            filenames.append( self.getNextFilename(file_seedname, file_suffix) )
        
        magnet_defined = (not self._magnet == [])
        temp_controller_defined = (not self._tc == [])
            
        #file_objects = []
        #for suffix in file_suffixes:
        #    newfile_obj = ICPDataFile.ICPDataFile(self, filename = None)
        #    fn = newfile_obj.getNextFilename(file_seedname, suffix, autoset = True)
        #    print fn
        #    file_objects.append(newfile_obj)
        #self.fo = file_objects
        
        #file_basename = self.getNextFilename(file_seedname, '.' + file_suffixes[0])[:-4] # only checks for existence of first suffix
        # might want to do a more complete check to avoid collisions + overwriting
        
        for i in self.ip.GetFixedMotors():
            motnums.remove(i)
            
        for i in motnums:
            initial_pos[i] = ibuf.data['a%dstart' % i]
            steps[i] = ibuf.data['a%dstep' % i]
            final_pos[i] = initial_pos[i] + steps[i] * numpoints
            if (initial_pos[i] > ul[i-1]) or (final_pos[i] > ul[i-1]):
                print 'Error: Moving motor %d will violate upper limit of %.4f' % (i, ul[i-1])
                return 'limit error'
            if (initial_pos[i] < ll[i-1]) or (final_pos[i] < ll[i-1]):
                print 'Error: Moving motor %d will violate lower limit of %.4f' % (i, ll[i-1])
                return 'limit error'
            if (ibuf.data['a%dstep' % i] > 1.0e-7): # darn floating-point errors 
                motors_to_move.append(i)
        
        data_keys = []
        data_info = {}
        
            
        initial_position = map(initial_pos.__getitem__, motnums)
        
        def calc_pos(n):
            pos = []
            for i in motors_to_move:
                pos.append(initial_pos[i] + (steps[i] * (n-1))) # first point has zero offset
            return pos
                
        pointnum = 0
        if not self._aborted:
            self.DriveMultiMotor(motnums, initial_position) # go to the start values for all non-fixed motors
            if temp_controller_defined:
                T0 = ibuf.data['T0']
                Tstep = ibuf.data['IncT']
                self._tc[0].SetTemperature(T0)
            if magnet_defined:
                H0 = ibuf.data['H0']
                Hstep = ibuf.data['Hinc']
                self._magnet[0].SetField(H0) # set the field on the primary field controller
            
            pointnum += 1
                
        while (pointnum <= numpoints):
            #if self._break: break # don't implement break on ibuffer run
            
            if self._suspended:
                print "suspended: press Ctrl-z to resume"
                while self._suspended:
                    #if self._break: break
                    if self._aborted: 
                        break # go do cleanup
                    time.sleep(self.loopdelay)
            if self._aborted:
                print "aborted"
                break # and go do cleanup
            
            new_positions = calc_pos(pointnum)
            data_info = []
            for new_pos in new_positions:
                data_info.append('%11g ' % new_pos)
                
            self.DriveMultiMotor(motors_to_move , new_positions)
                
            if temp_controller_defined:
                Tnow = T0 + Tstep * pointnum    
                data_info.append('%11g ' % Tnow)            
                self._tc[0].SetTemperature(Tnow)
            else: 
                Tnow = None
                        
            if magnet_defined:
                Hnow = H0 + Hstep * pointnum
                data_info.append('%11g ' % Hnow)
                self._magnet[0].SetField(Hnow)
            else:
                Hnow = None
                
                
            for pol_state, file_obj in zip(pol_states, file_objects):
                if pointnum == 1:
                    for publisher in self.publishers:
                        publisher.publish_start(output_params)
                self.setFlipperState(pol_state)
                result = self.Count(duration)
                #filename  = file_basename + '.' + file_suffix
                # self.dataOutput.AddPoint(result, filename)
                # write to file with file_suffix
                #self.dataOutput.AddPoint(result)
                #if DEBUG:
                #    print "opening %s and writing latest point (not really)" % file_obj.filename
                #record_monitor = (not ibuf.data['Type'] == 'NEUT')

                result['positions'] = new_positions
                result['Tnow'] = Tnow
                result['Hnow'] = Hnow
                output_params['result'] = result
                for publisher in self.publishers:
                    publisher.publish_datapoint(output_params)
                #file_obj.AddPoint(result, new_positions, record_monitor, Tnow, Hnow)
                #self.write(str(result['counts']), '')
            pointnum += 1
        
        # now for cleanup at the end:
        for publisher in self.publishers:
            publisher.publish_end(output_params)
    
    @inthread 
    def PrintFlipperCalibration(self, ps_num = None):
        if not ps_num:
            return self.PrintAllFlipperCal()
        else:
            fcals = self.ip.GetFcal()
            fcal = fcals[ps_num]
            result = 'Power supply: %d flipper current:   %.3f at energy  %.3f meV' % (ps_num, fcal['cur'], fcal['engy'])
            self.write(result)
            
    @inthread               
    def PrintAllFlipperCal(self):
        fcals = self.ip.GetFcal()
        result = ''
        for i in range(len(fcals)):
            fcal = fcals[i+1]
            result += 'Power supply: %d flipper current:   %.3f at energy  %.3f meV\n' % (i+1, fcal['cur'], fcal['engy'])
        self.write(result)
    
    @inthread            
    def SetFlipperCalibration(self, ps_num, cur, engy = None):
        self.ip.SetFcal(ps_num, cur, engy)
    
    @inthread
    def SetMonochromatorFlipper(self, enable):
        if enable: self.energizeFlipper(0)
        else: self.deenergizeFlipper(0)
    
    @inthread    
    def SetAnalyzerFlipper(self, enable):
        if enable: self.energizeFlipper(1)
        else: self.deenergizeFlipper(1)
    
    @inthread
    def setFlipperState(self, pol_state):
        for i, state in enumerate(pol_state):
            if state == True:
                self.energizeFlipper(i)
            else:
                self.deenergizeFlipper(i)
            
    @inthread
    def energizeFlipper(self, flippernum):
        """ flippers are numbered... flipper 0 is monochromator, flipper 1 is at analyzer usually
        flipper 0 has two power supplies (1 and 2), for flipping and compensation
        flipper 1 also has two (3 and 4)...
        this command lights up both power supplies for the given flipper """
        fcals = self.ip.GetFcal()
        # turn them on one at a time:
        ps_num = int(flippernum * 2)
        self.flipper_ps[ps_num].SetCurrent(fcals[ps_num+1]['cur'])  # ignores the 'energy' parameter.  This functionality is broken in ICP at ANDR anyway
        self.flipper_ps[ps_num+1].SetCurrent(fcals[ps_num+2]['cur'])
        
    @inthread
    def deenergizeFlipper(self, flippernum):
        ps_num = int(flippernum * 2)
        self.flipper_ps[ps_num].SetCurrent(0.0)
        self.flipper_ps[ps_num+1].SetCurrent(0.0)
    
    @inthread
    def SetFlipperPSCurr(self, ps_num, current):
        self.flipper_ps[ps_num].SetCurrent(float(current))
    
    @inthread
    def SetFlipperPSVolt(self, ps_num, voltage):
        self.flipper_ps[ps_num].SetVoltage(float(voltage))
        
    def fix(self, motornum):
        """ set the motor to "fixed", which means it won't be moved during an ibuffer scan """
        self.ip.SetMotorFixed(motornum)
        #self.fixed_motors.add(motornum)
        
    def rel(self, motornum):
        """ release a previously "fixed" motor """
        self.ip.SetMotorReleased(motornum)
        #self.fixed_motors.remove(motornum)
        
