import struct
import functools
import pprint

NUM_IBUFS = 30
BUF_SINGLE_CHARS = 320
# this is the total number of characters per individual buffer in a file - for IBUFFERS = 320
FLOAT_ZERO = 1.0e-7

class ibuf_single(object):
    """class to hold, read, write ICP-style IBUFFERs"""
    labels = ['description', 'spacer',  
                       'a1start', 'a2start', 'a3start', 'a4start', 'a5start', 'a6start', 
                       'a1step', 'a2step', 'a3step', 'a4step', 'a5step', 'a6step',
                       'numpoints', 'H0', 'T0', 'IncT', 'Wait', 'Hld0', 'Error',
                       'monit', 'Prefac', 'Type',
                       'p1exec','p2exec','p3exec','p4exec','Hinc','u6','u7', 'Hld']
    formats = ['50s', '2s',
                        'f', 'f', 'f', 'f', 'f', 'f',
                        'f', 'f', 'f', 'f', 'f', 'f',
                        'f', 'f', 'f', 'f', 'f', 'f', 'f',
                        'f', 'f', '4s',
                        'i', 'i', 'i', 'i', 'f', 'f', 'f', 'f' ]
    
    def __init__(self, binary_formatted_vals = None, data = None):
        #=======================================================================
        # self.labels = ['description', 'spacer',  
        #               'a1start', 'a2start', 'a3start', 'a4start', 'a5start', 'a6start', 
        #               'a1step', 'a2step', 'a3step', 'a4step', 'a5step', 'a6step',
        #               'numpoints', 'H0', 'T0', 'IncT', 'Wait', 'Hld0', 'Error',
        #               'monit', 'Prefac', 'Type',
        #               'p1exec','p2exec','p3exec','p4exec','Hinc','u6','u7', 'Hld']
        # 
        # self.formats = ['50s', '2s',
        #                'f', 'f', 'f', 'f', 'f', 'f',
        #                'f', 'f', 'f', 'f', 'f', 'f',
        #                'f', 'f', 'f', 'f', 'f', 'f', 'f',
        #                'f', 'f', '4s',
        #                'i', 'i', 'i', 'i', 'f', 'f', 'f', 'f' ] 
        #=======================================================================
        
        self.format_str = ''
        for fmt in self.formats:
            self.format_str += fmt
            
        self.total_length = BUF_SINGLE_CHARS

        self.data = {}
        self.default_values = ['description                                       ','\x00\x00',
                               0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
                               0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
                               101, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
                               1000, 1, 'TIME',
                               0, 0, 0, 0, 0.0, 0.0, 0.0, 0.0]
        if binary_formatted_vals:
            self.LoadFromBinaryString(binary_formatted_vals)
        elif data is not None:
            self.data = data.copy()
        else:
            self.data = dict(zip(self.labels, self.default_values))
        for label in self.labels:
            object.__setattr__(self, label, None)
            
    def __getitem__(self, label=None):
        return self.data[label]
    
    def __setitem__(self, label, value):
        self.data[label] = value
        
    def __getattribute__(self, item):  
        if item in ibuf_single.labels:
            return self.__getitem__(item)
        else:
            return object.__getattribute__(self, item)
     
    def __setattr__(self, item, value):
        if item in ibuf_single.labels:
            self.__setitem__(item, value)
        else:
            object.__setattr__(self, item, value)
            
    def __repr__(self):
        return 'ibuf_single( data=\n' + pprint.pformat(self.data) + ')\n'
    
    def LoadFromBinaryString(self, binary_data):
        offset = 0
        for key, fmt in zip(self.labels, self.formats):
            self.data[key] = struct.unpack_from(fmt, binary_data, offset)[0]
            datalength = struct.calcsize(fmt)
            offset += datalength
    
    def LoadFromFile(self, input_file):
        bin_data = input_file.read(172)
        excess_data = input_file.read(148)
        self.LoadFromBinaryString(bin_data)
        
    def GetBinaryRepr(self):
        bin_data = ''
        offset = 0
        for key,fmt in zip(self.labels, self.formats):
            bin_data += struct.pack(fmt, self.data[key])
            offset += struct.calcsize(fmt)
        if offset < self.total_length:
            filler = '\x00' * (self.total_length - offset)
            bin_data += filler
        return bin_data
     
class many_bufs(object):
    """ class to hold a list of bufs (all of them, typically)
    and operate on them all at once
    
    ib = ibuffer.IBUFFER()
    ib.all['Prefac']
    (returns [5.0, 5.0, ... ])
    ib.all.Prefac
    (returns [5.0, 5.0, ... ])
    ib.all['Prefac'] = 1.0
    ib[0:2]['Prefac']
    (returns [1.0, 1.0])
    ib[0:2].Prefac
    (returns [1.0, 1.0])
    """
    __slots__ = ibuf_single.labels + ['_bufs']
    
    def __init__(self, list_of_bufs):
        self._bufs = list_of_bufs
        for label in ibuf_single.labels:
            object.__setattr__(self, label, None)
      
    def __getattribute__(self, item):  
        if item in ibuf_single.labels:
            return self.__getitem__(item)
        else:
            return object.__getattribute__(self, item)
     
    def __setattr__(self, item, value):
        if item in ibuf_single.labels:
            self.__setitem__(item, value)
        else:
            object.__setattr__(self, item, value)
    
    def __getitem__(self, label=None):
        return [buf[label] for buf in self._bufs]
    
    def __setitem__(self, label, value):
        print label, value
        for buf in self._bufs:
            buf[label] = value    
        
