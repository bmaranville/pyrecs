import serial
import time
from numpy import abs, sign
import sys, os, serial, threading
import socket
from EiBotBoard import EBB

DEBUG = True
""" socat PTY,link=/dev/ttyVirtualS0,echo=0 PTY,link=/dev/ttyVirtualS1,echo=0
    to setup virtual serial ports for communication.  They are linked together. """

class EBBVME:
    def __init__(self, num_motors=2):
        self.newline_str = '\r'
        self.ok_str = 'OK:'
        self.read_timeout = 1.0
        self.num_motors = num_motors
        self.ebb = EBB()
    
    def write_one(self, write_str = ''):
        sys.stdout.write(self.ok_str + str(write_str) + self.newline_str)
        sys.stdout.flush()
         
    def process(self, command):
        command_pieces = command.strip().split(' ')
        print command_pieces
        if command_pieces[0] == 'scaler':
            print 'not a scaler\n'
            return
        elif command_pieces[0] == 'motor':
            self.motor_command(command_pieces[1:])
        
    def motor_command(self, command_pieces):
        #print "motor command: " + str(command_pieces) + '\n'
        if command_pieces[0] == 'position':
            motornum = int(command_pieces[1])
            if len(command_pieces) > 2:
                new_pos = float(command_pieces[2])
                self.write_one(self.ebb.SetMotorPos(motornum, new_pos))
            else:
                self.write_one('%.4f' % self.ebb.GetMotorPos(motornum))
        elif command_pieces[0] == 'move':
            motornum = int(command_pieces[1])
            new_pos = float(command_pieces[2])
            self.ebb.MoveMotor(motornum, new_pos)
            self.write_one("Moving %d to %s" % (motornum, command_pieces[2]))
        elif command_pieces[0] == 'motion':
            motornum = int(command_pieces[1])
            motion_status = self.ebb.CheckMoving(motornum)
            self.write_one(int(motion_status))
        elif command_pieces[0] == 'limits':
            # not implemented yet
            motornum = int(command_pieces[1])
            motion_limits = self.ebb.CheckHardwareLimits(motornum)
            self.write_one(int(motion_limits))
        elif command_pieces[0] == 'disable':
            motornum = int(command_pieces[1])
            disabled = self.ebb.DisableMotor(motornum)
            self.write_one(int(disabled))
        elif command_pieces[0] == 'enable':
            motornum = int(command_pieces[1])
            enabled = self.ebb.EnableMotor(motornum)
            self.write_one(int(enabled))
        elif command_pieces[0] == 'enabled':
            motornum = int(command_pieces[1])
            enabled = self.ebb.GetEnabled(motornum)
            self.write_one(int(enabled))    
        elif command_pieces[0] == 'stop':
            motornum = int(command_pieces[1])
            aborted = self.ebb.StopMotor(motornum)
            self.write_one(int(aborted))   
            

class serialVME(EBBVME):
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

import SocketServer

class MyTCPHandlerNoKeepAlive(SocketServer.BaseRequestHandler):
    """
    The request handler class for our server.

    It is instantiated once per connection to the server, and must
    override the handle() method to implement communication to the
    client.
    """

    def handle(self):
        # self.request is the TCP socket connected to the client
        self.data = self.request.recv(1024)
        if not self.data.endswith(self.server.vme.newline_str):
            print self.data, "not terminated correctly"
            return
        def write_one(output=''):
            output = self.server.vme.ok_str + str(output)
            if self.server.vme.echo_cmd:
                output += "@" + self.data
            else:
                output += self.server.vme.newline_str
            self.request.sendall(output)
        #self.server.vme.write_one = self.request.sendall
        self.server.vme.write_one = write_one
        self.server.vme.process(self.data)
        #print "{} wrote:".format(self.client_address[0])
        #print self.data
        # just send back the same data, but upper-cased
        #self.request.sendall(self.data.upper())
        
class MyTCPHandlerKeepAlive(SocketServer.BaseRequestHandler):
    """
    The request handler class for our server.

    It is instantiated once per connection to the server, and must
    override the handle() method to implement communication to the
    client.
    """
    
    def handle(self):
        # self.request is the TCP socket connected to the client
        self.data = None
        while not self.server._shutdown_requested:
            self.data = self.request.recv(1024)
            
            if not self.data.endswith(self.server.vme.newline_str):
                print "not terminated correctly"
                return
            def write_one(output=''):
                output = self.server.vme.ok_str + str(output)
                if self.server.vme.echo_cmd:
                    output += "@" + self.data
                else:
                    output += self.server.vme.newline_str
                self.request.sendall(output)
            #self.server.vme.write_one = self.request.sendall
            self.server.vme.write_one = write_one
            self.server.vme.process(self.data)
        
class TCPVME(serialVME):
    def __init__(self, host="localhost", port=5001, num_motors=25, echo_cmd=True):
        EBBVME.__init__(self, num_motors)
        self.echo_cmd = echo_cmd
        self.server = SocketServer.TCPServer((host, port), MyTCPHandlerKeepAlive)
        self.server._shutdown_requested = False
        self.server.vme = self
        
        self.flush = lambda x: None
        
    def start(self):
        # Activate the server; this will keep running until you
        # interrupt the program with Ctrl-C
        self.alive = True
        #start serial->console thread
        self.receiver_thread = threading.Thread(target=self.server.serve_forever)
        self.receiver_thread.setDaemon(1)
        self.receiver_thread.start()
        
    def stop(self):
        self.server._shutdown_requested = True
        self.server.shutdown()
    
def key_description(character):
    """generate a readable description for a key"""
    ascii_code = ord(character)
    if ascii_code < 32:
        return 'Ctrl+%c' % (ord('@') + ascii_code)
    else:
        return repr(ascii_code)
             
        
if __name__ == '__main__':
    vme = serialVME('/dev/ttyUSB1')
    vme.start()     
