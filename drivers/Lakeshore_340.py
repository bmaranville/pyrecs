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
        self.sensors = {'A': "Sensor A", 'B':"Sensor B"}
        valid_record = self.sensors.copy()
        valid_record.update({'setpoint':"Setpoint", 'all':"Record all"})
        self.valid_settings = {
            'sample_sensor': self.sensors,
            'control_sensor': self.sensors,
            'record': valid_record,
            'units': {1: "Kelvin", 2: "Celsius", 3: "Sensor units"},
            'control_loop': {1: "1", 2: "2"},
            'serial_port': dict([('/dev/ttyUSB%d' % i, 'Serial port %d' % (i+1)) for i in range(4, 16)]),
            }
    
    def updateSettings(self, keyword, value):
        self.settings[keyword] = value
        if keyword in ['control_sensor', 'units', 'control_loop']:
            self.setControlLoop()
    
    def initSerial(self):
        self.serial = serial.Serial(self.port, 9600, parity='N', rtscts=False, xonxoff=False, timeout=1)
        self.setControlLoop()
            
    def sendCommand(self, command = None, reply_expected = False):
        if self.serial is None:
            self.initSerial()
            
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
        state = {}
        for sensor in self.sensors:
            sensor_name = self.sensors[sensor]
            sensor_value = self.getTemp(sensor)
            state[sensor_name] = sensor_value
        state['Setpoint'] = self.getSetpoint() 
        return state
        
    def setControlLoop(self, on_off = 1):
    	""" initializes loop of temp controller, with correct control sensor etc. """
    	self.port = self.settings['serial_port']
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
        read_str = {1: "K", 2: "C", 3: "S"}
        reply_str = self.sendCommand('%sRDG? %s' % (read_str[self.settings['units']], sensor), reply_expected = True)
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
       
