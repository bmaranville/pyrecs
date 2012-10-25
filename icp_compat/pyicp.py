#!/usr/bin/python



import os, sys, threading, signal, time
from subprocess import Popen, PIPE, STDOUT
from collections import deque
import copy
import readline
import os
import pty

import xmlrpclib

    
## Not saving history file directly, for now: 
## still letting ICP do that, so leave next 2 commented
#import atexit
#atexit.register(readline.write_history_file, histfile)

class PyICP:
    """ Python ICP wrapper:  starts an ICP session, and sets up command interface 
    the reader thread runs continuously and sets the self.ready flag when 
    the command is finished running (safe to pick up data) """

    def __init__(self, prompt_str = '% ', python_esc_str = '@'):
        # now starting up ICP and initializing variables
        self.icp = Popen("icp", shell=True, stdin=PIPE, stdout=PIPE, stderr=PIPE, close_fds=True)
        (self.icp_write, self.icp_read, self.icp_error) = (self.icp.stdin, self.icp.stdout, self.icp.stderr)
        self.newline_str = '\n'
        self.prompt_str = prompt_str
        self.ready = False
        self.header_string = ''
        while not self.header_string[-2:] == self.prompt_str:
            self.header_string += self.icp_read.read(1)
        self.start()
             
    def sigAbort(self, signum=None, frame=None):
        """ this triggers ABORT in ICP 
        hook this up to your GUI button if you need a way to cancel ICP actions """
        os.kill(self.icp.pid, signal.SIGINT) # pass-through to ICP
        
            
    def sigSuspend(self, signum=None, frame=None):
        """ this triggers PAUSE in ICP """
        os.kill(self.icp.pid, signal.SIGTSTP) # pass-through: send suspend to ICP

    def sigQuit(self, signum=None, frame=None):
        """ this triggers FINISHUP in ICP """
        os.kill(self.icp.pid, signal.SIGQUIT) # pass-through: send quit to ICP
        
    def do_icp_cmd(self, cmd):
        """ sends a command and then waits for self.ready to get reset and returns reply """
        self.send_icp_cmd(cmd)
        while not self.ready: # wait for the receiver thread to reset the flag
            pass
        return self.reply  # then pick up and return the result
    
    def send_icp_cmd(self, cmd):
        """ use this one if you want to send a command to icp and then ignore it.
        You can check back as often as desired to see when self.ready flag gets set """
        self.icp_write.write(cmd + self.newline_str)
        self.icp_write.flush()
        self.ready = False
    
    def start(self):
        self.alive = True
        self.ready = True
        #start serial->console thread
        self.receiver_thread = threading.Thread(target=self.reader)
        self.receiver_thread.setDaemon(1)
        self.receiver_thread.start()
    
    def stop(self):
        self.alive = False
        
    def reader(self):
        """ catch and hold ICP response, and set the flag when ready """
        while self.alive:
            reply = ''
            self.last_read = ''
            while not self.ready:            
                data = self.icp_read.read(1)
                self.icp_read.flush()
                if not data:
                    break
                self.last_read += data
                reply += data
                if self.last_read == self.prompt_str:
                    # we've gotten another prompt: signal that we're ready for data pickup
                    self.reply = reply
                    self.ready = True
                if data == '\n' or data == '\r':
                    self.last_read = ''
    
    def get_icp_output(self):
        """ use this to get a complete response from ICP.  Not used to get line-by-line responses (as during scan) """
        self.last_read = ''
        self.ready = False
        self.reply = ''
        while not self.ready:
            data = self.icp_read.read(1)
            self.icp_read.flush()
            #sys.stdout.write(data)
            if not data:
                break
            self.last_read += data
            self.reply += data
            if self.last_read == self.prompt_str:
                # we've gotten another prompt: signal that we're ready for another command
                self.ready = True
            if data == '\n' or data == '\r':
                self.last_read = '' 
        return self.reply

    def __call__(self, cmd):
        return self.do_icp_cmd(cmd)

    def icp_quit(self):
        self.icp_write.write('exit\n')
        self.icp_write.flush()

