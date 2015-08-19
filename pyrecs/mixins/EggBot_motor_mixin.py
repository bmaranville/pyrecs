from pyrecs.drivers.EiBotBoard import EBB

class EggBotMotorMixin:
    """ simple mixin to set the motor controller and scaler to be VIPER """
    def __init__(self):
        self.mc = EBB()
        
# for compatibility and easy naming:
mixin_class = EggBotMotorMixin
