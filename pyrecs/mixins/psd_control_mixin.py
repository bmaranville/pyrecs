from pyrecs.drivers.brookhaven_psd import BrookhavenDetector
from pyrecs.drivers.nisto import NISTO
import time

INSTALLED_PSD = NISTO
MAX_RETRIES = 5

class PSDControlMixin:
    """ 
    Adds PSD interaction to InstrumentController
    
    Use as a Mixin class (needs methods from InstrumentController), i.e.
    class NewIC(InstrumentController, PSDControllerMixin):
        pass
        
    or use helper function Mixin:
    Mixin(InstrumentController, PSDControlMixin)
    """
    
    def __init__(self):
        # ICP commands
        self.a = self.setPSDActive
        self.pasd = self.PrintROI
        self.xmin = self.SetXmin
        self.xmax = self.SetXmax
        self.ymin = self.SetYmin
        self.ymax = self.SetYmax
        
        self.setPSDActive(True) #start with psd when activated
        
    def getPSDActive(self):
        """ Returns true if the PSD is the active counter """
        return self._psd_active
        
    def setPSDActive(self, enable):
        """ console command accessed via equivalent ICP command 'a+' or 'a-':
        switch modes to count with the PSD """
        if enable: # enable the PSD, make Count command do PSDCount
            if self.psd is None:
                try: self.psd = INSTALLED_PSD()
                except: self.write("loading PSD driver failed")
            if self.psd is not None:
                self.Count = self.PSDCount
                self._psd_active = True
                if self.psd.dims is None:
                    self.psd.AIM_DIMS()
        else: # disable it, re-enable pencil detector, make Count do PencilCount
            self.Count = self.PencilCount
            self._psd_active = False
            
    def PSDCount(self, duration, reraise_exceptions = False):
        """ PSDCount(self, duration, reraise_exceptions = False):
         Count using the PSD.  Specific to PSD """
        psd = self.psd
        duration = float(duration)
        self.scaler.ResetScaler()
        psd.AIM_CLEAR()
        psd.AIM_ARM()
        if duration < 0: # count by time
            duration *= -1.0 # reset the negative sign
            self.scaler.CountByTime(duration)
        else: # count vs. monitor
            self.scaler.CountByMonitor(duration)
            
        while self.scaler.IsCounting():
            if self._aborted:
                print "\nAborting"
                self.scaler.AbortCount()
                #if not reraise_exceptions:
                #    self._aborted = False
                break
            time.sleep(self.loopdelay)
            
        count_time, monitor, counts = self.scaler.GetCounts()
        elapsed_time = self.scaler.GetElapsed()
        psd.AIM_DISARM()
        psd_data = psd.AIM_XFER(max_retries=MAX_RETRIES)
        self.psd_data = psd_data
        psd.AIM_SAVE('asd.raw')
        
        xmin, ymin, xmax, ymax, numx, numy = self.ip.GetROI()
        
        # overwriting the counts from the scaler with the ones from the PSD:
        #counts = (psd_data[xmin:xmax+1,ymin:ymax+1]).sum() # psd_data is a numpy array, with sum method available
        counts = psd_data.sum()
        result = {'count_time': count_time, 'monitor': monitor, 'counts': counts, 'elapsed_time': elapsed_time, 'psd_data': psd_data}
        self.state['result'].update(result)
        return result
            
    def PrintROI(self):
        xmin, ymin, xmax, ymax, numx, numy = self.ip.GetROI()
        self.write('xmin: %d\nxmax: %d\nymin: %d\nymax: %d' % (xmin, xmax, ymin, ymax))
    
        
    def SetXmin(self, xmin):
        self.ip.SetROI(xmin, None, None, None)
    
    
    def SetXmax(self, xmax):
        self.ip.SetROI(None, None, xmax, None)
        
        
    def SetYmin(self, ymin):
        self.ip.SetROI(None, ymin, None, None)
    
        
    def SetYmax(self, ymax):
        self.ip.SetROI(None, None, None, ymax)
        
# for compatibility and easy naming:
mixin_class = PSDControlMixin
