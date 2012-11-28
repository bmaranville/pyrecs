import struct, sys, serial
import binascii
DEBUG=False

from temperature_controller import TemperatureController

class Lakeshore340(TemperatureController):
    """ driver for serial connection to Lakeshore 340 Temperature Controller """
    label = 'Lakeshore 331/340'
    def __init__(self, port = '/dev/ttyUSB2'):
        TemperatureController.__init__(self, port)
        """ the Temperature serial connection is on the third port at MAGIK, which is /dev/ttyUSB2 """
        self.setpoint = 0.0
        self.settings = {
            'sample_sensor': 'A',
            'control_sensor': 'A',
            'record': 'both'
            'units': 1,
            }
        sensors = {'A': "Sensor A", 'B':"Sensor B"}
        self.valid_settings = {
            'sample_sensor': sensors,
            'control_sensor': sensors,
            'record': {'setpoint':"Control setpoint", 'all':"Record all 3"}.update(sensors),
            'units': {1: "Kelvin", 2: "Celsius", 3: "Sensor units"}
            }
        self.SetControlLoop(self.settings['control_sensor'])
    
    def updateSettings(self, keyword, value):
        self.settings[keyword] = value
        if keyword == 'control_sensor' or keyword == 'units':
            self.SetControlLoop()
    
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
        
    def setControlLoop(self, on_off = 1):
    	""" initializes loop 1 of temp controller, with correct control sensor etc. """
    	# units[1] = Kelvin
    	# units[2] = Celsius
    	# units[3] = Sensor units
    	settings = self.settings
    	self.sendCommand('CSET 1, %s, %d, %d' % (settings['control_sensor'], settings['units'], on_off))
        
    def setTemp(self, new_setpoint):
        
        """ send a new temperature setpoint to the temperature controller """
        self.sendCommand('SETP 1,%7.3' % new_setpoint, reply_expected = False)
        return
        
    def getTemp(self, sensor = None):
        if sensor is None: sensor = self.settings['sample_sensor']
        """ retrieve the temperature of the sample thermometer """
        reply_str = self.sendCommand('KRDG? %s' % sensor, reply_expected = True)
        temperature  = float(reply_str)
        return temperature
        
    def getAuxTemp(self):
        return self.GetControlTemp()
        
    def getSampleTemp(self):
        """ retrieve the temperature of the sample thermometer """
        return self.GetTemperature(sensor = self.sample_sensor)
        
    def getControlTemp(self):
        """ retrieve the temperature of the control thermometer """
        return self.GetTemperature(sensor = self.control_sensor)


        
class CommunicationsError(Exception):
    """ To be thrown when serial communications fail """
    def __init__(self, device_name, error_type):
        self.device_name = device_name
        self.error_type = error_type
        self.msg = self.error_type + " Error in device: " + device_name
        print self.msg
       
