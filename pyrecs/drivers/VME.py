import serial
DEBUG = False

class VME:
    """Talk to the VME box"""
    def __init__(self, port):
        self.serial = serial.Serial(port, 9600, parity='N', rtscts=False, xonxoff=False, timeout=2)
        self.newline_str = '\r'
        self.max_resends = 1
    
    def readline(self):
        line = ''
        reply = ''
        while not reply == self.newline_str:
            reply = self.serial.read(1)
            line += reply
        return line
        
    def sendCMD(self, text_cmd = '', resend_number=0):
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
        if not self.reply[:3] == 'OK:':
            if resend_number < self.max_resends:
                self.sendCMD(text_cmd, resend_number+1)
            else:
                raise Exception('Max resends exceeded (%d) and VME says something bad: %s' % (resend_number, reply))
        return reply[3:].rstrip()
    
    ################### MOTOR FUNCTIONS #######################
    def GetMotorPos(self, motornum):
        reply = self.sendCMD('motor position %d' % motornum)
        try:
            result = float(reply)
        except:
            result = -999.99
        return result
        
    def SetMotorPos(self, motornum, position):
        self.sendCMD('motor position %d %.4f' % (motornum, position))
        
    def EnableMotor(self, motornum):
        self.sendCMD('motor enable %d' % motornum)
        
    def DisableMotor(self, motornum):
        self.sendCMD('motor disable %d' % motornum)
        
    def MoveMotor(self, motornum, position):
        self.sendCMD('motor move %d %.4f' % (motornum, position))
        
    def StopMotor(self, motornum):
        self.sendCMD('motor stop %d' % motornum)
        
    def CheckHardwareLimits(self, motornum):
        reply = self.sendCMD('motor limits %d' % motornum)
        if reply == '1': 
            return True
        else: 
            return False
            
    def CheckMoving(self, motornum):
        reply = self.sendCMD('motor motion %d' % motornum)
        if reply == '1': 
            return True
        else: 
            return False
            
    def GetMotorLabel(self, motornum):
        self.sendCMD('set $mc(%d,label)' % (motornum,))
        
    def GetAllMotorLabels(self):
        reply = self.sendCMD('set return_values {};foreach axis $mc(defined) {lappend return_values ${axis}:$mc(${axis},label)};join $return_values ";"')
        label_dict = {}
        for i in reply.split(";"):
            motnum, label = i.split(":")
            label_dict[int(motnum)] = label
        return label_dict
        
    def GetAllMotorPositions(self):
        reply = self.sendCMD('set return_values {};foreach axis $mc(defined) {lappend return_values [motor position ${axis}]};join $return_values ";"')
        return map(float, reply.split(";"))
            
    #################### DETECTOR FUNCTIONS #########################
    def CountByTime(self, duration):
        self.sendCMD('scaler time %d' % duration)
        
    def CountByMonitor(self, monitor_counts):
        self.sendCMD('scaler monitor %d' % monitor_counts)
        
    def ResetScaler(self):
        self.sendCMD('scaler reset')
        
    def IsCounting(self):
        reply = self.sendCMD('scaler status')
        if reply == '1':
            return True
        else:
            return False
        
    def AbortCount(self):
        self.sendCMD('scaler abort')
        
    def GetElapsed(self):
        reply = self.sendCMD('scaler elapsed')
        if reply:
            reply = float(reply)
        else: 
            reply = None
        return reply
        
    def GetCounts(self):
        reply = self.sendCMD('scaler read')
        pieces = reply.split()
        count_time = float(pieces[0])
        monitor = float(pieces[1])
        counts = float(pieces[2])
        return count_time, monitor, counts
