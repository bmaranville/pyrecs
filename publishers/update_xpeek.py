import socket
from publisher import Publisher
#bcast_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
#host = '129.6.121.255'
#port = 8080
from pyrecs.ordered_dict import OrderedDict
TEST = False

class XPeekPublisher(Publisher):
    """ publisher for state dictionaries coming from pyrecs InstrumentController """
    def __init__(self):
        self.broadcaster = xpeek_broadcast()

    def publish_start(self, state, scan_def):
        vary_dict = OrderedDict(scan_def['vary'])
        if scan_def['comment'] == 'Find_Peak':
            self.broadcaster.new_findpeak(scan_def['iterations'], scan_def['filename'], vary_dict.keys(), scan_def['namestr'])
        else:
            self.broadcaster.new_data(scan_def['iterations'], scan_def['filename'], vary_dict.keys(), scan_def['comment'], scan_def['namestr'])
    
    def publish_datapoint(self, state, scan_def):
        """ called to record a new datapoint """
        vary = OrderedDict(scan_def['vary']).keys()
        position = [state[d] for d in vary]
        counts = state['result']['counts']
        pointnum = state['i'] + 1
        instrument_name = scan_def['namestr']
        self.broadcaster.new_point(position, counts, pointnum, vary, instrument_name)
    
    def publish_end(self, state, scan_def):
        """ called when measurement complete - archive finished """
        instrument_name = scan_def['namestr']
        result = state['result']
        scan_type = result.get('TYPE', None)
        if scan_type == 'FP':
            fit_result = result['fit_result']
            fit_params = [fit_result[fp] for fp in fit_result if (not fp[-4:] == '_err')]
            # here we take care of the fact that in the standard gaussfit for xpeek, there is a linear 
            # offset term (P2) and a quadratic offset (P3) that we don't include in our fits, 
            # and we set them explicitly to 0:
            fit_params = [fit_params[0], 0.0, 0.0, fit_params[1], fit_params[2], fit_params[3]]
            converged = True
        elif scan_type == 'ISCAN':
            fit_result = result['fit_result']
            fit_params = [fit_result[fp] for fp in fit_result if (not fp[-4:] == '_err')]
            converged = True
        else :
            fit_params = []
            converged = False
            
        self.broadcaster.end(scan_type, fit_params, converged, namestr=instrument_name)
    
class xpeek_broadcast:
    """ initialize, update and end an xpeek broadcast of a findpeak scan """
    def __init__(self, instrument_name = 'CG1', host = '<broadcast>', port = 8080):
        self.bcast_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.host = host
        self.port = port
        self.bcast_sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.bcast_sock.bind(('', socket.htons(0)))
        self.instrument_name = instrument_name
        self.pointnum = 1
         
    def new_findpeak(self, npts, filename, vary, namestr=None):
        if namestr is None:
            namestr = self.instrument_name
        outstr = ''
        outstr += namestr + ':START\t'
        outstr += 'NPTS=% 10d\t' % npts
        outstr += 'FILE=%s\t' % filename
        outstr += 'VARY='
        for v in vary:
            outstr += '%s ' % str(v).upper()
            #outstr += 'A%02d ' % v
        outstr += '\t'
        outstr += 'Find_Peak' + '\n'
        self.pointnum = 1
        self.broadcast(outstr)
    
    def new_data(self, npts, filename, vary=[], comment = '', namestr=None):
        if namestr is None:
            namestr = self.instrument_name
        self.vary = vary
        self.npts = npts
        self.filename = filename
        outstr = ''
        outstr += namestr + ':START\t'
        outstr += 'NPTS=% 10d\t' % npts
        outstr += 'FILE=%s\t' % filename
        outstr += 'VARY='
        for v in vary:
            outstr += '%s ' % str(v).upper()
        outstr += '\t' + comment + '\n'
        self.pointnum = 1
        self.broadcast(outstr)
    
    def broadcast(self, outstr):
        if TEST: 
            print outstr
        else:
            print outstr
            self.bcast_sock.sendto(outstr, (self.host, self.port))
        
    def new_point(self, position, counts, pointnum = None, vary = None, instrument_name=None):
        if pointnum is None:
            pointnum = self.pointnum
        if vary is None:
            vary = self.vary
        if instrument_name == None:
            instrument_name = self.instrument_name
        outstr = ''
        outstr += instrument_name + ':\t'
        outstr += 'PT=% 10d\t' % pointnum
        for p,v in zip(position, vary):
            outstr += '%s=%11.3f ' % (str(v).upper(), p)
        outstr += '\tDATA=% 10d\n' % (counts)
        self.pointnum = pointnum + 1
        self.broadcast(outstr)
        
    def end(self, scan_type = None, fit_params = [], converged = False, namestr=None):
        if namestr is None:
            namestr = self.instrument_name
        outstr = ''
        outstr += namestr + ':END\t'
        if scan_type in ['FP', 'ISCAN']:
            outstr += 'TYPE=%s\t' % (scan_type,)
            for i, param in enumerate(fit_params):
                outstr += 'FIT_P%d=%11.4f\t' % (i+1, param)
        elif scan_type in ['NOCONV']:
            outstr += 'TYPE=NOCONV'
            
        outstr += '\n'
        self.broadcast(outstr)


