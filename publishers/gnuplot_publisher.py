from publisher import Publisher
from subprocess import Popen, PIPE
from pyrecs.ordered_dict import OrderedDict
import tempfile

class GnuplotPublisher(Publisher):
    def __init__(self, auto_poisson_errorbars=True):
        self.plot = Popen("gnuplot", shell=True, stdin=PIPE, stdout=PIPE, stderr=PIPE, close_fds=True)
        (self.tmp_fd, self.tmp_path) = tempfile.mkstemp() #temporary file for plotting
        self.auto_poisson_errorbars = auto_poisson_errorbars
    
    def publish_start(self, state, scan_definition, **kwargs):
        """ called to record the start time of the measurement """
        self.plot = Popen("gnuplot", shell=True, stdin=PIPE, stdout=PIPE, stderr=PIPE, close_fds=True)
        (self.tmp_fd, self.tmp_path) = tempfile.mkstemp() #temporary file for plotting
        
    def publish_datapoint(self, state, scan_def):
        outstr = ''
        col=1
        for movable in OrderedDict(scan_def['vary']):
            # strict ICP format:
            #outstr += '%10.4f    ' % state[movable]
            outstr += '%14g    ' % state[movable]
            col += 1
        outstr += '%14g\n' % state['result']['counts']
        counts_col = col
        with open(self.tmp_path, 'a') as f:
            f.write(outstr)            
        title = scan_def['filename']
        if self.auto_poisson_errorbars:
            self.plot.stdin.write('plot \'%s\' u 1:%d:(1+sqrt(%d)) title \'%s\' w errorbars lt 2 ps 1 pt 7 lc rgb "red"\n' % (self.tmp_path,counts_col,counts_col,title))
        else:
            self.plot.stdin.write('plot \'%s\' u 1:%d title \'%s\' lt 2 ps 1 pt 7 lc rgb "red"\n' % (self.tmp_path,counts_col,title))
        
    def publish_end(self, state, scan_def):
        counts_col = len(scan_def['vary']) + 1
        title = scan_def['filename']
        if state.has_key('result') and state['result'].has_key('fit_result'):
            fit_params = state['result']['fit_result']
            self.plot.stdin.write('f(x) = %s \n' % state['result']['fit_func'])
            for pn in fit_params.keys():
                self.plot.stdin.write('%s = %f \n' % (pn, fit_params[pn]))
            if self.auto_poisson_errorbars:
                self.plot.stdin.write('plot \'%s\' u 1:%d:(1+sqrt(%d))title \'%s\' w errorbars lt 2 ps 1 pt 7 lc rgb "green",' % (self.tmp_path,counts_col,counts_col,title))
            else:
                self.plot.stdin.write('plot \'%s\' u 1:%d title \'%s\' lt 2 ps 1 pt 7 lc rgb "green",' % (self.tmp_path,counts_col,title))
            self.plot.stdin.write('f(x) w lines lt 2 lc rgb "red"\n')
        else:
            if self.auto_poisson_errorbars:
                self.plot.stdin.write('plot \'%s\' u 1:%d:(1+sqrt(%d)) title \'%s\' w errorbars lt 2 ps 1 pt 7 lc rgb "red"\n' % (self.tmp_path,counts_col,counts_col,title))
            else:
                self.plot.stdin.write('plot \'%s\' u 1:%d title \'%s\' lt 2 ps 1 pt 7 lc rgb "red"\n' % (self.tmp_path,counts_col,title))

