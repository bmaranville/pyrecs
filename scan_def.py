#from ordered_dict import *
from collections import OrderedDict
scan_qz = {'comment': 'Qz scan',
 'filename': 'test.txt',
 'init_state': OrderedDict([('scaler_gating_mode', 'TIME'), ('scaler_time_preset', 1.0)]),
 'iterations': 21,
 'namestr': 'CG1',
 'vary': OrderedDict([('qz', '0.0 + 0.0001*i'), ('a4', '2.0*asin(wavelength*q/(4.0*pi)) * 180.0 / pi'), ('a3', 'a4/2.0')])}

scan_qx = {'comment': 'Qx scan',
 'filename': 'qx_20micron_sampletest.txt',
 'init_state': ([('scaler_gating_mode', 'TIME'), ('scaler_time_preset', 1.0), ('wavelength', 6550.0)]),
 'iterations': 1001,
 'namestr': 'CG1',
 'vary': ([ 
    ('qx', '-3.2e-4 + 6.4e-7*i'),
    ('qz', '0.0016'),
    ('q', 'sqrt(qx**2 + qz**2)'),
    ('a4', '2.0*asin(wavelength*q/(4.0*pi)) * 180.0 / pi'),
    ('sample_angle', 'a4/2.0 + (asin(qx/q) * 180.0 / pi)'),
    ('a3', 'a4 - sample_angle')])}



