import serial
DEBUG = False
port = '/dev/ttyUSB1'
import numpy

class MAS345:
    """Talk to the Sinometer MAS-345 box"""
    def __init__(self, port=port):
        #self.serial = serial.Serial(port, 600, parity='N', bytesize=7, stopbits=2, rtscts=False, xonxoff=False, dsrdtr=False, timeout=2)
        self.serial = serial.Serial(port, 600, parity='N', bytesize=7, timeout=1)
        self.newline_str = '\r'
    
    def readline(self):
        line = ''
        reply = ''
        while not reply == self.newline_str:
            reply = self.serial.read(1)
            if DEBUG: print reply
            line += reply
        return line
        
    def sendCMD(self, text_cmd = ''):
        self.serial.setRTS(0)
        self.serial.setDTR(1)
        self.serial.flushInput() # get rid of lingering replies before new command
        if DEBUG: print 'writing command: ' + text_cmd
        self.serial.write(text_cmd + self.newline_str)
        if DEBUG: print 'flushing...'
        self.serial.flush()
        if DEBUG: print 'reading reply...'
        #reply = self.serial.readline(eol='\r')
        reply = self.readline()
        if DEBUG: print 'reply = ' + str(reply)
        self.reply = reply
        self.serial.flush()
        return reply.rstrip()
    
    def readValue(self):
        value_string = self.sendCMD()
        mode = value_string[:2]
        units = (value_string[-4:]).strip()
        if value_string[5:8] == 'O.L':
            value = numpy.inf
        else: 
            value = float(value_string[3:-4])
        return mode, value, units
        
class Photometer:
    ranges = { 1: {'string': '20uW', 'value': 20e-6}, \
               2: {'string': '200uW', 'value': 200e-6}, \
               3: {'string': '2mW', 'value': 2e-3}, \
               4: {'string': '20mW', 'value': 20e-3} }
            
    """ Read out the photometer using the Sinometer voltmeter """
    def __init__(self, range_setting=4, voltmeter_port=port):
        self.voltmeter = MAS345(voltmeter_port)
        self.setRangeIndex(range_setting)
        
    def setRangeIndex(self, range_index):
        if not range_index in self.ranges: return
        self._range_index = range_index
        
    def getRangeIndex(self):
        return self._range_index
    
    def getRangeString(self):
        return self.ranges.get(self._range_index, self.ranges[4])['string']
        
    def getRangeValue(self):
        return self.ranges.get(self._range_index, self.ranges[4])['value']
        
    def readValue(self):
        mode, value, units = self.voltmeter.readValue()
        return value * self.getRangeValue(), self.getRangeString()
        
        
    
