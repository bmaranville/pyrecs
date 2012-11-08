import serial, struct
import time
DEBUG = True


class EZStepper:
    """Talk to the EZStepper box"""
    ERROR_CODES = {\
        0: "No Error",
        1: "Init Error",
        2: "Bad Command (illegal command was sent)",
        3: "Bad Operand (Out of range operand value)",
        4: "N/A",
        5: "Communications Error (Internal communications error)",
        6: "N/A",
        7: "Not Initialized (Controller was not initialized before attempting a move)",
        8: "N/A",
        9: "Overload Error (Physical system could not keep up with commanded position)",
        10: "N/A",
        11: "Move Not Allowed",
        12: "N/A",
        13: "N/A",
        14: "N/A",
        15: "Command overflow (unit was already executing a command when another command was received)"
    }
    
    MOTOR_STRINGS = {\
        1:'1',2:'2',3:'3',4:'4',5:'5',6:'6',7:'7',8:'8',9:'9',
        10:':',
        11:';',
        12:'<',
        13:'=',
        14:'>',
        15:'?',
        16:'@'
    }
    
    STEP_OFFSET = 2**31
    
    def __init__(self, port):
        self.serial = serial.Serial(port, 9600, parity='N', rtscts=False, xonxoff=False, timeout=2)
        self.newline_str = '\r'
        self.reply_terminator = '\n'
        self.steps_per_degree = 480.
        self.tolerance = 4
        self.num_mots = 13
    
    def readline(self):
        line = ''
        reply = ''
        while not reply == self.reply_terminator:
            reply = self.serial.read(1)
            if DEBUG: print reply,
            line += reply
        return line
    
    def interpret_status(self, status_string):
        status_byte = struct.unpack('B', status_string)[0]
        error_id = status_byte & 0xF
        busy = bool(status_byte & 0x20)
        # possibly this should be >> 4 instead of & 0xF, depending on whether it's little- or big-endian
        if DEBUG: print busy, error_id, self.ERROR_CODES[error_id]
        if DEBUG: 
            for i in range(8): 
                print bool(status_byte & 2**i)
        return busy, error_id, self.ERROR_CODES[error_id]
        
    def sendCMD(self, text_cmd = ''):
        error_code = 15 # message overlap
        while error_code == 15:
        #if 1:
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
            status_loc = reply.find('/0') + 2
            busy, error_code, error_msg = self.interpret_status(reply[status_loc]) # right after /0 header
        if error_code != 0:
            raise Exception('EZ stepper says something bad: ' + error_msg)
        return reply[status_loc + 1:-4] # clip the \r and EOL character (0x03)
    
    def step_to_pos(self, step):
        pos = float(step - self.STEP_OFFSET) / self.steps_per_degree
        return pos
        
    def pos_to_step(self, pos):
        step = int(self.steps_per_degree * pos) + self.STEP_OFFSET
        return step
        
    ################### MOTOR FUNCTIONS #######################
    def Initialize(self, motornum):
        self.sendCMD('/%ss0V4000L1m15h0j8N1R' % self.MOTOR_STRINGS[motornum])
    
    def GetMotorStep(self, motornum):
        step = long(self.sendCMD('/%s?A' % self.MOTOR_STRINGS[motornum]))
        if DEBUG: print "long pos: ", step
        return step
        
    def GetMotorPos(self, motornum):
        step = self.GetMotorStep(motornum)
        #reply = self.sendCMD('/%s?A' % self.MOTOR_STRINGS[motornum])       
        return self.step_to_pos(step)
        
    def SetMotorPos(self, motornum, position):
        step = self.pos_to_step(position)
        self.SetMotorStep(motornum, step)
    
    def SetMotorStep(self, motornum, step):
        self.sendCMD('/%sz%dR' % (self.MOTOR_STRINGS[motornum], step))
        
    def EnableMotor(self, motornum):
        pass
        
    def DisableMotor(self, motornum):
        pass
    
    def MoveMotorStep(self, motornum, step):
        self.sendCMD('/%sA%dR' % (self.MOTOR_STRINGS[motornum], step))
        
    def MoveMotor(self, motornum, position):
        step = self.pos_to_step(position)
        self.MoveMotorStep(motornum, step)
        
    def StopMotor(self, motornum):
        self.sendCMD('/%sT' % self.MOTOR_STRINGS[motornum])
    
    def StopAll(self):
        self.sendCMD('/_T')
        
    def CheckHardwareLimits(self, motornum):
        return True
            
    def CheckMoving(self, motornum):
        step_now = long(self.sendCMD('/%s?A' % self.MOTOR_STRINGS[motornum]))
        #time.sleep(0.2) # fix... need to check status byte to see if command running
        target_step = long(self.sendCMD('/%s?0' % self.MOTOR_STRINGS[motornum]))
        if abs(step_now - target_step) > self.tolerance:
            return True
        else: 
            return False
    #################################
    # convenience function:
    def pa(self):
        for i in range(1,self.num_mots):
            print i, self.GetMotorPos(i)
            