#outstr = 'CG1:START\tNPTS=12\tFILE=blah.txt\tVARY=A03\t\'Find_Peak\'\n'
#bcast_sock.sendto(outstr, (host, port))
# new point:
def send_new_point(point_num, motornum, position, counts, host, port, instrument_name = 'CG1'):
    outstr = '%s:\tPT=%d\tA%02d=%.4f\tDATA=%d' % (instrument_name, point_num, motornum, position, counts)
    bcast_sock.sendto(outstr, (host, port))

# when done, if fit converges:
def send_end_fpscan(p1, p2, p3, p4, p5, p6, instrument_name = 'CG1'):
    outstr = '%s:END\tTYPE=FP\tFIT_P1=%g\tFIT_P2=%g\tFIT_P3=%g\tFIT_P4=%g\tFIT_P5=%g\tFIT_P6=%g\t\n' % (instrument_name, p1, p2, p3, p4, p5, p6)
    bcast_sock.sendto(outstr, (host, port))
    
# if it doesn't converge:
def send_end_fp_noconverge(instrument_name = 'CG1'):
    outstr = '%s:END\tTYPE=NOCONV\n' % (instrument_name,)
    bcast_sock.sendto(outstr, (host, port))

def test_xpeek_stream(instrument_name="CGD", port=8080):
    import time
    import numpy
    xpeek = xpeek_broadcast(instrument_name = instrument_name, port=port)
    npts = 10
    filename = 'fpx03001.cgd'
    comment = 'test of xpeek broadcast network'
    vary = ['A3',]
    xpeek.new_data(npts, filename, vary, comment = comment)
    time.sleep(1.0)
    for i in range(npts):
        xpeek.new_point([i], numpy.random.randint(20))
        time.sleep(1.0)
    xpeek.end()

""" It seems from ICP that the parameters for a gauss fit go like this:
P1: scalar offset (P1 + )
P2: linear offset (P2*x + )
P3: quadr. offset (P3*x**2 + )
P4: amplitude,
P5: x-offset,
P6: FWHM,         ( + P4 * exp(-((x-P5)*1.665109/P6)**2)
"""

""" Params for Sine fit are as follows:
P1: scalar offset    (P1 + )
P2: amplitude,
P3: x-scaling,
P4: phase-offset        (P2 * cos(x * P3 + P4))
"""

# from ICP writestr:

