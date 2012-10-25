from __future__ import with_statement
import struct, glob, time, os
from FileManifest import FileManifest
import time
import pprint
from collections import OrderedDict

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
    def publish_start(self, state, scan_def):
        state.setdefault('monitor', 0.0) # typically don't measure monitor before findpeak
        self.fileManifest.publish_start(state, scan_def)
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
            
    def publish_datapoint(self, state, scan_def):
        outstr = ''
        for movable in OrderedDict(scan_def['vary']):
            #outstr += '%10.4f    ' % state[movable]
            outstr += '%14g    ' % state[movable]
        outstr += '%14g\n' % state['result']['counts']
        with open(scan_def['filename'], 'a') as f:
            f.write(outstr)
            
    def publish_end(self, state, scan_def):
        self.fileManifest.publish_filecreation(state, scan_def)
        self.fileManifest.publish_end(state, scan_def)
