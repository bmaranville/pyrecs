ICP_CONVERSIONS = {
    'arg_commands': {
        'pwl': { 'numargs': [0], 'pyrecs_cmd': 'GetWavelength' },
        'wl': { 'numargs': [1], 'pyrecs_cmd': 'SetWavelength' },
        'pa': { 'numargs': [0,1], 'pyrecs_cmd': 'PrintMotorPos' },
        'pt': { 'numargs': [0], 'pyrecs_cmd': 'PrintTemperature'},
        'phf': { 'numargs': [0], 'pyrecs_cmd': 'PrintField'},
        'pu': { 'numargs': [0,1], 'pyrecs_cmd': 'PrintUpperLimits'},
        'pl': { 'numargs': [0,1], 'pyrecs_cmd': 'PrintLowerLimits'},
        'init': { 'numargs': [2], 'pyrecs_cmd': 'SetHardMotorPos'},
        'set': { 'numargs': [2], 'pyrecs_cmd': 'SetSoftMotorPos'},
        'st': { 'numargs': [1], 'pyrecs_cmd': 'SetTemperature'},
        'ct': { 'numargs': [1], 'pyrecs_cmd': 'PrintCounts'},
        'mon': { 'numargs': [1], 'pyrecs_cmd': 'PrintMonitor'},
        'fp': { 'numargs': [3,4], 'pyrecs_cmd': 'FindPeak'},
        'fl': { 'numargs': [3,4], 'pyrecs_cmd': 'FindLine'},
        'rapid': { 'numargs': [3,4,5], 'pyrecs_cmd': 'RapidScan_new'},
        'u': { 'numargs': [2], 'pyrecs_cmd': 'SetUpperLimit'},
        'l': { 'numargs': [2], 'pyrecs_cmd': 'SetLowerLimit'},
        'ri': { 'numargs': [1], 'pyrecs_cmd': 'RunIBuffer'},
        'rsf': { 'numargs': [1], 'pyrecs_cmd': 'RunICPSequenceFile'},
        'drsf': { 'numargs': [1], 'pyrecs_cmd': 'DryRunICPSequenceFile'},
        'rs': { 'numargs': [1], 'pyrecs_cmd': 'RunSequence'},
        'dp': { 'numargs': [0], 'pyrecs_cmd': 'DrivePeak'},
        'd': { 'numargs': [2], 'pyrecs_cmd': 'DriveMotor'},
        'tdev': { 'numargs': [0,1,2], 'pyrecs_cmd': 'TemperatureDevice'},
        'atdev': { 'numargs': [0,1,2], 'pyrecs_cmd': 'NewTemperatureDevice'},
        'rtdev': { 'numargs': [0,1], 'pyrecs_cmd': 'RemoveTemperatureDevice'},
        'hdev': { 'numargs': [0,1,2], 'pyrecs_cmd': 'MagnetDevice'},
        'ahdev': { 'numargs': [0,1], 'pyrecs_cmd': 'NewMagnetDevice'},
        'rhdev': { 'numargs': [0,1], 'pyrecs_cmd': 'RemoveMagnetDevice'}
    },
        
    'arg_kw_commands': {
        'tdev': { 'numargs': [1], 'pyrecs_cmd': 'ConfigureTemperatureDevice'},
    },
    
    'en_dis_commands': {
        'w': { 'numargs': [1], 'pyrecs_cmd': 'setLogging'},
        'p': { 'numargs': [1], 'pyrecs_cmd': 'setPolarization'}
    },

    'increment_commands': {
        'd': { 'numargs': [2], 'pyrecs_cmd': 'DriveMotorIncrement'}
    },
    
    'tied_commands': {
        'd': { 'numargs': [2], 'pyrecs_cmd': 'DriveMotorTied'},
        'fp': { 'numargs': [3,4], 'pyrecs_cmd': 'FindPeakTied'}
    },
    
    'stringarg_commands': {
        'rsf': { 'numargs': [0], 'pyrecs_cmd': 'RunICPSequenceFile'},
    },
}
