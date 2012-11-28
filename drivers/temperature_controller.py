class TemperatureController(object):
    """ base class for generic (serial-port controlled) temperature controller.  Methods for:
        GetTemp, 
        GetAuxTemp, 
        SetTemp
        GetSetpoint
    must be defined in derived classes
    """
    def GetSettings(self):
        settings = {
            'port': self.port,
            'control_sensor': self.control_sensor,
            'sample_sensor': self.sample_sensor,
            'record': self.record }
        return settings
    def configure(self, keyword, value):
        valid_keywords = ['control_sensor', 'sample_sensor', 'record']
        if not keyword in valid_keywords:
            return "not a valid keyword: choices are " + ",".join(valid_keywords)
    def GetTemp(self):
        pass
    
    def SetTemp(self, temp):
        pass
        
    def GetSetpoint(self):
        pass
    
    def GetAuxTemp(self):
        pass
