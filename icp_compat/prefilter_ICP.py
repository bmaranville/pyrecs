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
ICP_NOARG = re.compile(r'^[ \t]*(pasd|pa|pt|pm|pfcal|pu|pl|statline|mon|rs|dp|pr)[ \t]*$', re.IGNORECASE)
ICP_ENDIS = re.compile(r'^[ \t]*(a|w|flm|fla|p|ph)[ \t]*([-+*])[ \t]*$', re.IGNORECASE)
ICP_1ARG = re.compile(r'[ \t]*(pa|pm|ct|pfcal|fix|rel|xmin|xmax|ymin|ymax|ri|sr)[ \t]*[,=]?[ \t]*'+FP_REGEXP+r'[ \t]*$', re.IGNORECASE)
ICP_2ARG = re.compile(r'[ \t]*(init|set|setm|d|dm|dp|u|l|iset|vset)[ \t]*' + INT_REGEXP + r'[ \t]*[,=]?[ \t]*'+FP_REGEXP +r'[ \t]*$', re.IGNORECASE)
ICP_3ARG = re.compile(r'[ \t]*(fp|fpt|fpm)[ \t]*[,=]?[ \t]*'+INT_REGEXP + SEP + FP_REGEXP + SEP + FP_REGEXP + r'[ \t]*$', re.IGNORECASE)   
ICP_4ARG = re.compile(r'^[ \t]*(fp|fpt|fpm|iscan)[ \t]*[,=]?[ \t]*'+INT_REGEXP + SEP + FP_REGEXP + SEP + FP_REGEXP + SEP + FP_REGEXP + r'[ \t]*$', re.IGNORECASE)
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

#import IPython
#    
#class ICPTransformer(object):
#    """IPython command line transformer that recognizes and replaces ICP
#    commands.
#    """
#    # XXX: inheriting from PrefilterTransformer as documented gives TypeErrors,
#    # but apparently is not needed after all
#    priority = 99
#    enabled = True
#    log_unfiltered = False
#    ic = None
#    
#    def transform(self, line, continue_prompt):
#        """Alternate prefilter for ICP-formatted commands """
#        prefiltered_cmds = ''
#        for subline in split_command_line(line):

#            if not subline:
#                return ''
#            
#            cmd = subline # default is unchanged subline pass-through... override if it matches an ICP command below
#            
#            for regexp in regexps:
#                match = regexp.match(subline)
#                if match:
#                    if regexp is ICP_DI:
#                         # special handling for d7i=4 (increment drive) command:
#                        groups = match.groups()
#                        cmd = 'ic.' + 'di' + '('
#                    else:
#                        groups = match.groups()
#                        cmd = 'ic.' + groups[0] + '('
#                    for group in groups[1:]:
#                        if group: 
#                            if group == '+' or group == '*': # this is an enable command
#                                cmd += 'True' 
#                            elif group == '-': # this is a disable command
#                                cmd += 'False'
#                            else: # everything else
#                                cmd += group + ', '
#                    cmd += ')'
#                    break # go with the first match    
#                  
#            prefiltered_cmds += (cmd + ';')
#            if DEBUG: print cmd
#            if self.log_unfiltered and (self.ic is not None):
#                print 'log_unfiltered: ', self.log_unfiltered
#                self.ic.write('', subline, timestamp = True) # callback to InstrumentController
#        prefiltered_cmds = prefiltered_cmds[:-1] #strip off the trailing ';', only needed as separator
#        # also, it gets added even to non-matching lines, so we don't want to pass it along

#        # after we're done prefiltering, pass off to the usual prefilter:
#        # return self._prefilter(prefiltered_cmds,continuation)
#        
#        line = prefiltered_cmds
#        
#        return line

