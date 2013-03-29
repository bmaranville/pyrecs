import rs232gpib
from magnet_controller import MagnetController
DEBUG=True

class HP6632B(MagnetController):
    label = 'Hewlett-Packard 6632B'
    def __init__(self):
        MagnetController.__init__(self)
        """ the serial to gpib converter is on the fourth port at MAGIK, which is /dev/ttyUSB3 """
        self.serial_eol = '\r'
        self.settings = {
            'serial_port': '/dev/ttyUSB4',
            'gpib_addr': '5',
            'comm_mode': 'gpib',
            'serial_to_gpib_port': '/dev/ttyUSB3',
            }
        self.valid_settings = {
            'serial_port': dict([('/dev/ttyUSB%d' % i, 'Serial port %d' % (i+1)) for i in range(4, 16)]),
            'gpib_addr': dict([(str(i), '') for i in range(1, 32)]),
            'comm_mode': {'gpib': 'GPIB or HPIB', 'serial': 'RS232 connection'},
            'serial_to_gpib_port': dict([('/dev/ttyUSB%d' % i, 'Serial port %d' % (i+1)) for i in range(3, 16)]),
            }
	self.setCommunications()
    
    def updateSettings(self, keyword, value):
        self.settings[keyword] = value
        if keyword in ['comm_mode', 'gpib_addr', 'serial_port', 'serial_to_gpib_port']:
            self.setCommunications()
    
    def sendCommandSerial(self, command, reply_expected=False):
        self.serial.write(command + self.serial_eol)
        if reply_expected == True:
            return self.receiveReply()
            
    def receiveReplySerial(self):
        char_in = 'x'
        reply = ''
        while not char_in in [self.serial_eol, '']:
            # if '' is returned, it's a timeout...
            char_in = self.serial.read(1)
            reply += char_in
        return reply
    
    def sendCommandGPIB(self, command, reply_expected=False):
        addr = int(self.settings['gpib_addr'])
        self.gpib.sendCommand(addr, command)
        if reply_expected == True:
            return self.receiveReply()
        
    def receiveReplyGPIB(self):
        addr = int(self.settings['gpib_addr'])
        return self.gpib.receiveReply(addr)
    
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
            self.gpib = rs232gpib.RS232GPIB(serial_port = serial_to_gpib_port)
            self.sendCommand = self.sendCommandGPIB
            self.receiveReply = self.receiveReplyGPIB
        elif comm_mode.lower() == 'serial':
            self.serial = serial.Serial(self.settings['serial_port'], 9600, parity='N', rtscts=False, xonxoff=False, timeout=1)
            self.sendCommand = self.sendCommandSerial
            self.receiveReply  = self.receiveReplySerial
        else:
            return "not a valid comm_mode (serial or gpib)"
      
    def setCurrent(self, value):
        self.sendCommand('ISET %.4f' % value)
        
    def getCurrent(self):
        self.sendCommand('IOUT?')
        reply = self.receiveReply()
        return float(reply.split()[-1]) # if the supply returns more strings, take the last one
        
    def setVoltage(self, value):
        self.sendCommand('VSET %.4f' % value)
        
    def getVoltage(self):
        self.sendCommand('VOUT?')
        reply = self.receiveReply()
        return float(reply.split()[-1]) # if the supply returns more strings, take the last one 
