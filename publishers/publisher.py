from __future__ import with_statement
import struct, glob, time, os
from FileManifest import FileManifest
import time
import pprint
from pyrecs.ordered_dict import OrderedDict
#from collections import OrderedDict

class Publisher:
    """ generic measurement publisher.  inherit and override the classes 
    for specific publishers (file, Xpeek, manifest, etc.) """
    def __init__(self, *args, **kwargs):
        pass
       
    def publish_start(self, *args, **kwargs):
        """ called to record the start time of the measurement """
        pass
    
    def publish_archive_creation(self, *args, **kwargs):
        """ called to record the creation of the data archive
        (needed in the MONITOR.REC file) """
        pass
    
    def publish_datapoint(self, *args, **kwargs):
        """ called to record a new datapoint """
        pass
    
    def publish_end(self, *args, **kwargs):
        """ called when measurement complete - archive finished """
        pass

class RunScanPublisher(Publisher):
    fileManifest = FileManifest()
    def publish_start(self, state, scan_def, **kwargs):
        state.setdefault('monitor', 0.0) # typically don't measure monitor before findpeak
        self.fileManifest.publish_start(state, scan_def, **kwargs)
        header = '# Scan definition: \n'
        scan_def_lines = pprint.pformat(scan_def, indent=4).split('\n')
        for line in scan_def_lines:
            header += '# ' + line + '\n'
        header += '#\n# Column names: \n' # spacer    
        for movable in OrderedDict(scan_def['vary']):
            header += '# Motor no. % 2s ' % movable
        header += '   Intensity   ' + time.strftime('%b %d %Y %H:%M') + '\n'
        with open(scan_def['filename'], 'w') as f:
            f.write(header)
            
    def publish_datapoint(self, state, scan_def, **kwargs):
        outstr = ''
        for movable in OrderedDict(scan_def['vary']):
            #outstr += '%10.4f    ' % state[movable]
            outstr += '%14g    ' % state[movable]
        outstr += '%14g\n' % state['result']['counts']
        
        psd_str = ''
        if state['result']['psd_data'] is not None:
            psd_str = format_psddata(state['result']['psd_data']) + '\n'
        outstr += psd_str
        
        with open(scan_def['filename'], 'a') as f:
            f.write(outstr)
            
    def publish_end(self, state, scan_def, **kwargs):
        self.fileManifest.publish_filecreation(state, scan_def, **kwargs)
        self.fileManifest.publish_end(state, scan_def)
        
def format_psddata(psd_data):
    full_data_str = ''
    data_str = ' '
    dim1, dim2 = psd_data.shape
    for j in range(dim2):
        for i in range(dim1):                
            entry = psd_data[i,j]
            if i == dim1 - 1:
                if j == dim2 - 1:
                    new_data_str = '%i' % entry # leave off comma on last point
                else:
                    new_data_str = '%i;' % entry # end of row gets semicolon
            else:
                new_data_str = '%i,' % entry # regular data points get a comma afterward
            if ((len(new_data_str) + len(data_str)) > 80 ):
                full_data_str += data_str + '\n'
                data_str = ' ' + new_data_str
            else:
                data_str += new_data_str
    full_data_str += data_str
    return full_data_str
