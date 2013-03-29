""" from Kathryn: the canonical list of measurements that need to get 
done to characterize a 3He cell.

1. a) T_unpolarized(cell out)  # together, these allow P_cell determination
   b) T_unpolarized(cell in) # this only needs to get measured once.
   c) blocked beam (dark counts) # subtract this from EVERY measurement before other math
   
2. a) T_unpolarized(cell in) # this, with T_unpolarized(cell out) gives P_cell
   b) T_up_up
   c) T_down_up  # for example, if the cell starts out up
   d) FLIP!
   e) T_down_down
   f) T_up_down # b through f give P_flipper
   g) T_unpolarized(cell in) # again, gives P_cell as sanity check
   
3. any combination of spin-flip and non-spin-flip, which gives Psm_prime
   (including sample depolarization)
   This is often a bigger issue on SANS (large sample volume) than on reflectometers
   Also on SANS, the error bars on this measurement are large.
   
repeat 2. every time you flip the cell, and 3 as often as you can (between every buffer)
"""

class he3wizard:
	"""
	A tool for performing the minimum characterization needed
	to get cell polarization and transmission (and flipping ratio)
	as a fuction of time
	"""
	parameter_procurement_recipes = OrderedDict(
        {'T_E': {'measurements': {'T_E': 'transmission_unpolarized'},
				    'description': 'Initial transmission (cell out, unpolarized)',
				    'experiment status': 'Initial characterization not complete',
				    'returns': 'T_E'},
		'T_0': {'measurements': {'T_0': 'transmission_unpolarized'},
				  	'description': 'Initial transmission (cell in, unpolarized)',
				  	'experiment status': 'Initial characterization complete.  Begin experiment.',
				  	'returns': 'T_0'},
		'P_f': {'measurements': {'Iuu': 'transmission_up_up',
								'Iud': 'transmission_up_down',
								'Idu': 'transmission_down_up',
								'Idd': 'transmission_down_down'},
					'description': 'Flipper efficiency (polarized - do this at a flip to get all four cross sections)',
					'experiment status': 'Running - doing a flip',
					'returns': '((Idd/Idu - 1.0) * (Iuu/Iud + 1.0)) / ((Idd/Idu + 1.0) * (Iuu/Iud - 1.0))'},
		'P_3He': {'measurements': {'T_cell': 'transmission_unpolarized'},
					'description': 'Polarization of 3He atoms',
					'experiment status': 'Running',
					'returns': 'acosh(T_cell/T_E) * (1.0/(mu * T_E * exp(-mu)))'},
		'P_cell': {'measurements': {'P_3He': 'P_3He'},
					'description': 'Polarization of cell',
					'experiment status': 'Running',
					'returns': 'tanh(mu * P_3He)'},
		'P_SM': {'measurements': {'P_cell': 'P_cell',
								'I_on': 'transmission_wflipper_on',
								'I_off': 'transmission_wflipper_off'},
					'description': 'Polarization of supermirror minus sample depolarization',
					'experiment status': 'Running',
					'returns': ''}
		})
	def __init__(self):
		pass
	
	def measureTEmpty(self, normalize=False):
		""" Initial transmission (cell out, unpolarized) """
		instrument.set('unpolarized') # rotate out supermirror, e.g.
		monitor, counts = instrument.measure('transmission') # measure main beam transmission
		T_E = float(counts)
		if normalize:
			T_E = T_E / float(monitor) 
		return T_E
		
	def measureT_0Empty(self, normalize=False):
		""" Initial transmission (cell out, unpolarized) """
		instrument.set('unpolarized') # rotate out supermirror, e.g.
		monitor, counts = instrument.measure('transmission') # measure main beam transmission
		T_E = float(counts)
		if normalize:
			T_E = T_E / float(monitor) 
		return T_E