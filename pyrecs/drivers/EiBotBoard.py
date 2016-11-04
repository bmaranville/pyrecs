import serial
from persistent_dict import PersistentDict
import os
# we will store the motor state in the home directory under $HOME/.pyrecs/EBBMotorState.json
DEBUG = False
DEFAULT_STORE = os.path.join(os.getenv('HOME'), '.pyrecs')
DEFAULT_SPD = 200.0 * 16 / 360 # 200 * 16 steps per revolution (smallest microstep possible)
DEFAULT_MOTOR_CONFIG = {
    "position": 0.0, 
    "stepzero_position": 0.0, 
    "steps": 0,
    "enabled": False,
    "speed": 25.0,
    "stepsPerDegree": DEFAULT_SPD
}
MICROSTEPS_CODES = {
    # for EBB v1.2 and above
    16: 1,
    8: 2,
    4: 3,
    2: 4,
    1: 5
}
EBB_MAX_CURRENT = 1.25 # Amps

class EBB(object):
    """Talk to the EiBotBoard"""

    def __init__(self, port="/dev/ttyACM0", storedir=DEFAULT_STORE):
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
        self.persistent_state.setdefault("microsteps", 16) # must use the same value for both motors
        self.persistent_state.sync()
        self.pushEnabledState()
    
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
        
    def GetCurrent(self):
        """ get the output current to the motor
        (changed by pot on EBB surface) """
        result = self.sendCMD("QC")
        currint, V0 = result.split(',')
        curr = float(currint) / 1023.0 * EBB_MAX_CURRENT
        return curr
    
    ################### MOTOR FUNCTIONS #######################
    def GetMotorPos(self, motornum):
        state = self.persistent_state[str(motornum)]
        return state["position"]
                
    def SetMotorPos(self, motornum, position):
        self.persistent_state[str(motornum)]["stepzero_position"] = position
        self.persistent_state[str(motornum)]["position"] = position
        self.persistent_state[str(motornum)]["steps"] = 0
        self.persistent_state.sync()
        return 0
        
    def EnableMotor(self, motornum):
        # this is done by the board with every move command;
        # the command would be "EM,<enable 1>,<enable 2>\r\n"
        self.persistent_state[str(motornum)]["enabled"] = True
        self.persistent_state.sync()
        self.pushEnabledState()
        return 1
        
    def GetEnabled(self, motornum):
        return self.persistent_state[str(motornum)]["enabled"]
        
    def DisableMotor(self, motornum):
        self.persistent_state[str(motornum)]["enabled"] = False
        self.persistent_state.sync()
        self.pushEnabledState()
        return 0
    
    def pushEnabledState(self):
        microsteps = self.persistent_state["microsteps"]
        if not (microsteps in MICROSTEPS_CODES):
            error_msg = "error: inconsistent microsteps number %d\n" % (microsteps,)
            error_msg += "\nAllowed values: %s" % (str(MICROSTEPS_CODES.keys()))
            print(error_msg)
            return
        
        enableCode = MICROSTEPS_CODES[microsteps]
            
        m1en = enableCode if self.persistent_state["1"]["enabled"] else 0
        m2en = enableCode if self.persistent_state["2"]["enabled"] else 0
        self.sendCMD("EM,%d,%d" % (m1en, m2en))
        
    def MoveMotor(self, motornum, position):
        state = self.persistent_state[str(motornum)]
        microsteps = int(self.persistent_state["microsteps"])
        spd = float(state["stepsPerDegree"])
        szero = float(state["stepzero_position"])
        steps = int(state["steps"])
        speed = float(state["speed"])
        old_pos = (float(steps) / spd) + szero

        posdelta = float(position - old_pos)
        pdelta = int(posdelta * spd * microsteps/16)
        new_steps = steps + int(pdelta * 16/microsteps)
        tdelta = int(abs(posdelta / speed * 1000.0)) # milliseconds
        axes = {"1": 0, "2": 0} # motor move distance
        axes[str(motornum)] = pdelta
        if pdelta == 0:
            print("already there.")
            return
        if self.CheckAnyMoving():
            print("error: already moving")
            return
        self.sendCMD("SM,%d,%d,%d" % (tdelta, axes["1"], axes["2"]))
        self.persistent_state[str(motornum)]["steps"] = new_steps
        actual_pos = (float(new_steps) / spd) + szero
        self.persistent_state[str(motornum)]["position"] = actual_pos
        self.persistent_state["1"]["enabled"] = True
        self.persistent_state["2"]["enabled"] = True        
        self.persistent_state.sync()
        
    def StopMotor(self, motornum):
        #print("stopping...")
        self.sendCMD('ES')
        #self.sendCMD('EM,0,0')
        #self.pushEnabledState()
        #print "not implemented: no stopping with EBB!"
        return 0
        
    def CheckHardwareLimits(self, motornum):
        return False
           
    def CheckAnyMoving(self):
        reply = self.sendCMD('QM')
        moving = reply.split(',')[1].strip() == '1'
        return moving
        
    def CheckMoving(self, motornum):
        reply = self.sendCMD('QM')
        moving = reply.split(',')[motornum+1].strip() == '1'
        return moving
            
