from scipy import *
from scipy.optimize import leastsq
#import scipy.io.array_import
#from scipy import gplt

#from pylab import plot, legend
from numpy import loadtxt, exp, log, array, arange, float

class Fit:
    """ inherit from here to do general fitting """    
    def __init__(self, xdata = None, ydata = None, p0 = None, pname = [], verbose = False):
        
        if ydata is None: # this has to be filled, or fail
            return
        self.ydata = ydata
        
        if xdata is not None:
            self.xdata = xdata
        else:
            self.xdata = arange(len(ydata), dtype=float) 
            
        self.p0 = p0
        self.pname = pname
        self.verbose = verbose
        self.maxfev = 2000
        
    def evaluate(self, x, p):
        pass # you must override this for any fit: function goes here
    
    ##############################################################
    # don't need to override any functions below when inheriting #
    ##############################################################
    
    def residuals(self, p, y, x):
        err = y - self.evaluate(x,p) 
        return err
            
    def do_fit(self):
        out = leastsq(self.residuals, self.p0, args=(self.ydata, self.xdata), maxfev=self.maxfev, full_output=1)
        plsq = out[0]
        self.plsq = plsq
        self.y_calc = self.evaluate(self.xdata, plsq)
        covar = out[1]
        y_diff = out[2]['fvec']

        self.out = out
        n_params = float(len(self.p0))
        y_variance = sum(y_diff) / (len(self.ydata) - n_params)
        
        result = {}
        for i in range(len(self.pname)):
            if self.verbose: print "%s = %.4f " % (self.pname[i], self.plsq[i])
            result[self.pname[i]] = plsq[i]
            result[self.pname[i] + '_err'] = sqrt(covar[i][i] * y_variance)
        return result

class FitGaussInher(Fit):
    def __init__(self, xdata, ydata, y0 = None, A0 = None, x0 = None, FWHM0 = None, verbose = False):
        self.params = 4
        self.xdata = xdata
        self.ydata = ydata
        if not len(self.xdata) == len(self.ydata):
            print "fit error: x and y dimensions don't match"
            return
        if not y0:
            y0 = ydata.min()
        if not A0:
            A0 = ydata.max() - ydata.min()
        if not x0:
            x0 = xdata[ydata.argmax()]
        if not FWHM0:
            maxpos = ydata.argmax()
            datalen = len(ydata)
            points_above_halfway = arange(datalen)[ydata > (A0/2.0 + y0)]
            if len(points_above_halfway) > 0:
                lower_pos = points_above_halfway[0]
                higher_pos = points_above_halfway[-1]
                if lower_pos == maxpos:
                    if maxpos == 0:
                        lower_pos = maxpos
                    else:
                        lower_pos = maxpos - 1
                if higher_pos == maxpos:
                    if maxpos == datalen:
                        higher_pos = maxpos
                    else:
                        higher_pos = maxpos + 1
                FWHM0 = float(xdata[higher_pos] - xdata[lower_pos])
            else: # there is no peak if there are no points above halfway
                FWHM0 = 0.01 # we're going to die anyway.  Just make something up
            
            
        pname = (['y_offset','amplitude','center','FWHM'])
        p0 = array([y0, A0, x0, FWHM0])
        Fit.__init__(self, xdata, ydata, p0=p0, pname=pname, verbose=verbose)
        
    def evaluate(self, x, p):
        return p[0] + p[1] * exp( - (x - p[2])**2.0 / (p[3])**2 * (4.0 * log(2.0)) )

