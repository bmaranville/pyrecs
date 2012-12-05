import serial

DEBUG = False
SER_PORT = '/dev/ttyUSB3'

#define UNL     0x3F
#define UNT     0x5F
#define GET     0x08
#define MTA(x) (0x40 + x)
#define MLA(x) (0x20 + x)

class RS232GPIB:
    """" driver for talking to rs232->GPIB bridge (National Instruments) 
    designed for device-as-GPIB-controller mode (rs232 from computer, GPIB to instruments)"""
    
    def __init__(self, serial_port = SER_PORT):
        self.serial = serial.Serial(serial_port, 9600, parity='N', rtscts=False, xonxoff=False, timeout=2)
        self.newline_str = '\r'
        self.session = ''
        self._isController = False
    
    def setAsController(self):
        self.serial.write('sic\r')
        self.serial.flush()
    
    def sendReset(self):
        self.serial.write('cmd\n?\r')
        if DEBUG: self.session += 'cmd\n?\r'
        self.serial.flush()        
        
    def setListener(self, gpib_addr):
        listen_chr = 32 + int(gpib_addr)
        self.serial.write('cmd\n'+chr(listen_chr)+'\r')
        if DEBUG: self.session += 'cmd\n'+chr(listen_chr)+'\r'
        self.serial.flush()
        
    def setTalker(self, gpib_addr):
        talker_chr = 64 + int(gpib_addr)
        self.serial.write('cmd\n'+chr(talker_chr)+'\r')
        if DEBUG: self.session += 'cmd\n'+chr(talker_chr)+'\r'
        self.serial.flush()
        
    def sendCommand(self, gpib_addr, text_cmd):
        if not self._isController:
            self.setAsController()
            self._isController = True
        #self.sendReset()
        #self.setListener(gpib_addr)
        #self.setTalker(0) # self
        self.serial.write('wr '+str(gpib_addr)+'\n;'+text_cmd+';\r')
        if DEBUG: self.session += 'wr '+str(gpib_addr)+'\n;'+text_cmd+';\r'
        self.serial.flush()
        #self.sendReset()
        
    def receiveReply(self, gpib_addr):
        #self.setTalker(gpib_addr)
        #self.setListener(0) # self
        self.serial.write('rd #70 '+str(gpib_addr)+'\r')
        if DEBUG: self.session += 'rd #256 '+str(gpib_addr)+'\r'
        self.serial.flush()
        result = self.serial.readline()
        checksum_maybe = self.serial.readline()
        return result
        
class RS232GPIB_new(object):
    """ driver for talking to rs232->GPIB bridge (National Instruments) 
    designed for device-as-GPIB-controller mode (rs232 from computer, GPIB to instruments)"""
    # a lot simpler?
    def __init__(self, serial_port = SER_PORT):
        self.serial = serial.Serial(serial_port, 9600, parity='N', rtscts=False, xonxoff=False, timeout=2)
        self.newline_str = '\r'
        self.session = ''
        self._isController = False
    
    def sendCommand(self, gpib_addr, text_cmd):
        if not self._isController:
            self.setAsController()
            self._isController = True
        self.serial.write('wr '+str(gpib_addr)+'\n;'+text_cmd+';\r')
        if DEBUG: self.session += 'wr '+str(gpib_addr)+'\n;'+text_cmd+';\r'
        self.serial.flush()
    
    def receiveReply(self, gpib_addr):
        self.serial.write('rd #70 '+str(gpib_addr)+'\r')
        if DEBUG: self.session += 'rd #256 '+str(gpib_addr)+'\n'
        self.serial.flush()
        result = self.serial.readline()
        checksum_maybe = self.serial.readline()
        return result    

sample_session = """
sic^Mcmd
?^Mcmd
!^Mcmd
@^Mwr 1
;VSET 15.000;^Mcmd
?^Mcmd
?^Mcmd
"^Mcmd
@^Mwr 2
;ISET  0.0000;^Mcmd
?^Mcmd
?^Mcmd
"^Mcmd
@^Mwr 2
;IOUT?;^Mcmd
?^Mcmd
B^Mcmd
 ^Mrd #70 2^Mcmd
?^Mcmd
"^Mcmd
@^Mwr 2
;IOUT?;^Mcmd
?^Mcmd
"""
