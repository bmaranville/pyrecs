import re
import tokenize, StringIO
DEBUG = False


#FP_REGEXP = r'([-+]?[0-9]*(?:\.[0-9]*)?)'
#FP_REGEXP = r'([-+]?[0-9]*\.[0-9]+|[0-9]+)'
FP_REGEXP = r'([-+]?[0-9]*\.?[0-9]+)'
INT_REGEXP = r'([0-9]+)'
SEP = r'[ \t]*[,][ \t]*'
# different types of commands: 0 argument (pa, pt etc), enable/disable(with plus or minus), then 1, 2, 3, 4, and 5 argument commands
# [-+]?([0-9]*\.[0-9]+|[0-9]+)
ICP_NOARG = re.compile(r'^[ \t]*(pasd|pa|pt|pm|pfcal|pu|pl|statline|mon|rs|dp)[ \t]*$', re.IGNORECASE)
ICP_ENDIS = re.compile(r'^[ \t]*(a|w|flm|fla|p)[ \t]*([-+*])[ \t]*$', re.IGNORECASE)
ICP_1ARG = re.compile(r'[ \t]*(pa|ct|pfcal|fix|rel|xmin|xmax|ymin|ymax|ri)[ \t]*[,=]?[ \t]*'+FP_REGEXP+r'[ \t]*$', re.IGNORECASE)
ICP_2ARG = re.compile(r'[ \t]*(init|set|d|u|l|iset|vset)[ \t]*' + INT_REGEXP + r'[ \t]*[,=]?[ \t]*'+FP_REGEXP +r'[ \t]*$', re.IGNORECASE)
ICP_3ARG = re.compile(r'[ \t]*(fp)[ \t]*[,=]?[ \t]*'+INT_REGEXP + SEP + FP_REGEXP + SEP + FP_REGEXP + r'[ \t]*$', re.IGNORECASE)   
ICP_4ARG = re.compile(r'^[ \t]*(fp|iscan)[ \t]*[,=]?[ \t]*'+INT_REGEXP + SEP + FP_REGEXP + SEP + FP_REGEXP + SEP + FP_REGEXP + r'[ \t]*$', re.IGNORECASE)
ICP_5ARG = re.compile(r'^[ \t]*(iscan)[ \t]*[,=]?[ \t]*'+INT_REGEXP + SEP + FP_REGEXP + SEP + FP_REGEXP + SEP + FP_REGEXP + SEP + FP_REGEXP +r'[ \t]*$', re.IGNORECASE)
ICP_DI = re.compile(r'[ \t]*(d)[ \t]*' + INT_REGEXP + r'[ \t]*i' + r'[ \t]*[,=]?[ \t]*'+FP_REGEXP +r'[ \t]*$', re.IGNORECASE)
ICP_RS = re.compile(r'[ \t]*(rs)[ \t]*' r'[ \t]*[=][ \t]*'+r'(.*)', re.IGNORECASE)
regexps = [ICP_NOARG, ICP_ENDIS, ICP_1ARG, ICP_2ARG, ICP_3ARG, ICP_4ARG, ICP_5ARG, ICP_DI, ICP_RS]

def split_command_line(line):
    s = StringIO.StringIO(line)
    tg = tokenize.generate_tokens(s.readline)
    # get positions of all separators:
    separators = []
    try:
        for t in tg:
            if (t[0]==tokenize.OP and t[1]==';'):
                separators.append(t[2][1])
    except:
        pass # TokenError will get thrown if in the middle of multline statement
               
    #separators = [t[2][1] for t in tg if (t[0]==tokenize.OP and t[1]==';')]
    sublines = []
    start = 0
    for sep in separators:
        subline = line[start:sep]
        if len(subline) > 0: sublines.append(subline)
        start = sep+1

    subline = line[start:]
    if len(subline) > 0: sublines.append(subline)
    return sublines
    

def generate_prefilter(instrument_controller, log_unfiltered = False):
    ic = instrument_controller

    def prefilter_ICP(self,line,continuation):
        """Alternate prefilter for ICP-formatted commands """
        prefiltered_cmds = ''
        for subline in split_command_line(line):

            if not subline:
                return ''
            
            cmd = subline # default is unchanged subline pass-through... override if it matches an ICP command below
            
            for regexp in regexps:
                match = regexp.match(subline)
                if match:
                    if regexp is ICP_DI:
                         # special handling for d7i=4 (increment drive) command:
                        groups = match.groups()
                        cmd = 'ic.' + 'di' + '('
                    else:
                        groups = match.groups()
                        cmd = 'ic.' + groups[0] + '('
                    for group in groups[1:]:
                        if group: 
                            if group == '+' or group == '*': # this is an enable command
                                cmd += 'True' 
                            elif group == '-': # this is a disable command
                                cmd += 'False'
                            else: # everything else
                                cmd += group + ', '
                    cmd += ')'
                    break # go with the first match    
                  
            prefiltered_cmds += (cmd + ';')
            if DEBUG: print cmd
            if log_unfiltered:
                print 'log_unfiltered: ', log_unfiltered
                ic.write('', subline, timestamp = True) # callback to InstrumentController
        prefiltered_cmds = prefiltered_cmds[:-1] #strip off the trailing ';', only needed as separator
        # also, it gets added even to non-matching lines, so we don't want to pass it along

        # after we're done prefiltering, pass off to the usual prefilter:
        return self._prefilter(prefiltered_cmds,continuation)
        
    return prefilter_ICP