class FitGaussNoOffset(Fit):
    def __init__(self, xdata, ydata, A0 = None, x0 = None, FWHM0 = None, verbose = False):
        self.params = 3
        self.xdata = xdata
        self.ydata = ydata
        if not len(self.xdata) == len(self.ydata):
            print "fit error: x and y dimensions don't match"
            return
        if not A0:
            A0 = ydata.max() - ydata.min()
        if not x0:
            x0 = xdata[ydata.argmax()]
        if not FWHM0:
            maxpos = ydata.argmax()
            datalen = len(ydata)
            points_above_halfway = arange(datalen)[ydata > (A0/2.0)]
            if len(points_above_halfway) > 0:
                lower_pos = points_above_halfway[0]
                higher_pos = points_above_halfway[-1]
                if lower_pos == maxpos:
                    if maxpos == 0:
                        lower_pos = maxpos
                    else:
                        lower_pos = maxpos - 1
                if higher_pos == maxpos:
                    if maxpos == datalen:
                        higher_pos = maxpos
                    else:
                        higher_pos = maxpos + 1
                FWHM0 = float(xdata[higher_pos] - xdata[lower_pos])
            else: # there is no peak if there are no points above halfway
                FWHM0 = 0.01 # we're going to die anyway.  Just make something up
            
            
        pname = (['A','x0','FWHM'])
        p0 = array([A0, x0, FWHM0])
        Fit.__init__(self, xdata, ydata, p0=p0, pname=pname, verbose=verbose)
        
    def evaluate(self, x, p):
        return p[0] * exp( - (x - p[1])**2.0 / (p[2])**2 * (4.0 * log(2.0)) )
    
class FitMultiGauss(Fit):
    """ feed in guesses for multiple peaks, fit to N gaussians where N is number of guesses supplied
    set the y_offset to zero for all peaks N>1 """
    def __init__(self, xdata, ydata, guesses, verbose = False):
        self.function_count = len(guesses)
        self.gaussians = []
        p0 = []
        pname = []
        for i, guess in enumerate(guesses):
            gaussian = FitGaussNoOffset(xdata, ydata, guess[0], guess[1], guess[2], verbose = False)
            self.gaussians.append(gaussian)
            p0.extend(gaussian.p0)
            pname.extend(['A_%d' % i,'x0_%d' % i,'FWHM_%d' % i])
        p0.extend([ydata.min()])
        pname.extend(['y_offset'])
        Fit.__init__(self, xdata, ydata, p0 = p0, pname = pname, verbose = verbose)
    
    def evaluate(self, x, p):
        result = 0.0
        i = 0
        # map parameters onto individual functions from large concatenated parameter array
        for gaussian in self.gaussians:
            params = gaussian.params
            ploc = p[i:i+params]
            i += params
            result += gaussian.evaluate(x, ploc)
        # last parameter is offset:
        result += p[-1]
        return result
        
    def do_fit(self):
        in_result = Fit.do_fit(self)
        out_result = {}
        
        for i in range(self.function_count):
            result = {}
            for name in self.gaussians[i].pname:
                result[name] = in_result['%s_%d' % (name, i)]
                
            out_result[i] = result
        out_result[i+1] = {self.pname[-1]: in_result[self.pname[-1]]}
        return out_result

class FitGauss:
    """ feed in data (2-d array) and fit to a gaussian """
    def __init__(self, xdata, ydata, y0 = None, A0 = None, x0 = None, FWHM0 = None, verbose = False):
        self.params = 4
        self.xdata = xdata
        self.ydata = ydata
        datalen = len(ydata)
        self.verbose = verbose
        if not len(self.xdata) == len(self.ydata):
            print "fit error: x and y dimensions don't match"
            return
        if not y0:
            y0 = ydata.min()
        if not A0:
            A0 = ydata.max() - ydata.min()
        if not x0:
            x0 = xdata[ydata.argmax()]
        if not FWHM0:
            maxpos = ydata.argmax()
            datalen = len(ydata)
            points_above_halfway = arange(datalen)[ydata > (A0/2.0 + y0)]
            if len(points_above_halfway) > 0:
                lower_pos = points_above_halfway[0]
                higher_pos = points_above_halfway[-1]
                if lower_pos == maxpos:
                    if maxpos == 0:
                        lower_pos = maxpos
                    else:
                        lower_pos = maxpos - 1
                if higher_pos == maxpos:
                    if maxpos == datalen:
                        higher_pos = maxpos
                    else:
                        higher_pos = maxpos + 1
                FWHM0 = float(xdata[higher_pos] - xdata[lower_pos])
            else: # there is no peak if there are no points above halfway
                FWHM0 = 0.01 # we're going to die anyway.  Just make something up
            
            
        self.pname = (['y_offset','amplitude','center','FWHM'])
        self.p0 = array([y0, A0, x0, FWHM0])
        self.p0_orig = self.p0.copy()
        self.maxfev = 2000
    
    def gauss_residuals(self, p, y, x): 
        err = y-self.gauss_eval(x,p) 
        return err
	
    def gauss_eval(self, x, p):
        return p[0] + p[1] * exp( - (x - p[2])**2.0 / (p[3])**2 * (4.0 * log(2.0)) )
    
    def do_fit(self):
        out = leastsq(self.gauss_residuals, self.p0, args=(self.ydata, self.xdata), maxfev=self.maxfev, full_output=1)
        plsq = out[0]
        covar = out[1]
        y_diff = out[2]['fvec']

        self.out = out
        n_params = float(len(self.p0))
        y_variance = sum(y_diff) / (len(self.ydata) - n_params)
        
        result = {}
        for i in range(len(self.pname)):
            if self.verbose: print "%s = %.4f " % (self.pname[i], self.plsq[i])
            result[self.pname[i]] = plsq[i]
            result[self.pname[i] + '_error'] = sqrt(covar[i][i] * y_variance)
        return result

