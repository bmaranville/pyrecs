import sys, os
sys.path.append('/home/bbm/pydev/pyrecs/publishers')

import reflectometry.reduction as red
from ICPDataFile import ICPDataFile
import simplejson

def add_timestamps(filename=None):
    data_obj = red.load(filename)
    folder = os.path.dirname(filename)
    end_times = simplejson.load(open(os.path.join(folder, 'end_times.json'), 'r'))
    basename = os.path.basename()[-12:]
    #new_file = open('T'+filename, 'w')
    
    end_time = end_times[basename]
    print end_time
    
        