#def activate_prefilter(instrument_controller, log_unfiltered = False):
#    from IPython import InteractiveShell 
#    """Rebind the ICP filter to be the new IPython prefilter, 
#    with a callback to the instrument_controller write() method for logging"""
#    InteractiveShell.prefilter = generate_prefilter(instrument_controller, log_unfiltered)

#def deactivate_prefilter():
#    from IPython import InteractiveShell 
#    """Reset the filter."""
#    InteractiveShell.prefilter = InteractiveShell._prefilter


# Just a heads up at the console
#activate_prefilter()
#print '*** commands such as fp7,2,3 are allowed now.\ntype motor=CreateDummyMotors() to test syntax'

def prefilterICPString(line):
    """Alternate prefilter for ICP-formatted commands """
    prefiltered_cmds = ''
    for subline in split_command_line(line):

        if not subline:
            return ''
        
        cmd = subline # default is unchanged subline pass-through... override if it matches an ICP command below
        
        for regexp in regexps:
            match = regexp.match(subline)
            if match:
                if regexp is ICP_DI:
                    # special handling for d7i=4 (increment drive) command:
                    groups = match.groups()
                    cmd = 'di' + '('
                else:
                    groups = match.groups()
                    cmd = groups[0].lower() + '('
                #cmd = 'ic.' + groups[0].lower() + '('
                for group in groups[1:]:
                    if group: 
                        if group == '+' or group == '*': # this is an enable command
                            cmd += 'True' 
                        elif group == '-': # this is a disable command
                            cmd += 'False'
                        else: # everything else
                            cmd += group + ', '
                cmd += ')'
                break # go with the first match    
              
        prefiltered_cmds += (cmd + ';')
        if DEBUG: print cmd
    prefiltered_cmds = prefiltered_cmds[:-1] #strip off the trailing ';', only needed as separator
    # also, it gets added even to non-matching lines, so we don't want to pass it along

    # after we're done prefiltering, pass off to the usual prefilter:
    return prefiltered_cmds

import IPython
    
class ICPTransformer(object):
    """IPython command line transformer that recognizes and replaces ICP
    commands.
    """
    # XXX: inheriting from PrefilterTransformer as documented gives TypeErrors,
    # but apparently is not needed after all
    priority = 99
    enabled = True
    log_unfiltered = False
    ic = None
    
    def transform(self, line, continue_prompt):
        """Alternate prefilter for ICP-formatted commands """
        prefiltered_cmds = ''
        for subline in split_command_line(line):

            if not subline:
                return ''
            
            cmd = subline # default is unchanged subline pass-through... override if it matches an ICP command below
            
            for regexp in regexps:
                match = regexp.match(subline)
                if match:
                    if regexp is ICP_DI:
                         # special handling for d7i=4 (increment drive) command:
                        groups = match.groups()
                        cmd = 'ic.' + 'di' + '('
                    else:
                        groups = match.groups()
                        cmd = 'ic.' + groups[0] + '('
                    for group in groups[1:]:
                        if group: 
                            if group == '+' or group == '*': # this is an enable command
                                cmd += 'True' 
                            elif group == '-': # this is a disable command
                                cmd += 'False'
                            else: # everything else
                                cmd += group + ', '
                    cmd += ')'
                    break # go with the first match    
                  
            prefiltered_cmds += (cmd + ';')
            if DEBUG: print cmd
            if self.log_unfiltered and (self.ic is not None):
                print 'log_unfiltered: ', self.log_unfiltered
                self.ic.write('', subline, timestamp = True) # callback to InstrumentController
        prefiltered_cmds = prefiltered_cmds[:-1] #strip off the trailing ';', only needed as separator
        # also, it gets added even to non-matching lines, so we don't want to pass it along

        # after we're done prefiltering, pass off to the usual prefilter:
        # return self._prefilter(prefiltered_cmds,continuation)
        
        line = prefiltered_cmds
        
        return line
        
icpt = ICPTransformer()

def activate_prefilter(instrument_controller, log_unfiltered = False):
    icpt.ic = instrument_controller
    icpt.log_unfiltered = log_unfiltered
    
    ip = get_ipython()
    ip.prefilter_manager.register_transformer(icpt)
    return
    
def deactivate_prefilter():
    ip = get_ipython()
    ip.prefilter_manager.unregister_transformer(icpt)
    return
    
