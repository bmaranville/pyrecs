from __future__ import with_statement
from StringIO import StringIO

class PyICPSequence:
    """controls and reads from a sequence file, moving the marker around
       it is defined as an iterator, so getting the next element moves the marker
       can use syntax "for cmd in PyICPSequenceFile(filename):" to iterate
       through file, moving the marker
       """
    def __init__(self, marker = '%', data = ''):
        self.data = data
        self.marker = marker
        self.last = ''
        self.next_command = ''
        self.current_command = ''
    
    def LoadData(self):
        return self.data
    
    def ParseData(self):
        data = self.LoadData()
        
        current_command = None
        seek_pos = 0
        datalen = len(data)
        not_separator = True
        def next_cmd(data, seek_pos):
            cmd = ''
            not_separator = True
            while not_separator and seek_pos < datalen:
                next_char = data[seek_pos]
                if next_char in [';', '\n', '\r']:
                    not_separator = False
                cmd += next_char
                seek_pos += 1
            return cmd, seek_pos
        
        new_data = ''
        match = False
        while seek_pos < datalen and match == False:
            cmd, new_seek_pos = next_cmd(data, seek_pos)
            marker_loc = cmd.rfind(self.marker)
            # check to see if there's anything after the marker - if not, proceed
            if marker_loc > -1 and cmd[marker_loc+1:].rstrip('; \t\n\r') == '':
                #current_command = cmd[:marker_loc]
                match = True # we found it!  set the flag
                current_command = cmd[:marker_loc].strip('; \t\n\r')
                replacement_str = cmd[:marker_loc] + cmd[marker_loc+1:]
                new_data = data[:seek_pos]+replacement_str
            seek_pos = new_seek_pos
        
        if not match:
            seek_pos = 0
            
        # or else we've got a match - what's the next command?
        
        next_command = None
        commands_left = 0
        next_command_found = False
        while seek_pos < datalen:
            cmd, new_seek_pos = next_cmd(data, seek_pos)
            if cmd.strip('; \t\n\r') == '':
                new_data += cmd
            else: # we have a non-blank command:
                commands_left += 1 # add one to the stack
                if not next_command_found:
                    next_command_found = True
                    next_command = cmd.rstrip('; \t\n\r'+self.marker)
                    # check to see if it's already got a marker (or more than one) and clear them
                    # and then put exactly one marker back
                    end_of_command = len(cmd.rstrip('; \t\r\n'+self.marker))
                    cmd = cmd[:end_of_command] + self.marker + cmd[end_of_command:].replace(self.marker, '')
                    #new_data += cmd[:-1] + self.marker + cmd[-1]
                                    
                new_data += cmd
            seek_pos = new_seek_pos
                    
        return current_command, next_command, commands_left, new_data
        
    def GetCurrentCommand(self):
        current_command, next_command, commands_left, new_data = self.ParseData()
        return current_command
        
    def __len__(self):
        current_command, next_command, commands_left, new_data = self.ParseData()
        return commands_left
        
    def clear(self):
        """move the marker to the last command"""
        while self.__len__() > 0:
            self.GetNextCommand()
        
    def GetNextCommand(self):        
        current_command, next_command, commands_left, new_data = self.ParseData()
        self.WriteData(new_data)
        return next_command
    
    def WriteData(self, new_data):
        self.data = new_data

    def __iter__(self):
        return self
            
    def next(self):
        self.next_command = self.GetNextCommand()
        if self.next_command == None:
            raise StopIteration
        else:
            self.last = self.next_command
            return self.next_command
            
    #def popleft(self):
    #    return next(self)

class PyICPSequenceFile(PyICPSequence):
    """controls and reads from a sequence file, moving the marker around
       it is defined as an iterator, so getting the next element moves the marker
       can use syntax "for cmd in PyICPSequenceFile(filename):" to iterate
       through file, moving the marker
       """
    def __init__(self, filename, marker = '%'):
        self.filename = filename
        PyICPSequence.__init__(self, marker)
        
    def LoadData(self):
        with open(self.filename, 'r') as f:
            data = f.read()
        return data 
    
    def WriteData(self, new_data):
        with open(self.filename, 'w') as f:
            f.write(new_data)
    
class PyICPSequenceStringIO(PyICPSequence):
    def __init__(self, string_io_obj, marker = '%' ):
        self.string_io_obj = string_io_obj
        PyICPSequence.__init__(self, marker)
        
    def LoadData(self):
        self.string_io_obj.seek(0)
        data = self.string_io_obj.read()
        return data
    
    def WriteData(self, new_data):
        StringIO.truncate(self.string_io_obj, 0)
        self.string_io_obj.write(new_data)
        
