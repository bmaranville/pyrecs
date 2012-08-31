from __future__ import generators
from collections import MutableMapping
from copy import copy, deepcopy

class OrderedDict(dict, MutableMapping):
    """ from PEP 372: OrderedDict
    (to be included in Python 3.1, in collections module)
    in the future: when python >= 3.1, do 
    'from collections import OrderedDict' instead """

    def __init__(self, *args, **kwds):
        if len(args) > 1:
            raise TypeError('expected at most 1 arguments, got %d' % len(args))
        if not hasattr(self, '_keys'):
            self._keys = []
        self.update(*args, **kwds)

    def clear(self):
        del self._keys[:]
        dict.clear(self)

    def __setitem__(self, key, value):
        if key not in self:
            self._keys.append(key)
        dict.__setitem__(self, key, value)

    def __delitem__(self, key):
        dict.__delitem__(self, key)
        self._keys.remove(key)

    def __iter__(self):
        return iter(self._keys)

    def __reversed__(self):
        return reversed(self._keys)

    def popitem(self):
        if not self:
            raise KeyError('dictionary is empty')
        key = self._keys.pop()
        value = dict.pop(self, key)
        return key, value

    def __reduce__(self):
        items = [[k, self[k]] for k in self]
        inst_dict = vars(self).copy()
        inst_dict.pop('_keys', None)
        return (self.__class__, (items,), inst_dict)

    setdefault = MutableMapping.setdefault
    update = MutableMapping.update
    pop = MutableMapping.pop
    keys = MutableMapping.keys
    values = MutableMapping.values
    items = MutableMapping.items

    def __repr__(self):
        if not self:
            return '%s()' % (self.__class__.__name__,)
        return '%s(%r)' % (self.__class__.__name__, list(self.items()))

    def copy(self):
        return self.__class__(self)

    @classmethod
    def fromkeys(cls, iterable, value=None):
        d = cls()
        for key in iterable:
            d[key] = value
        return d

    def __eq__(self, other):
        if isinstance(other, OrderedDict):
            return all(p==q for p, q in  _zip_longest(self.items(), other.items()))
        return dict.__eq__(self, other)

class Trajectory:
    """ the FOR loop for doing scans... 
    evaluate the expression for each movable at each point """
    def __init__(self, iterations = 1, expressions = [], state = {}):
        """ expressions should be of the form [('movable_id', 'text expression')]
        for example, [('a3', 'i * 0.01 + 0.2'), ('a4',  '2.0 * a3')]
        they will be evaluated in order so keep that in mind when specifying 
        relationships between state variables """
        self.state = OrderedDict(state)
        self.expressions = expressions
        self.iterations = iterations
        self.dims = self.get_dims()
        self._all = None
        #self.output_states = self.get_all()
        self.i = 0 # for loop starts here!
        self.j = 0 # position within expressions list
    
    def get_next(self, state):
        if self.i >= self.iterations:
            raise StopIteration
        
        state['i'] = self.i
        target_list = []
        for expr in self.expressions:
            if isinstance(expr, Trajectory):
                expr.state = state.copy()
                target_list.append(expr.get_all())
            else:
                movable = expr[0]
                state[movable] = eval(expr[1], globals(), state)
                new_target = OrderedDict({movable: state[movable]})
                if ((len(target_list) > 0) and isinstance(target_list[-1], dict)):
                    target_list[-1].update(new_target)
                else:
                    target_list.append(new_target)
        self.i += 1
        return target_list
               
    def __getitem__(self, index):
        if self._all is None:
            self._all = self.get_all()
        return self._all[index]
    
    def get_dims(self):
        dims = [self.iterations]
        subdim = 0
        for expr in self.expressions:
            if isinstance(expr, Trajectory):
                dims.append(expr.get_dims())
        return dims
    
    def get_steps(self):
        steps = self.iterations
        substeps = 0
        for expr in self.expressions:
            if isinstance(expr, Trajectory):
                substeps += expr.get_steps()
        if substeps == 0:
            return steps
        else:
            return steps * substeps
        
    def get_all(self):
        state = self.state.copy()
        self.i = 0
        self._all = [self.get_next(state) for i in range(self.iterations)]
        return self._all
        
        #return [self[i] for i in range(self.iterations)]

    def __repr__(self):
        return self._all.__repr__()
    
    def __str__(self):
        return self._all.__str__()
    
    def __iter__(self):
        self.i = 0        
        return self

class TrajectoryBuilder(Trajectory):        
    
    def add_context(self, module):
        self.state.update(module.__dict__)
        
    def add_increment_move(self, movable, increment = 0.01, start = 0.0):
        self.expressions.append((movable, '(i * %f) + %f' % (increment, start)))
        
    def add_expression(self, movable, expression):
        self.expressions.append((movable, expression))
        
    def add_list_move(self, movable, list_of_moves):
        self.expressions.append((movable, str(list_of_moves) + '[i]'))
        
    def add_subtrajectory(self, trajectory = Trajectory()):
        self.expressions.append(('trajectory', list(trajectory.expressions)))
        
  

    


    
           
class chewable_list:
    def __init__(self, chewable):
        self.list = chewable
        self.i = 0
        self.next = self.main_next
        self.sublist = None
        
    def __iter__(self):
        self.i = 0
        return self
    
    def sublist_next(self):
        try:
            return_val = self.sublist.next()
            return return_val
        except StopIteration:
            self.i += 1
            self.next = self.main_next
            self.sublist = None
            return self.next()
    
    def main_next(self):
        print self.i
        if self.i >= len(self.list):
            raise StopIteration
        else:
            if isinstance(self.list[self.i], list):
                self.sublist = chewable_list(self.list[self.i])
                self.next = self.sublist_next
                return self.next()
            else:
                exprs = []
                while ((self.i < len(self.list)) and (not isinstance(self.list[self.i], list))):
                    exprs.append(self.list[self.i])
                    self.i += 1        
                return exprs
            
    def get_pos(self):
        pos = [self.i]
        if self.sublist is not None:
            if self.sublist.sublist is not None:
                pos.append(self.sublist.sublist.get_pos())
        return pos
