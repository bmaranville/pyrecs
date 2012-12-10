from pyrecs.drivers.rs232gpib import RS232GPIB
from pyrecs.drivers.FlipperDriver import FlipperPS
import functools
import collections
DEBUG = False

def update(d, u):
    """ recursive dictionary update """
    for k, v in u.iteritems():
        if isinstance(v, collections.Mapping):
            r = update(d.get(k, {}), v)
            d[k] = r
        else:
            d[k] = u[k]
    return d
#from mixin import MixIn
ICP_CONVERSIONS = {
    'arg_commands': {
        'pfcal': { 'numargs': [0,1], 'pyrecs_cmd': 'PrintFlipperCalibration' },
        'fcal': { 'numargs': [2,3], 'pyrecs_cmd': 'setFlipperCalibration' },
        'rm': { 'numargs': [0,1], 'pyrecs_cmd': 'getMonoFlippingRatio' },
        'ra': { 'numargs': [0,1], 'pyrecs_cmd': 'getAnaFlippingRatio' },
        'iset': { 'numargs': [2], 'pyrecs_cmd': 'iset' },
        'vset': { 'numargs': [2], 'pyrecs_cmd': 'vset' },
        'iget': { 'numargs': [1], 'pyrecs_cmd': 'iget' },
        'vget': { 'numargs': [1], 'pyrecs_cmd': 'vget' },
        'iscan': { 'numargs': [4,5], 'pyrecs_cmd': 'IScan' },
        'flm': {'numargs': [0], 'pyrecs_cmd': 'getFlipperMonochromator'},
        'fla': {'numargs': [0], 'pyrecs_cmd': 'getFlipperAnalyzer'}
    },
        
    'en_dis_commands': {
        'flm': { 'numargs': [1], 'pyrecs_cmd': 'setFlipperMonochromator' },
        'fla': { 'numargs': [1], 'pyrecs_cmd': 'setFlipperAnalyzer'},
    },

    'increment_commands': {},

    'tied_commands': {},
}
class FlipperControlMixin:
    """ 
    Adds flipper control (and polarization awareness) to InstrumentController
    
    Use as a Mixin class (needs methods from InstrumentController), i.e.
    via Multiple Inheritance mechanism:
    
    class NewIC(InstrumentController, FlipperControlMixin):
        def __init__(self):
            InstrumentController.__init__(self)
            FlipperControlMixin.__init__(self)
        
    or use helper function Mixin:
    MixIn(InstrumentController, FlipperControlMixin)
    """
    
    def __init__(self):
        term_line = int(self.ip.InstrCfg['term_line,'])
        #term_line = 4
        if self.gpib is None:
            self.gpib = RS232GPIB(serial_port = self.ip.GetSerialPort(term_line)) # initialize our gpib controller
        #num_flipper_ps = len(self.ip.GetFcal())
        num_pol_ps = int(self.ip.InstrCfg['#pol_ps'])
        self.ps_names = ['ps%d' %i for i in range(1, num_pol_ps+1)]
        self.ps_lookup = dict(zip(self.ps_names, range(num_pol_ps)))
        self.flipper_ps = []
        for i in range(num_pol_ps): #initialize all the flipper power supplies
            self.flipper_ps.append(FlipperPS(gpib_addr=i+1, gpib_controller = self.gpib))
        self.flipperstate = [None, None] # initialize the flippers to "Unknown"    
        
        # ICP commands:
        self.pfcal = self.PrintFlipperCalibration
        self.fcal = self.setFlipperCalibration
        self.flm = functools.partial(self.setFlipper, 0)
        self.fla = functools.partial(self.setFlipper, 1)
        self.rm = functools.partial(self.getFlippingRatio, 0)
        self.ra = functools.partial(self.getFlippingRatio, 1)
        self.iscan = self.IScan
        
        # hook into the IC device registry:
        self.device_registry.update( {'ps':
                                            {'names': self.ps_names, 'updater': self.setCurrentByName, 'getter': self.getCurrentByName },
                                      'flippers':
                                            {'names': ['flipper1', 'flipper2'], 'updater': self.setFlipperByName, 'getter': None}
                                      } )
        self.icp_conversions = update(self.icp_conversions, ICP_CONVERSIONS)
    
    def PrintFlipperCalibration(self, ps_num = None):
        if not ps_num:
            return self.PrintAllFlipperCal()
        else:
            fcals = self.ip.GetFcal()
            fcal = fcals[ps_num]
            result = 'Power supply: %d flipper current:   %.3f at energy  %.3f meV' % (ps_num, fcal['cur'], fcal['engy'])
            self.write(result)
            
                   
    def PrintAllFlipperCal(self):
        fcals = self.ip.GetFcal()
        result = ''
        for i in range(len(fcals)):
            fcal = fcals[i+1]
            result += 'Power supply: %d flipper current:   %.3f at energy  %.3f meV\n' % (i+1, fcal['cur'], fcal['engy'])
        self.write(result)
    
    def IScan(self, ps_num, istart, istep, istop, duration=-1, auto_drive_fit = False):
        numsteps = int( abs(float(istop - istart) / (istep)) + 1)
        comment = 'ISCAN'
        if ps_num in [1,3]:
            Fitter = self.cossquared_fitter
        else:
            Fitter = self.quadratic_fitter
        movable = 'ps%d' % (ps_num,)
        val_now = self.getCurrentByName(movable, poll=True)
        self.PeakScan(movable, numsteps, istart, istep, duration, val_now, comment=comment, Fitter=Fitter, auto_drive_fit=auto_drive_fit)
                
    def setFlipperCalibration(self, ps_num, cur, engy = None):
        self.ip.SetFcal(ps_num, cur, engy)
    
    def setFlipperMonochromator(self, enable):
        self.setFlipper(1, enable)
    def setFlipperAnalyzer(self, enable):
        self.setFlipper(2, enable)
        
    def getFlipperMonochromator(self):
        return self.state.get('flipper1', False)
    def getFlipperAnalyzer(self):
        return self.state.get('flipper2', False)
    
    def setFlipper(self, flippernum, enable):
        """ flippers are numbered... flipper 1 is monochromator, flipper 2 is at analyzer usually
        flipper 1 has two power supplies (1 and 2), for flipping and compensation
        flipper 2 also has two (3 and 4)...
        this command lights up both power supplies for the given flipper """
        # turn them on one at a time:
        ps_num = int((flippernum-1) * 2)
        if enable:
            fcals = self.ip.GetFcal()
            self.flipper_ps[ps_num].setCurrent(fcals[ps_num+1]['cur'])  # ignores the 'energy' parameter.  This functionality is broken in ICP at ANDR anyway
            self.flipper_ps[ps_num+1].setCurrent(fcals[ps_num+2]['cur'])
        else:
            self.flipper_ps[ps_num].setCurrent(0.0)
            self.flipper_ps[ps_num+1].setCurrent(0.0)
        self.state['flipper%d' % flippernum] = enable
        
    def getFlippingRatio(self, flippernum, duration):
        """ flippers are numbered... flipper 0 is monochromator, flipper 1 is at analyzer usually
        flipper 0 has two power supplies (1 and 2), for flipping and compensation
        flipper 1 also has two (3 and 4)...
        this command turns the flipper off and measures, then repeats with the flipper on """
        # turn them on one at a time:
        self.setFlipper(flippernum, False) # turn it off
        result = self.Count(duration)
        off_counts = result['counts']
        msg = 'FLIPPER %d OFF:\ncount time: %.4f monitor: %g counts: %g \n' % (flippernum, result['count_time'], result['monitor'], result['counts'])
        self.write(msg, file_msg = ('Count: '+ msg))
        
        self.setFlipper(flippernum, True) # turn it on
        result = self.Count(duration)
        on_counts = result['counts']
        msg = 'FLIPPER %d ON:\ncount time: %.4f monitor: %g counts: %g \n' % (flippernum, result['count_time'], result['monitor'], result['counts'])
        self.write(msg, file_msg = ('Count: '+ msg))
        
        if (off_counts == 0 or on_counts == 0): 
            flipping_ratio = 0.0
            self.write("flipping ratio = 0 or bad")
            return 0.0
        else:
            flipping_ratio = float(off_counts) / on_counts
            inverse_ratio = float(on_counts) / off_counts
            self.write("flipping ratio: %.4f (inverse: %.4f) \n" % (flipping_ratio, inverse_ratio))
        
        return flipping_ratio
    
    def getMonoFlippingRatio(self, duration):
        self.getFlippingRatio(1, duration)
    def getAnaFlippingRatio(self, duration):
        self.getFlippingRatio(2, duration)
            
    def setFlipperByName(self, flippernames, enable_list):
        if DEBUG: print "setting flippers by name!: ", flippernames
        id_len = len('flipper')
        for flippername, en in zip(flippernames, enable_list):
            flippernum = int(flippername[id_len:])
            self.setFlipper(flippernum, en)
    
    def setCurrentByName(self, ps_names, currents):
        ps_nums = [self.ps_lookup[pn] for pn in ps_names]
        for ps_num, current in zip(ps_nums, currents):
            self.setFlipperPSCurr(ps_num, current)
        return [self.getCurrentByName(ps_name, poll=True) for ps_name in ps_names]
            
    
    def getCurrentByName(self, ps_name, poll=False):
        ps_num = self.ps_lookup[ps_name]
        if poll==True:
            curr = self.getFlipperPSCurr(ps_num)
            self.state[ps_name] = curr
            return curr
        else:
            return self.state.get(ps_name, '')
    
    def getFlipperPSCurr(self, ps_num):
        return self.flipper_ps[ps_num].getCurrent()
    def getFlipperPSVolt(self, ps_num):
        return self.flipper_ps[ps_num].getVoltage()
        
    def setFlipperPSCurr(self, ps_num, current):
        self.flipper_ps[ps_num].setCurrent(float(current))
      
    def setFlipperPSVolt(self, ps_num, voltage):
        self.flipper_ps[ps_num].setVoltage(float(voltage))
    
    def iset(self, ps_id, current):
        """ power supply id begins at 1, not 0 in interface """
        self.setFlipperPSCurr((ps_id-1), current)
    def iget(self, ps_id):
        """ power supply id begins at 1, not 0 in interface """
        return self.getFlipperPSCurr((ps_id-1))
    def vset(self, ps_id, voltage):
        """ power supply id begins at 1, not 0 in interface """
        self.setFlipperPSVolt((ps_id-1), voltage)
    def vget(self, ps_id):
        """ power supply id begins at 1, not 0 in interface """
        return self.getFlipperPSVolt((ps_id-1))
          
# for compatibility and easy mixing:
mixin_class = FlipperControlMixin
