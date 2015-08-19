from pyrecs.drivers.VME import VME

class VIPERScalerMotorMixin:
    """ simple mixin to set the motor controller and scaler to be VIPER """
    def __init__(self):
        VIPER_mot_line = int(self.ip.InstrCfg['VIPER_mot_line'])
        vme = VME(port = self.ip.GetSerialPort(VIPER_mot_line)) # initialize the VME box (motors, scaler)
        self.scaler = vme
        self.mc = vme
        self.Count = self.PencilCount
        
# for compatibility and easy naming:
mixin_class = VIPERScalerMotorMixin
