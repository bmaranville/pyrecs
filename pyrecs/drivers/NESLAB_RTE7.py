import struct, sys, serial
import binascii
DEBUG=False

from temperature_controller import TemperatureController

class NESLAB_BATH(TemperatureController):
    """
    driver for NESLAB RTE 7 bath used often at ANDR/MAGIK
    commands available:
        GetTemp()
        GetAuxTemp()
        GetSetpoint()
        SetTemp(temperature in deg. C)
        MakeLocal()
    """
    label = 'Neslab RTE7'
    commands = {
        'Read Acknowledge': 0x00,
        'Read Status': 0x09,
        'Read Internal Temperature': 0x20,
        'Read External Sensor': 0x21,
        'Set Setpoint': 0xF0,
        'Set On/Off Array': 0x81
    }
    
    def __init__(self, port = '/dev/ttyUSB2'):
        TemperatureController.__init__(self, port)
        """ the Temperature serial connection is on the second port at AND/R, which is /dev/ttyUSB1 """
        self.settings = {
            'sample_sensor': 'I',
            'control_sensor': 'I',
            'record': 'all'
            }
        self.sensors = {'I': "Internal", 'X':"External"}
        valid_record = self.sensors.copy()
        valid_record.update({'setpoint':"Setpoint", 'all':"Record all"})
        self.valid_settings = {
            'sample_sensor': self.sensors,
            'control_sensor': self.sensors,
            'record': valid_record,
            }
        #self.commands = {
        #    'Read Acknowledge': 0x00,
        #    'Read Status': 0x09,
        #    'Read Internal Temperature': 0x20,
        #    'Read External Sensor': 0x21,
        #    'Set Setpoint': 0xF0,
        #    'Set On/Off Array': 0x81
        #    }
        
        
    def _send_command(self, cmd_string):
        if self.serial is None:
            self.initSerial()
            
        self.serial.flushInput() # drain the pipes before issuing a command
        send_str = '\xca'
        send_str += cmd_string
        send_str += self._checksum(cmd_string)
        if DEBUG: print "send str: ", binascii.b2a_hex(send_str)
        self.serial.write(send_str)
        self.serial.flush()
           
    def _checksum(self, cmd_string):
        tot = 0
        for s in cmd_string:
            tot += struct.unpack_from('B', s, 0)[0]
        checksum = (tot & 255) ^ 255
        return struct.pack('B', checksum)
   
    def _get_temp_response(self):
        response = self._get_response()
        qualifier = response[0]
        if qualifier == '\x10' or qualifier == '\x11':
            mult = 0.1
        elif qualifier == '\x20' or qualifier == '\x21':
            mult = 0.01

        temperature = struct.unpack_from('>h', response[1:3], 0)[0] * mult
        return temperature
    
    def _get_response(self):
        header = self.serial.read(5)
        self.serial.flush()
        self.header = header
        if DEBUG: print "header: ", binascii.b2a_hex(header)
        # address is the first 3 bytes, '\xCA\x00\x01'
        command_code = header[3]
        bytes_coming = struct.unpack_from('B', header[4], 0)[0]
        reply = self.serial.read(bytes_coming)
        bath_checksum = self.serial.read(1)
        self_checksum = self._checksum(header[1:] + reply)
        if not bath_checksum == self_checksum:
            raise CommunicationsError('NESLAB_RTE7', 'Checksum')
            return
        else:
            return reply
    
    def getState(self, poll=True):
        state = {}
        for sensor in self.sensors:
            sensor_name = self.sensors[sensor]
            sensor_value = self.getTemp(sensor)
            state[sensor_name] = sensor_value
        state['Setpoint'] = self.getSetpoint() 
        return state
    
    def getTemp(self):
        cmd_string = '\x00\x01\x20\x00'
        self._send_command(cmd_string)
        temperature = self._get_temp_response()
        return temperature
    
    def setTemp(self, temp):
        mult = 0.1
        t_sent = struct.pack('>h', int(temp/mult))
        cmd_str = '\x00\x01\xF0\x02' + t_sent
        self._send_command(cmd_str)
        temperature = self._get_temp_response()
        return temperature
        
    def getSetpoint(self):
        cmd_string = '\x00\x01\x70\x00'
        self._send_command(cmd_string)
        temperature = self._get_temp_response()
        return temperature
    
    def getAuxTemp(self):
        cmd_string = '\x00\x01\x21\x00'
        self._send_command(cmd_string)
        temperature = self._get_temp_response()
        return temperature
        
    def makeLocal(self):
        cmd_string = '\x00\x01\x81\x08\x02\x02\x02\x02\x02\x02\x02\x00'
        self._send_command(cmd_string)
        self._get_response()
        return
        
class CommunicationsError(Exception):
    """ To be thrown when serial communications fail """
    def __init__(self, device_name, error_type):
        self.device_name = device_name
        self.error_type = error_type
        self.msg = self.error_type + " Error in device: " + device_name
        print self.msg
       
