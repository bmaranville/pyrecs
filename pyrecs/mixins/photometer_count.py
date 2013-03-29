from pyrecs.drivers.MAS345 import MAS345, Photometer
from numpy import sum, array
import time

class PhotometerControlMixin:
    """ 
    Adds photometer interaction to InstrumentController
    
    Use as a Mixin class (needs methods from InstrumentController), i.e.
    class NewIC(InstrumentController, PSDControllerMixin):
        pass
        
    or use helper function Mixin:
    Mixin(InstrumentController, PhotometerControlMixin)
    """
    
    def __init__(self):
        # ICP commands
        self.ph = self.setPhotometerActive
        self.photometer = None        
        self.setPhotometerActive(True) #start with photometer detector by default
        self.pr = self.printPhotometerRange
        self.sr = self.setPhotometerRange
        
    def getPhotometerActive(self):
        """ Returns true if the voltmeter is the active counter """
        return self._photometer_active
        
    def setPhotometerActive(self, enable):
        """ console command accessed via equivalent ICP command 'ph+' or 'ph-':
        switch modes to count with the photometer """
        if enable: # enable the photometer, make Count command do PhotometerCount
            if self.photometer is None:
                try: 
                    self.photometer = Photometer()
                    self.write('counter set to be photometer with MAS-345 voltmeter')
                    self.write('range set to %s' % self.photometer.getRangeString())
                
                except: self.write("loading photometer driver failed")
            if self.photometer is not None:
                self.Count = self.PhotometerCount
                self._photometer_active = True
        else: # disable it, re-enable pencil detector, make Count do PencilCount
            self.Count = self.PencilCount
            self._photometer_active = False
            
    def setPhotometerRange(self, range_index):
        self.photometer.setRangeIndex(range_index)
        self.write('range set to %s' % self.photometer.getRangeString())
        
    def printPhotometerRange(self):
        self.write('range setting %d: %s' % (self.photometer.getRangeIndex(), self.photometer.getRangeString()))
        
    def PhotometerCount(self, duration, pause_time = 1.0, reraise_exceptions = False):
        """ PhotometerCount(self, duration, pause_time=1.0, reraise_exceptions = False):
         Count using the MAS-345 voltmeter connected to photometer """
        photometer = self.photometer
        duration = abs(int(round(float(duration))))
        # duration is interpreted as number of samples - 
        # there is a pause of 1 sec between readings, so it is like time in seconds
        
        if duration < 1: duration = 1
        
        values = []
        for i in range(duration):
            if self._aborted:
                print "\nAborting"
                break
            value, units = photometer.readValue()
            values.append(value)
            start_time = time.time()
            while (time.time() - start_time) < pause_time:
                if self._aborted:
                    print "\nAborting"
                    #self.scaler.AbortCount()
                    #if not reraise_exceptions:
                    #    self._aborted = False
                    break
                time.sleep(self.loopdelay)
        
        count_time = duration
        monitor = duration
        elapsed_time = duration
        counts = sum(array(values))
        result = {'count_time': count_time, 'monitor': monitor, 'counts': counts, 'elapsed_time': elapsed_time, 'photometer_range': photometer.getRangeString()}
        self.state['result'].update(result)
        return result
            
        
# for compatibility and easy naming:
mixin_class = PhotometerControlMixin
