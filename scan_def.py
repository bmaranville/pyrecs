#from ordered_dict import *
from collections import OrderedDict
scan_qz = {'comment': 'Qz scan',
 'filename': 'test.txt',
 'init_state': OrderedDict([('scaler_gating_mode', 'TIME'), ('scaler_time_preset', 1.0)]),
 'iterations': 21,
 'namestr': 'CG1',
 'vary': OrderedDict([('qz', '0.0 + 0.0001*i'), ('a4', '2.0*asin(wavelength*q/(4.0*pi)) * 180.0 / pi'), ('a3', 'a4/2.0')])}

scan_qx = {'comment': 'Qx scan',
 'filename': 'qx_test.txt',
 'init_state': ([('scaler_gating_mode', 'TIME'), ('scaler_time_preset', 1.0)]),
 'iterations': 21,
 'namestr': 'CG1',
 'vary': ([ 
    ('qx', '-1.0e-5 + 1.0e-6*i'),
    ('qz', '0.001'),
    ('q', 'sqrt(qx**2 + qz**2)'),
    ('a3', '2.0*asin(wavelength*q/(4.0*pi)) * 180.0 / pi'),
    ('a1', 'a3/2.0 + (asin(qx/q) * 180.0 / pi)')])}



