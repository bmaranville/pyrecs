import wx
import serial
import time
import rs232GPIB

ADDR = '/dev/ttyUSB3'

class Lakeshore_340_Temp_Controller(Serial_Instrument):
    """ driver for serial connection to Lakeshore 340 Temperature Controller """
    def __init__(self, port = '/dev/ttyUSB3', serial_mode = True, gpib_addr = GPIB_ADDR, sample_sensor = "A", control_sensor = "B"):
        Serial_Instrument.__init__(self, port = port, serial_mode = serial_mode, gpib_addr = gpib_addr, baudrate = 9600, parity='N', bytesize=7)
        self.setpoint = 0.0
        self.sample_sensor = sample_sensor
        self.control_sensor = control_sensor
        self.SetControlLoop(control_sensor)
        
    def SetControlLoop(self, control_sensor = "A", units = 1, on_off = 1):
    	""" initializes loop 1 of temp controller, with correct control sensor etc. """
    	# units[1] = Kelvin
    	# units[2] = Celsius
    	# units[3] = Sensor units
    	self.sendCommand('CSET 1, %s, %d, %d' % (control_sensor, units, on_off))
        
    def SetTemperature(self, new_setpoint):
        """ send a new temperature setpoint to the temperature controller """
        self.sendCommand('SETP 1,%7.3' % new_setpoint, reply_expected = False)
        return
        
    def GetTemperature(self, sensor = "A"):
        """ retrieve the temperature of the sample thermometer """
        reply_str = self.sendCommand('KRDG? %s' % sensor, reply_expected = True)
        temperature  = float(reply_str)
        return temperature   
        
    def GetSampleTemp(self):
        """ retrieve the temperature of the sample thermometer """
        return self.GetTemperature(sensor = self.sample_sensor)
        
    def GetControlTemp(self):
        """ retrieve the temperature of the control thermometer """
        return self.GetTemperature(sensor = self.control_sensor)
       

class Serial_Instrument:
    """ generic class for driver talking to instrument connected via RS232 or
    RS232->GPIB bridge """
    def __init__(self, port = '/dev/ttyUSB3', serial_mode = True, gpib_addr = GPIB_ADDR, baudrate=19200, **kwargs):
        if serial_mode:
            self.serial = serial.serial_for_url(port=port, baudrate=baudrate, parity='N', rtscts=False, xonxoff=False, timeout=1, **kwargs)
            self.newline_str = '\r'
            self.sendCommand = self.sendSerialCommand
            self.receiveReply = self.receiveSerialReply
        else: # gpib mode
            self.gpib = rs232GPIB.rs232GPIB()
            self.gpib_addr = gpib_addr
            self.sendCommand = self.sendGPIBCommand
            self.receiveReply = self.receiveGPIBReply
        self.read_timeout = 1.0

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


"""	elseif (temptype .eq. 10)then !lakeshore 340
c	  lkcommand='SDAT?'
	  IF (samp_sensor .eq. 2) THEN
	    lkcommand='KRDG? B'
	  ELSEIF (samp_sensor .eq. 3) THEN
	    lkcommand='KRDG? C'
	  ELSEIF (samp_sensor .eq. 4) THEN
	    lkcommand='KRDG? D'
	  ELSE
	    lkcommand='KRDG? A'  !default
	  ENDIF
	  lcom=7
	  call lk232(lkcommand,lcom,reply,lreply,getreply)
	  if (lreply.eq.0)then
c	    type *,' no reply from temp controller'
	    sample=0.0
	  else
	    read (reply(1:lreply),fmt=*,err=96)sample
	  endif
	  IF (contr_sensor .eq. 1) THEN
	    lkcommand='KRDG? A'
	  ELSEIF (contr_sensor .eq. 3) THEN
	    lkcommand='KRDG? C'
	  ELSEIF (contr_sensor .eq. 4) THEN
	    lkcommand='KRDG? D'
	  ELSE
	    lkcommand='KRDG? B'  !default
	  ENDIF
	  lcom=7
	  call lk232(lkcommand,lcom,reply,lreply,getreply)
	  if (lreply.eq.0)then
c	    type *,' no reply from temp controller'
	    control=0.0
	  else
	    read (reply(1:lreply),fmt=*,err=96)control
	  endif
	  lkcommand='SETP? 1'
	  lcom=7
	  call lk232(lkcommand,lcom,reply,lreply,getreply)
	  if (lreply.eq.0)then
c	    type *,' no reply from temp controller'
	    setpoint=0.0
	  else
	    read (reply(1:lreply),fmt=*,err=96)setpoint
	  endif
	  """
