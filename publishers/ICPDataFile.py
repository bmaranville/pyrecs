from __future__ import with_statement
import struct, glob, time, os
from pyrecs.icp_compat import ibuffer
from FileManifest import FileManifest
from publisher import Publisher
from copy import copy, deepcopy
import math
import time
import pprint
from pyrecs.ordered_dict import OrderedDict
#from collections import OrderedDict
 
PUBLISH_FITRESULT = True

class ICPFindPeakPublisher(Publisher):
    fileManifest = FileManifest()
    def publish_start(self, state, scan_def, **kwargs):
        state.setdefault('monitor', 0.0) # typically don't measure monitor before findpeak
        self.fileManifest.publish_start(state, scan_def)
        header = ''
        for movable in OrderedDict(scan_def['vary']):
            header += ' Motor no. % 2s ' % movable
        header += '   Intensity   ' + time.strftime('%b %d %Y %H:%M') + '\n'
        with open(scan_def['filename'], 'w') as f:
            f.write(header)
            
    def publish_datapoint(self, state, scan_def, **kwargs):
        outstr = ''
        for movable in OrderedDict(scan_def['vary']):
            #outstr += '%10.4f    ' % state[movable]
            outstr += '%14g    ' % state[movable]
        outstr += '%14g\n' % state['result']['counts']
        with open(scan_def['filename'], 'a') as f:
            f.write(outstr)
            
    def publish_end(self, state, scan_def, **kwargs):
        if (PUBLISH_FITRESULT == True) and state['result'].has_key('fit_str'):
            #outstrs = pprint.pformat(state['result']['fit_result'], indent=4).split('\n')
            outstrs = state['result']['fit_str'].split('\n')
            with open(scan_def['filename'], 'a') as f:
                for outstr in outstrs:
                    f.write('# ' + outstr + '\n')    
        self.fileManifest.publish_filecreation(state, scan_def)
        self.fileManifest.publish_end(state, scan_def)

class ICPDataFilePublisher(Publisher):
    """ inherits from generic publisher class """
    fileManifest = FileManifest()
    def __init__(self):
        self.ICPD = ICPDataFile()
        Publisher.__init__(self)
    
    def publish_start(self, params, scan_def, **kwargs):
        #if params.get('timestamp') is None:
        #    params['timestr'] = time.strftime('%b %d %Y %H:%M')
        params.setdefault('monitor', 0.0) # typically don't measure monitor before findpeak
        self.fileManifest.publish_start(params, scan_def)
        params['timestr'] = time.strftime('%b %d %Y %H:%M')
        header = self.ICPD.GenerateHeader(params, scan_def)
        with open(scan_def['filename'], 'w') as f:
            f.write(header)
            
    def publish_datapoint(self, params, scan_def, **kwargs):
        self.ICPD.AddPoint(params, scan_def)
        
    def publish_end(self, state, scan_def, **kwargs):
        self.fileManifest.publish_filecreation(state, scan_def)
        self.fileManifest.publish_end(state, scan_def)
          
