import struct, time
from ordered_dict import OrderedDict
import os
#home_dir = os.environ['HOME']
home_dir = '/usr/local'
 
DEFAULT_VME_PORT = '/dev/ttyUSB0'
DEBUG = False
MAXMOTOR = 24
MAXMOTS = 40 # for PBR and MAGIK - 30 for other instruments
MOTPOS_BUF = os.path.join(home_dir, 'icp/cfg/MOTPOS.BUF')
MOTORS_BUF = os.path.join(home_dir, 'icp/cfg/MOTORS.BUF')
INSTR_CFG = os.path.join(home_dir, 'icp/cfg/INSTR.CFG')
DEBUG = False
RS232_CFG = os.path.join(home_dir, 'icp/cfg/rs232.conf')
FIELD_LENGTH = 64 # new PBR and MAGIK - this is 40 for BT4 etc.

class InstrumentParameters:
    """ class to handle values stored in ICP config files.  Convert to XML at your leisure"""
    def __init__(self):
        self.field_length = FIELD_LENGTH
        self.rs232cfgfile = RS232_CFG
        self.motorsbuffile = MOTORS_BUF
        self.motposbuffile = MOTPOS_BUF
        self.instrcfgfile = INSTR_CFG
        self.maxmots = MAXMOTS
        self.loadRS232Params()
        self.loadInstrCfg()
        self.loadMotors()
        self.num_motors = self.InstrCfg['#mots']
        
        
    def loadRS232Params(self):
        self.rs232 = {}
        f = open(self.rs232cfgfile, 'r')
        lines = f.readlines()
        f.close()
        for line in lines:
            if not line.lstrip().startswith('#'):
                data = line.split()
                if DEBUG: print data
                if not len(data) == 5:
                    # serial parameter lines should have 5 entries
                    break
                self.rs232[int(data[0])] = {'port':data[1], 'baud':data[2], 'stop':data[3], 'parity':data[4]}
                
    def GetSerialPort(self, entry_num):
        return self.rs232[entry_num]['port']
        
    def loadInstrCfg(self):
        self.InstrCfg = {}
        f = open(self.instrcfgfile, 'r')
        self.InstrCfg['header'] = f.readline()[:-1] # omit final '\n'
        data = f.readline().split() # split on whitespace
        keys = f.readline()[:-1].split(',') # keys are comma-separated
        for key, datum in zip(keys, data):
            self.InstrCfg[key] = datum
        # and again... there are two lines formatted like this
        data = f.readline().split() # split on whitespace
        keys = f.readline()[:-1].split(',') # keys are comma-separated
        for key, datum in zip(keys, data):
            self.InstrCfg[key] = datum
        # and again... but the last entry is subdivided, so stop at 5    
        data = f.readline().split() # split on whitespace
        keys = f.readline()[:-1].split(',') # keys are comma-separated
        for key, datum in zip(keys[:5], data[:5]):
            self.InstrCfg[key] = datum
        pols = range(1, int(self.InstrCfg['#pol_ps'])+1)
        self.InstrCfg['types'] = {}
        for key, datum in zip(pols, data[5:]):
            self.InstrCfg['types'][key] = datum
