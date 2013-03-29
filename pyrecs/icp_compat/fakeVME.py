import serial
import time
from numpy import abs, sign
import sys, os, serial, threading
import socket

DEBUG = True
""" socat PTY,link=/dev/ttyVirtualS0,echo=0 PTY,link=/dev/ttyVirtualS1,echo=0
    to setup virtual serial ports for communication.  They are linked together. """

class VME:
    def __init__(self, num_motors=25):
        self.newline_str = '\r'
        self.ok_str = 'OK:'
        self.read_timeout = 1.0
        self.volt_change_rate = 2.0 #volts/second
        self.curr_change_rate = 1.0 #amps/second
        self.voltage = None
        self.current = None
        self.scaler_time_expiration = 0.0
        self.scaler_status = 0
        self.scaler_time = 0.0
        self.motors = []
        self.cmd_log = []
        self.num_motors = num_motors
        for i in range(self.num_motors):
            self.motors.append(Motor(num = i))
    
    def write_one(self, write_str = ''):
        sys.stdout.write(self.ok_str + str(write_str) + self.newline_str)
        sys.stdout.flush()
         
    def process(self, command):
        command_pieces = command.split(' ')
        if command_pieces[0] == 'scaler':
            self.scaler_command(command_pieces[1:])
        elif command_pieces[0] == 'motor':
            self.motor_command(command_pieces[1:])
            
    def scaler_command(self, command_pieces):
        if command_pieces[0] == 'reset':
            self.write_one('Reset Done')
        elif command_pieces[0] == 'time':
            t = float(command_pieces[1])
            self.scaler_time_expiration = time.time() + t
            self.scaler_status = 1
            self.scaler_time = t
            self.write_one('Counting Started')
        elif command_pieces[0] =='monitor':
            m = int(command_pieces[1])
            self.scaler_time_expiration = time.time() + (m/1000.0)
            self.scaler_status = 1
            self.scaler_time = m/1000.0
            self.write_one('Counting Started')
        elif command_pieces[0] == 'status':
            if self.scaler_status == 0:
                self.write_one('0')
            elif self.scaler_status == 1:
                if time.time() > self.scaler_time_expiration:
                    self.scaler_status = 0
                    self.write_one('0')
                else:
                    self.write_one('1')
        elif command_pieces[0] == 'read':
            self.write_one(str(int(self.scaler_time * 10000)) + ' 45 124 100 0 0 0 0 0 0 0 0 0 0 0 0')
        elif command_pieces[0] == 'elapsed':
            self.write_one()
        elif command_pieces[0] == 'abort':
            self.write_one(0)
        
    def motor_command(self, command_pieces):
        #print "motor command: " + str(command_pieces) + '\n'
        if command_pieces[0] == 'position':
            motornum = int(command_pieces[1])
            self.write_one('%.4f' % self.motors[motornum].GetPosition())
        elif command_pieces[0] == 'move':
            motornum = int(command_pieces[1])
            new_pos = float(command_pieces[2])
            self.motors[motornum].SetPosition(new_pos)
            self.write_one()
        elif command_pieces[0] == 'motion':
            motornum = int(command_pieces[1])
            motion_status = self.motors[motornum].GetMotionStatus()
            self.write_one(motion_status)
        elif command_pieces[0] == 'limits':
            motornum = int(command_pieces[1])
            motion_limits = self.motors[motornum].GetIsAtLimits()
            self.write_one(motion_limits)
        elif command_pieces[0] == 'disable':
            motornum = int(command_pieces[1])
            disabled = self.motors[motornum].Disable()
            self.write_one(disabled)
        elif command_pieces[0] == 'enable':
            motornum = int(command_pieces[1])
            enabled = self.motors[motornum].Enable()
            self.write_one(enabled)    
        elif command_pieces[0] == 'stop':
            motornum = int(command_pieces[1])
            aborted = self.motors[motornum].AbortMove()
            self.write_one(aborted)   
            

class serialVME(VME):
    def __init__(self, port, num_motors=25):
        VME.__init__(self, num_motors)
        self.serial = serial.Serial(port, 9600, parity='N', rtscts=False, xonxoff=False, timeout=1)
        self.read = self.serial.read
        self.write = self.serial.write
        self.flush = self.serial.flush

    def start(self):
        self.alive = True
        #start serial->console thread
        self.receiver_thread = threading.Thread(target=self.reader)
        self.receiver_thread.setDaemon(1)
        self.receiver_thread.start()

    def stop(self):
        self.alive = False
        
    def reader(self):
        """loop and copy serial->console"""
        command = ''
        while self.alive:
            data = self.read(1)
            if data == self.newline_str:
                sys.stdout.write(command + self.newline_str + '\n')
                sys.stdout.flush()
                self.cmd_log.append(command)
                time.sleep(0.05)
                self.process(command)
                command = ''
            else: 
                command += data
                
    def write_one(self, write_str = ''):
        self.write(self.ok_str + str(write_str) + self.newline_str)
        self.flush()
        if DEBUG:
            print '\t' + self.ok_str + str(write_str) + self.newline_str

class sockVME(serialVME):
    def __init__(self, sock = '/tmp/com1', num_motors=25):
        VME.__init__(self, num_motors)
        self.serial = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.serial.connect(sock)
        self.read = self.serial.recv
        self.write = self.serial.send
        self.flush = lambda x: None

    
def key_description(character):
    """generate a readable description for a key"""
    ascii_code = ord(character)
    if ascii_code < 32:
        return 'Ctrl+%c' % (ord('@') + ascii_code)
    else:
        return repr(ascii_code)
        
class Motor:
    def __init__(self, position = 0.0, rate = 0.3, disabled = True, ul = 20.0, ll = -20.0, num = 0):
        self.position = position
        self.rate = rate # deg/s or mm/s
        self.disabled = disabled
        self.motion = 0
        self.direction = +1.0
        self.upper_limit = ul
        self.lower_limit = ll
        self.num = num
        
    def GetMotionStatus(self):
        return self.motion
        
    def GetPosition(self):
        return self.position
    
    def SetPosition(self, new_pos):
        curr_time = time.time()
        curr_pos = self.GetPosition()
        self.disabled = False
        self.moving_thread = threading.Thread(target = self.MoveTo, args=(curr_pos, new_pos, curr_time, self.rate))
        self.moving_thread.start()
        return 0
        
    def MoveTo(self, curr_pos, new_pos, curr_time, rate):
        self.motion = 1
        move_distance = float(new_pos - curr_pos)
        direction = sign(move_distance)
        while self.motion == 1:
            time_elapsed = time.time() - curr_time
            change_in_pos = rate * direction * time_elapsed
            if abs(change_in_pos) >= abs(move_distance):
                self.position = new_pos
                self.motion = 0
                break
            else:
                self.position = curr_pos + change_in_pos
        self.abort = 0
                
    def Disable(self):
        self.disabled = True
        return 0
        
    def Enable(self):
        self.disabled = False
        return 0
        
    def AbortMove(self):
        if self.motion == 1:
            self.motion = 0
        return 0
       
    def GetIsAtLimits(self):
        if self.GetPosition() > self.upper_limit or self.GetPosition() < self.lower_limit:
            return 1
        else:
            return 0
             
        
if __name__ == '__main__':
    vme = VME('/dev/ttyUSB1')
    vme.start()     
