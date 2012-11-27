import struct, sys, serial
import binascii
DEBUG=False

from temperature_controller import TemperatureController

class Lakeshore340(TemperatureController):
    """ driver for serial connection to Lakeshore 340 Temperature Controller """
    def __init__(self, port = '/dev/ttyUSB2'):
        self.port = port
        self.serial = serial.Serial(port, 9600, parity='N', rtscts=False, xonxoff=False, timeout=1)
        self.setpoint = 0.0
        self.sample_sensor = sample_sensor
        self.control_sensor = control_sensor
        self.SetControlLoop(control_sensor)
    
    def sendCommand(self, command = None, reply_expected = False):
        if not command:
            return ''
        else:
            self.serial.write(command)
            self.serial.write(self.newline_str)
            self.serial.flush()
            
        if reply_expected:
            reply = self.receiveReply()
            return reply
            
    def receiveReply(self):
        reply = self.serial.readline(eol='\r')
        return reply
        
    def SetControlLoop(self, control_sensor = "A", units = 1, on_off = 1):
    	""" initializes loop 1 of temp controller, with correct control sensor etc. """
    	# units[1] = Kelvin
    	# units[2] = Celsius
    	# units[3] = Sensor units
    	self.sendCommand('CSET 1, %s, %d, %d' % (control_sensor, units, on_off))
        
    def SetTemp(self, new_setpoint):
        """ send a new temperature setpoint to the temperature controller """
        self.sendCommand('SETP 1,%7.3' % new_setpoint, reply_expected = False)
        return
        
    def GetTemp(self, sensor = None):
        if sensor is None: sensor = self.sample_sensor
        """ retrieve the temperature of the sample thermometer """
        reply_str = self.sendCommand('KRDG? %s' % sensor, reply_expected = True)
        temperature  = float(reply_str)
        return temperature
        
    def GetAuxTemp(self):
        return self.GetControlTemp()
        
    def GetSampleTemp(self):
        """ retrieve the temperature of the sample thermometer """
        return self.GetTemperature(sensor = self.sample_sensor)
        
    def GetControlTemp(self):
        """ retrieve the temperature of the control thermometer """
        return self.GetTemperature(sensor = self.control_sensor)


        
class CommunicationsError(Exception):
    """ To be thrown when serial communications fail """
    def __init__(self, device_name, error_type):
        self.device_name = device_name
        self.error_type = error_type
        self.msg = self.error_type + " Error in device: " + device_name
        print self.msg
       
