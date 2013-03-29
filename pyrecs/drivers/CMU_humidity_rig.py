import struct, sys, serial
from temperature_controller import TemperatureController

calibrations = {
    1: lambda T_raw: T_raw*0.97877 - 0.86433, 
    2: lambda T_raw: T_raw*0.97398 - 0.58107
}

"""
Converting relative humidity to voltage and vice-versa:
The voltage setpoint is a function of the set temperature (T_set), humidity setpoint (Rh_set) and a voltage (V_ps) value on the controller. 
The humidity is a function of the calibrated sample temperature (T_cal), the voltage sensor reading (V_read) and V_ps. 

V_ps will be a fixed value and I will get it to you once we have it. == 5.06

Convert from T_set and Rh_set to V_set -- V_set = ((0.00721 - 2.371089*10^-5*T_set)*Rh_set + 0.13471)*V_ps
Convert from V_read and T_cal to Rh_read -- Rh_read = ((V_read/V_ps) - 0.13471)/(0.00721 - 2.371089*10^-5*T_cal)
"""

def getVSet(T_set, Rh_set, V_ps=5.06):
    return ((0.00721 - 2.371089e-5*T_set)*Rh_set + 0.13471)*V_ps
    
def getRH(V_read, T_cal, V_ps=5.06):
    return ((V_read/V_ps) - 0.13471)/(0.00721 - 2.371089e-5*T_cal)

V_PS = 5.06 # this is the voltage to the power pin on the humidity sensor

class Lakeshore340Humidity(TemperatureController):
    """ driver for serial connection to Lakeshore 340 Temperature Controller """
    label = 'Lakeshore 331/340 (Humidity)'
    def __init__(self, port = '/dev/ttyUSB6'):
        TemperatureController.__init__(self, port)
        """ the Temperature serial connection is on the third port at MAGIK, which is /dev/ttyUSB2 """
        self.setpoint = 0.0
        self.serial_eol = '\n'
        self.settings = {
            'sample_sensor': 'B',
            'control_sensor': 'A',
            'record': 'all',
            'units': 3,
            'control_loop': 1,
            'thermometer_calibration': 1, # applied to sample sensor
            'serial_port': '/dev/ttyUSB6'
            }
        self.sensors = {'A': "Sensor A", 'B':"Sensor B"}
        valid_record = self.sensors.copy()
        valid_record.update({'setpoint':"Setpoint", 'RH': 'RH', 'T_raw': 'T_raw', 'T_cal': 'T_cal', 'all':"Record all"})
        self.valid_settings = {
            'sample_sensor': self.sensors,
            'control_sensor': self.sensors,
            'record': valid_record,
            'units': {1: "Kelvin", 2: "Celsius", 3: "Sensor units"},
            'control_loop': {1: "1", 2: "2"},
            'thermometer_calibration': {1: "T_raw*0.97877 - 0.86433", 2: "T_raw*0.97398 - 0.58107"},
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
        state.update(self.getRH())
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
    
    def setAnalog(self, new_voltage, bipolar_enable=1):
        """ set the analog output 2 of Lakeshore controller """
        manual_value = new_voltage * 10.0 # output is specified as percentage of 10V
        mode = 2 # manual setting of voltage
        self.sendCommand('ANALOG 2, %d, %d, , , , , %.3f' % (bipolar_enable, mode, manual_value), reply_expected = False)
        return
        
    def getAnalog(self):
        manual_value = self.sendCommand('AOUT? 2', reply_expected=True)
        return float(manual_value) / 10.0 # again, it is returned as a % of 10V
    
    def getTemp(self, sensor = None, units=None):
        if sensor is None: sensor = self.settings['sample_sensor']
        if units is None: units = self.settings['units']
        """ retrieve the temperature of the sample thermometer """
        read_str = {1: "K", 2: "C", 3: "S"}
        reply_str = self.sendCommand('%sRDG? %s' % (read_str[units], sensor), reply_expected = True)
        temperature  = float(reply_str)
        return temperature 
        
    def getAuxTemp(self):
        return self.getControlTemp()
    
    def getSetpoint(self):
        reply_str = self.sendCommand('SETP? %d' % self.settings['control_loop'], reply_expected = True)
        temperature  = float(reply_str)
        return temperature
    
    def getCalibratedTemp(self, sensor=None):
        """ retrieve the temperature of the sample thermometer """
        T_raw =  self.getTemp(sensor = sensor)
        calibration_function = calibrations[self.settings['thermometer_calibration']]
        T_sensor = calibration_function(T_raw)
        return T_sensor
        
    def getSampleTemp(self):
        """ retrieve the temperature of the sample thermometer """
        return self.getTemp(sensor = self.settings['sample_sensor'])
        
    def getControlTemp(self):
        """ retrieve the temperature of the control thermometer """
        return self.getTemp(sensor = self.settings['control_sensor'])
        
    def getRH(self, print_vars=True):
        V_read = self.getTemp(sensor='A', units=3)
        T_raw = self.getTemp(sensor='B', units=2)
        calibration_function = calibrations[self.settings['thermometer_calibration']]
        T_cal = calibration_function(T_raw)
        if print_vars == True: print "V_read, T_raw, T_cal:", V_read, T_raw, T_cal
        RH = ((V_read/V_PS) - 0.13471)/(0.00721 - 2.371089e-5*T_cal)
        return {'RH': RH, 'V_read': V_read, 'T_raw': T_raw, 'T_cal': T_cal} 
        
    def setRH(self, Rh_set, T_set):
        V_set = ((0.00721 - 2.371089e-5*T_set)*Rh_set + 0.13471)*V_PS
        self.RH_setpoint = Rh_set
        self.setTemp(V_set)
        
                
class CommunicationsError(Exception):
    """ To be thrown when serial communications fail """
    def __init__(self, device_name, error_type):
        self.device_name = device_name
        self.error_type = error_type
        self.msg = self.error_type + " Error in device: " + device_name
        print self.msg
       