class Overlord:
    """begin an ICP process.  take all input from keyboard and pass through to ICP,
    except if it begins with an '@' symbol:  then interpret as python command"""
    
    def __init__(self, prompt_strs = ['% ', ')', '):'], python_esc_str = '@'):
        self.oldAbort = signal.signal(signal.SIGINT, self.sigAbort)
        self.oldSuspend = signal.signal(signal.SIGTSTP, self.sigSuspend)
        self.oldQuit = signal.signal(signal.SIGQUIT, self.sigQuit)
        
        histfile = os.path.join(os.getcwd(), '.icp_history')
        try:
            readline.read_history_file(histfile)
        except IOError:
            pass
            
        self.master, self.slave = pty.openpty()
        # now starting up ICP and initializing variables
        # note: piping error to slaves
        self.icp = Popen("icp", shell=True, stdin=PIPE, stdout=self.slave, stderr=self.slave, close_fds=True, bufsize=0)
        (self.icp_write, self.icp_read, self.icp_error) = (self.icp.stdin, self.icp.stdout, self.icp.stderr)
        self.alive = False 
        self.newline_str = '\n'
        self.python_esc_str = python_esc_str
        self.prompt_strs = prompt_strs
        self.ready = False
        self.icp_command_count = 0
        self.python_command_count = 0
        self.python_commands = deque()
        self.icp_commands = deque()
        self.sequence = None
        self._pythoncmd_running = False # set True during execution of python commands
        
    def sigAbort(self, signum, frame):
        os.kill(self.icp.pid, signal.SIGINT) # pass-through to ICP
        if self._pythoncmd_running: # but still catch KeyboardInterrupt if we're in python mode
            raise KeyboardInterrupt
            
    def sigSuspend(self, signum, frame):
        os.kill(self.icp.pid, signal.SIGTSTP) # pass-through: send suspend to ICP

    def sigQuit(self, signum, frame):
        os.kill(self.icp.pid, signal.SIGQUIT) # pass-through: send quit to ICP

    def start(self):
        self.alive = True
        self.ready = True
        sys.stdout.write('enter python commands by prefixing with @ symbol, e.g.:\n * @print 3 * 4\n')
        sys.stdout.flush()
        #start serial->console thread
        self.receiver_thread = threading.Thread(target=self.reader)
        self.receiver_thread.setDaemon(1)
        self.receiver_thread.start()
        #enter console->serial loop
        self.transmitter_thread = threading.Thread(target=self.writer)
        self.transmitter_thread.setDaemon(1)
        self.transmitter_thread.start()
        #enter command_queue loop
        self.command_thread = threading.Thread(target=self.command_loop)
        self.command_thread.start()
        #watch to see if icp subprocess ends - if so, exit
        self.watcher_thread = threading.Thread(target=self.icp_subprocess_watcher)
        self.watcher_thread.setDaemon(1)
        self.watcher_thread.start()

       
    def join(self, transmit_only=False):
        self.transmitter_thread.join()
        self.receiver_thread.join()

    def stop(self):
        self.alive = False
        
    def reader(self):
        """loop and copy icp->console"""
        icpout = os.fdopen(self.master)
        self.last_read = ''
        while self.alive:
            data = icpout.read(1)
            #icpout.flush()
            if not data:
                print "breaking..."
                break
            self.last_read += data
            sys.stdout.write(data)
            sys.stdout.flush()
            if any([self.last_read.endswith(ps) for ps in self.prompt_strs]):
                # we've gotten another prompt: signal that we're ready for another command
                # print self.last_read		
                self.ready = True
            if data == '\n' or data == '\r':
                self.last_read = ''

    def writer(self):
        while self.alive:
            cmd_line = raw_input()
            self.parse_cmd_line(cmd_line)

    def command_loop(self):
        """loop to hold the command queue and drop it into ICP when a prompt appears"""
        while self.alive:
            if self.ready:
                if not self.sequence == None:
                    next_cmd = self.sequence.GetNextCommand()
                    if next_cmd == None:
                        self.sequence = None
                        # this resets the sequence, and the loop will start over
                        # (it will catch commands in the icp_commands queue now)
                    else:
                        self.do_icp_cmd(next_cmd)
                elif len(self.icp_commands) > 0:
                    self.do_icp_cmd(self.icp_commands.popleft())
                time.sleep(0.1)
            else: # we're not ready, just hang out
                time.sleep(0.1)

    def error(self):
        """loop and copy icp->console"""
        command = ''
        while self.alive:
            data = self.icp_error.read(1)
            if not data:
                break
            sys.stderr.write(data)
            sys.stderr.flush()
            
    def icp_subprocess_watcher(self):
        """ if the return code of the subprocess ever changes, icp is done, so exit """
        while self.alive:
            if not self.icp.poll() == None:
                self.exit()    

    def parse_cmd_line(self, cmd_line):
        cmds = []
        for cmd in cmd_line.split(';'):  
            cmd = cmd.strip()  # clean off whitespace surround, incl. newlines
            if cmd: # reject empty commands
                self.icp_commands.append(cmd)
          
    def do_icp_cmd(self, cmd):
        self.ready = False
        self.icp_command_count += 1
        if cmd.startswith(self.python_esc_str):
            self.do_python_cmd(cmd[1:])
        else:
            if self.alive:
                sys.stdout.write(cmd + ':')
                self.icp_write.write(cmd + self.newline_str)
                self.icp_write.flush()   
        
    def do_python_cmd(self, cmd):
        self._pythoncmd_running = True # switch on the interrupt catcher
        try:
            exec(cmd, globals(), globals())
        except:  # note: statements resulting in errors go away
            pass
        self._pythoncmd_running = False # switch off the interrupt catcher
        sys.stdout.write(self.prompt_strs[0])
        sys.stdout.flush()
        self.ready = True
        return
                
    def run_py_seq_file(self, filename):
        seq_file = PyICPSequenceFile(filename)
        self.sequence = seq_file
        
    def dry_run_py_seq_file(self, filename):
        seq_file = PyICPSequenceFile(filename)
        lines, pos, current_command = seq_file.ParseFile()
        # not done yet...
                     
    def exit(self):        
        # reinstate the signal handlers
        #signal.signal(signal.SIGINT, self.oldAbort)
        #signal.signal(signal.SIGTSTP, self.oldSuspend)
        #signal.signal(signal.SIGQUIT, self.oldQuit)
        self.stop()
        sys.exit(0)
        
