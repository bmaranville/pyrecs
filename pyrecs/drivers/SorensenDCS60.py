import serial
from numpy import abs
import time
import rs232gpib
from magnet_controller import MagnetController

GPIB_ADDR = 7 # this is the current address for Sorensen at AND/R
debug = False


class Sorensen:
    """Class to read and write Voltage and Current to Sorensen DCS30"""
    def __init__(self, port = '/dev/ttyUSB3', serial_mode = True, gpib_addr = GPIB_ADDR):
        if serial_mode:
            self.serial = serial.Serial(port, 19200, parity='N', rtscts=False, xonxoff=False, timeout=1)
            self.newline_str = '\r'
            self.sendCommand = self.sendSerialCommand
            self.receiveReply = self.receiveSerialReply
        else: # gpib mode
            self.gpib = rs232gpib.RS232GPIB()
            self.gpib_addr = gpib_addr
            self.sendCommand = self.sendGPIBCommand
            self.receiveReply = self.receiveGPIBReply
        self.read_timeout = 1.0
        self.volt_change_rate = 2.0 #volts/second
        self.curr_change_rate = 1.0 #amps/second
        self.voltage = None
        self.current = None
        self.check_errors = False

    def sendSerialCommand(self, command = None, reply_expected = False):
        if not command:
            return ''
        else:
            self.serial.write(command)
            self.serial.write(self.newline_str)
            self.serial.flush()
            
        if reply_expected:
            reply = self.receiveReply()
            return reply
            
    def receiveSerialReply(self):
        reply = self.serial.readline()
        return reply
        
    def sendGPIBCommand(self, command = None, reply_expected = False):
        if command:
            self.gpib.sendCommand(self.gpib_addr, command)
            
        if reply_expected:
            reply = self.receiveReply()
            return reply
            
    def receiveGPIBReply(self):
        reply = self.gpib.receiveReply(self.gpib_addr)
        return reply
        
    def receiveSerialReply_old(self):
        begin_read_time = time.time()
        endofline = False
        data = ''
        while (time.time() - begin_read_time) < self.read_timeout and endofline == False:
            newdata = self.serial.read(1)
            if newdata == self.newline_str:
                endofline = True
            else: 
                data += newdata
        return data

    def sendCommandAuto(self, command = None):
        if not command:
            return
        else:
            if command[-1] == '?':
                return self.sendCommand(command, reply_expected = True)
            else:
                self.sendCommand(command, reply_expected = False)

    def GetVoltageSetpoint(self):
        if self.check_errors: self.err_state = self.sendCommand('SYST:ERR?', reply_expected = True)
        reply_str = self.sendCommand('SOUR:VOLT?', reply_expected = True)
        self.voltage_setp = float(reply_str)
        return self.voltage_setp
        
    def GetCurrentSetpoint(self):
        if self.check_errors: self.err_state = self.sendCommand('SYST:ERR?', reply_expected = True)
        #self.err_state = self.sendCommand('SYST:ERR?', reply_expected = True)
        reply_str = self.sendCommand('SOUR:CURR?', reply_expected = True)
        self.current_setp = float(reply_str)
        return self.current_setp
        
    def GetVoltageMeasured(self):
        if self.check_errors: self.err_state = self.sendCommand('SYST:ERR?', reply_expected = True)
        #self.err_state = self.sendCommand('SYST:ERR?', reply_expected = True)
        reply_str = self.sendCommand('MEAS:VOLT?', reply_expected = True)
        self.voltage_meas = float(reply_str)
        return self.voltage_meas
  
    def GetCurrentMeasured(self):
        if self.check_errors: self.err_state = self.sendCommand('SYST:ERR?', reply_expected = True)
        #self.err_state = self.sendCommand('SYST:ERR?', reply_expected = True)
        reply_str = self.sendCommand('MEAS:CURR?', reply_expected = True)
        self.current_meas = float(reply_str)
        return self.current_meas   
        
    def SetVoltage(self, voltage = 0.0):
        volts_now = self.GetVoltageSetpoint()
        voltage_str = '%.3f' % voltage
        diff = abs(voltage - volts_now)
        t_change = diff / self.volt_change_rate
        t_change_str = '%.3f' % t_change
        print 'SOUR:VOLT:RAMP ' + voltage_str + ' ' + t_change_str
        if self.check_errors: self.err_state = self.sendCommand('SYST:ERR?', reply_expected = True)
        self.sendCommand('SOUR:VOLT:RAMP ' + voltage_str + ' ' + t_change_str, reply_expected = False)
        time.sleep(t_change)
        return
        
    def SetCurrent(self, current = 0.0):
        curr_now = self.GetCurrentSetpoint()
        curr_str = '%.3f' % current
        diff = abs(current - curr_now)
        t_change = diff / self.curr_change_rate
        t_change_str = '%.3f' % t_change
        print('SOUR:CURR:RAMP ' + curr_str + ' ' + t_change_str)
        if self.check_errors: self.err_state = self.sendCommand('SYST:ERR?', reply_expected = True)
        self.sendCommand('SOUR:CURR:RAMP ' + curr_str + ' ' + t_change_str, reply_expected = False)
        time.sleep(t_change)
        return
        
    def MakeLocal(self):
        if self.check_errors: self.err_state = self.sendCommand('SYST:ERR?', reply_expected = True)
        self.sendCommand('SYST:LOCAL ON', reply_expected = False)
        