#===============================================================================
# bstr(1:)=namestr//':END'//tab
#    lb=8
#    IF (conv) THEN
#      bstr(1:)=bstr(1:lb)//'TYPE=FP'//tab
#      lb=lb+8
#      WRITE (UNIT=response(1:), FMT= '(a,f10.3)', iostat=ios)
#    1              ' Fit Results:   BG = ', p(1)
#      CALL Putcontr_NT ( response)
#      WRITE (UNIT=response(1:), FMT= '(a,f10.3)', iostat=ios)
#    1              '            Height = ', p(4)
#      CALL Putcontr_NT ( response)
#      WRITE (UNIT=response(1:), FMT= '(a,f11.4)', iostat=ios)
#    1              '               Pos = ', p(5)
#      CALL Putcontr_NT ( response)
#      WRITE (UNIT=response(1:), FMT= '(a,f11.4)', iostat=ios)
#    1              '             Width = ', p(6)
#      CALL Putcontr_NT ( response)
#      CALL Putcontr_NF ( ' ')
#      IF (chgfile)THEN
#        fitstr1(1:)=' Fit: '
#        fitstr2(1:)=' **'
#        WRITE(unit=fitstr1(1:),
#     1            fmt='(1x,a,f11.4,2(a,f10.3),a,f11.4)', iostat=ios)
#     1            ' Fit: Pos= ',p(5),' BG= ',p(1),' Height= ',
#     1                    p(4),' Width= ',p(6)
#        WRITE(unit=fitstr2(1:),fmt=
#     1         '(1x,a,f10.3,a,f10.3,a,f10.3,a,f10.3,a,f11.4,a,f11.4,a)',
#     1             iostat=ios)' Fit eq: ',
#     1                    p(1),coeff1,p(2),coeff2,p(3),coeff3,
#     1            p(4),coeff4,p(5),coeff5,p(6),coeff6
#      ENDIF !chgfile
#      bfit = 'FIT_P1='
#      do i = 1,6
#        write(unit=bfit(6:6),fmt='(I1)',iostat=ios)i
#        write(unit=bfit(8:),fmt='(f11.4)',iostat=ios)p(i)
#        bstr(1:)=bstr(1:lb)//bfit//tab
#        lb=lb+19
#      enddo
#    ELSE !no convergence
#      bstr(1:)=bstr(1:lb)//'TYPE=NOCONV'
#      lb=lb+11
#      CALL Putcontr_NT (' Fit did not converge!')
#      IF (chgfile) then
#        fitstr1(1:)=' Fit: ** Did not converge ** '
#        fitstr2(1:)=' **'
#      ENDIF !chgfile
#    ENDIF !converged
#    CALL GoBroad(lb,bstr)
#===============================================================================


# examples, gleaned from the vast (port 8080, host 0.0.0.0) udp broadcast in the sky:
"""
CG1:START    NPTS=         9    FILE=fpx05005.cg1    VARY=A05     Find_Peak
"""

"""
CG1:    PT=         7    A05=   -0.800     DATA=       167
"""

"""
CG1:END    TYPE=FP    FIT_P1=     1.7240    FIT_P2=     0.0000    FIT_P3=     0.0000    FIT_P4=  4099.1540    FIT_P5=     0.6864    FIT_P6=     0.3449
"""

"""
NG1:START    NPTS=        11    FILE=                VARY=CURISCAN
"""

"""
NG1:    PT=        11    CUR=    2.5000    DATA=       812
"""

"""
' CG1:    PT=        1    A01=      1.600    A02=      1.600    A03=      4.000    A04=      8.000    T=307.107    M=   1.00    DATA=          15
'
"""

"""
' CG1:START    NPTS=      126    FILE=/home/NCNRWIN/cg1/Eastman/d36h2006.cg1    VARY=A01 A02 A03 A04 A05 A06     d36h2 thick 60c dp is 30.065      
'

' CG1:FINISH
'

' NB1:    PT=        9    A03=    0.43000    A04=    0.26000    M=   0.69    DATA=         127
'
"""
