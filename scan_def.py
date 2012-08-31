from ordered_dict import *

scan_qz = {'comment': 'Qz scan',
 'filename': 'test.txt',
 'init_state': OrderedDict([('scaler_gating_mode', 'TIME'), ('scaler_time_preset', 1.0)]),
 'iterations': 21,
 'namestr': 'CG1',
 'vary': OrderedDict([('qz', '0.0 + 0.0001*i'), ('a4', '2.0*asin(wavelength*q/(4.0*pi)) * 180.0 / pi'), ('a3', 'a4/2.0')])}

scan_qx = {'comment': 'Qx scan',
 'filename': 'qx_test.txt',
 'init_state': OrderedDict([('scaler_gating_mode', 'TIME'), ('scaler_time_preset', 1.0)]),
 'iterations': 21,
 'namestr': 'CG1',
 'vary': OrderedDict([ 
    ('qz', '0.001'),
    ('qx', '-1.0e-5 + 1.0e-6*i'),
    ('q', 'sqrt(qx**2 + qz**2)'),
    ('a4', '2.0*asin(wavelength*q/(4.0*pi)) * 180.0 / pi'),
    ('a3', 'a4/2.0 + asin(qx/q)')])}