class ICPDataFile:
    """ class to write to ICP-style data files """
    time_fmt = '%a %b %d %H:%M:%S %Y'
    
    def __init__(self, params = {}):
        #self.ic = instrument_controller
        #self.ip = self.ic.ip # InstrumentParameters object: need it to get configuration data (wavelength etc)
        self.params = self.default_params
        self.params.update(params)  # override the defaults, if specified
        self.filename = self.params['filename']

    def getNextFilename(self, file_path, file_prefix, file_suffix, autoset = False):
        """ find the highest filenumber with prefix and suffix
        and return 'prefix + (highest+1) + suffix' """
        os.chdir(file_path)
        fl = glob.glob(file_prefix+'*'+file_suffix)
        fl.sort()
        if len(fl) == 0:
            # first scan!
            biggest = 0
        else:
            biggest = fl[-1][len(file_prefix):-len(file_suffix)]
        new_filenum = int(biggest) + 1
        new_filenum_str = '%03d' % new_filenum
        new_filename = file_prefix + new_filenum_str + file_suffix
        if autoset:
            self.filename = new_filename
        return new_filename
    
    def WriteIBufferHeader(self, bufnum):
        header = self.GenerateIBufferHeader(bufnum)
        with open(self.filename, 'a') as f:
            f.write(header)            
            
    def GenerateIBufferHeader(self, datafolder, bufnum, collim, mosaic, wavelength, num_scalers, tc_defined = False, magnet_defined = False):
        """ Create the header for an ibuffer datafile
        tc_defined is true if a temperature controller is defined and will be used
        magnet_defined is true if a magnet controller is defined and will be used """
        ################################################################################
        # Format carefully copied from dmp_data.src - should be the same as ICP output #
        ################################################################################
        
        ibufs = ibuffer.IBUFFER(project_path = datafolder) # use default values to get IBUFFER: current directory, IBUFFER.BUF, 30 entries
        ibuf = ibufs.buffers[bufnum-1] # array starts at zero - bufnum starts at one
        # Generate header:
        description = ibuf.data['description']
        file_prefix = description[:5]
        filename = self.getNextFilename(file_prefix, '.cg1')
        tstring = "'I'   " # this is an i-buffer, after all
        ttype  = 'RAW' # dunno why
        npts = ibuf.data['numpoints']
        count_type = ibuf.data['Type']
        monitor = ibuf.data['monit']
        prefactor = ibuf.data['Prefac']
        tstart = float(ibuf.data['T0'])
        tincr = float(ibuf.data['IncT'])
        hfield = float(ibuf.data['H0'])
        num_detectors = int(ip.InstrCfg['#scl'])
        p1exec, p2exec, p3exec, p4exec = (ibuf.data['p1exec'], ibuf.data['p2exec'], ibuf.data['p3exec'], ibuf.data['p4exec'])
        if p1exec or p2exec or p3exec or p4exec:
            polarized_beam = True
        else: 
            polarized_beam = False
        timestr = time.strftime('%b %d %Y %H:%M')
        #collim, mosaic = ip.GetCollimationMosaic()
        wavelength = ip.GetWavelength()
        
        header = "'%12s' '%17s' %6s%8.f.%5i  '%4s'%5i  '%3s'\n" % (filename, timestr, tstring, monitor, prefactor, count_type, npts, ttype)
        header += '  Filename         Date            Scan       Mon    Prf  Base   #pts  Type    \n'
        header += '%50s ' % (description,)
        if polarized_beam: 
            flipper1 = 'OFF' # to be implemented
            flipper2 = 'ON ' # to be implemented
            header += 'F1: %3s  F2: %3s  \n' % (flipper1, flipper2)
        else: 
            header += '\n'
        header += '%4i %4i %4i %4i %3i %3i %3i ' % (collim[0], collim[1], collim[2], collim[3], mosaic[0], mosaic[1], mosaic[2])
        header += ' %7.4f    %8.5f %7.5f %9.5f %4i ' % (wavelength, tstart, tincr, hfield, num_detectors)
        if magnet_defined: # looks back into the calling parent, ic.  Make explicit?
            Hinc = ibuf.data['Hinc']
            Hconv = 1.000 # need to look up in MOTORS.BUF?
            header += '%7.4f %7.4f' % (Hinc, Hconv)
        header += '\n'
        header += ' Collimation      Mosaic    Wavelength   T-Start   Incr.   H-field #Det    '
        if magnet_defined: 
            header += '  H-conv   H-Inc'
        header += '\n'
        
        motnums = set(range(1,7))
        motors_to_move = []
        
        for motnum in motnums:
            start = float(ibuf.data['a%dstart' % motnum])
            step = float(ibuf.data['a%dstep' % motnum])
            stop = start + ((npts - 1) * step)
            if step > 1.0e-7: # motor precision is less than this
                motors_to_move.append(motnum)
            header += '%3d   %11.5f%11.5f%11.5f\n' % (motnum, start, step, stop)
        header += ' Mot:    Start       Step      End\n'
        
        data_keys = []
        for motnum in motors_to_move:
            data_keys.append('     A%d   ' % motnum) 
        if tc_defined:
            data_keys.append(' TEMP  ')
            # this mimics the ICP behaviour in which the temperature is only looked at if a T device is defined
        if magnet_defined == None:
            data_keys.append(' H-Field ')
            # this mimics the ICP behaviour in which the H-field is only looked at if a magnet device is defined
        data_keys.append('  MIN  ')
        if not ibuf.data['Type'] == 'NEUT': 
            data_keys.append('    MONITOR ')
        data_keys.append('     COUNTS ')
        if num_scalers > 1: 
            data_keys.append('     EXTRA  ')
        
        # now generate the data header from the keys
        for key in data_keys:
            header += key
        header += '\n'
        
        return header
             
    def GenerateICPHeader(self, params = {}):
        description = params['comment']
        description = '%-50s' % description[:50]  # chop it off at 50, but also pad the right to 50 if too short
        file_prefix = description[:5]
        filename = params['filename']
        tstring = "'I'   " # this is an i-buffer, after all
        ttype  = 'RAW' # dunno why
        numpoints = params['numpoints']
        count_type = params['Type']
        monitor = params['monit']
        prefactor = params['Prefac']
        tstart = float(params['T0'])
        tincr = float(params['IncT'])
        hfield = float(params['H0'])
        Hinc = float(params['Hinc'])
        Hconv = float(params['Hconv'])
        num_detectors = int(params['num_detectors'])
        timestr = params['timestr']
        collim = params['collim']
        mosaic = params['mosaic']
        wavelength = params['wavelength']
        
        header = "'%12s' '%17s' %6s%8.f.%5i  '%4s'%5i  '%3s'\n" % (filename, timestr, tstring, monitor, prefactor, count_type, numpoints, ttype)
        header += '  Filename         Date            Scan       Mon    Prf  Base   #pts  Type    \n'
        header += '%50s ' % (description,)
        if (params['flipper0'] is not None) or (params['flipper1'] is not None): 
            #flipper1state = 'OFF' # to be implemented
            #flipper2state = 'ON ' # to be implemented
            # flipperstate should be 'OFF' or 'ON '
            if params.get('flipper0', None) is True:
                f0 = "ON "
            else: 
                f0 = "OFF"
            if params.get('flipper1', None) is True:
                f1 = "ON "
            else: 
                f1 = "OFF"
            header += 'F1: %3s  F2: %3s  ' % (f0, f1)
        header += '\n'
        header += '%4i %4i %4i %4i %3i %3i %3i ' % (collim[0], collim[1], collim[2], collim[3], mosaic[0], mosaic[1], mosaic[2])
        header += ' %7.4f    %8.5f %7.5f %9.5f %4i ' % (wavelength, tstart, tincr, hfield, num_detectors)
        if params['magnet_defined']: 
            header += '%7.4f %7.4f' % (Hinc, Hconv)
        header += '\n'
        header += ' Collimation      Mosaic    Wavelength   T-Start   Incr.   H-field #Det    '
        if params['magnet_defined']: # looks back into the calling parent, ic.  Make explicit?
            header += '  H-conv   H-Inc'
        header += '\n'
        
        motnums = set(range(1,7))
        motors_to_move = []
        
        for motnum in motnums:
            start = float(params['a%dstart' % motnum])
            step = float(params['a%dstep' % motnum])
            stop = start + ((npts - 1) * step)
            if step > 1.0e-7: # motor precision is less than this
                motors_to_move.append(motnum)
            header += '%3d   %11.5f%11.5f%11.5f\n' % (motnum, start, step, stop)
        header += ' Mot:    Start       Step      End\n'
        
        data_keys = []
        for motnum in motors_to_move:
            data_keys.append('     A%d   ' % motnum) 
        if params['temp_controller_defined']:
            data_keys.append(' TEMP  ')
            # this mimics the ICP behaviour in which the temperature is only looked at if a T device is defined
        if params['magnet_defined']:
            data_keys.append(' H-Field ')
            # this mimics the ICP behaviour in which the H-field is only looked at if a magnet device is defined
        data_keys.append('  MIN  ')
        if not params['Type'] == 'NEUT': 
            data_keys.append('    MONITOR ')
        data_keys.append('     COUNTS ')
        if num_detectors > 1: 
            data_keys.append('     EXTRA  ')
        
        # now generate the data header from the keys
        for key in data_keys:
            header += key
        header += '\n'
        
        return header 
    
    def getHeader(self, filename):
        f_in = open(filename, 'r')
        header = []
        for i in range(13):
            header.append(f_in.readline())
        f_in.close()
        return header
        
    def ParseHeader(self, header=None, filename=None):
        """ returns a dictionary of all the header parameters, which can then be fed back into GenerateHeader """
        params = {}
        if header==None:
            if filename==None:
                print "no header or file specified"
                return params
            header = self.getHeader(filename)
        
        filename, month, day, year, hour_minute, tstring, monitor, prefactor, count_type, numpoints, ttype = header[0].split()
        params['timestr'] = ('%s %s %s %s' % (month, day, year, hour_minute)).strip("'")
        params['tstring'] = "%-6s" % tstring
        params['filename'] = filename.strip("'")
        params['count_type'] = count_type.strip("'")
        params['prefactor'] = int(prefactor)
        params['monitor'] = float(monitor)
        params['ttype'] = ttype.strip("'")
        params['numpoints'] = int(numpoints)
        
        params['comment'] = header[2][:50]
        flipper_defs = header[2][50:]
        flipper1_strpos = flipper_defs.find('F1: ')
        flipper2_strpos = flipper_defs.find('F2: ')
        if flipper1_strpos > -1:
            sp = flipper1_strpos + 4 # move to end of 'F1: '
            params['flipper1'] = flipper_defs[sp : sp+3]
        if flipper1_strpos > -1:
            sp = flipper2_strpos + 4
            params['flipper2'] = flipper_defs[sp : sp+3]
        
        collim = [0,0,0,0]
        mosaic = [0,0,0]  
        h3 = header[3].split()
        collim[0], collim[1], collim[2], collim[3], mosaic[0], mosaic[1], mosaic[2] = [int(s) for s in h3[:7]]
        params['collim'] = tuple(collim)
        params['mosaic'] = tuple(mosaic)
        params['wavelength'], params['tstart'], params['tincr'], params['hfield'] = [float(s) for s in h3[7:11]]
        params['num_detectors'] = int(h3[11])
        if 'H-conv' in header[4] and len(h3) > 12:
            params['Hconv'] = float(h3[12])
        if 'H-inc' in header[4] and len(h3) > 13:
            params['Hinc'] = float(h3[13])

        motnums = 6
        for motline in header[5:5+motnums]:
            motnum, start, step, stop = motline.split()
            params['a%sstart' % motnum] = float(start)
            params['a%sstep' % motnum] = float(step)
        
        return params
        
    def scan_def_from_params(self, params=None):
        pass
        
    
    default_params = {
        'description': 'abcde this is my description',
        'filename': '',
        'timestr': time.strftime('%b %d %Y %H:%M'),
        'numpoints': 0,
        'a1start': 0.0, 'a1step': 0.0,
        'a2start': 0.0, 'a2step': 0.0,
        'a3start': 0.0, 'a3step': 0.0,
        'a4start': 0.0, 'a4step': 0.0,
        'a5start': 0.0, 'a5step': 0.0,
        'a6start': 0.0, 'a6step': 0.0,
        'count_type': 'TIME',
        'monit': 1,
        'Prefac': 1,
        'T0': None,
        'IncT': 0.0,
        'H0': None,
        'Hinc': 0.0,
        'Hconv': 0.0,
        'num_detectors': 1,
        'p1exec': 0,
        'p2exec': 0,
        'p3exec': 0,
        'p4exec': 0,
        'collim': (460, 1, 500, 512),
        'mosaic': (608, 512, 0),
        'wavelength': 5.00,
        'magnet_defined': False,
        'temp_controller_defined': False,
        'flipper1': False, # off
        'flipper2': False, # off
        }
             
    def GenerateHeader(self, state = {}, scan_def = {}):
        params = deepcopy(state)
        params.update(scan_def['init_state'])
        scan_expr = OrderedDict(scan_def['vary'])
        scan_state0 = {'i': 0}
        context = deepcopy(params)
        context.update(math.__dict__) # load up the standard context
        
        for d in scan_expr:
            scan_state0[d] = eval(str(scan_expr[d]), context, scan_state0)
        scan_state1 = {'i': 1}
        for d in scan_expr:
            scan_state1[d] = eval(str(scan_expr[d]), context, scan_state1)
        diff = {}
        for d in scan_expr:
            diff[d] = scan_state1[d] - scan_state0[d]
        #ibuf_data = scan_def['ibuf_data']
        description = scan_def['comment']
        description = '%-50s' % description[:50]  # chop it off at 50, but also pad the right to 50 if too short
        file_prefix = description[:5]
        filename = scan_def['filename']
        tstring = "'I'   " # this is an i-buffer, after all
        ttype  = 'RAW' # dunno why
        numpoints = scan_def['iterations']
        count_type = params.get('scaler_gating_mode', 'TIME') #default to time, if not specified
        if count_type == 'TIME':
            monitor = params.get('scaler_time_preset', 1.0)
        elif count_type == 'NEUT':
            monitor = params.get('scaler_monitor_preset', 1)
        else:
            monitor = 1
        prefactor = params.get('scaler_prefactor', 1)
        tstart = float(params.get('t0', 0.0))
        tincr = float(diff.get('t0', 0.0))
        hfield = float(params.get('h0', 0.0))
        num_detectors = int(params['num_detectors'])
        polarized_beam = scan_def.get('polarization_enabled', False)
        timestr =  time.strftime('%b %d %Y %H:%M')
        #timestr = params['timestr']
        collim = params['collimation']
        mosaic = params['mosaic']
        wavelength = params['wavelength']
        
        header = "'%12s' '%17s' %6s%8.f.%5i  '%4s'%5i  '%3s'\n" % (filename, timestr, tstring, monitor, prefactor, count_type, numpoints, ttype)
        header += '  Filename         Date            Scan       Mon    Prf  Base   #pts  Type    \n'
        header += '%50s ' % (description,)
        flipper_state_string = {True: 'ON ', False: 'OFF'}
        if polarized_beam: 
            header += 'F1: %3s  F2: %3s  \n' % (flipper_state_string[params['flipper1']], flipper_state_string[params['flipper2']])
        else: 
            header += '\n'
        header += '%4i %4i %4i %4i %3i %3i %3i ' % (collim[0], collim[1], collim[2], collim[3], mosaic[0], mosaic[1], mosaic[2])
        header += ' %7.4f    %8.5f %7.5f %9.5f %4i ' % (wavelength, tstart, tincr, hfield, num_detectors)
        if params['magnet_defined']: # looks back into the calling parent, ic.  Make explicit?
            Hinc = float(diff.get('h0', 0.0))
            Hconv = 1.000 # need to look up in MOTORS.BUF?
            header += '%7.4f %7.4f' % (Hinc, Hconv)
        header += '\n'
        header += ' Collimation      Mosaic    Wavelength   T-Start   Incr.   H-field #Det    '
        if params['magnet_defined']: # looks back into the calling parent, ic.  Make explicit?
            header += '  H-conv   H-Inc'
        header += '\n'
        
        motnames = []
        for motnum in range(1,7):
            motname = 'a%d' % motnum
            start = float(params.get(motname, 0.0))
            step = float(diff.get(motname, 0.0))
            stop = start + ((numpoints - 1) * step)
            header += '%3d   %11.5f%11.5f%11.5f\n' % (motnum, start, step, stop)
            motnames.append(motname)
        header += ' Mot:    Start       Step      End\n'
        
        data_keys = []
        motors_to_move = [m for m in motnames if m in scan_expr.keys()]
        for motname in motors_to_move:
            data_keys.append('     %s   ' % motname.upper()) 
        if params['temp_controller_defined']:
            data_keys.append(' TEMP  ')
            # this mimics the ICP behaviour in which the temperature is only looked at if a T device is defined
        if params['magnet_defined']:
            data_keys.append(' H-Field ')
            # this mimics the ICP behaviour in which the H-field is only looked at if a magnet device is defined
        data_keys.append('  MIN  ')
        if not count_type == 'NEUT': 
            data_keys.append('    MONITOR ')
        data_keys.append('     COUNTS ')
        if num_detectors > 1: 
            data_keys.append('     EXTRA  ')
        
        # now generate the data header from the keys
        for key in data_keys:
            header += key
        header += '\n'
        
        return header 
    
