import wx
import serial
from numpy import abs
import time
import rs232GPIB
GPIB_ADDR = 7 # this is the current address for Sorensen at AND/R

class Sorensen:
    """Class to read and write Voltage and Current to Sorensen DCS30"""
    def __init__(self, port = '/dev/ttyUSB3', serial_mode = True, gpib_addr = GPIB_ADDR):
        if serial_mode:
            self.serial = serial.serial_for_url(port, 19200, parity='N', rtscts=False, xonxoff=False, timeout=1)
            self.newline_str = '\r'
            self.sendCommand = self.sendSerialCommand
            self.receiveReply = self.receiveSerialReply
        else: # gpib mode
            self.gpib = rs232GPIB.rs232GPIB()
            self.gpib_addr = gpib_addr
            self.sendCommand = self.sendGPIBCommand
            self.receiveReply = self.receiveGPIBReply
        self.read_timeout = 1.0
        self.volt_change_rate = 2.0 #volts/second
        self.curr_change_rate = 1.0 #amps/second
        self.voltage = None
        self.current = None

    def sendSerialCommand(self, command = None, reply_expected = False):
        if not command:
            return ''
        else:
            self.serial.write(command)
            self.serial.write(self.newline_str)
            self.serial.flush()
            
        if reply_expected:
            reply = self.receiveReply()
            return reply
            
    def receiveSerialReply(self):
        reply = self.serial.readline(eol='\r')
        return reply
        
    def sendGPIBCommand(self, command = None, reply_expected = False):
        if command:
            self.gpib.sendCommand(self.gpib_addr, command)
            
        if reply_expected:
            reply = self.receiveReply()
            return reply
            
    def receiveGPIBReply(self):
        reply = self.gpib.receiveReply(self.gpib_addr)
        return reply
        
    def receiveSerialReply_old(self):
        begin_read_time = time.time()
        endofline = False
        data = ''
        while (time.time() - begin_read_time) < self.read_timeout and endofline == False:
            newdata = self.serial.read(1)
            if newdata == self.newline_str:
                endofline = True
            else: 
                data += newdata
        return data

    def sendCommandAuto(self, command = None):
        if not command:
            return
        else:
            if command[-1] == '?':
                return self.sendCommand(command, reply_expected = True)
            else:
                self.sendCommand(command, reply_expected = False)

    def GetVoltageSetpoint(self):
        self.err_state = self.sendCommand('SYST:ERR?', reply_expected = True)
        reply_str = self.sendCommand('SOUR:VOLT?', reply_expected = True)
        self.voltage_setp = float(reply_str)
        return self.voltage_setp
        
    def GetCurrentSetpoint(self):
        self.err_state = self.sendCommand('SYST:ERR?', reply_expected = True)
        reply_str = self.sendCommand('SOUR:CURR?', reply_expected = True)
        self.current_setp = float(reply_str)
        return self.current_setp
        
    def GetVoltageMeasured(self):
        self.err_state = self.sendCommand('SYST:ERR?', reply_expected = True)
        reply_str = self.sendCommand('MEAS:VOLT?', reply_expected = True)
        self.voltage_meas = float(reply_str)
        return self.voltage_meas
  
    def GetCurrentMeasured(self):
        self.err_state = self.sendCommand('SYST:ERR?', reply_expected = True)
        reply_str = self.sendCommand('MEAS:CURR?', reply_expected = True)
        self.current_meas = float(reply_str)
        return self.current_meas   
        
    def SetVoltage(self, voltage = 0.0):
        volts_now = self.GetVoltageSetpoint()
        voltage_str = '%.3f' % voltage
        diff = abs(voltage - volts_now)
        t_change = diff / self.volt_change_rate
        t_change_str = '%.3f' % t_change
        print 'SOUR:VOLT:RAMP ' + voltage_str + ' ' + t_change_str
        self.err_state = self.sendCommand('SYST:ERR?', reply_expected = True)
        self.sendCommand('SOUR:VOLT:RAMP ' + voltage_str + ' ' + t_change_str, reply_expected = False)
        time.sleep(t_change)
        return
        
    def SetCurrent(self, current = 0.0):
        curr_now = self.GetCurrentSetpoint()
        curr_str = '%.3f' % current
        diff = abs(current - curr_now)
        t_change = diff / self.curr_change_rate
        t_change_str = '%.3f' % t_change
        print('SOUR:CURR:RAMP ' + curr_str + ' ' + t_change_str)
        self.err_state = self.sendCommand('SYST:ERR?', reply_expected = True)
        self.sendCommand('SOUR:CURR:RAMP ' + curr_str + ' ' + t_change_str, reply_expected = False)
        time.sleep(t_change)
        return
        
    def MakeLocal(self):
        self.err_state = self.sendCommand('SYST:ERR?', reply_expected = True)
        self.sendCommand('SYST:LOCAL ON', reply_expected = False)
        
