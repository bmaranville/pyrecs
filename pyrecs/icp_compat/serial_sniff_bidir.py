import serial
import time, datetime
import threading

baudrate = 9600
parity = 'N'
bytesize = 8
stopbits = 1

eol_strings = ['\n', '\r']

""" run this command:
socat pty,link=/tmp/ttyV0,raw,echo=0 pty,link=/tmp/ttyV1,raw,echo=0
"""

class serial_sniff(object):
    def __init__(self, port1='/dev/ttyS0', port2='/tmp/ttyV0', input_filename='input.txt', output_filename='output.txt'):
        self.s1 = serial.Serial(port1, baudrate=baudrate, parity=parity, bytesize=bytesize, stopbits=stopbits)
        self.s2 = serial.Serial(port2, baudrate=baudrate, parity=parity, bytesize=bytesize, stopbits=stopbits)
        self.log_input = open(input_filename, 'a')
        self.log_output = open(output_filename, 'a')
    
        self.set_input_timestamp = [True]
        self.set_output_timestamp = [True]
        self.alive = True
        self.time_fmt = "%Y-%m-%d %T,%f: "
    
    def capture(self, source, target, logfile, set_timestamp):
        s_in = source
        s_out = target
        while self.alive:
            try:
                byte_in = s_in.read(1)
                s_out.write(byte_in)
                if set_timestamp[0] == True and not byte_in in eol_strings:
                    logfile.write(datetime.datetime.now().strftime(self.time_fmt))
                    logfile.flush()
                    set_timestamp[0] = False
                logfile.write(byte_in)
                if byte_in in eol_strings:
                    set_timestamp[0] = True
            except KeyboardInterrupt:
                self.alive = false
                break
                
    def start(self):
        self.alive = True
        self.thread1 = threading.Thread(target=self.capture, args=(self.s1, self.s2, self.log_input, self.set_input_timestamp))
        self.thread1.setDaemon(1)
        self.thread1.start()
        self.thread2 = threading.Thread(target=self.capture, args=(self.s2, self.s1, self.log_output, self.set_output_timestamp))
        self.thread2.setDaemon(1)
        self.thread2.start()
    
    def stop(self):
        self.alive = False
        self.log_input.close()
        self.log_output.close()
        print "finished"
   
class serial_sniff_singlefile(object):
    def __init__(self, port1='/dev/ttyS0', port2='/tmp/ttyV0', log_filename='serial_log.txt'):
        self.s1 = serial.Serial(port1, baudrate=baudrate, parity=parity, bytesize=bytesize, stopbits=stopbits)
        self.s2 = serial.Serial(port2, baudrate=baudrate, parity=parity, bytesize=bytesize, stopbits=stopbits)
        self.log = open(log_filename, 'a')
        self.lock = threading.Lock()
        self.input_buffer = ""
        self.output_buffer = ""
            
        self.set_input_timestamp = [False]
        self.set_output_timestamp = [False]
        self.alive = True
        self.time_fmt = "%Y-%m-%d %T,%f: "
    
    def capture(self, source, target, str_buffer, id_str, set_timestamp):
        s_in = source
        s_out = target
        while self.alive:
            try:
                byte_in = s_in.read(1)
                s_out.write(byte_in)
                if set_timestamp[0] == True and not byte_in in eol_strings:
                    timestamp = datetime.datetime.now().strftime(self.time_fmt)
                    with self.lock:
                        # always end the log line with a \n character
                        self.log.write(timestamp + id_str + str_buffer.rstrip() + '\n')
                        self.log.flush()
                    set_timestamp[0] = False
                    str_buffer = ""
                str_buffer += byte_in
                if byte_in in eol_strings:
                    set_timestamp[0] = True
            except KeyboardInterrupt:
                self.alive = false
                break
                
    def start(self):
        self.alive = True
        self.thread1 = threading.Thread(target=self.capture, args=(self.s1, self.s2, self.input_buffer, "In <== ", self.set_input_timestamp))
        self.thread1.setDaemon(1)
        self.thread1.start()
        self.thread2 = threading.Thread(target=self.capture, args=(self.s2, self.s1, self.output_buffer, "Out ==> ", self.set_output_timestamp))
        self.thread2.setDaemon(1)
        self.thread2.start()
    
    def stop(self):
        self.alive = False
        self.log.close()
        print "finished"
 
if __name__ == '__main__': 
    s = serial_sniff_singlefile()
    s.start()           