#    def ReadHeader(self, filename):
#        """ returns a dictionary of all the header parameters, which can then be fed back into GenerateHeader """
#        params = {}
#        f_in = open(filename, 'r')
#        header = []
#        for i in range(13):
#            header.append(f_in.readline())
#        f_in.close()
#        filename, month, day, year, hour_minute, tstring, monitor, prefactor, count_type, numpoints, ttype = header[0].split()
#        params['timestr'] = ('%s %s %s %s' % (month, day, year, hour_minute)).strip("'")
#        params['tstring'] = "%-6s" % tstring
#        params['filename'] = filename.strip("'")
#        params['count_type'] = count_type.strip("'")
#        params['prefactor'] = int(prefactor)
#        params['monitor'] = float(monitor)
#        params['ttype'] = ttype.strip("'")
#        params['numpoints'] = int(numpoints)
#        
#        return params
        
    def AddPoint(self, params, scan_def):
        result = params['result']
        outstr = ''
        for movable in OrderedDict(scan_def['vary']):
            outstr += '%11.5f ' % params[movable]
        t_seconds = result['count_time'] / 10000.0
        t_minutes = t_seconds / 60.0
        #t_minutes = int(t_seconds / 60)
        #t_seconds -= t_minutes * 60
        #time_str = '%d:%02d ' % (t_minutes, t_seconds)
        time_str = '%.2f ' % (t_minutes)
        outstr += time_str
        if params['scaler_gating_mode'] == 'TIME':
            outstr += '%11g ' % result['monitor']
        outstr += '%11g ' % result['counts']
        Tnow = params.get('t0', None)
        if Tnow is not None:
            outstr += '%11g ' % Tnow
        Hnow = params.get('h0', None)
        if Hnow is not None:
            outstr += '%11g ' % Hnow
        outstr += '\n'
        
        with open(scan_def['filename'], 'a') as f:
            f.write(outstr)    
        
        if result['psd_data'] is not None:
            # time to format and spit out the PSD data
            psd_data = result['psd_data']
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
                        print data_str
                        full_data_str += data_str + '\n'
                        data_str = ' ' + new_data_str
                    else:
                        data_str += new_data_str
            print data_str
            full_data_str += data_str + '\n'
            
            print scan_def
            print full_data_str
            with open(scan_def['filename'], 'a') as f:
                f.write(full_data_str)
        
    def AddPointTimestamped(self, params, scan_def, timestamp=None):
        result = params['result']
        outstr = ''
        for movable in OrderedDict(scan_def['vary']):
            outstr += '%11.5f ' % params[movable]
        t_seconds = result['count_time'] / 10000.0
        t_minutes = t_seconds / 60.0
        #t_minutes = int(t_seconds / 60)
        #t_seconds -= t_minutes * 60
        #time_str = '%d:%02d ' % (t_minutes, t_seconds)
        time_str = '%.2f ' % (t_minutes)
        outstr += time_str
        if params['scaler_gating_mode'] == 'TIME':
            outstr += '%11g ' % result['monitor']
        outstr += '%11g ' % result['counts']
        Tnow = params.get('t0', None)
        if Tnow is not None:
            outstr += '%11g ' % Tnow
        Hnow = params.get('h0', None)
        if Hnow is not None:
            outstr += '%11g ' % Hnow
        if timestamp==None:
            outstr += time.srtftime(self.time_fmt)
        else:
            outstr += str(timestamp)
        outstr += '\n'
        
        with open(scan_def['filename'], 'a') as f:
            f.write(outstr)    
        
        if result['psd_data'] is not None:
            # time to format and spit out the PSD data
            psd_data = result['psd_data']
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
                        print data_str
                        full_data_str += data_str + '\n'
                        data_str = ' ' + new_data_str
                    else:
                        data_str += new_data_str
            print data_str
            full_data_str += data_str + '\n'
            
            print scan_def
            print full_data_str
            with open(scan_def['filename'], 'a') as f:
                f.write(full_data_str)
