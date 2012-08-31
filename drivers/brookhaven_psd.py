 # Echo server program
import socket, struct, time, os

# from tcp_io.h in ICP source

# $Id: brookhaven_psd.py,v 1.1 2011/03/02 23:29:53 bbm Exp $ 
#ifndef _TCP_IO_H
#define _TCP_IO_H

#/*
# * Define opcodes
# */
OP_CMD = 1 #/* Plaintext command */
OP_ACK = 2 #/* Acknowledgement */
OP_DAT = 3 #/* Data */
OP_ERR = 4 #/* Error, see error codes */
OP_SET = 5 #/* Set parameters */
OP_GET = 6 #/* Get parameters */

#/*
# * Define error codes
# */
ERR_UNDEF = 0
ERR_ACCESS= 1
ERR_BADOP = 2
ERR_BADID = 3

#/*
# * Command Syntax defines
# */
CMD_NOP     = 0 #/* No operation */
CMD_START   = 1 #/* Arm */
CMD_STOP    = 2 #/* Disarm */
CMD_CLEAR   = 3 #/* Clear remote histogram */
CMD_XFER    = 4 #/* Transfer histogram data */
CMD_STAT    = 5 #/* Get status */
CMD_SPY     = 6 #/* Get time of last transfer */
CMD_WRITE   = 7 #/* Write XML file with settings */

SET_SIZ    = 0

GET_RANK   = 0 #/* Get rank of the data array */
GET_DIMS   = 1 #/* Get dimension array */

#/*
# * "Boundary" defines
# */

MAXBUF    = 2048        #/* Xmit and recv buffer length (in longwords)*/
MAXBLOCK  =  256
EOS       =    0


# from tcp_aim.c
SERVERPORT = 20000
SERVERHOST = "detector"
CMDWAIT = 500000

INTSIZE = 4
DEBUG = False

class BrookhavenDetector:
    """ holds the server address and port for the Brookhaven area detector
    also contains member functions for arm, disarm, read, etc..."""
    import numpy
    def __init__(self, path = None, server_addr = SERVERHOST, server_port = SERVERPORT):
        if path is None:
            path = os.getcwd()
        self.path = path
        self.host = server_addr
        self.port = server_port
        self.connection = None
        self.waittime = CMDWAIT / 1000000.0  # originally in microseconds
        self.dims = None
        self.data = None
        self.xmin = 1 # window default values - doesn't set dimensions of data
        self.xmax = 608
        self.ymin = 1
        self.ymax = 512
        
    def tobinstr(self, datum):
	    return struct.pack('I', socket.htonl(datum))
	    
    def frombinstr(self, datum):
        return socket.ntohl(struct.unpack('I', datum)[0])
        
    def tcp_open(self):
        self.connection = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.connection.connect((self.host, self.port))
        return self.connection
        
    def tcp_close(self):
        self.connection.close()
        
    def sendPKG(self, connection, opcode, prm, data = None, ldata = 0):
        if data == None:
            ldata = 0
        else:
            ldata = len(data)
        n = 3 * INTSIZE + ldata
        if (opcode == OP_CMD) or (opcode == OP_ERR): n += 1
        mesg_len = n - INTSIZE
        
        mesg = ''
        mesg += self.tobinstr(mesg_len)
        mesg += self.tobinstr(opcode)
        mesg += self.tobinstr(prm)
        
        if data:
            mesg += data
        
        if (opcode == OP_CMD) or (opcode == OP_ERR): mesg += '\x00'
        if DEBUG: print mesg
        if connection.send(mesg) != n:
            print "error: send_PKG: not all bytes written"
            
        
    def recvPKG(self, connection):
        mesg = connection.recv(MAXBUF)
        mesg_len = self.frombinstr(mesg[:INTSIZE])
        opcode = self.frombinstr(mesg[INTSIZE:2*INTSIZE])
        prm = self.frombinstr(mesg[2*INTSIZE:3*INTSIZE])
        data_offset = 3*INTSIZE
        data_len = mesg_len - (2*INTSIZE)
        if (opcode == OP_CMD) or (opcode == OP_ERR): 
            data_len -= 1
            data_offset += 1
        if data_len > 0:
            data = mesg[data_offset:data_offset + data_len]
        else: data = 0
            
        if DEBUG:
            print 'opcode = ' + str(opcode) + ', prm = ' + str(prm) + ', data = ' + str(data)
        return opcode, prm, data
        
    def recvHIST(self, connection):
        data = ''
        while 1:
            opcode, prm, newdata = self.recvPKG(connection)
            if not opcode == OP_DAT: break
            data += newdata
            if DEBUG: print prm
            self.sendPKG(connection, OP_ACK, prm)
        hist = (self.numpy.fromstring(data, self.numpy.uint32)).byteswap()
        hist
        return hist

    def AIM_INIT(self):
        connection = self.tcp_open()
        self.tcp_close()
        time.wait(self.waittime)
        
    def AIM_CLEAR(self):
        connection = self.tcp_open()
        self.sendPKG(connection, OP_CMD, CMD_CLEAR)
        retn = self.recvPKG(connection)
        self.tcp_close()
        time.wait(self.waittime)
        
    def AIM_ARM(self):
        connection = self.tcp_open()
        self.sendPKG(connection, OP_CMD, CMD_START)
        retn = self.recvPKG(connection)
        self.tcp_close()
        time.wait(self.waittime)
        
    def AIM_DISARM(self):
        connection = self.tcp_open()
        self.sendPKG(connection, OP_CMD, CMD_STOP)
        retn = self.recvPKG(connection)
        self.tcp_close()
        time.wait(self.waittime)

    def AIM_DIMS(self):
        connection = self.tcp_open()
        self.sendPKG(connection, OP_GET, GET_DIMS)
        retn = self.recvHIST(connection)
        self.tcp_close()
        self.dims = tuple(retn)
        time.wait(self.waittime)
        return retn
        
    def AIM_XFER(self):
        blocksize = 1024
        connection = self.tcp_open()
        self.sendPKG(connection, OP_CMD, CMD_XFER, struct.pack('I', blocksize), 4)
        start_time = time.time()
        retn = self.recvHIST(connection)
        end_time = time.time()
        xfer_time = end_time - start_time
        print 'data transferred in %.1f seconds\n' % xfer_time
        self.tcp_close()
        self.data = retn
        if self.dims == None: # populate on first use
            self.dims = self.AIM_DIMS()
        self.data.shape = self.dims
        time.wait(self.waittime)
        return retn
        
    def AIM_SAVE(self, filename = 'asd.raw'):
        fn = os.path.join(self.path, filename)
        if not self.data == None:
            f_out = open(fn, 'w')
            self.data.tofile(f_out, sep =' ', format = '%d')
            f_out.close()
        
    def CountsInROI(self):
        if not self.data == None:
            counts = self.numpy.sum(self.data[self.xmin:self.xmax,self.ymin:self.ymax])
            return counts
        else:
            return 0

        
