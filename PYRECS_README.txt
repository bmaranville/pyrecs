Experimental ICP analog program (in pure Python)

requires non-standard python packages:
serial (for simple serial I/O)
numpy (not sure this is necessary - using numpy.int32 and numpy.float32 but int and float would probably work as well)
ipython (very important - this is the shell in which the program runs)
(Note: it's not a python module, but the program uses gnuplot to show real-time data.  This isn't critical and can be changed)

Modules:
pyrecs_thread.py: contains class definition for InstrumentController, which is main program.  Will have analogs for all ICP functions relevant to reflectometers.
InstrumentParameters.py: backend interface class, does all manipulations of instrument parameters (limits, tolerances, backlash values, PSD region of interest, etc)
VME.py: contains class VME, which is a driver for communications with the VME box, including both motor-control and scaler-control commands
rs232GPIB.py: driver for rs232->GPIB converter (used to talk to flipper power supplies etc)
FlipperDriver.py: driver for HP power supplies used to run the flippers
SorensenDCS30.py: driver for Sorensen magnet power supply (not integrated yet)
fit_gausspeak.py: class for fitting a dataset to a gaussian and returning result
prefilter_ICP: contains function to override prefilter for ipython, enabling ICP-like syntax, also does logging of unfiltered commands through hook back to InstrumentController
    Converts fp7,1,2,3 to ic.fp(7,1,2,3) where ic is the InstrumentController, a+ becomes ic.a(True), etc.
ibuffer.py: creates object from IBUFFER.BUF, with full interaction including load, reload, save, etc.
ICPDataFile.py: driver for writing files with correct ICP format.
PSD.py: Contains one driver, for Brookhaven PSD controller currently implemented at AND/R  (copied almost verbatim from ICP source)

    