class IBUFFER:
    """class to hold, read and write IBUFFER.BUF
        each file contains NUM_IBUFS individual buffers"""
    
    def __init__(self, project_path = './', infile_name = 'IBUFFER.BUF', outfile_name = 'IBUFFER.BUF', num_buffers = NUM_IBUFS):
        self.num_buffers = num_buffers
        self.buffers = []
        self.infile_name = infile_name
        self.outfile_name = outfile_name
        self.single_buffer_length = BUF_SINGLE_CHARS
        
        # if an input file is specified, load it up
        if infile_name:
            self.LoadFromFile(infile_name)
        else: # or initialize a blank one
            for i in range(self.num_buffers):
                self.buffers.append( ibuf_single() )
        self.all = many_bufs(self.buffers)
    
    def __getitem__(self, i):
        if type(i) is slice:
            return many_bufs(self.buffers[i])
        else:
            return self.buffers[i]
        
    def __len__(self):
        return len(self.buffers)         
    
    def DeleteAllBuffers(self):
        for buffer in self.buffers:
            del(buffer)
        self.buffers = []
        
    def LoadFromFile(self, infile_name):
        self.DeleteAllBuffers()
        infile = open(infile_name, 'rb')
        for i in range(self.num_buffers):
            bin_data = infile.read(self.single_buffer_length)
            new_buf = ibuf_single(binary_formatted_vals = bin_data)
            self.buffers.append( new_buf )
            setattr(self, 'buf%d' % (i+1), new_buf)
        infile.close()
        
    def SaveToFile(self, outfile_name):
        """save data to chosen output file in IBUFFER.BUF format"""
        outfile = open(outfile_name, 'wb')
        for buffer in self.buffers:
            bin_data = buffer.GetBinaryRepr()
            outfile.write(bin_data)
        outfile.close()
        
    def Save(self):
        """overwrites input file"""
        self.SaveToFile(self.infile_name)
        
    def Reload(self):
        """reads from alread-defined input file.  Useful for Save->Reload loops"""
        self.LoadFromFile(self.infile_name)
        
class ibufSequence:
    """ create a sequence (iterator) from an ibuffer """
    def __init__(self, ibuf):
        self.ibuf = ibuf
        self.current_point = 0
        self.numpoints = self.ibuf.data['numpoints']
        self.motors_that_move = []
        self.keys = []
        self.inital_values = {}
        self.step_sizes = {}
        self.motor_now = {} # one list for motors
        self.motor_step = {} # with accompanying step sizes
        for i in range(6):
            motnum = i + 1 # motor counting starts at one, not zero
            start = float(ibuf.data['a%dstart' % motnum])
            self.motor_now[motnum] = start
            step = float(ibuf.data['a%dstep' % motnum])
            self.motor_step[motnum] = step
            stop = start + ((self.numpoints - 1) * step)
            if abs(step) > FLOAT_ZERO: # checking for zero in floating-point... 1e-10 is close enough?
                self.motors_that_move.append(motnum)
                
        self.vals_now = {}
        self.steps = {}
        self.keys = [] # another list for 
        if abs(self.ibuf.data['IncT']) > FLOAT_ZERO:
            self.keys.append('TEMP')
            self.vals_now['TEMP'] = self.ibuf.data['T0']
            self.steps['TEMP'] = self.ibuf.data['IncT']
        if abs(self.ibuf.data['Hinc']) > FLOAT_ZERO:
            self.keys.append('H-Field')
            self.vals_now['H-Field'] = self.ibuf.data['H0']
            self.steps['H-Field'] = self.ibuf.data['Hinc']
        if abs(self.ibuf.data['Hld']) > FLOAT_ZERO:
            self.keys.append('Hold')
            self.vals_now['Hold'] = self.ibuf.data['Hld']
            self.steps['Hold'] = 0.0
        self.next_point = {}
    
    def GetNextPoint(self):
        if self.current_point >= self.numpoints: 
            return None
        else:
            next_point = self.__getitem__(self.current_point)
            self.current_point += 1
            return next_point
            
        """ new_config = {}
        motor_new = {}
        for motnum in self.motors_that_move:
            motor_new[motnum] = self.motor_now[motnum] + self.motor_step[motnum] * self.current_point
        new_config['motors'] = motor_new
        for key in self.keys:
            new_config[key] = self.vals_now[key] + self.steps[key] * self.current_point
        self.current_point += 1
        return new_config """
    
    def __getitem__(self, pointnum):
        if (pointnum >= len(self)) or (pointnum < 0):
            raise IndexError
        new_config = {}
        motor_new = {}
        for motnum in self.motors_that_move:
            motor_new[motnum] = self.motor_now[motnum] + self.motor_step[motnum] * (pointnum + self.current_point)
        new_config['motors'] = motor_new
        for key in self.keys:
            new_config[key] = self.vals_now[key] + self.steps[key] * (pointnum + self.current_point)
        return new_config
            
    def __len__(self):
        return int(self.numpoints - self.current_point)
    
    def __iter__(self):
        return self
            
    def oldnext(self):
        if self.next_point == None:
            raise StopIteration
        else:
            self.next_point = self.GetNextPoint()
            self.last = self.next_point
            return self.next_point
     
    def next(self):
        self.next_point = self.GetNextPoint()
        self.last = self.next_point
        if self.next_point == None:
            raise StopIteration
        else:
            return self.next_point
                   
    def popleft(self):
        return next(self)
    
    def restart_iteration(self):
        self.current_point = 0        
       
       
        