class PyICPSequenceFile:
    """controls and reads from a sequence file, moving the marker around
       it is defined as an iterator, so getting the next element moves the marker
       can use syntax "for cmd in PyICPSequenceFile(filename):" to iterate
       through file, moving the marker
       """
    def __init__(self, filename, marker = '%'):
        self.filename = filename
        self.marker = marker
        self.last = ''
        self.next_command = ''
        self.current_command = ''
        
    def ParseFile(self):
        f_in = open(self.filename, 'r')
        #lines = f_in.readlines()
        data = f_in.read()
        #print data
        f_in.close() # we're done reading
        
        current_command = None
        seek_pos = 0
        datalen = len(data)
        not_separator = True
        def next_cmd(data, seek_pos):
            cmd = ''
            not_separator = True
            while not_separator:
                next_char = data[seek_pos]
                if next_char == ';' or next_char == '\n' or next_char == '\r':
                    not_separator = False
                cmd += next_char
                seek_pos += 1
            return cmd, seek_pos
        
        new_data = ''
        match = False
        while seek_pos < datalen and match == False:
            cmd, new_seek_pos = next_cmd(data, seek_pos)
            marker_loc = cmd.rfind(self.marker)
            # check to see if there's anything after the marker - if not, proceed
            if marker_loc > -1 and cmd[marker_loc+1:].rstrip('; \t\n\r') == '':
                #current_command = cmd[:marker_loc]
                match = True # we found it!  set the flag
                current_command = cmd[:marker_loc].strip('; \t\n\r')
                replacement_str = cmd[:marker_loc] + cmd[marker_loc+1:]
                new_data = data[:seek_pos]+replacement_str
            seek_pos = new_seek_pos
        
        if not match:
            seek_pos = 0
            
        # or else we've got a match - what's the next command?
        
        next_command = None
        commands_left = 0
        next_command_found = False
        while seek_pos < datalen:
            cmd, new_seek_pos = next_cmd(data, seek_pos)
            if cmd.strip('; \t\n\r') == '':
                new_data += cmd
            else: # we have a non-blank command:
                commands_left += 1 # add one to the stack
                if not next_command_found:
                    next_command_found = True
                    next_command = cmd.rstrip('; \t\n\r'+self.marker)
                    # check to see if it's already got a marker (or more than one) and clear them
                    end_of_command = len(cmd.rstrip('; \t\r\n'+self.marker))
                    cmd = cmd[:end_of_command] + cmd[end_of_command:].replace(self.marker, '')
                    # and then put exactly one marker back, right before the end
                    new_data += cmd[:-1] + self.marker + cmd[-1]
                else:
                    new_data += cmd
            seek_pos = new_seek_pos
                    
        return current_command, next_command, commands_left, new_data
        
    def GetCurrentCommand(self):
        current_command, next_command, commands_left, new_data = self.ParseFile()
        return current_command
        
    #def __len__(self):
    #    current_command, next_command, commands_left, new_data = self.ParseFile()
    #    return commands_left
        
    #def clear(self):
    #    """move the marker to the last command"""
    #    while self.__len__() > 0:
    #        self.GetNextCommand()
        
    def GetNextCommand(self):        
        current_command, next_command, commands_left, new_data = self.ParseFile()
        f_out = open(self.filename, 'w')
        f_out.write(new_data)
        f_out.close()
        return next_command

    #def __iter__(self):
    #    return self
            
    #def next(self):
    #    self.next_command = self.GetNextCommand()
    #    if self.next_command == None:
    #        raise StopIteration
    #    else:
    #        self.last = self.next_command
    #        return self.next_command
            
    #def popleft(self):
    #    return next(self)


if __name__ == '__main__':
    overlord = GasLoadingOverlord("% ")
    icp = overlord.do_icp_cmd
    rpsf = overlord.run_py_seq_file
    overlord.start()
    overlord.join()
