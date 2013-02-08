import struct, sys, serial
from temperature_controller import TemperatureController
    
calibrations = {
    1: lambda T_raw: T_raw*0.97877 - 0.86433, 
    2: lambda T_raw: T_raw*0.97398 - 0.58107
}
    
class PetiteFleur(TemperatureController):
    """ driver for serial connection to Huber Petite Fleur temperature controller """
    label = 'Huber Petite Fleur'
    def __init__(self, port = '/dev/ttyUSB2'):
        TemperatureController.__init__(self, port)
        """ the Temperature serial connection is on the third port at MAGIK, which is /dev/ttyUSB2 """
        self.setpoint = 0.0
        self.serial_eol = '\n'
        self.settings = {
            'sample_sensor': 2,
            'control_sensor': 0,
            'record': 'all',
            'control_loop': 0,
            'thermometer_calibration': 1 # applied to sample sensor
            }
        sensors = {0: "Bath temp", 1:"Sensor 1", 2:"Process temp"}
        self.valid_settings = {
            'sample_sensor': sensors,
            'control_sensor': sensors,
            'record': {'setpoint':"Control setpoint", 'all':"Record all 3"}.update(sensors),
            'control_loop': {0: "0", 1: "1", 2: "2"},
            'thermometer_calibration': {1: "T_raw*0.97877 - 0.86433", 2: "T_raw*0.97398 - 0.58107"}
            }
    
    def updateSettings(self, keyword, value):
        self.settings[keyword] = value
        #if keyword in ['control_sensor', 'units', 'control_loop']:
        #    self.SetControlLoop()
    
    def sendCommand(self, command = None, reply_expected = False):
        if not command:
            return ''
        else:
            self.serial.write(command)
            self.serial.write(self.serial_eol)
            self.serial.flush()
            
        if reply_expected:
            reply = self.receiveReply()
            return reply
            
    def receiveReply(self):
        reply = self.serial.readline().rstrip('\r\n')
        return reply
        
    def setTemp(self, new_setpoint):        
        """ send a new temperature setpoint to the temperature controller """
        self.sendCommand('OUT_SP_%02d %7.3f' % (self.settings['control_loop'], new_setpoint), reply_expected = False)
        return
        
    def getTemp(self, sensor = None):
        if sensor is None: sensor = self.settings['sample_sensor']
        """ retrieve the temperature of the sample thermometer """
        reply_str = self.sendCommand('IN_PV_%02d' % sensor, reply_expected = True)
        temperature  = float(reply_str)
        return temperature
        
    def getAuxTemp(self):
        return self.getControlTemp()
    
    def getSetpoint(self):
        reply_str = self.sendCommand('IN_SP_%02d' % self.settings['control_loop'], reply_expected = True)
        temperature  = float(reply_str)
        return temperature
        
    def getSampleTemp(self):
        """ retrieve the temperature of the sample thermometer """
        T_raw = self.getTemp(sensor = self.settings['sample_sensor'])
        calibration_function = calibrations[self.settings['thermometer_calibration']]
        T_sensor = calibration_function(T_raw)
        return T_sensor
        
    def getControlTemp(self):
        """ retrieve the temperature of the control thermometer """
        return self.getTemp(sensor = self.settings['control_sensor'])
        
    def bathStart(self):
        """ send the start command for the bath """
        self.sendCommand('START', reply_expected = False)
        
    def bathStop(self):
        """ send the start command for the bath """
        self.sendCommand('STOP', reply_expected = False)
    
    
        
class CommunicationsError(Exception):
    """ To be thrown when serial communications fail """
    def __init__(self, device_name, error_type):
        self.device_name = device_name
        self.error_type = error_type
        self.msg = self.error_type + " Error in device: " + device_name
        print self.msg
       