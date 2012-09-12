import serial
DEBUG = False

class MAS345:
    """Talk to the Sinometer MAS-345 box"""
    def __init__(self, port):
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
    
    
