import serial
from persistent_dict import PersistentDict
import os
# we will store the motor state in the home directory under $HOME/.pyrecs/EBBMotorState.json
DEBUG = False
DEFAULT_STORE = os.path.join(os.getenv('HOME'), '.pyrecs')
DEFAULT_PPD = 200.0 * 16 / 360 # 200 steps per revolution, 16 pulses per step
DEFAULT_MOTOR_CONFIG = {"pulses": 0, "enabled": False, "speed": 1.0, "pulsesPerDegree": DEFAULT_PPD})

class EBB(object):
    """Talk to the EiBotBoard"""

    def __init__(self, port, storedir=DEFAULT_STORE):
        self.serial = serial.Serial(port, 9600, parity='N', rtscts=False, xonxoff=False, timeout=2)
        self.newline_str = '\r\n'
        self.storedir = storedir
        self.max_resends = 1
        self.maxmotors = 2
        if not os.path.isdir(storedir):
            os.mkdir(storedir)
        self.persistent_state = PersistentDict(os.path.join(self.storedir, "EBBMotorState.json"), format="json")
        # initialize motor states if they are not there already
        self.persistent_state.setdefault("1", DEFAULT_MOTOR_CONFIG)
        self.persistent_state.setdefault("2", DEFAULT_MOTOR_CONFIG)
        self.persistent_state.sync()
    
    def readline(self):
        # with this board, always seems to be 2 delimiters but the order varies.
        line = ''
        reply = ''
        delim_count=0
        while delim_count < 2:
            reply = self.serial.read(1)
            if reply == '\r' or reply == '\n':
                delim_count += 1
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
        return reply.rstrip()
    
    ################### MOTOR FUNCTIONS #######################
    def GetMotorPos(self, motornum):
        state = self.persistent_state[str(motornum)]
        pulses = state["pulses"]
        ppd = state["pulsesPerDegree"]
        position = float(pulses) / ppd
        return position
        
    def SetMotorPos(self, motornum, position):
        state = self.persistent_state[str(motornum)]
        ppd = float(state["pulsesPerDegree"])
        new_pulses = int(position * ppd)
        self.persistent_state[str(motornum)]["pulses"] = new_pulses
        self.persistent_state.sync()
        
    def EnableMotor(self, motornum):
        # this is done by the board with every move command;
        # the command would be "EM,<enable 1>,<enable 2>\r\n"
        self.persistent_state[str(motornum)]["enabled"] = True
        self.persistent_state.sync()
        self.pushEnabledState()
        
    def DisableMotor(self, motornum):
        self.persistent_state[str(motornum)]["enabled"] = True
        self.persistent_state.sync()
        self.pushEnabledState()
    
    def pushEnabledState(self):
        m1en = 1 if self.persistent_state["1"]["enabled"] else 0
        m2en = 1 if self.persistent_state["2"]["enabled"] else 0
        self.sendCMD("EM,%d,%d" % (m1en, m2en))
        
    def MoveMotor(self, motornum, position):
        state = self.persistent_state[str(motornum)]
        ppd = float(state["pulsesPerDegree"])
        new_pulses = int(position * ppd)
        pulses = int(state["pulses"])
        speed = float(state["speed"])

        pdelta = new_pulses - pulses
        posdelta = pdelta / ppd
        tdelta = int(posdelta / speed * 1000.0) # milliseconds
        axes = {"1": 0, "2",0} # motor move distance
        axes[str(motornum)] = pdelta
        self.sendCMD("SM,%d,%d,%d" % (tdelta, axes["1"], axes["2"]))
        self.persistent_state[str(motornum)]["pulses"] = new_pulses
        self.persistent_state.sync()
        
    def StopMotor(self, motornum):
        print "not implemented: no stopping with EBB!"
        
    def CheckHardwareLimits(self, motornum):
        return False
            
    def CheckMoving(self, motornum):
        reply = self.sendCMD('QM')
        moving = reply.split(',')[motornum+1] == '1'
        return moving
            
