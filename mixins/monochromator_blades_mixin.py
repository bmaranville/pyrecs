from pyrecs.drivers.EZ_motor import EZStepper
#import functools
#from mixin import MixIn
MONO_BLADE_LINE = 3
NUM_BLADES = 13

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
        port = self.ip.GetSerialPort(rs232conf_line)
        self.mbc = EZStepper(port)
        self.mbc.num_mots = NUM_BLADES
        self.blade_names = ['b%d' % (i+1) for i in range(NUM_BLADES)]
        self.blade_numbers = range(1, NUM_BLADES+1)
        self.blade_lookup = dict(zip(self.blade_names, self.blade_numbers))
        
        # ICP commands:
        self.dm = self.mbc.MoveMotor
        self.setm = self.mbc.SetMotorPos
        self.pm = self.PrintMonoBladeAngle
        self.fpm = self.FindPeakMonoBlade
        
        # hook into the IC device registry:
        self.device_registry.update( {'monoblades':
                                {'names': self.blade_names, 'updater': self.DriveMonoBladeByName }} )
        
    def DriveMonoBladeByName(self, blades_to_move, position_list):
        blade_list = [self.blade_lookup[s] for s in blades_to_move]
        # i.e. 'b3' is blade 3
        for b,p in zip(blade_list, position_list):
            self.dm(b, p)
            
    def PrintMonoBladeAngle(self, bladenum=None):
        if bladenum:
            pos = self.mbc.GetMotorPos(bladenum)
            self.write('B%02d=%8.3f\n' % (bladenum, pos))
        else:  # no motor specified - get them all
            out_line = ''
            for i, b in enumerate(self.blade_numbers):
                pos = self.mbc.GetMotorPos(b)
                out_line += 'B%02d=%8.3f ' % (b, pos)
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
        val_now = self.getState()[movable]
        mstart = val_now - ( int(numsteps/2) * mstep)
        comment = 'FP'
        Fitter = self.gauss_fitter  
        self.PeakScan(movable, numsteps, mstart, mstep, duration, val_now, comment=comment, Fitter=Fitter, auto_drive_fit=auto_drive_fit)
        
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
