import struct, sys, serial, time
from temperature_controller import TemperatureController
DEBUG = False
calibrations = {
    1: lambda T_raw: T_raw*0.97877 - 0.86433, 
    2: lambda T_raw: T_raw*0.97398 - 0.58107
}
    
class PetiteFleur(TemperatureController):
    """ driver for serial connection to Huber Petite Fleur temperature controller """
    label = 'Huber Petite Fleur'
    def __init__(self, port = '/dev/ttyUSB7'):
        TemperatureController.__init__(self, port)
        """ the Temperature serial connection is on the third port at MAGIK, which is /dev/ttyUSB2 """
        self.setpoint = 0.0
        self.wait_time = 0.0 # give the bath a moment to reply
        self.serial_eol = '\r\n'
        self.settings = {
            'sample_sensor': 2,
            'control_sensor': 0,
            'record': 'all',
            'control_loop': 0,
            'thermometer_calibration': 1, # applied to sample sensor
            'serial_port': '/dev/ttyUSB7'            
            }
        self.sensors = {0: "Bath temp", 2:"Process temp"}
        valid_record = self.sensors.copy()
        valid_record.update({'setpoint':"Setpoint", 'all':"Record all"})
        self.valid_settings = {
            'sample_sensor': self.sensors,
            'control_sensor': self.sensors,
            'record': valid_record,
            'control_loop': {0: "0", 1: "1", 2: "2"},
            'thermometer_calibration': {1: "T_raw*0.97877 - 0.86433", 2: "T_raw*0.97398 - 0.58107"},
            'serial_port': dict([('/dev/ttyUSB%d' % i, 'Serial port %d' % (i+1)) for i in range(4, 16)]),
            }
        self.port = self.settings['serial_port']
    
    def updateSettings(self, keyword, value):
        self.settings[keyword] = value
        if keyword == 'port':
            self.port = value
            if self.serial is not None:
                self.serial.port = self.port
    
    def sendCommand(self, command = None, reply_expected = False):
        if self.serial is None:
            self.initSerial()
        if command is None:
            return ''
        else:
            self.serial.write(command + self.serial_eol)
            #self.serial.write(self.serial_eol)
            #self.serial.flush()
            
        if reply_expected:
            time.sleep(self.wait_time)
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
                
    def setTemp(self, new_setpoint):        
        """ send a new temperature setpoint to the temperature controller """
        self.sendCommand('OUT_SP_%02d %7.3f' % (self.settings['control_loop'], new_setpoint), reply_expected = False)
        return
        
    def getTemp(self, sensor = None):
        if sensor is None: sensor = self.settings['sample_sensor']
        """ retrieve the temperature of the sample thermometer """
        if DEBUG: print 'IN_PV_%02d' % sensor
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
       
