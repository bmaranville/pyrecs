#############################################################################################
# 
# Constants
# 
#############################################################################################

DET_DIMX = 128;
DET_DIMY = 128;
DET_SIZE = DET_DIMX * DET_DIMY;

#
# NISTO apparently uses a buffer size of 2^16 (64K). This means that the maximum block size it
# is capable of transferring is (2^16 - 12). The 12 bytes are for the length, op, and arg ints
# that preceed the returned data block.

# This could probably be raised to 65536/bytes_per_int = 16384
XFER_BLOCK_SIZE = 1024;
MAXBUF = 2**16

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


# Define error codes

ERR_UNDEF	= 0 #/* Undefined error */
ERR_ACCESS	= 1 #/* */
ERR_BADOP	= 2 #/* Bad opcode */
ERR_BADID	= 3 #/* Bad parameter */
ERR_STATE	= 4 #/* Run state not appropriate for action */
ERR_ARGS	= 5 #/* Wrong number of arguments */
ERR_INVAL   = 6 #/* Bad value for parameter */
ERR_BOUNDS  = 7 #/* Boundary error */

ERR_CODES = {
    0: "Undefined error"
    1: "Access error"
    2: "Bad opcode"
    3: "Bad parameter"
    4: "Run state not appropriate for action"
    5: "Wrong number of arguments"
    6: "Bad value for parameter"
    7: "Boundary error"
}


# Command Syntax defines

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
#SERVERHOST = "detector"
SERVERHOST= "129.6.120.160"
CMDWAIT = 50000

import socket, struct, time, os
INTSIZE = struct.calcsize("I")
DEBUG = False

import socket, struct, time, os
import StringIO

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
	self.connection.shutdown(socket.SHUT_RDWR)
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
        if DEBUG: print 'SEND: opcode = ' + str(opcode) + ', prm = ' + str(prm) + ', data = ' + str(data)
        if connection.send(mesg) != n:
            print "error: send_PKG: not all bytes written"
            
        
    def recvPKG(self, connection):
        mesg_lenbytes = connection.recv(INTSIZE)
        if len(mesg_lenbytes) < INTSIZE: 
            if DEBUG: print str(len(mesg_lenbytes)) + ' mesglen bytes received - expecting %d' % INTSIZE
            return (None, None, None)
            
        mesg_len = self.frombinstr(mesg_lenbytes)
        if DEBUG: print "message coming: requested length = ", mesg_len
        #mesg = connection.recv(mesg_len)
        mesg = connection.recv(MAXBUF)
        if DEBUG: print "actual length: ", len(mesg)
        if len(mesg) < 2*INTSIZE:
            if DEBUG: print "message too short - returning"
            return (0, 0, None)
        opcode = self.frombinstr(mesg[:INTSIZE])
        prm = self.frombinstr(mesg[INTSIZE:2*INTSIZE])
        data_offset = 2*INTSIZE
        data_len = mesg_len - (2*INTSIZE)
        if (opcode == OP_CMD) or (opcode == OP_ERR): 
            data_len -= 1
            data_offset += 1
        if data_len > 0:
            data = mesg[data_offset:data_offset + data_len]
        else: data = ""
            
        if DEBUG:
            print 'RECV: opcode = ' + str(opcode) + ', prm = ' + str(prm) + ', data = ' + str(data)
        return opcode, prm, data
        
    def recvHIST(self, connection):
        data = StringIO.StringIO()
        expected_length = self.dims[0] * self.dims[1] * INTSIZE
        if DEBUG: print 'expected length: ', str(expected_length)
        while 1:
            opcode, prm, newdata = self.recvPKG(connection)
            if not opcode == OP_DAT: break
            data.write(newdata)
            if DEBUG: print "buflength: ", data.tell()
            if data.tell() > expected_length: break
            self.sendPKG(connection, OP_ACK, prm)
        data.seek(0)
        datastr = data.read()
        hist = (self.numpy.fromstring(datastr, self.numpy.uint32)).byteswap()
        self.sendPKG(connection, OP_ACK, prm)
        return hist

    def AIM_INIT(self):
        connection = self.tcp_open()
        self.tcp_close()
        time.sleep(self.waittime)
        
    def AIM_CLEAR(self):
        connection = self.tcp_open()
        self.sendPKG(connection, OP_CMD, CMD_CLEAR)
        retn = self.recvPKG(connection)
        self.tcp_close()
        time.sleep(self.waittime)
        
    def AIM_ARM(self):
        connection = self.tcp_open()
        self.sendPKG(connection, OP_CMD, CMD_START)
        retn = self.recvPKG(connection)
        self.tcp_close()
        time.sleep(self.waittime)
        
    def AIM_DISARM(self):
        connection = self.tcp_open()
        self.sendPKG(connection, OP_CMD, CMD_STOP)
        retn = self.recvPKG(connection)
        self.tcp_close()
        time.sleep(self.waittime)

    def AIM_DIMS(self):
        # this command changed from HISTO to NISTO...
        connection = self.tcp_open()
        self.sendPKG(connection, OP_CMD, CMD_GET, self.tobinstr(PAR_DIMENSIONS))
        opcode, prm, newdata = self.recvPKG(connection)
        dims = (self.numpy.fromstring(newdata, self.numpy.uint32)).byteswap()
        self.tcp_close()
        self.dims = dims
        time.sleep(self.waittime)
        return dims
        
    def AIM_XFER(self):
        # this has changed from HISTO to NISTO
        #blocksize = 1024
        connection = self.tcp_open()
        self.sendPKG(connection, OP_CMD, CMD_XFER, self.tobinstr(XFER_BLOCK_SIZE))
        start_time = time.time()
        retn = self.recvHIST(connection)
        end_time = time.time()
        xfer_time = end_time - start_time
        print 'data transferred in %.1f seconds\n' % xfer_time
        self.tcp_close()
        self.data = retn
        if self.dims == None: # populate on first use
            time.sleep(self.waittime)
            self.dims = self.AIM_DIMS()
        try: 
            self.data.shape = self.dims
        except:
            pass
        time.sleep(self.waittime)
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
        
        