class SorensenNew(MagnetController):
    label = 'Sorensen DCS 60'
    def __init__(self):
        MagnetController.__init__(self)
        self.newline_str = '\r'
        self.read_timeout = 1.0
        self.check_errors = False
        """ the serial to gpib converter is on the fourth port at MAGIK, which is /dev/ttyUSB3 """
        self.settings = {
            'serial_port': '/dev/ttyUSB4',
            'gpib_addr': '5',
            'comm_mode': 'gpib',
            'serial_to_gpib_port': '/dev/ttyUSB3',
            'volt_change_rate': 2.0, # volts/second
            'curr_change_rate': 1.0 # amps/second
            }
        self.valid_settings = {
            'serial_port': dict([('/dev/ttyUSB%d' % i, 'Serial port %d' % (i+1)) for i in range(4, 16)]),
            'gpib_addr': dict([(i, str(i)) for i in range(5, 32)]),
            'comm_mode': {'gpib': 'gpib', 'serial': 'serial'},
            'serial_to_gpib_port': dict([('/dev/ttyUSB%d' % i, 'Serial port %d' % (i+1)) for i in range(3, 16)]),
            'volt_change_rate': dict([(i, str(i)) for i in [1,2,5,10]]),
            'curr_change_rate': dict([(i, str(i)) for i in [1,2,5,10]])
            }
        self.gpib = None
        self.serial = None
        self.getVoltage = self.getVoltageMeasured
        self.getCurrent = self.getCurrentMeasured
        self.setCommunications()
    
    def updateSettings(self, keyword, value):
        self.settings[keyword] = value
        if keyword in ['comm_mode', 'gpib_addr', 'serial_port', 'serial_to_gpib_port']:
            self.setCommunications()
    
    def setCommunications(self, comm_mode=None, serial_port=None, gpib_addr=None, serial_to_gpib_port=None):
        if comm_mode is None:
            comm_mode = self.settings['comm_mode']
        if serial_port is None:
            serial_port = self.settings['serial_port']
        if gpib_addr is None:
            gpib_addr = self.settings['gpib_addr']
        if serial_to_gpib_port is None:
            serial_to_gpib_port = self.settings['serial_to_gpib_port']
            
        if comm_mode.lower() == 'gpib':
            #self.gpib = rs232gpib.RS232GPIB(serial_port = serial_to_gpib_port)
            self.sendCommand = self.sendGPIBCommand
            self.receiveReply = self.receiveGPIBReply
        elif comm_mode.lower() == 'serial':
            #self.serial = serial.Serial(self.settings['serial_port'], 9600, parity='N', rtscts=False, xonxoff=False, timeout=1)
            self.sendCommand = self.writesendCommandSerial
            self.receiveReply  = self.receiveReplySerial
        else:
            return "not a valid comm_mode (serial or gpib)"
    
    def initSerial(self):
        self.serial = serial.Serial(self.settings['serial_port'], 9600, parity='N', rtscts=False, xonxoff=False, timeout=1)
        
    def initGPIB(self):
        self.gpib = rs232gpib.RS232GPIB(serial_port = self.settings['serial_to_gpib_port'])
    
    def sendSerialCommand(self, command = None, reply_expected = False):
        if self.serial is None:
            self.initSerial()
        if not command:
            return ''
        else:
            self.serial.write(command)
            self.serial.write(self.newline_str)
            self.serial.flush()
            
        if reply_expected:
            reply = self.receiveReply()
            return reply
            
    def receiveSerialReply(self):
        reply = self.serial.readline()
        return reply
        
    def sendGPIBCommand(self, command = None, reply_expected = False):
        if self.gpib is None:
            self.initGPIB()
        if command:
            self.gpib.sendCommand(self.settings['gpib_addr'], command)
            
        if reply_expected:
            reply = self.receiveReply()
            return reply
            
    def receiveGPIBReply(self):
        reply = self.gpib.receiveReply( self.settings['gpib_addr'])
        return reply
    
    def getVoltageSetpoint(self):
        if self.check_errors: self.err_state = self.sendCommand('SYST:ERR?', reply_expected = True)
        reply_str = self.sendCommand('SOUR:VOLT?', reply_expected = True)
        self.voltage_setp = float(reply_str)
        return self.voltage_setp
        
    def getCurrentSetpoint(self):
        if self.check_errors: self.err_state = self.sendCommand('SYST:ERR?', reply_expected = True)
        #self.err_state = self.sendCommand('SYST:ERR?', reply_expected = True)
        reply_str = self.sendCommand('SOUR:CURR?', reply_expected = True)
        self.current_setp = float(reply_str)
        return self.current_setp
        
    def getVoltageMeasured(self):
        if self.check_errors: self.err_state = self.sendCommand('SYST:ERR?', reply_expected = True)
        #self.err_state = self.sendCommand('SYST:ERR?', reply_expected = True)
        reply_str = self.sendCommand('MEAS:VOLT?', reply_expected = True)
        self.voltage_meas = float(reply_str)
        return self.voltage_meas
  
    def getCurrentMeasured(self):
        if self.check_errors: self.err_state = self.sendCommand('SYST:ERR?', reply_expected = True)
        #self.err_state = self.sendCommand('SYST:ERR?', reply_expected = True)
        reply_str = self.sendCommand('MEAS:CURR?', reply_expected = True)
        self.current_meas = float(reply_str)
        return self.current_meas   
        
    def setVoltage(self, voltage = 0.0):
        volts_now = self.getVoltageSetpoint()
        voltage_str = '%.3f' % voltage
        diff = abs(voltage - volts_now)
        t_change = diff / self.settings['volt_change_rate']
        t_change_str = '%.3f' % t_change
        if debug: print 'SOUR:VOLT:RAMP ' + voltage_str + ' ' + t_change_str
        if self.check_errors: self.err_state = self.sendCommand('SYST:ERR?', reply_expected = True)
        self.sendCommand('SOUR:VOLT:RAMP ' + voltage_str + ' ' + t_change_str, reply_expected = False)
        time.sleep(t_change)
        return
        
    def setCurrent(self, current = 0.0):
        curr_now = self.getCurrentSetpoint()
        curr_str = '%.3f' % current
        diff = abs(current - curr_now)
        t_change = diff / self.settings['curr_change_rate']
        t_change_str = '%.3f' % t_change
        if debug: print('SOUR:CURR:RAMP ' + curr_str + ' ' + t_change_str)
        if self.check_errors: self.err_state = self.sendCommand('SYST:ERR?', reply_expected = True)
        self.sendCommand('SOUR:CURR:RAMP ' + curr_str + ' ' + t_change_str, reply_expected = False)
        time.sleep(t_change)
        return
        
    def setOvervoltageLimit(self, overvoltage=10):
        if self.check_errors: self.err_state = self.sendCommand('SYST:ERR?', reply_expected = True)
        ov_str = 'SOUR:VOLT:PROT %.2f' % (overvoltage,)
        self.sendCommand(ov_str, reply_expected = False)
        return
        
    def getOvervoltageLimit(self):
        if self.check_errors: self.err_state = self.sendCommand('SYST:ERR?', reply_expected = True)
        reply_str = self.sendCommand('SOUR:VOLT:PROT?', reply_expected = True)
        self.overvoltage_limit = float(reply_str)
        return self.overvoltage_limit
        
      
