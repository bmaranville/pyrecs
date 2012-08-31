from pyrecs.drivers.rs232gpib import RS232GPIB
from pyrecs.drivers.FlipperDriver import FlipperPS
import functools
#from mixin import MixIn

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
        if self.gpib is None:
            self.gpib = RS232GPIB(serial_port = self.ip.GetSerialPort(term_line)) # initialize our gpib controller
        num_flipper_ps = len(self.ip.GetFcal())
        self.flipper_ps = []
        for i in range(num_flipper_ps): #initialize all the flipper power supplies
            self.flipper_ps.append(FlipperPS(gpib_addr=i+1, gpib_controller = self.gpib))
        self.flipperstate = [None, None] # initialize the flippers to "Unknown"
        
        # ICP commands:
        self.pfcal = self.PrintFlipperCalibration
        self.fcal = self.SetFlipperCalibration
        self.flm = functools.partial(self.SetFlipper, 0)
        self.fla = functools.partial(self.SetFlipper, 1)
        self.iset = self.SetFlipperPSCurr
        self.vset = self.SetFlipperPSVolt
        self.iscan = self.IScan
        
        # hook into the IC device registry:
        self.device_registry.update( {'ps':
                                {'names': self.ps_names, 'updater': self.SetCurrentByName }} )
        
    
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
        Fitter = self.cossquared_fitter
        movable = 'ps%d' % (ps_num,)
        val_now = self.getState()[movable]
        self.PeakScan(movable, numsteps, istart, istep, duration, val_now, comment, Fitter, auto_drive_fit)
                
    def SetFlipperCalibration(self, ps_num, cur, engy = None):
        self.ip.SetFcal(ps_num, cur, engy)
    
    def SetFlipper(self, flippernum, enable):
        """ flippers are numbered... flipper 0 is monochromator, flipper 1 is at analyzer usually
        flipper 0 has two power supplies (1 and 2), for flipping and compensation
        flipper 1 also has two (3 and 4)...
        this command lights up both power supplies for the given flipper """
        # turn them on one at a time:
        ps_num = int(flippernum * 2)
        if enable:
            fcals = self.ip.GetFcal()
            self.flipper_ps[ps_num].SetCurrent(fcals[ps_num+1]['cur'])  # ignores the 'energy' parameter.  This functionality is broken in ICP at ANDR anyway
            self.flipper_ps[ps_num+1].SetCurrent(fcals[ps_num+2]['cur'])
        else:
            self.flipper_ps[ps_num].SetCurrent(0.0)
            self.flipper_ps[ps_num+1].SetCurrent(0.0)
        self.state['flipper%dstate' % flippernum] = enable
            
    def SetFlipperByName(self, flippernames, enable):
        id_len = len('flipper')
        for flippername in flippernames:
            flippernum = int(flippername[id_len:])
            self.SetFlipper(flippernum, enable)
    
    def SetCurrentByName(self, ps_names, currents):
        ps_nums = [self.ps_lookup[pn] for pn in ps_names]
        for ps_num, current in zip(ps_nums, currents):
            self.SetFlipperPSCurr(ps_num, current)
    
    def SetFlipperPSCurr(self, ps_num, current):
        self.flipper_ps[ps_num].SetCurrent(float(current))
    
    
    def SetFlipperPSVolt(self, ps_num, voltage):
        self.flipper_ps[ps_num].SetVoltage(float(voltage))
        
# for compatibility and easy mixing:
mixin_class = FlipperControlMixin