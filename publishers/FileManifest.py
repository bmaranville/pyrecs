from __future__ import with_statement
import time, math, os

MONITOR_REC = '/home/brian/icp/ICP/cfg/MONITOR.REC'

class FileManifest:
    """ 
    class for dealing with manifest file on ICP system
    doubles as a publisher for InstrumentController
    current system: 
        - publish_start at start of scan,
        - publish_filecreation when scan halted if file is created (not for aborted findpeak)
        - publish_end when scan halted, without regard for archival status
    """
    def __init__(self):
        self.manifestfile = MONITOR_REC
        self.time_format = ' %b %d %Y %H:%M'
        self.entries = []
        
    def energy_from_wavelength(self, wavelength):
        """ returns kinetic energy in meV from wavelength in Angstroms """
        return (81.82 / (float(wavelength)**2))
    
    def wavelength_from_energy(self, energy):
        """ returns wavelength in Angstroms from energy in meV """
        return 9.045 / math.sqrt(energy) 
    
    def publish_start(self, params, scan_def):
        monitor_counts = params.get('monitor', 0.0)
        energy_mev = self.energy_from_wavelength(params['wavelength'])
        timestr = time.strftime(self.time_format)
        outstr = '%s %9d. %9.2f meV   Start of Run\n' % (timestr, monitor_counts, energy_mev)
        with open(self.manifestfile, 'a') as mf:
            mf.write(outstr)
              
    def publish_filecreation(self, params, scan_def):
        filepath_str = os.path.join(params['project_path'], scan_def['filename'])
        timestr = time.strftime(self.time_format)
        outstr = '%s  Created:  %s\n' % (timestr, filepath_str)
        with open(self.manifestfile, 'a') as mf:
            mf.write(outstr)
        
    def publish_end(self, params, scan_def):
        #filepath_str = os.path.join(params['project_path'], params['filename'])
        timestr = time.strftime(self.time_format)
        outstr = '%s End of Run\n' % (timestr,)
        with open(self.manifestfile, 'a') as mf:
            mf.write(outstr)
    
    def publish_datapoint(self, params, scan_def):
        pass
            
    def parse_file(self):
        self.entries = []
        l = len(time.strftime(self.time_format))
        line = 'beginning of parse'
        with open(self.manifestfile, 'r') as mf:
            while not line == '':
                line = mf.readline()
                if line.endswith('Start of Run\n'):
                    line_time = time.strptime(line[:l], self.time_format)
                    new_entry = {}
                    new_entry['start_time'] = line_time
                    new_entry['start_monitor'] = float(line[l:].split()[0])
                    new_entry['start_energy'] = float(line[l:].split()[1])
                    line = mf.readline()
                    if line[l:].startswith('  Created:  '):
                        line_time = time.strptime(line[:l], self.time_format)
                        new_entry['filename'] = line[(l + len('  Created:  ')):-1]
                        line = mf.readline()
                    if line.endswith('End of Run\n'):
                        line_time = time.strptime(line[:l], self.time_format)
                        new_entry['end_time'] = line_time
                        self.entries.append(new_entry)
                        continue

    def readline_backwards(self, f):
        backline = ''
        last = ''
        while not last == '\n':
            backline = last + backline
            if f.tell() <= 0:
                return backline
            f.seek(-1, 1)
            last = f.read(1)
            f.seek(-1, 1)
        backline = last
        last = ''
        while not last == '\n':
            backline = last + backline
            if f.tell() <= 0:
                return backline
            f.seek(-1, 1)
            last = f.read(1)
            f.seek(-1, 1)
        f.seek(1, 1)
        return backline
        
    def update_entries(self):
        """read backwards through file to find new entries"""
        l = len(time.strftime(self.time_format))
        line = 'beginning of parse'
        new_entries = []
        with open(self.manifestfile, 'r') as mf:
            mf.seek(0, 2) # go to the end
            while not line == '':
                line = self.readline_backwards(mf)
                if line.endswith('End of Run\n'):
                    while line.endswith('End of Run\n'):
                        # skip duplicate "End of Run" entries
                        line_time = time.strptime(line[:l], self.time_format)
                        new_entry = {}
                        new_entry['end_time'] = line_time
                        line = self.readline_backwards(mf)
                    if line[l:].startswith('  Created:  '):
                        line_time = time.strptime(line[:l], self.time_format)
                        new_entry['filename'] = line[(l + len('  Created:  ')):-1]
                        line = self.readline_backwards(mf)
                    if line.endswith('Start of Run\n'):
                        line_time = time.strptime(line[:l], self.time_format)
                        new_entry['start_time'] = line_time
                        new_entry['start_monitor'] = float(line[l:].split()[0])
                        new_entry['start_energy'] = float(line[l:].split()[1])
                        if (len(self.entries) == 0) or (new_entry['start_time'] > self.entries[-1]['start_time']):
                            new_entries.insert(0, new_entry)
                            continue
                        else:
                            break
                
        self.entries.extend(new_entries)
        return new_entries