class ICPCommandList(object):
    """ base class for different kinds of icp commands """
    # some class variables (constants)
    FP_REGEXP = r'([-+]?[0-9]*\.?[0-9]+)'
    INT_REGEXP = r'([0-9]+)'
    SEP = r'[ \t]*[ ,=][ \t]*'
    END = r'[ \t]*$'
    extra_args = ''
    
    def __init__(self, rootname=''):
        self.rootname = rootname
        self.clear_all()
    
    def clear_all(self):
        self.commands = {}
        self.commands_compiled = {}
        self.command_conversion = {}
    
    def match_and_replace(self, subline):
        match_found = False
        cmd = subline
        for numarg in self.commands_compiled:
            regexp = self.commands_compiled[numarg]
            match = regexp.match(subline)
            if match:
                match_found = True
                groups = match.groups()
                self.groups = groups
                cmd = self.rootname + self.command_conversion[groups[0]] + '('
                for group in groups[1:numarg+1]:
                    if group: 
                        if group == '+' or group == '*': # this is an enable command
                            cmd += 'True' 
                        elif group == '-': # this is a disable command
                            cmd += 'False'
                        else: # everything else
                            cmd += group + ', '
                for group in groups[numarg+1:]: # extra, kwargs
                    cmd += repr(group) + ', '
                cmd += self.extra_args
                cmd += ')'
                break # go with the first match
        return match_found, cmd
        
    def add(self, cmd_string, numargs=0, new_cmd_string=None):
        """ add new command (that takes number arguments)
        to the list of ICP-style commands to intercept
        numargs should be integer or list of integers """
        if new_cmd_string is None: new_cmd_string = cmd_string
        if not hasattr(numargs, '__iter__'): numargs = [numargs,] # convert to list
        for numarg in numargs:
            if not numarg in self.commands:
                self.commands[numarg] = [cmd_string,]
            elif not cmd_string in self.commands[numarg]:
                self.commands[numarg].append(cmd_string)
        self.command_conversion[cmd_string] = new_cmd_string
        self.recompile_commands()
    
    def remove_command(self, cmd_string):
        for numarg in self.commands.keys():
            if cmd_string in self.commands[numarg]:
                self.commands[numarg].remove(cmd_string)
        self.recompile_commands()
    
    def recompile_commands(self):
        self.commands_compiled = {}
        for numarg in self.commands.keys():
            cmds = self.commands[numarg]
            if len(cmds) > 0:
                regexp = r'[ \t]*(' + r'|'.join(cmds) + r')'
                if numarg > 0:
                    regexp += r'[ \t]*[,=]?[ \t]*'
                    regexp += self.SEP.join([self.FP_REGEXP,] * numarg)
                regexp += self.END
                self.commands_compiled[numarg]=re.compile(regexp, re.IGNORECASE)

class ICPEnableDisableCommands(ICPCommandList):
    """ commands that take + or - as only argument, and do an enable or disable """
    def recompile_commands(self):
        self.commands_compiled = {}
        for numarg in self.commands.keys():
            cmds = self.commands[numarg]
            if len(cmds) > 0:
                regexp = r'[ \t]*(' + r'|'.join(cmds) + r')[ \t]*([-+*])[ \t]*$'
                self.commands_compiled[numarg]=re.compile(regexp, re.IGNORECASE)
                
class ICPIncrementCommands(ICPCommandList):
    """ commands that increment the value of a device - always 2 arguments:
    motornum and delta """
    extra_args = ''
    
    def recompile_commands(self):
        self.commands_compiled = {}
        for numarg in self.commands.keys():
            cmds = self.commands[numarg]
            if len(cmds) > 0:
                regexp = r'[ \t]*('+r'|'.join(cmds)+r')[ \t]*'+self.INT_REGEXP+r'[ \t]*i'+r'[ \t]*[,=]?[ \t]*'+self.FP_REGEXP+r'[ \t]*$'
                self.commands_compiled[numarg]=re.compile(regexp, re.IGNORECASE)
                
class ICPTiedCommands(ICPCommandList):
    """ commands that tie two motors, usually 3 and 4 """
    extra_args = ''
    
    def recompile_commands(self):
        
        self.commands_compiled = {}
        for numarg in self.commands.keys():
            cmds = self.commands[numarg]
            if len(cmds) > 0:
                regexp = r'[ \t]*(' + r'|'.join(cmds) + r')'+self.INT_REGEXP+r'[ \t]*t'
                if numarg > 0:
                    regexp += r'[ \t]*[,=]?[ \t]*'
                    regexp += self.SEP.join([self.FP_REGEXP,] * (numarg - 1))
                regexp += self.END
                self.commands_compiled[numarg]=re.compile(regexp, re.IGNORECASE)                

class ICPArgKeywordCommands(ICPCommandList):
    """ commands that include keywords with values in addition to arguments """
    extra_args = ''    
    def recompile_commands(self):
        self.commands_compiled = {}
        for numarg in self.commands.keys():
            cmds = self.commands[numarg]
            if len(cmds) > 0:
                regexp = r'[ \t]*(' + r'|'.join(cmds) + r')'
                if numarg > 0:
                    regexp += r'[ \t]*[,=]?[ \t]*'
                    regexp += self.SEP.join([self.FP_REGEXP,] * numarg)
                regexp += '(?:' + self.SEP + r'([a-z0-9]+)[ \t]*[ ,=][ \t]*([a-z0-9]+))*'
                regexp += self.END
                self.commands_compiled[numarg]=re.compile(regexp, re.IGNORECASE)

