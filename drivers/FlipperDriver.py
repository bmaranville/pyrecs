import rs232gpib
import numpy
DEBUG=True

class FlipperPS:
    """ class to control a flipper power supply.
    in our case, it is run through an rs232->gpib line """
    def __init__(self, gpib_addr = 1, gpib_controller = None):
        # we should be passed an object to read/write gpib, but...
        if gpib_controller == None:
            self.gpib = rs232gpib.RS232GPIB(serial_port = '/dev/ttyUSB3')
        else:
            self.gpib = gpib_controller
        self.gpib_addr = gpib_addr
    
    def sendCommand(self, cmd):
        self.gpib.sendCommand(self.gpib_addr, cmd)
        
    def receiveReply(self):
        return self.gpib.receiveReply(self.gpib_addr)
        
    def setCurrent(self, value):
        self.sendCommand('ISET %.4f' % value)
        
    def getCurrent(self):
        self.sendCommand('IOUT?')
        reply = self.receiveReply()
        return numpy.float32(reply.split()[-1]) # if the supply returns more strings, take the last one
        
    def setVoltage(self, value):
        self.sendCommand('VSET %.4f' % value)
        
    def getVoltage(self):
        self.sendCommand('VOUT?')
        reply = self.receiveReply()
        return numpy.float32(reply.split()[-1]) # if the supply returns more strings, take the last one
