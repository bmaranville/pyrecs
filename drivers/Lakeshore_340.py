import struct, sys, serial
from temperature_controller import TemperatureController

class Lakeshore340(TemperatureController):
    """ driver for serial connection to Lakeshore 340 Temperature Controller """
    label = 'Lakeshore 331/340'
    def __init__(self, port = '/dev/ttyUSB6'):
        TemperatureController.__init__(self, port)
        """ the Temperature serial connection is on the third port at MAGIK, which is /dev/ttyUSB2 """
        self.setpoint = 0.0
        self.serial_eol = '\n'
        self.settings = {
            'sample_sensor': 'A',
            'control_sensor': 'A',
            'record': 'all',
            'units': 1,
            'control_loop': 1,
            'serial_port': '/dev/ttyUSB6'
            }
        sensors = {'A': "Sensor A", 'B':"Sensor B"}
        self.valid_settings = {
            'sample_sensor': sensors,
            'control_sensor': sensors,
            'record': {'setpoint':"Control setpoint", 'all':"Record all 3"}.update(sensors),
            'units': {1: "Kelvin", 2: "Celsius", 3: "Sensor units"},
            'control_loop': {1: "1", 2: "2"},
            'serial_port': dict([('/dev/ttyUSB%d' % i, 'Serial port %d' % (i+1)) for i in range(4, 16)]),
            }
        self.setControlLoop()
    
    def updateSettings(self, keyword, value):
        self.settings[keyword] = value
        if keyword in ['control_sensor', 'units', 'control_loop']:
            self.SetControlLoop()
            
    def sendCommand(self, command = None, reply_expected = False):
        if not command:
            return ''
        else:
            self.serial.write(command)
            self.serial.write(self.serial_eol)
            #self.serial.flush()
            
        if reply_expected:
            reply = self.receiveReply()
            return reply
            
    def receiveReply(self):
        reply = self.serial.readline().rstrip('\r\n')
        return reply
    
    def getState(self, poll=True):
        state = {
            'settings': self.settings.copy(),
            'sample_temp': self.getSampleTemp(),
            'control_temp': self.getControlTemp(),
            'setpoint': self.getSetpoint()
        }
        return state
        
    def setControlLoop(self, on_off = 1):
    	""" initializes loop of temp controller, with correct control sensor etc. """
    	self.serial.port = self.settings['serial_port']
    	# units[1] = Kelvin
    	# units[2] = Celsius
    	# units[3] = Sensor units
    	settings = self.settings
    	print (settings['control_loop'], settings['control_sensor'], settings['units'], on_off)
    	self.sendCommand('CSET %d, %s, %d, %d' % (settings['control_loop'], settings['control_sensor'], settings['units'], on_off))
        
    def setTemp(self, new_setpoint):        
        """ send a new temperature setpoint to the temperature controller """
        self.sendCommand('SETP %d,%7.3f' % (self.settings['control_loop'], new_setpoint), reply_expected = False)
        return
        
    def getTemp(self, sensor = None):
        if sensor is None: sensor = self.settings['sample_sensor']
        """ retrieve the temperature of the sample thermometer """
        reply_str = self.sendCommand('SRDG? %s' % sensor, reply_expected = True)
        temperature  = float(reply_str)
        return temperature
        
    def getAuxTemp(self):
        return self.getControlTemp()
    
    def getSetpoint(self):
        reply_str = self.sendCommand('SETP? %d' % self.settings['control_loop'], reply_expected = True)
        temperature  = float(reply_str)
        return temperature
        
    def getSampleTemp(self):
        """ retrieve the temperature of the sample thermometer """
        return self.getTemp(sensor = self.settings['sample_sensor'])
        
    def getControlTemp(self):
        """ retrieve the temperature of the control thermometer """
        return self.getTemp(sensor = self.settings['control_sensor'])


        
class CommunicationsError(Exception):
    """ To be thrown when serial communications fail """
    def __init__(self, device_name, error_type):
        self.device_name = device_name
        self.error_type = error_type
        self.msg = self.error_type + " Error in device: " + device_name
        print self.msg
       
