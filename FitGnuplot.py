from copy import deepcopy
from subprocess import Popen, PIPE
import tempfile, os
import math
import select
from ordered_dict import OrderedDict

POISSON_ERROR = False

class FitGnuplot:
    def __init__(self, xdata, ydata, params_in):
        """ at minimum, need params['fit_func'] and params['pname'] """
        self.gp = Popen("gnuplot", shell=True, stdin=PIPE, stdout=PIPE, stderr=PIPE, close_fds=True)        
        (self.tmp_fd, self.tmp_path) = tempfile.mkstemp() #temporary file for fitting, plotting
        self.tmp_file = open(self.tmp_path, 'w')
        for x, y in zip(xdata, ydata):
            out_str  = '%.4f\t%.4f' % (x, y)
            self.tmp_file.write(out_str + '\n')
        self.tmp_file.close()
        self.xdata = xdata
        self.ydata = ydata
        #self.fit_func = params_in['fit_func']
        
        self.params_out = deepcopy(params_in)
        self.params_out['p0'] = self.make_guesses() # make guesses for params
        if params_in.has_key('p0'):
            self.params_out['p0'].update(params_in['p0']) # but then override them if specified in input params
        self.gp.stdin.write('set print "-" \n')
        self.gp.stdin.write('set fit errorvariables \n')
        self.error = None   
        
    def make_guesses(self):
        """ p0 = {'a': 1.0, 'b': 12.3} etc. """
        p0 = {}
        return p0       

    def do_fit(self, poisson_error=POISSON_ERROR):
        self.gp.stdin.write('f(x) = %s \n' % self.params_out['fit_func'])
        for pn in self.params_out['pname']:
            self.gp.stdin.write('%s = %f \n' % (pn, self.params_out['p0'][pn]))
        
        if poisson_error == True:
            fit_str = 'fit f(x) \'%s\' using 1:2:(1+sqrt($2)) via ' % self.tmp_path
        else:
            fit_str = 'fit f(x) \'%s\' using 1:2 via ' % self.tmp_path
        for pn in self.params_out['pname']:
            fit_str += '%s,' % pn
        fit_str = fit_str[:-1] + '\n'
        self.gp.stdin.write(fit_str)
        #out_fd = select.select([self.gp.stdout, self.gp.stderr], [], [], 1.0)
        #if len(out_fd[0]) == 0:
        #    self.error = 'timeout'
        #    return
        #if (len(out_fd[0]) > 0) and (self.gp.stderr in out_fd[0]):
        #    self.error = self.gp.stderr.readline()
        #    return
        result = OrderedDict()
        for pn in self.params_out['pname']:
            self.gp.stdin.write('print %s \n' % pn)
            result[pn] = float(self.gp.stdout.readline())
            self.gp.stdin.write('print %s_err \n' % pn)
            result['%s_err' % pn] = float(self.gp.stdout.readline())
        self.params_out['fit_result'] = result
        self.fit_result = result
        return result
        
    def plot_result(self):
        if not self.params_out.has_key('result'):
            return
        self.gp.stdin.write("plot \'%s\' u 1:2:(1+sqrt($2)) w errorbars, f(x) w l \n" % (self.tmp_path,) )

class FitGaussGnuplot(FitGnuplot):
    def __init__(self, xdata, ydata, params_in = {}):
        params_in['fit_func'] = 'y_offset + amplitude * exp( - ( x - center )**2 * 4 * log(2) / FWHM**2  )'
        params_in['pname'] = ['y_offset','amplitude','center','FWHM']
        FitGnuplot.__init__(self, xdata, ydata, params_in)
        
    def make_guesses(self):
        xdata = self.xdata
        ydata = self.ydata
        p0 = {}
        p0['y_offset'] = min(ydata)
        p0['amplitude'] = max(ydata) - min(ydata)
        weighted_x = 0.
        sum_relative_y = 0.
        for x,y in zip(xdata,ydata):
            weighted_x += x * (y - p0['y_offset'])
            sum_relative_y += (y - p0['y_offset'])
        if sum_relative_y == 0.0:
            p0['center'] = (xdata[-1] + xdata[0])/2.0
            p0['FWHM'] = abs(xdata[-1] - xdata[0])/2.0
            return p0
        x0 = weighted_x/sum_relative_y
        moment_sum = 0.
        for x,y in zip(xdata,ydata):
            moment_sum += (x0 - x)**2 * (y - p0['y_offset'])
        sigma = math.sqrt(abs(moment_sum/sum_relative_y))
        FWHM = 2.0*math.sqrt(2.0 * math.log(2.0)) * sigma
        p0['center'] = x0
        p0['FWHM'] = FWHM
        return p0

class FitLineGnuplot(FitGnuplot):
    def __init__(self, xdata, ydata, params_in = {}):
        params_in['fit_func'] = 'y_offset + (slope *  x)'
        params_in['pname'] = ['y_offset','slope']
        FitGnuplot.__init__(self, xdata, ydata, params_in)
        
    def make_guesses(self):
        xdata = self.xdata
        ydata = self.ydata
        p0 = {'y_offset': 0.0, 'slope': 0.0}
        return p0

class FitLineAlternate(FitGnuplot):
    def __init__(self, xdata, ydata, params_in = {}):
        params_in['fit_func'] = 'slope * (x - x_offset)'
        params_in['pname'] = ['slope','x_offset']
        FitGnuplot.__init__(self, xdata, ydata, params_in)
        
    def do_fit(self, poisson_error=POISSON_ERROR):
        result = FitGnuplot.do_fit(self, poisson_error)
        result['center'] = result['x_offset']
        self.params_out['fit_result'] = result
        return result
        
    def make_guesses(self):
        xdata = self.xdata
        ydata = self.ydata
        slope = (ydata[-1] - ydata[0]) / (xdata[-1] - xdata[0])
        x_offset = xdata[0] - (ydata[0] / slope)
        p0 = {'slope': slope, 'x_offset': x_offset}
        return p0
        
class FitCosSquaredGnuplot(FitGnuplot):
    def __init__(self, xdata, ydata, params_in = {}):
        params_in['fit_func'] = 'y_offset - amplitude * (cos((x - center) * 2 * pi / period))**2'
        params_in['pname'] = ['y_offset', 'amplitude', 'center', 'period']
        FitGnuplot.__init__(self, xdata, ydata, params_in)
        
    def make_guesses(self):
        xdata = self.xdata
        ydata = self.ydata
        p0 = {}
        p0['y_offset'] = min(ydata)
        p0['amplitude'] = max(ydata) - p0['y_offset']
        minpos = ydata.index(min(ydata))
        p0['center'] = xdata[minpos]
        p0['period'] = 2.0 * ( max(xdata) - min(xdata) )
        return p0
        
class FitQuadraticGnuplot(FitGnuplot):
    def __init__(self, xdata, ydata, params_in = {}):
        params_in['fit_func'] = 'y_offset + amplitude * (x - center)**2'
        params_in['pname'] = ['y_offset', 'amplitude', 'center']
        FitGnuplot.__init__(self, xdata, ydata, params_in)
        
    def make_guesses(self):
        xdata = self.xdata
        ydata = self.ydata
        p0 = {}
        p0['y_offset'] = min(ydata)
        minpos = ydata.index(min(ydata))
        maxpos = ydata.index(max(ydata))
        p0['center'] = xdata[minpos]
        p0['amplitude'] = (max(ydata) - min(ydata)) / (xdata[maxpos] - xdata[minpos])**2
        return p0
      
        
