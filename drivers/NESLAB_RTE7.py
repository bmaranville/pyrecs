import struct, sys, serial

class NESLAB_BATH:
    """
    driver for NESLAB RTE 7 bath used often at ANDR/MAGIK
    commands available:
        GetTemp()
        GetAuxTemp()
        GetSetpoint()
        SetTemp(temperature in deg. C)
        MakeLocal()
    """
    def __init__(self, port = '/dev/ttyUSB1'):
        """ the Temperature serial connection is on the second port at AND/R, which is /dev/ttyUSB1 """
        self.port = port
        self.serial = serial.serial_for_url(port, 9600, parity='N', rtscts=False, xonxoff=False, timeout=1)
        self.read_timeout = 1.0
        self.commands = {
            'Read Acknowledge': 0x00,
            'Read Status': 0x09,
            'Read Internal Temperature': 0x20,
            'Read External Sensor': 0x21,
            'Set Setpoint': 0xF0,
            'Set On/Off Array': 0x81
            }
        
        
    def _send_command(self, cmd_string):
        self.serial.flushInput() # drain the pipes before issuing a command
        send_str = '\xca'
        send_str += cmd_string
        send_str += self._checksum(cmd_string)
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
    
    def GetTemp(self):
        cmd_string = '\x00\x01\x20\x00'
        self._send_command(cmd_string)
        temperature = self._get_temp_response()
        return temperature
    
    def SetTemp(self, temp):
        mult = 0.1
        t_sent = struct.pack('>h', int(temp/mult))
        cmd_str = '\x00\x01\xF0\x02' + t_sent
        self._send_command(cmd_str)
        temperature = self._get_temp_response()
        return temperature
        
    def GetSetpoint(self):
        cmd_string = '\x00\x01\x70\x00'
        self._send_command(cmd_string)
        temperature = self._get_temp_response()
        return temperature
    
    def GetAuxTemp(self):
        cmd_string = '\x00\x01\x21\x00'
        self._send_command(cmd_string)
        temperature = self._get_temp_response()
        return temperature
        
    def MakeLocal(self):
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
       