"""
int
   242 sendPKG(int sockfd, int opcode, int prm, void * data, int ldata) 
   243 {
   244   unsigned char * ptr;
   245   int retn, n;
   246 
   247   bzero(mesg,sizeof(mesg)); /* Clear out data */
   248   ptr = &mesg[0];
   249   if (data == NULL) ldata = 0;
   250   n = 3 *sizeof(uint32_t) + ldata;
   251   if ((opcode == OP_CMD) || (opcode == OP_ERR)) n += 1;
   252   *(uint32_t *)ptr = (uint32_t) htonl(n - sizeof(uint32_t)); 
   253   ptr += sizeof(uint32_t);
   254   *(uint32_t *)ptr = (uint32_t) htonl(opcode);           
   255   ptr += sizeof(uint32_t);
   256   *(uint32_t *)ptr = (uint32_t) htonl(prm);              
   257   ptr += sizeof(uint32_t);
   258 
   259   /* Write data as-is */
   260   if (data != NULL) { 
   261     memcpy(ptr,data,ldata); 
   262     ptr += ldata;
   263   }
   264   if ((opcode == OP_CMD) || (opcode == OP_ERR)) *ptr = EOS; /* End of pkg */
   265 
   266   if (traceflag&2) {
   267     printf("SendPKG:"); phex((char *)mesg,n);
   268   }
   269   if ((retn = write(sockfd,mesg,n)) != n) err_dump("send_PKG:write");
   270   return retn;
   271 }
   272 
   273 int
   274 recvPKG(int sockfd, int * len, int * opcode, int * prm, void * data) {
   275   int n;
   276   char * ptr;
   277   fd_set fds;  
   278   struct timeval timeout;
   279 
   280   FD_ZERO(&fds); FD_SET(sockfd,&fds);
   281   timeout.tv_sec = to_sec; timeout.tv_usec=0;
   282   n=select(sockfd+1,&fds,(fd_set*)NULL,(fd_set*)NULL,&timeout);
   283   if (n<0) {
   284     fprintf(stderr,"recvPKG: select failed\n");
   285     return -1;
   286   }
   287   if (n==0) {
   288     if (traceflag) { printf("recvPKG: timed out\n"); }
   289     return -2; /* timeout */
   290   }
   291 
   292   bzero(mesg,sizeof(mesg));
   293   n = -1;
   294   while(n<0){
   295     n = read(sockfd, (char *)mesg, sizeof(mesg));
   296   }
   297   if (n == 0) return -3; /* Empty message */
   298 
   299   /* Check number of bytes read */
   300   ptr = &mesg[0];
   301   *len = ntohl(*(uint32_t *)ptr);     ptr += sizeof(uint32_t);
   302   *opcode = ntohl(*(uint32_t *) ptr); ptr += sizeof(uint32_t);
   303   *prm    = ntohl(*(uint32_t *) ptr); ptr += sizeof(uint32_t);
   304   *len   -= 2 * sizeof(uint32_t); /* Return length of data, NOT package */
   305   if ((*opcode == OP_CMD) || (*opcode == OP_ERR)) *len -= 1;
   306   if (data != NULL) {
   307     /* Pass data as-is */
   308     memcpy(data, ptr, (*len));
   309   }
   310 
   311   if (traceflag&2) {
   312     printf("recvPKG:"); phex((char *)mesg,*len + 2*sizeof(uint32_t));
   313     printf("recvPKG: OP = %d PRM = %d len = %d recvlen = %d\n",
   314 	   *opcode, *prm, *len, n);
   315   }
   316   
   317   return *opcode;
   318 }
"""