class ICPStringArgCommands(ICPCommandList):
    """ command that takes an arbitrary string as input.
    e.g. rsf and drsf """
    extra_args = ''
    def recompile_commands(self):
        self.commands_compiled = {}
        for numarg in self.commands.keys():
            cmds = self.commands[numarg]
            if len(cmds) > 0:
                regexp = r'[ \t]*(' + r'|'.join(cmds) + r')'
                if numarg > 0:
                    regexp += r'[ \t]*[,=]?[ \t]*'
                    regexp += self.SEP.join([self.FP_REGEXP,] * numarg)
                regexp += '(?:' + self.SEP + r'([a-z0-9\._]+))*'
                regexp += self.END
                self.commands_compiled[numarg]=re.compile(regexp, re.IGNORECASE)

class ICPTransformer(object):
    """IPython command line transformer that recognizes and replaces ICP
    commands.
    """
    # some class variables (constants)
    FP_REGEXP = r'([-+]?[0-9]*\.?[0-9]+)'
    INT_REGEXP = r'([0-9]+)'
    SEP = r'[ \t]*[,][ \t]*'
    END = r'[ \t]*$'
    
    # XXX: inheriting from PrefilterTransformer as documented gives TypeErrors,
    # but apparently is not needed after all
    def __init__(self, rootname=''):
        self.rootname = rootname
        self.priority = 99
        self.enabled = True
        self.log_unfiltered = False
        self.ic = None
        
        self.arg_commands = ICPCommandList(rootname=rootname)
        self.en_dis_commands = ICPEnableDisableCommands(rootname=rootname)
        self.increment_commands = ICPIncrementCommands(rootname=rootname)
        self.tied_commands = ICPTiedCommands(rootname=rootname)
        self.arg_kw_commands = ICPArgKeywordCommands(rootname=rootname)
        self.stringarg_commands = ICPStringArgCommands(rootname=rootname)
        self.icp_commands = [self.arg_commands, self.en_dis_commands, self.increment_commands, self.tied_commands, self.arg_kw_commands, self.stringarg_commands]
    
    def register_icp_conversions(self, icp_conversions):
        """ take a dict of 'arg_commands': {'....'} ... and register all """
        for key in icp_conversions:
            subcmds = icp_conversions[key]
            cmd_list = getattr(self, key)
            for cmdname in subcmds:
                cmd_info = subcmds[cmdname]
                cmd_list.add(cmdname, cmd_info['numargs'], cmd_info['pyrecs_cmd'])
                  
    def transform(self, line, continue_prompt):
        """Alternate prefilter for ICP-formatted commands """
        prefiltered_cmds = ''
        prefiltered_cmdlist = []
        for subline in split_command_line(line):
            if not subline:
                return ''
            
            cmd = subline
            for cmd_list in self.icp_commands:
                matched, new_cmd = cmd_list.match_and_replace(subline)
                if matched == True: 
                    cmd = new_cmd
                    break # go with the first match
            
            #prefiltered_cmds += (cmd + ';')
            prefiltered_cmdlist.append(cmd)
            if DEBUG: print cmd
            if self.log_unfiltered and (self.ic is not None):
                print 'log_unfiltered: ', self.log_unfiltered
                self.ic.write('', subline, timestamp = True) # callback to InstrumentController
        prefiltered_cmds = ';'.join(prefiltered_cmdlist)
        #prefiltered_cmds = prefiltered_cmds[:-1] #strip off the trailing ';', only needed as separator
        # also, it gets added even to non-matching lines, so we don't want to pass it along

        # after we're done prefiltering, pass off to the usual prefilter:
        # return self._prefilter(prefiltered_cmds,continuation)
        
        line = prefiltered_cmds
        
        return line
        
icpt = ICPTransformer(rootname='ic.')

def prefilter_ICP(self,line,continuation):
    """Alternate prefilter for ICP-formatted commands """
    prefiltered_cmds = icpt.transform(line, continuation)
    return self._prefilter(prefiltered_cmds,continuation)
    
try:
    get_ipython() # test for newer version of Ipython
    
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
        
except NameError:
    # old-style prefiltering (ipython 0.10)
    def activate_prefilter(instrument_controller, log_unfiltered = False):
        from IPython.iplib import InteractiveShell 
        """Rebind the ICP filter to be the new IPython prefilter, 
        with a callback to the instrument_controller write() method for logging"""
        #InteractiveShell.prefilter = generate_prefilter(instrument_controller, log_unfiltered)
        InteractiveShell.prefilter = prefilter_ICP

    def deactivate_prefilter():
        from IPython.iplib import InteractiveShell 
        """Reset the filter."""
        InteractiveShell.prefilter = InteractiveShell._prefilter
        
        