class FitGaussFromFile(FitGauss):
    """ grab data from file and feed to FitGauss """
    def __init__(self, filename, skiprows = 1, y0 = None, A0 = None, x0 = None, FWHM0 = None, verbose = False):
        data = loadtxt(filename, skiprows = skiprows)
        xdata = data[:,0]
        ydata = data[:,1]
        FitGauss.__init__(self, xdata, ydata, y0=y0, A0=A0, x0=x0, FWHM0=FWHM0, verbose=verbose)
  
def test_gaussian():
    """ the right answer is: y-offset = 0.1, amplitude = 105.0, center = 98.7, FWHM = 23.7 """
    p = [0.1, 105.0, 98.7, 23.7]
    def g(x):
        return p[0] + p[1] * exp( - (x - p[2])**2.0 / (p[3])**2 * (4.0 * log(2.0)) )
    xdata = arange(200.)
    y_raw = g(xdata)
    ydata = random.poisson(y_raw)
    return ydata
      
def test_line():
    """ the right answer is: slope = 1.23, y-intercept = -45.6 """
    p = [-45.6, 1.23]
    def l(x):
        return p[0] + p[1] * x
    xdata = arange(200.)
    y_raw = l(xdata)
    ydata = (0.5 - random.rand(200)) * 10.0 + y_raw
    return ydata
    
      
class FitLine:
    """ feed in data (2-d array) and fit to a gaussian """
    def __init__(self, xdata, ydata, slope = None, y0 = None, verbose = False):
        self.xdata = xdata
        self.ydata = ydata
        datalen = len(ydata)
        self.verbose = verbose
        if not len(self.xdata) == len(self.ydata):
            print "fit error: x and y dimensions don't match"
            return
        guess_slope = ( ydata.max() - ydata.min() ) / ( xdata.max() - xdata.min() )
        guess_y0 = ydata.max() - (guess_slope * xdata.max())
        if not y0:
            y0 = guess_y0
        if not slope:
            slope = guess_slope            
            
        self.pname = (['y_offset','slope'])
        self.p0 = array([y0, slope])
        self.p0_orig = self.p0.copy()
        self.maxfev = 2000
    
    def line_residuals(self, p, y, x): 
        err = y-self.line_eval(x,p) 
        return err
	
    def line_eval(self, x, p):
        return p[0] + p[1] * x
    
    def do_fit(self):
        out = leastsq(self.line_residuals, self.p0, args=(self.ydata, self.xdata), maxfev=self.maxfev, full_output=1)
        plsq = out[0]
        covar = out[1]
        y_diff = out[2]['fvec']

        self.out = out
        n_params = float(len(self.p0))
        y_variance = sum(y_diff) / (len(self.ydata) - n_params)
        
        result = {}
        for i in range(len(self.pname)):
            if self.verbose: print "%s = %.4f " % (self.pname[i], self.plsq[i])
            result[self.pname[i]] = plsq[i]
            result[self.pname[i] + '_error'] = sqrt(covar[i][i] * y_variance)
        return result

