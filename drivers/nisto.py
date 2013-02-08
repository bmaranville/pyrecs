#############################################################################################
# 
# Constants
# 
#############################################################################################
 

INT_BYTES = Integer.SIZE / Byte.SIZE;

DET_DIMX = 128;
DET_DIMY = 128;
DET_SIZE = DET_DIMX * DET_DIMY;
DET_SIZE_BYTES = DET_SIZE * INT_BYTES;

#
# NISTO apparently uses a buffer size of 2^16 (64K). This means that the maximum block size it
# is capable of transferring is (2^16 - 12). The 12 bytes are for the length, op, and arg ints
# that preceed the returned data block.

XFER_BLOCK_SIZE = 32768;

""" All of the following constants were lifted straight from the DALI driver """

# Define opcodes

""" Do nothing """
OP_NOP = 0;
""" Plaintext command """
OP_CMD = 1;
""" Acknowledgement """
OP_ACK = 2;
""" Data """
OP_DAT = 3;
""" Error, see error codes """
OP_ERR = 4;

"""
 * Command Syntax defines
 """
""" No operation """
CMD_NOP = 0;
""" Arm """
CMD_START = 1;
""" Disarm """
CMD_STOP = 2;
""" Clear remote histogram """
CMD_CLEAR = 3;
""" Transfer histogram data """
CMD_XFER = 4;
""" Set a parameter """
CMD_SET = 5;
""" Get a parameter """
CMD_GET = 6;

#
# Command Parameters
# From Remote control of NCNR Detector Server (v0.9)
# by Nick Maliszewskyj 2/25/2009
#

""" System status word """
PAR_STATUS = 0;
""" Rank o fPosition Histogram """
PAR_RANK = 1;
""" Dimensions of Position Histogram """
PAR_DIMENSIONS = 2;
""" Mode of data tranfer: histogram(default) or raw events """
PAR_TRANSFERMODE = 3;
""" Which histogram to transfer """
PAR_TRANSFERSEL = 4;
""" Bounds of region of interest """
PAR_ROI = 5;
""" Preset counts in ROI (default 0=not present """
PAR_ROIPRESET = 6;
""" Number of events binned in ROI """
PAR_ROICOUNTS = 7;
""" Total number of events over the detector """
PAR_TOTALCOUNTS = 8;
""" Histogram with timeslicing (true/false) """
PAR_TIMESLICING = 9;
""" Number of time bins (default=1) """
PAR_NTIMEBINS = 11;
""" Constant time bin width (in microseconds) """
PAR_TIMEBINWIDTH = 12;
""" Array of time bin widths (in microseconds) """
PAR_TIMEBINS = 13;
""" State of shutter (1=open, 0=closed) """
PAR_SHUTTERSTATE = 16;
""" CPS at which shutter will automatically close """
PAR_SHUTTERTHRESHOLD = 17;
""" State of HV bias (1=on, 0=off) """
PAR_HVBIASSTATE = 20;
""" CPS at which HV bias will be turned off """
PAR_HVBIASTHRESHOLD = 21;

""" Byte appended to the end of OP_CMD and OP_ERR messages """
END_OF_STREAM = 0;

# from tcp_aim.c
SERVERPORT = 20000
SERVERHOST = "detector"
CMDWAIT = 500000

INTSIZE = 4
DEBUG = False

class NISTO:
    """ reading and controlling area detectors using NISTO protocol """
    
    # this ends up being almost identical to how we talked to HISTO?
    
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
        
    def sendPKG(self, connection, opcode, prm, data = None):
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
        #if (opcode == OP_CMD) or (opcode == OP_ERR): mesg += struct.pack('b', END_OF_STREAM)
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
        # this command changed from HISTO to NISTO...
        connection = self.tcp_open()
        self.sendPKG(connection, OP_CMD, CMD_GET, struct.pack('I', PAR_DIMENSIONS))
        retn = self.recvHIST(connection)
        self.tcp_close()
        self.dims = tuple(retn)
        time.wait(self.waittime)
        return retn
        
    def AIM_XFER(self):
        # this has changed from HISTO to NISTO
        #blocksize = 1024
        connection = self.tcp_open()
        self.sendPKG(connection, OP_CMD, CMD_XFER, struct.pack('I', XFER_BLOCK_SIZE))
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
        
        

