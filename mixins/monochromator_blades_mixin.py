from pyrecs.drivers.EZ_motor import EZStepper
import collections
#import functools
#from mixin import MixIn
MONO_BLADE_LINE = None
MONO_PORT_FALLBACK = '/dev/ttyUSB4'
NUM_BLADES = 13

def update(d, u):
    """ recursive dictionary update """
    for k, v in u.iteritems():
        if isinstance(v, collections.Mapping):
            r = update(d.get(k, {}), v)
            d[k] = r
        else:
            d[k] = u[k]
    return d
    
ICP_CONVERSIONS = {
    'arg_commands': {
        'pm': { 'numargs': [0,1], 'pyrecs_cmd': 'PrintMonoBladeAngle' },
        'dm': { 'numargs': [2], 'pyrecs_cmd': 'DriveMonoBlade' },
        'setm': { 'numargs': [2], 'pyrecs_cmd': 'SetMonoBladePosition' },
        'fpm': { 'numargs': [3,4], 'pyrecs_cmd': 'FindPeakMonoBlade' }
    },
        
    'en_dis_commands': {
    },

    'increment_commands': {},

    'tied_commands': {},
}

class MonoBladeMixin:
    """ 
    Adds motor control of monochromator blades to InstrumentController
    
    Use as a Mixin class (needs methods from InstrumentController), i.e.
    via Multiple Inheritance mechanism:
    
    class NewIC(InstrumentController, MonoBladeMixin):
        def __init__(self):
            InstrumentController.__init__(self)
            MonoBladeMixin.__init__(self)
        
    or use helper function Mixin:
    MixIn(InstrumentController, MonoBladeMixin)
    """
    
    def __init__(self):
        rs232conf_line = MONO_BLADE_LINE
        if MONO_BLADE_LINE is None:
            port = MONO_PORT_FALLBACK
        else:
            port = self.ip.GetSerialPort(rs232conf_line)
        self.mbc = EZStepper(port)
        self.mbc.num_mots = NUM_BLADES
        self.blade_names = ['b%d' % (i+1) for i in range(NUM_BLADES)]
        self.blade_numbers = range(1, NUM_BLADES+1)
        self.blade_lookup = dict(zip(self.blade_names, self.blade_numbers))
        
        # ICP commands:
        self.dm = self.mbc.MoveMotor
        self.setm = self.SetMonoBladePosition
        self.pm = self.PrintMonoBladeAngle
        self.fpm = self.FindPeakMonoBlade
        
        # hook into the IC device registry:
        self.device_registry.update( {'monoblades':
                                {'names': self.blade_names, 'updater': self.DriveMonoBladeByName, 'getter': self.GetMonoBladeByName  }} )
        self.icp_conversions = update(self.icp_conversions, ICP_CONVERSIONS)
        
    def SetMonoBladePosition(self, bladenum, pos):
        self.mbc.SetMotorPos(bladenum, pos)
        self.state['b%d' % (bladenum,)] = pos
        
    def DriveMonoBladeByName(self, blades_to_move, position_list):
        blade_list = [self.blade_lookup[s] for s in blades_to_move]
        # i.e. 'b3' is blade 3
        for b,p in zip(blade_list, position_list):
            self.dm(b, p)
            self.state['b%d' % (b,)] = p
            
    def GetMonoBladeByName(self, blade_name, poll=False):
        bladenum = self.blade_lookup[blade_name]
        pos = self.mbc.GetMotorPos(bladenum)
        #self.state['b%d' % (bladenum,)] = pos
        return pos
    
    def DriveMonoBlade(self, bladenum, pos):
        self.mbc.MoveMotor(bladenum, pos)
            
    def PrintMonoBladeAngle(self, bladenum=None):
        if bladenum:
            pos = self.mbc.GetMotorPos(bladenum)
            self.write('B%02d=%8.3f\n' % (bladenum, pos))
            self.state['b%d' % (bladenum,)] = pos
        else:  # no motor specified - get them all
            out_line = ''
            for i, b in enumerate(self.blade_numbers):
                pos = self.mbc.GetMotorPos(b)
                out_line += 'B%02d=%8.3f ' % (b, pos)
                self.state['b%d' % (b,)] = pos
                if ( (i+1) % 5 == 0) or ((i+1) == len(self.blade_numbers)):
                    self.write(out_line + '\n')
                    out_line = ''
        
    def FindPeakMonoBlade(self, bladenum, mrange, mstep, duration=-1, auto_drive_fit = False):
        """the classic ICP function (fp), specific to monochromator blades
        It can be suspended with ctrl-z (ctrl-z again to resume)
        or the 'finishup' routine skips the rest of the points and fits now (ctrl-\)
        Abort (ctrl-c) works the same as usual """
        numsteps = int( abs(float(mrange) / (mstep)) + 1)
        movable = 'b%d' % (bladenum,)
        val_now = self.mbc.GetMotorPos(bladenum)
        self.state[movable] = val_now
        mstart = val_now - ( int(numsteps/2) * mstep)
        comment = 'FP'
        Fitter = self.gauss_fitter  
        self.PeakScan(movable, numsteps, mstart, mstep, duration, val_now, comment=comment, Fitter=Fitter, auto_drive_fit=auto_drive_fit)
        
    def RapidScanMonoBlade(self, bladenum=None, start_angle=None, stop_angle=None, client_plotter=None):
         
    #def RapidScan(self, motornum = None, start_angle = None, stop_angle = None, client_plotter = None, reraise_exceptions = False, disable=AUTO_MOTOR_DISABLE):
        """ new, non-ICP function: count while moving.
                returns: (position, counts, elapsed_time) """
        
        (tmp_fd, tmp_path) = tempfile.mkstemp() #temporary file for plotting
        title = 'ic.RapidScanMonoBlade(%d, %.4f, %.4f)' % (bladenum, start_angle, stop_angle)
        
        position_list = []
        ptime_list = []
        cum_counts_list = []
        counts_list = []
        cps_list = []
        ctime_list = []
        self.DriveMonoBladeByName(['b%d' % (monoblade,)], [start_angle])
        self.scaler.ResetScaler()
        self.scaler.CountByTime(-1)
        start_time = time.time()
        
        t1 = time.time() - start_time
        cum_counts_list.append( self.scaler.GetCounts()[2] )
        t2 = time.time() - start_time
        ctime = (t1+t2)/2.0
        ctime_list.append(ctime)
        pos =  self.mbc.GetMotorPos(bladenum)
        position_list.append(pos)
        t3 = time.time() - start_time
        ptime = ((t2+t3)/2.0)
        
        hard_stop = stop_angle
        self.mbc.MoveMotor(bladenum, hard_stop)
        
        pos = start_angle
        while self.mbc.CheckMoving(bladenum):
        #soft_pos = start_angle
        #tol = self.ip.GetMotorTolerance(motornum)
        #while 1:
            if self._aborted:
                self.write("aborted")
                #if not reraise_exceptions:
                #    self._aborted = False
                break
            t1 = time.time() - start_time
            cum_counts_list.append( self.scaler.GetCounts()[2] )
            t2 = time.time() - start_time
            new_pos =  self.mbc.GetMotorPos(bladenum)
            t3 = time.time() - start_time
            
            new_count = cum_counts_list[-1] - cum_counts_list[-2]
            counts_list.append(new_count)
            new_ctime = (t1+t2)/2.0
            ctime_list.append(new_ctime)
            new_cps = new_count/(new_ctime - ctime)
            cps_list.append(new_cps)
            # we want the timestamp of the center of the counts window
            t_center = (new_ctime + ctime)/2.0
            
            new_ptime = (t2+t3)/2.0
            pslope = (new_pos - pos) / (new_ptime - ptime)
            # now we want to calculate the position at the center of the counts window
            estimated_pos = pos + ((t_center - ptime) * pslope) # linearly interpolate, 
            # based on count timestamp vs. position timestamp
            position_list.append(estimated_pos)
            
            self.write(str(position_list[-1]) + '\t'+ str(cps_list[-1]))
            out_str = '%.4f\t%.4f' % (estimated_pos, new_cps)
            tmp_file = open(tmp_path, 'a')
            tmp_file.write(out_str + '\n')
            tmp_file.close()
            self.updateGnuplot(tmp_path, title)
            
            #if abs(new_soft_pos - soft_pos) <= tol:
            #   break
            pos = new_pos
            ptime = new_ptime
            ctime = new_ctime
            time.sleep(0.2)
        
        self.scaler.AbortCount()
        count_time, monitor, counts = self.scaler.GetCounts()
        self.scaler.GetElapsed()
        self.write('count time: %.3f' % count_time)
        self.mbc.StopMotor(bladenum)
        while self.mbc.CheckMoving(bladenum) == True: # make sure we're stopped before disabling
            time.sleep(self.loopdelay)
       
        return position_list, cps_list, ctime_list 
           
# for compatibility and easy mixing:
mixin_class = MonoBladeMixin
# to use:
""" 
from pyrecs.InstrumentController_unmixed import *
ic = InstrumentController()
from pyrecs.mixins import monochromator_blades_mixin
InstrumentController.__bases__ = (monochromator_blades_mixin.MonoBladeMixin,)
monochromator_blades_mixin.MonoBladeMixin.__init__(ic)
"""
