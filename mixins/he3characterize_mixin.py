import simplejson
import datetime
import pprint
import pyrecs.he3analyzer

class He3CharacterizeMixin:
    """ 
    Provides commands needed to run an experiment with a He3 analyzer (not pumped)
    
    Intended as a Mixin class with InstrumentController - gives new functions but 
    depends on functions that are available within IC 
    
    """
    def __init__(self):
        # no new ICP commands associated with this.
        self.time_fmt = pyrecs.he3analyzer.He3Analyzer.time_fmt
        self.active_he3_cell = None
        self.he3_cell_collection = None
        
    
    def He3CellStart(self, name='', start_time=None):
        cell_collection = pyrecs.he3analyzer.He3AnalyzerCollection(path=self.datafolder)
        if start_time == None:
            start_time = datetime.datetime.now()
        new_params = {'name': name, 't0_str':start_time.strftime(self.time_fmt)}
        new_cell = cell_collection.AddNew(params = new_params)
        self.active_he3_cell = new_cell
        self.he3_cell_collection = cell_collection
        self.write('New He3 cell started at %s' % (self.active_he3_cell.params['t0_str']))
        
    def He3CellRename(self, name):
        if not self.active_he3_cell is None:
            self.active_he3_cell.params['name'] = name
            self.he3_cell_collection.Save()
    
    def He3TransmissionSetup(self, state_before, state_after={}):
        """ define the instrument setup for doing transmission measurements.
        Instrument will revert to prior state if no after-state is defined """
        self.he3_transmission_state_before = state_before.copy()
        self.he3_transmission_state_after = state_after.copy()
        
    def He3MeasureTransmission(self, label = ''):
        current_state = self.getState()
        output_msg = 'Measuring He3 cell transmission with settings:\n'
        output_msg += pprint.pformat(self.he3_transmission_state_before, indent=4) + '\n'
        self.updateState(self.he3_transmission_state_before)
        counting_state = self.getState()
        result = self.measure()['result']
        timestamp = datetime.datetime.now()
        output_msg += 'result:\n'
        output_msg += pprint.pformat(result, indent=4)
        self.write(output_msg)
        state_after = self.he3_transmission_state_after.copy()
        state_after.update(current_state)
        self.updateState(state_after)
        
        measurement = {'timestamp': timestamp.strftime(self.time_fmt), 'label': label}
        measurement['value']  = result['counts']
        cell_measurement_list = self.active_he3_cell.params.get('Measurements', [])
        cell_measurement_list.append(measurement)
        self.active_he3_cell.params['Measurements'] = cell_measurement_list
        self.he3_cell_collection.Save()
        return result
        
# for compatibility and easy naming:
mixin_class = He3CharacterizeMixin
    
        
    