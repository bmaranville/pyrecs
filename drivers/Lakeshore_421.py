import rs232gpib
from magnet_controller import MagnetController
DEBUG=True

class Lakeshore421(MagnetController):
    label = 'Lakeshore 421 Gaussmeter'
    def __init__(self):
        MagnetController.__init__(self)
        """ the serial to gpib converter is on the fourth port at MAGIK, which is /dev/ttyUSB3 """
        self.serial_eol = '\n'
        self.settings = {
            'serial_port': '/dev/ttyUSB4'
            }
        self.valid_settings = {
            'serial_port': dict([('/dev/ttyUSB%d' % i, 'Serial port %d' % (i+1)) for i in range(4, 16)]),
            }
	self.setCommunications()
	self.field_multipliers = {'μ': 1e-6, 'm': 1e-3, '': 1.0, 'k': 1e3}

    
    def updateSettings(self, keyword, value):
        self.settings[keyword] = value
        if keyword in ['serial_port']:
            self.setCommunications()
    
    def sendCommand(self, command, reply_expected=False):
        self.serial.write(command + self.serial_eol)
        if reply_expected == True:
            return self.receiveReply()
            
    def receiveReply(self):
        reply = self.serial.readline()
        return reply
    
    
    def setCommunications(self, comm_mode=None, serial_port=None, gpib_addr=None, serial_to_gpib_port=None):
        if serial_port is None:
            serial_port = self.settings['serial_port']
        self.serial = serial.Serial(self.settings['serial_port'], 9600, parity='N', rtscts=False, xonxoff=False, timeout=1)    
        
    def getField(self):
        value = self.getFieldValue()
        multiplier = self.getFieldMulitplier()       
        
    def getFieldString(self):
        field = self.getField()
        units = self.getUnits()
        return '%.4f %s' % (field, units)
        
    def getUnits(self):
        self.sendCommand('UNIT?')
        return self.receiveReply()
        
    def setUnits(self, units):
        """ valid units are 'G' and 'T' for Gauss and Tesla """
        self.sendCommand('UNIT %s' % units)
        
    def getFieldValue(self):
        self.sendCommand('FIELD?')
        return float(self.receiveReply())
        
    def getFieldMultiplier(self):
        self.sendCommand('FIELDM?')
        m = self.receiveReply()
        return self.field_multpliers[m]
        
        
