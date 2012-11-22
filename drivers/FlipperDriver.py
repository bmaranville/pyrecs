import rs232gpib
import numpy
DEBUG=True

class FlipperPS:
    """ class to control a flipper power supply.
    in our case, it is run through an rs232->gpib line """
    def __init__(self, gpib_addr = 1, gpib_controller = None):
        # we should be passed an object to read/write gpib, but...
        if gpib_controller == None:
            self.gpib = rs232gpib.RS232GPIB(serial_port = '/dev/ttyUSB2')
        else:
            self.gpib = gpib_controller
        self.gpib_addr = gpib_addr
        
    def SetCurrent(self, value):
        self.gpib.sendCommand(self.gpib_addr, 'ISET %.4f' % value)
        
    def GetCurrent(self):
        self.gpib.sendCommand(self.gpib_addr, 'IOUT?')
        reply = self.gpib.receiveReply(self.gpib_addr)
        return numpy.float32(reply.split()[-1]) # if the supply returns more strings, take the last one
        
    def SetVoltage(self, value):
        self.gpib.sendCommand(self.gpib_addr, 'VSET %.4f' % value)
        
    def GetVoltage(self):
        self.gpib.sendCommand(self.gpib_addr, 'VOUT?')
        reply = self.gpib.receiveReply(self.gpib_addr)
        return numpy.float32(reply.split()[-1]) # if the supply returns more strings, take the last one