class FitPoly:
    """ feed in data (2-d array) and fit to a polynomial """
    def __init__(self, xdata, ydata, order = 1, a = None, verbose = False):
        self.xdata = xdata
        self.ydata = ydata
        self.order = order
        datalen = len(ydata)
        self.verbose = verbose
        if not len(self.xdata) == len(self.ydata):
            print "fit error: x and y dimensions don't match"
            return
        guess_slope = ( ydata.max() - ydata.min() ) / ( xdata.max() - xdata.min() )
        guess_y0 = ydata.max() - (guess_slope * xdata.max())
        if not a:
            a = ones(order + 1)     
            
        self.pname = []
        for o in range(0, order + 1):
            self.pname.append('a[%d]' % o)
        self.p0 = a
        self.p0_orig = self.p0.copy()
        self.maxfev = 2000
    
    def poly_residuals(self, p, y, x): 
        err = y-self.poly_eval(x,p) 
        return err
	
    def poly_eval(self, x, p):
        result = 0.
        for o in range(0, self.order +1):
            result += p[o] * x**o
        return result
    
    def do_fit(self):
        out = leastsq(self.poly_residuals, self.p0, args=(self.ydata, self.xdata), maxfev=self.maxfev, full_output=1)
        plsq = out[0]
        covar = out[1]
        y_diff = out[2]['fvec']

        self.out = out
        n_params = float(len(self.p0))
        y_variance = sum(y_diff**2) / (len(self.ydata) - n_params)
        
        result = {}
        for i in range(len(self.pname)):
            if self.verbose: print "%s = %.4f " % (self.pname[i], self.plsq[i])
            result[self.pname[i]] = plsq[i]
            result[self.pname[i] + '_error'] = sqrt(covar[i][i] * y_variance)
        return result

        

class FitGaussGnuplotOld:
    def __init__(self, xdata, ydata,  y_offset = None, amplitude = None, center = None, FWHM = None, plot_result = False, title = "Findpeak"):
        self.gp = Popen("gnuplot", shell=True, stdin=PIPE, stdout=PIPE, stderr=PIPE, close_fds=True)        
        (self.tmp_fd, self.tmp_path) = tempfile.mkstemp() #temporary file for plotting
        self.tmp_file = open(self.tmp_path, 'w')
        for x, y in zip(xdata, ydata):
            out_str  = '%.4f\t%.4f' % (x, y)
            self.tmp_file.write(out_str + '\n')
        self.tmp_file.close()
    
        # make initial guesses
        if not y_offset:
            y_offset = min(ydata)
        if not amplitude:
            amplitude = max(ydata) - min(ydata)
        maxpos = ydata.index(max(ydata))
        if not center:
            center = xdata[maxpos]

        # calculate the moments
        if not FWHM:
            weighted_x = 0.
            for x,y in zip(xdata,ydata):
                weighted_x += x * (y - y_offset)
            x0 = weighted_x/sum(ydata)
            moment_sum = 0.
            for x,y in zip(xdata,ydata):
                moment_sum += (x0 - x)**2 * (y - y_offset)
            FWHM = math.sqrt(abs(moment_sum/sum(ydata)))

        datalen = len(ydata)
        self.pname = ['y_offset','amplitude','center','FWHM']
        self.p0 = [y_offset, amplitude, center, FWHM]
    
        self.gp.stdin.write('set print "-" \n')
        self.gp.stdin.write('set fit errorvariables \n')
        self.gp.stdin.write('f(x) = y_offset + amplitude * exp( - ( x - center )**2 * 4 * log(2) / FWHM**2  )\n')
        for pn, pv in zip(self.pname, self.p0):
            self.gp.stdin.write('%s = %f \n' % (pn, pv))
        fit_str = 'fit f(x) \'%s\' using 1:2:(1+sqrt($2)) via ' % self.tmp_path
        for pn in self.pname:
            fit_str += '%s,' % pn
        fit_str = fit_str[:-1] + '\n'
        self.gp.stdin.write(fit_str)
        result = {}
        for pn in self.pname:
            self.gp.stdin.write('print %s \n' % pn)
            result[pn] = float(self.gp.stdout.readline())
            self.gp.stdin.write('print %s_err \n' % pn)
            result['%s_err' % pn] = float(self.gp.stdout.readline())
        
        if plot_result:
            self.gp.stdin.write("plot \'%s\' u 1:2:(1+sqrt($2)) w errorbars, f(x) w l \n" % (self.tmp_path,) )
        self.result = result
            
    def do_fit(self):
        os.remove(self.tmp_path)
        return self.result
