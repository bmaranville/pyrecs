import serial

class TemperatureController(object):
    """ base class for generic (serial-port controlled) temperature controller.  Methods for:
        GetTemp, 
        GetAuxTemp, 
        SetTemp
        GetSetpoint
    must be defined in derived classes
    """
    def __init__(self, port = '/dev/ttyUSB2'):
        """ the Temperature serial connection is on the third port at MAGIK, which is /dev/ttyUSB2 """
        self.port = port
        #self.serial = serial.serial_for_url(port, 9600, parity='N', rtscts=False, xonxoff=False, timeout=1)
        self.serial = serial.Serial(port, 9600, parity='N', rtscts=False, xonxoff=False, timeout=1)
        self.settings = {}
        self.valid_settings = {}
        
    def getSettings(self):
        return self.settings
    
    def configure(self, keyword=None, value=None):
        valid_keywords = self.settings.keys()
        if not keyword in valid_keywords:
            return "not a valid keyword: choices are " + ",".join(valid_keywords)
        valid_values = self.valid_settings[keyword]
        if not value in valid_values.keys():
            return_str = "valid values for %s:\n" % (keyword,)
            return_str += '\n'.join(['%s: %s' % (key, valid_values[key]) for key in valid_values])
            return return_str
        else:
            self.updateSettings(keyword, value)
            return str(self.settings)
    
    def updateSettings(self, keyword, value):
        self.settings[keyword] = value
        # override if you need more than this.
        
    def getTemp(self, sensor=None):
        pass
    
    def getTemp(self, temp):
        pass
        
    def getSetpoint(self):
        pass
    