#        if self.InstrCfg['sta#'] == '-1':
#            # and again... there are two lines formatted like this
#            data = f.readline().split() # split on whitespace
#            keys = f.readline()[:-1].split(',') # keys are comma-separated
#            for key, datum in zip(keys, data):
#                self.InstrCfg[key] = datum
        # and again... another like the first two but with tabs
        data = f.readline().split() # split on whitespace
        keys = f.readline()[:-1].split('\t') # keys are tab-separated
        for key, datum in zip(keys, data):
            self.InstrCfg[key] = datum
            
        # now loading up motor params
        motorkeys = f.readline().split()
        motors = OrderedDict()
        for i in range(int(self.InstrCfg['#mots'])):
            data = f.readline().split()
            motordict = OrderedDict()
            for key, datum in zip(motorkeys, data):
                motordict[key] = int(float(datum))
            if motordict['SpcAddr'] == 0: 
                motors[i+1] = motordict
        self.InstrCfg['motors'] = motors    
        f.close()
              
    def GetNameStr(self):
        """ get the intrument identifier string, based on the station number """
        nsta = int(self.InstrCfg['sta#'])
        if nsta > 0:
            namestr = 'BT%d' % nsta
        elif nsta == 0:
            namestr = 'XR%d' % nsta
        elif nsta == -11:
            namestr = 'CG1'
        elif nsta == -1:
            namestr = 'PBR'
        else:
            namestr = 'NG%d' % nsta
        
        return namestr
           
    def loadMotors(self):
        self.MotorsBuf = {}
        field_length = self.field_length
        entry_length = 4 # 32-bit floating-point numbers and ints
        f = open(self.motorsbuffile, 'rb')
        fcontents = f.read()
        f.close()
        data_chunks = []
        num_chunks = len(fcontents)/(field_length * entry_length)
        for i in range(num_chunks):
            data_chunks.append(fcontents[i*field_length*entry_length:(i+1)*field_length*entry_length])
        
        #the motor data is structured just like in INSTR.CFG.  Not an accident.
        motorkeys = ['Base', 'Ramp', 'Top', 'Pulses/Deg', 'Backlash', 'Err', 'Type']
        motors = {}
        num_mots = int(self.InstrCfg['#mots'])
        self.maxmotor = num_mots
        for i in range(num_mots):
            line = data_chunks[i]
            data = struct.unpack('7i', line[:7*4])
            motordict = {}
            for key, datum in zip(motorkeys, data):
                motordict[key] = datum
            motors[i+1] = motordict
        self.MotorsBuf['motors'] = motors
            
        self.MotorsCfg = {}
        #data_chunks from num_mots to self.maxmots are useless and ignored
        
        # will fill these in as needed... right now need psd parameters and fcal
        fcal = {}
        num_pols = int(self.InstrCfg['#pol_ps'])
        read_len = 4 * 3 * num_pols
        line = data_chunks[35]
        data = struct.unpack('%df' % num_pols*3, line[:read_len])
        for i in range(num_pols):
            fcaldict = {}
            fcaldict['fullamp'] = data[0+i]
            fcaldict['cur'] = data[num_pols + i]
            fcaldict['engy'] = data[num_pols*2 + i]
            fcal[i+1] = fcaldict
            
        psd = {}
        
    def GetCollimationMosaic(self):
        field_length = self.field_length
        entry_length = 4 # 32-bit floating-point numbers and ints
        seek_pos = (self.maxmots + 4 - 1) * field_length * entry_length
        # the stuff we're looking for is at maxmots + 4, with -1 offset 
        f_in = open(self.motorsbuffile, 'rb')
        f_in.seek(seek_pos)
        data = f_in.read(field_length * entry_length)
        collimation = struct.unpack('4I', data[:4*4])
        mosaic = struct.unpack('3I', data[4*4:7*4])
        wavelength = struct.unpack('f', data[7*4:8*4])
        f_in.flush()
        f_in.close()
        return collimation, mosaic
    
    def GetWavelength(self):
        field_length = self.field_length
        entry_length = 4 # 32-bit floating-point numbers and ints
        seek_pos = (self.maxmots + 4 - 1) * field_length * entry_length + 7 * entry_length
        # the stuff we're looking for is at maxmots + 4, with -1 offset 
        f_in = open(self.motorsbuffile, 'rb')
        f_in.seek(seek_pos)
        data = f_in.read(4)
        wavelength = struct.unpack('f', data)[0]
        f_in.flush()
        f_in.close()
        return wavelength
        
    def SetWavelength(self, wl):
        field_length = self.field_length
        entry_length = 4 # 32-bit floating-point numbers and ints
        seek_pos = (self.maxmots + 4 - 1) * field_length * entry_length + 7 * entry_length
        # the stuff we're looking for is at maxmots + 4, with -1 offset 
        f_out = open(self.motorsbuffile, 'r+b')
        f_out.seek(seek_pos)
        f_out.write(struct.pack('f', wl))
        f_out.flush()
        f_out.close()
        return

    def oldGetMotorBacklash(self, motornum):
        """ return the backlash in real units (Backlash_pulses / (Pulses/Deg)) """
        backlashes = self.GetAllMotorBacklashes()
        if not motornum in backlashes.keys():
            print "not a valid motor"
        else:
            return backlashes[motornum]
    
    def SetMotorBacklash(self, motornum, backlash):
        motor = self.MotorsBuf['motors'][motornum]
        pulses_per_deg = motor['Pulses/Deg']
        backlash_pulses = int(backlash * pulses_per_deg)
        self.SetMotorBacklashPulses(motornum, backlash_pulses)
        return
        
    def SetMotorBacklashPulses(self, motornum, backlash_pulses):
        field_length = self.field_length
        entry_length = 4 # 32-bit floating-point numbers
        seek_pos = (motornum - 1) * field_length * entry_length
        seek_pos += 4 * entry_length # backlash is 5th entry: 4 if counting from 0
        f_out = open(self.motorsbuffile, 'r+b')
        f_out.seek(seek_pos)
        f_out.write(struct.pack('i', int(backlash_pulses)))
        f_out.flush()
        f_out.close()
        return
        
    def GetMotorBacklash(self, motornum):
        motor = self.MotorsBuf['motors'][motornum]
        pulses_per_deg = motor['Pulses/Deg']
        backlash_pulses = self.GetMotorBacklashPulses(motornum)
        backlash = float(backlash_pulses) / float(pulses_per_deg)
        return backlash
    
    def GetMotorBacklashPulses(self, motornum):
        field_length = self.field_length
        entry_length = 4 # 32-bit floating-point numbers
        seek_pos = (motornum - 1) * field_length * entry_length
        seek_pos += 4 * entry_length # backlash is 5th entry: 4 if counting from 0
        f_in = open(self.motorsbuffile, 'rb')
        f_in.seek(seek_pos)
        data = f_in.read(entry_length)
        f_in.flush()
        f_in.close()
        backlash_pulses = struct.unpack('i', data)[0]
        return backlash_pulses
        
    def GetMotorTolerance(self, motornum):        
        motor = self.MotorsBuf['motors'][motornum]
        pulses_per_deg = motor['Pulses/Deg']
        tolerance_pulses = self.GetMotorTolerancePulses(motornum)
        tolerance = float(tolerance_pulses) / float(pulses_per_deg)
        return tolerance
    
    def GetMotorTolerancePulses(self, motornum):
        field_length = self.field_length
        entry_length = 4 # 32-bit floating-point numbers
        seek_pos = (motornum - 1) * field_length * entry_length
        seek_pos += 5 * entry_length # tolerance ('err') is 6th entry: 5 if counting from 0
        f_in = open(self.motorsbuffile, 'rb')
        f_in.seek(seek_pos)
        data = f_in.read(entry_length)
        f_in.flush()
        f_in.close()
        tolerance_pulses = struct.unpack('i', data)[0]
        return tolerance_pulses  
        
    def oldGetMotorTolerance(self, motornum):
        """ return the tolerance (acceptable offset from target value) =  (tolerance_pulses / (Pulses/Deg)) """
        motor_data = self.MotorsBuf['motors'][motornum]
        tolerance_pulses = motor_data['Err']
        pulses_per_deg = motor_data['Pulses/Deg']
        if int(pulses_per_deg) == 0:
            return 0.0
        else: 
            tolerance = float(tolerance_pulses) / float(pulses_per_deg)
            return tolerance
    
    def SetMotorTolerance(self, motornum, tolerance):       
        motor = self.MotorsBuf['motors'][motornum]
        pulses_per_deg = motor['Pulses/Deg']
        tolerance_pulses = int(tolerance * pulses_per_deg)
        self.SetMotorTolerancePulses(motornum, tolerance_pulses)
        
    def SetMotorTolerancePulses(self, motornum, tolerance_pulses):
        field_length = self.field_length
        entry_length = 4 # 32-bit floating-point numbers
        seek_pos = (motornum - 1) * field_length * entry_length
        seek_pos += 5 * entry_length # tolerance ('err') is 6th entry: 5 if counting from 0
        f_out = open(self.motorsbuffile, 'r+b')
        f_out.seek(seek_pos)
        f_out.write(struct.pack('i', int(tolerance_pulses)))
        f_out.flush()
        f_out.close()
        return 
    
    def GetAllMotorBacklashes(self):
        """ return a dictionary of backlash values for all motors up to MAXMOTS """    
        backlashes = {}
        for i in self.InstrCfg['motors']:
            M = self.InstrCfg['motors'][i]['M']
            backlashes[M] = self.GetMotorBacklash(i)
        return backlashes 
        
    def GetAllMotorTolerances(self):
        """ return a dictionary of tolerance values for all motors up to MAXMOTS """    
        tolerances = {}
        for i in self.InstrCfg['motors']:
        #range(1, self.maxmotor+1):
            motor = self.InstrCfg['motors'][i]
            tolerances[motor['M']] = self.GetMotorTolerance(i)
        return tolerances   
          
    def GetUpperLimits(self):
        field_length = self.field_length
        entry_length = 4 # 32-bit floating-point numbers
        seek_pos = (self.maxmots + 2 - 1) * field_length * entry_length
        # the stuff we're looking for is at maxmots + 2, with -1 offset 
        f_in = open(self.motorsbuffile, 'rb')
        f_in.seek(seek_pos)
        data = f_in.read(self.maxmots * entry_length)
        f_in.flush()
        f_in.close()
        return list(struct.unpack('%df' % self.maxmots, data))
        
    def SetUpperLimit(self, motornum, position):
        field_length = self.field_length
        entry_length = 4 # 32-bit floating-point numbers
        seek_pos = (self.maxmots + 2 - 1) * field_length * entry_length
        seek_pos += (motornum - 1) * entry_length
        # the stuff we're looking for is at maxmots + 2, with -1 offset 
        f_out = open(self.motorsbuffile, 'r+b')
        f_out.seek(seek_pos)
        f_out.write(struct.pack('f', position))
        f_out.flush()
        f_out.close()
        return 
        
    def GetLowerLimits(self):
        field_length = self.field_length
        entry_length = 4 # 32-bit floating-point numbers
        seek_pos = (self.maxmots + 3 - 1) * field_length * entry_length
        # the stuff we're looking for is at maxmots + 3, with -1 offset 
        f_in = open(self.motorsbuffile, 'rb')
        f_in.seek(seek_pos)
        data = f_in.read(self.maxmots * entry_length)
        f_in.flush()
        f_in.close()
        return list(struct.unpack('%df' % self.maxmots, data))
        
    def SetLowerLimit(self, motornum, position):
        field_length = self.field_length
        entry_length = 4 # 32-bit floating-point numbers
        seek_pos = (self.maxmots + 3 - 1) * field_length * entry_length
        seek_pos += (motornum - 1) * entry_length
        # the stuff we're looking for is at maxmots + 3, with -1 offset 
        f_out = open(self.motorsbuffile, 'r+b')
        f_out.seek(seek_pos)
        f_out.write(struct.pack('f', position))
        f_out.flush()
        f_out.close()
        return 

    def GetFixedMotors(self):
        """ returns the complete set of fixed motors, unlike GetMotorsFixed, which returns a list of booleans
        indicating fixed yes/no for all motors """
        fixed_list = self.GetMotorsFixed()
        fixed_motors = set()
        for motnum, fixed in enumerate(fixed_list):
            if fixed:
                fixed_motors.add(motnum + 1)
        return fixed_motors

    def GetMotorsFixed(self):
        field_length = self.field_length
        entry_length = 4 # 32-bit floating-point numbers
        seek_pos = (self.maxmots + 5 - 1) * field_length * entry_length
        # the stuff we're looking for is at maxmots + 5, with -1 offset 
        f_in = open(self.motorsbuffile, 'rb')
        f_in.seek(seek_pos)
        data = f_in.read(self.maxmots * entry_length)
        f_in.flush()
        f_in.close()
        return list(struct.unpack('%di' % self.maxmots, data))
            
    def GetMotorFixed(self, motornum):
        fixed_list = self.GetMotorsFixed()
        fixed = fixed_list[motornum - 1]
        if fixed == 0:
            return False
        elif fixed == 1:
            return True
        else:
            return "not defined"
            
    def SetMotorFixed(self, motornum):
        if motornum > self.maxmots:
            return
        true_value = 1
        field_length = self.field_length
        entry_length = 4 # 32-bit floating-point numbers
        seek_pos = (self.maxmots + 5 - 1) * field_length * entry_length
        seek_pos += (motornum - 1) * entry_length
        # the stuff we're looking for is at maxmots + 5, with -1 offset 
        f_out = open(self.motorsbuffile, 'r+b')
        f_out.seek(seek_pos)
        f_out.write(struct.pack('i', true_value))
        f_out.flush()
        f_out.close()
        return
        
    def SetMotorReleased(self, motornum):
        if motornum > self.maxmots:
            return
        false_value = 0
        field_length = self.field_length
        entry_length = 4 # 32-bit floating-point numbers
        seek_pos = (self.maxmots + 5 - 1) * field_length * entry_length
        seek_pos += (motornum - 1) * entry_length
        # the stuff we're looking for is at maxmots + 5, with -1 offset 
        f_out = open(self.motorsbuffile, 'r+b')
        f_out.seek(seek_pos)
        f_out.write(struct.pack('i', false_value))
        f_out.flush()
        f_out.close()
        return
    
    def GetROI(self):
        """ get the Region of Interest (ROI) for Position Sensitive Detector, 
        i.e. xmin, xmax, ymin, ymax, numx, numy """
        field_length = self.field_length
        entry_length = 4 # 32-bit floating-point numbers
        seek_pos = (self.maxmots + 7 - 1) * field_length * entry_length
        # the stuff we're looking for is at maxmots + 7, with -1 offset
        seek_pos += 3 * entry_length
        # within the line, we're looking for 4 entries starting at the 4th entry
        f_in = open(self.motorsbuffile, 'rb')
        f_in.seek(seek_pos)
        data = f_in.read(6 * entry_length) # 6 numbers to read
        f_in.flush()
        f_in.close()
        return list(struct.unpack('6I', data))
        
    def SetROI(self, xmin = None, ymin = None, xmax = None, ymax = None):
        """ get the Region of Interest (ROI) for Position Sensitive Detector, 
        i.e. xmin, xmax, ymin, ymax, numx, numy """
        newxmin, newymin, newxmax, newymax, newnumx, newnumy = self.GetROI()
        # now override the ones specified in the arguments to the function:
        if xmin:
            newxmin = xmin
        if ymin:
            newymin = ymin
        if xmax:
            newxmax = xmax
        if ymax:
            newymax = ymax
            
        new_str = struct.pack('6I', newxmin, newymin, newxmax, newymax, newnumx, newnumy)
        
        field_length = self.field_length
        entry_length = 4 # 32-bit floating-point numbers
        seek_pos = (self.maxmots + 7 - 1) * field_length * entry_length
        # the stuff we're looking for is at maxmots + 7, with -1 offset
        seek_pos += 3 * entry_length
        # within the line, we're looking for 4 entries starting at the 4th entry
        f_out = open(self.motorsbuffile, 'r+b')
        f_out.seek(seek_pos)
        f_out.write(new_str)
        f_out.flush()
        f_out.close()
        return [newxmin, newymin, newxmax, newymax, newnumx, newnumy]
            
    def GetFcal(self):
        field_length = self.field_length
        entry_length = 4 # 32-bit floating-point numbers
        seek_pos = (self.maxmots + 6 - 1) * field_length * entry_length
        # the stuff we're looking for is at maxmots + 6, with -1 offset
        f_in = open(self.motorsbuffile, 'rb')
        f_in.seek(seek_pos)
        num_pols = int(self.InstrCfg['#pol_ps'])
        data = f_in.read(3 * num_pols * entry_length)
        f_in.flush()
        f_in.close()
        
        fcal = {}
        values = struct.unpack('%df' % num_pols*3, data)
        for i in range(num_pols):
            fcaldict = {}
            fcaldict['fullamp'] = values[0+i]
            fcaldict['cur'] = values[num_pols + i]
            fcaldict['engy'] = values[num_pols*2 + i]
            fcal[i+1] = fcaldict
        return fcal
        
    def SetFcal(self, ps_num, cur, engy = None):
        num_pols = int(self.InstrCfg['#pol_ps'])
        if ps_num > num_pols:
            print "invalid powersupply number"
            return
        fcal = self.GetFcal()
        #ok, now replace the current in the proper power supply
        fcal[ps_num]['cur'] = cur
        if engy:
            fcal[ps_num]['engy'] = engy
        
        # and write back to file
        new_str = ''
        for i in range(num_pols):
            new_str += struct.pack('f', fcal[i+1]['fullamp'])
        for i in range(num_pols):
            new_str += struct.pack('f', fcal[i+1]['cur'])
        for i in range(num_pols):
            new_str += struct.pack('f', fcal[i+1]['engy'])
        
        field_length = self.field_length
        entry_length = 4 # 32-bit floating-point numbers
        seek_pos = (self.maxmots + 6 - 1) * field_length * entry_length
        # the stuff we're looking for is at maxmots + 6, with -1 offset
        f = open(self.motorsbuffile, 'r+b')
        f.seek(seek_pos)
        f.write(new_str)
        f.flush()
        f.close()
    
        
    def ParseMotpos(self):
        f_in = open(self.motposbuffile, 'rb')
        data = f_in.read()
        f_in.close()
        motors = []
        field_length = self.field_length 
        entry_length = 4 # 32-bit floating-point numbers
        for i in range(self.maxmots):
            chunk = data[i*field_length*entry_length:(i+1)*field_length*entry_length]
            motors.append(struct.unpack('%df' % field_length, chunk))
        return motors
        
    def GetSoftMotorOffset(self, motornum):
        field_length = self.field_length
        entry_length = 4 # 32-bit floating-point numbers
        seek_pos = ((motornum - 1) * field_length * entry_length) + entry_length
        # the (motornum - 1) is because our motor indexing at the user-interface starts at 1, not zero
        f_in = open(self.motposbuffile, 'rb')
        f_in.seek(seek_pos)
        data = f_in.read(entry_length)
        f_in.flush()
        f_in.close()
        return struct.unpack('f', data)[0]
        
    def GetHardMotorPos(self, motornum):
        field_length = self.field_length
        entry_length = 4 # 32-bit floating-point numbers
        seek_pos = ((motornum - 1) * field_length * entry_length) + 0
        # the (motornum - 1) is because our motor indexing at the user-interface starts at 1, not zero
        f_in = open(self.motposbuffile, 'rb')
        f_in.seek(seek_pos)
        data = f_in.read(entry_length)
        f_in.flush()
        f_in.close()
        return struct.unpack('f', data)[0]
              
    def SetSoftMotorOffset(self, motornum, offset):
        field_length = self.field_length
        entry_length = 4 # 32-bit floating-point numbers
        seek_pos = ((motornum - 1) * field_length * entry_length) + entry_length
        # the (motornum - 1) is because our motor indexing at the user-interface starts at 1, not zero
        f_out = open(self.motposbuffile, 'r+b')
        f_out.seek(seek_pos)
        f_out.write(struct.pack('f', offset))
        f_out.flush()
        f_out.close()
        
    def SetHardMotorPos(self, motornum, hard_pos):
        field_length = self.field_length
        entry_length = 4 # 32-bit floating-point numbers
        seek_pos = ((motornum - 1) * field_length * entry_length) + 0
        # the (motornum - 1) is because our motor indexing at the user-interface starts at 1, not zero
        f_out = open(self.motposbuffile, 'r+b')
        f_out.seek(seek_pos)
        f_out.write(struct.pack('f', hard_pos))
        f_out.flush()
        f_out.close()
    
    def GetSoftMotorPos(self, motornum):
        """ convenience function:  returns the value often used at instrument for control """
        hard_pos = self.GetHardMotorPos(motornum)
        offset = self.GetSoftMotorOffset(motornum)
        return hard_pos - offset
        
    def SetSoftPos(self, motornum, position):
        hard_pos = self.GetHardMotorPos(motornum)
        new_soft_offset = hard_pos - position
        self.SetSoftMotorOffset(motornum, new_soft_offset)
        
    def getState(self):
        """ a dictionary with a snapshot of the current instrument state """
        state = OrderedDict()
        num_mots = int(self.InstrCfg['#mots'])
        state['num_mots'] = num_mots
        motpos = self.ParseMotpos()
        for i in range(num_mots):
            state['a%d' % (i+1)] = motpos[i][0] - motpos[i][1] # use the soft value = hard - offset
        state['wavelength'] = self.GetWavelength()
        state['collimation'], state['mosaic'] = self.GetCollimationMosaic()
        state['namestr'] = self.GetNameStr()
        state['num_detectors'] = int(self.InstrCfg['#scl'])
        return state
        
            
        
    
