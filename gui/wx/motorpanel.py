#!/usr/bin/env python
# -*- coding: utf-8 -*-
# generated by wxGlade 0.6.3 on Fri Nov  5 09:50:14 2010

import wx
import functools
import os
from ordered_dict import OrderedDict
from pprint import pformat

DEBUG = False
MOTOR_CFG_FILE = os.path.join(os.path.dirname(__file__), 'motor_cfg_file.txt')

# begin wxGlade: extracode
# end wxGlade

"""
motors = OrderedDict([ 
'a1': {'motnum': 1, 'label': 'Slit 1 Aperture', 'visible': False},
'a2': {'motnum': 2, 'label': 'Slit 2 Aperture', 'visible': False},
])

"""
            
COL_LABELS = [
            'Motor Name',
            'Position',
            'Destination',
            '']

class MotorNamer(wx.Dialog):
    def __init__(self, parent, id=-1, motors=None):
        wx.Dialog.__init__(self, parent, id)
        self.motors = motors.copy()
        self.nameboxes = {}
        grid_sizer = wx.FlexGridSizer(len(self.motors), 2, 0, 0)
        for motor_id in self.motors:
            motor = self.motors[motor_id]
            name = motor['label']
            new_namebox = wx.TextCtrl(self, -1, '%s' % (name), style=wx.TE_RIGHT, size=(300,-1))
            self.nameboxes[motor_id] = new_namebox
            
        self.done_button = wx.Button(self, -1, "Done")
        self.undo_button = wx.Button(self, -1, "Undo")
        self.Bind(wx.EVT_BUTTON, self.undo, self.undo_button)
        self.Bind(wx.EVT_BUTTON, self.done, self.done_button)
        sizer_1 = wx.BoxSizer(wx.VERTICAL)
        sizer_2 = wx.BoxSizer(wx.HORIZONTAL)
        for motor_id in self.motors:   
            grid_sizer.Add(wx.StaticText(self, -1, '%s:' % (motor_id,)), 0, wx.ALIGN_CENTER_VERTICAL, 0)
            grid_sizer.Add(self.nameboxes[motor_id],  0, wx.ALIGN_RIGHT|wx.ALIGN_CENTER_VERTICAL, 0)
        sizer_2.Add(self.undo_button)
        sizer_2.Add(self.done_button)
        sizer_1.Add(grid_sizer)
        sizer_1.Add(sizer_2)
        self.SetSizer(sizer_1)
        sizer_1.Fit(self)
        self.Layout()
    
    def undo(self):
        for motor_id in self.motors:
            self.nameboxes[motor_id].SetValue(self.motors[motor_id]['label'])
        
    def done(self, event = None):
        ret_code = wx.ID_OK
        for motor_id in self.motors:
            self.motors[motor_id]['label'] = self.nameboxes[motor_id].GetValue()
        self.EndModal(ret_code)   

class MotorChooser(wx.Dialog):
    def __init__(self, parent, id=-1, motors=None):
        wx.Dialog.__init__(self, parent, id)
        self.motors = motors.copy()
        self.checkboxes = {}
        for motor_id in self.motors:
            motor = self.motors[motor_id]
            name = motor['label']
            val = motor['visible']
            motnum = motor['motnum']
            new_checkbox = wx.CheckBox(self, -1, '%d: %s' % (motnum, name))
            self.checkboxes[motor_id] = new_checkbox
            new_checkbox.SetValue(val)
            
        self.done_button = wx.Button(self, -1, "Done")
        self.clear_all_button = wx.Button(self, -1, "Clear all")
        self.select_all_button = wx.Button(self, -1, "Select All")
        self.Bind(wx.EVT_BUTTON, self.select_all, self.select_all_button)
        self.Bind(wx.EVT_BUTTON, self.clear_all, self.clear_all_button)
        self.Bind(wx.EVT_BUTTON, self.done, self.done_button)
        sizer_1 = wx.BoxSizer(wx.VERTICAL)
        sizer_2 = wx.BoxSizer(wx.HORIZONTAL)
        for motor_id in self.motors:
            sizer_1.Add(self.checkboxes[motor_id])
        sizer_2.Add(self.select_all_button)
        sizer_2.Add(self.clear_all_button)
        sizer_2.Add(self.done_button)
        sizer_1.Add(sizer_2)
        self.SetSizer(sizer_1)
        sizer_1.Fit(self)
        self.Layout()
    
    def select_all(self, event=None):
        for motor_id in self.motors:
            self.checkboxes[motor_id].SetValue(True)
        
    def clear_all(self, event = None):
        for motor_id in self.motors:
            self.checkboxes[motor_id].SetValue(False)
            
    def done(self, event = None):
        ret_code = wx.ID_OK
        for motor_id in self.motors:
            self.motors[motor_id]['visible'] = self.checkboxes[motor_id].GetValue()
        self.EndModal(ret_code)  

class MotorConfiguration:
    """ works with the various panels to provide motor information.  Includes a menu to modify
    this configuration.  Requires overriding of get_num_mots in used version """
    
    def __init__(self, parent, motors_file=MOTOR_CFG_FILE):
        """ make a motors object! """
        self.parent = parent
        self.motors_file = motors_file
        if not os.access(motors_file, os.R_OK):
            # then generate a new motors_file
            self.generate_new_motors_file()
            
        self.motors = eval(open(motors_file).read())
        
        self.motormenu = wx.Menu()
        self.motormenu_title = '&Motors'
        showall_menuopt = self.motormenu.Append(wx.ID_ANY, 'Show all motors', 'Show all motors')
        wx.EVT_MENU(self.parent, showall_menuopt.GetId(), self.ShowAllMotors)
        chooser_menuopt = self.motormenu.Append(wx.ID_ANY, 'Choose motors to display/control', 'Choose motors to display/control')
        wx.EVT_MENU(self.parent, chooser_menuopt.GetId(), self.ChooserDialog)
        namer_menuopt = self.motormenu.Append(wx.ID_ANY, 'Change motor display labels', 'Change motor display labels')
        wx.EVT_MENU(self.parent, namer_menuopt.GetId(), self.NamerDialog)
        #self.Bind(wx.EVT_MENU, self.ChooserDialog, chooser_menuopt)
        
    def ShowAllMotors(self, event=None):
        for motor_id in self.motors:
            self.motors[motor_id]['visible'] = True         
        self.__do_layout()
     
    def ChooserDialog(self, event = None):
        dlg = MotorChooser(self.parent, -1, self.motors)
        if dlg.ShowModal() == wx.ID_OK:
            #print "chosen:", dlg.enabled
            self.motors = dlg.motors
            self.parent.update_motors(self.motors)
            self.update_motors_file()
        #self.motors_enabled = dlg.enabled
        #self.__do_layout()
        
    def NamerDialog(self, event = None):
        dlg = MotorNamer(self.parent, -1, self.motors)
        if dlg.ShowModal() == wx.ID_OK:
            #print "chosen:", dlg.enabled
            self.motors = dlg.motors
            self.parent.update_motors(self.motors)
            self.update_motors_file()
            
    def generate_new_motors_file(self):
        num_mots = self.get_num_mots()
        motnums = range(1, num_mots+1)
        mot_ids = ['a%d' % (motnum,) for motnum in motnums]
        new_motors = OrderedDict()
        for motnum in motnums:
            new_motor = {}
            new_motor['motnum'] = motnum
            new_motor['label'] = ''
            new_motor['visible'] = True
            new_id = 'a%d' % (motnum,)
            new_motors[new_id] = new_motor
        open(self.motors_file, 'w').write(pformat(new_motors))
        self.motors = new_motors
        
    def update_motors_file(self):
        open(self.motors_file, 'w').write(pformat(self.motors))
    
    def get_num_mots(self):
        # override in used version so that we can generate a new motors file when needed
        pass

class MotorPanel(wx.Panel):
    def __init__(self, parent, id = -1, motors_cfg=None):
        wx.Panel.__init__(self, parent, id)
        self.menus = []
        self.buttons = []
        
        self.motors = motors_cfg.motors
        self.motors_cfg = motors_cfg
                
        self.col_label = []
        self.motor_label = {} # these lists will be populated with wx objects
        self.motor_pos = {}
        self.motor_dest = {}
        self.motor_gobuttons = {}
        # make title line
        col_labels = ['Motor Name', 'Position', 'Destination', '']
        for c in range(4):
            label = col_labels[c]
            newlabel = wx.StaticText(self, -1, label)
            self.col_label.append(newlabel)
            newlabel.SetFont(wx.Font(10, wx.DEFAULT, wx.NORMAL, wx.BOLD, 0, ""))
        for motor_id in self.motors:
            self.motor_label[motor_id] = wx.StaticText(self, -1, '%s: %s' % (motor_id, self.motors[motor_id]['label']))
            self.motor_pos[motor_id] = wx.StaticText(self, -1, 'Unknown')
            self.motor_dest[motor_id] = wx.TextCtrl(self, -1, '%.3f' % 0.0, style=wx.TE_RIGHT)
            self.motor_gobuttons[motor_id] = wx.Button(self, -1, "Go")
            func = functools.partial(self.motor_go, motor_id = motor_id)
            self.Bind(wx.EVT_BUTTON, func, self.motor_gobuttons[motor_id])
        self.buttons.extend(self.motor_gobuttons.values())
        self.move_all_button = wx.Button(self, -1, 'Move all\nat once')
        self.Bind(wx.EVT_BUTTON, self.move_all, self.move_all_button)
        self.buttons.append(self.move_all_button)
        self.__set_properties()
        #self.__do_layout()
        self.update_all_motors()
        
    def __set_properties(self):
        pass
        # begin wxGlade: MyFrame.__set_properties
        # self.SetTitle("frame_1")
        # end wxGlade
    
    def __do_layout(self):
        # begin wxGlade: MyFrame.__do_layout
        #sizer_1 = wx.BoxSizer(wx.VERTICAL)
        spacer = wx.StaticText(self, -1, '')
        grid_sizer_1 = wx.FlexGridSizer(len(self.motors)+1, 4, 0, 0)
        #grid_sizer_1 = wx.GridBagSizer()
        self.sizer = grid_sizer_1
        for label in self.col_label:
            grid_sizer_1.Add(label, 0, 0, 0)
        for motor_id in self.motors:
            motor = self.motors[motor_id]
            show = motor['visible']
            if show == True:
                grid_sizer_1.Add(self.motor_label[motor_id], 0, wx.ALIGN_CENTER_VERTICAL, 0)
                grid_sizer_1.Add(self.motor_pos[motor_id], 0, wx.ALIGN_RIGHT|wx.ALIGN_CENTER_VERTICAL, 0)
                grid_sizer_1.Add(self.motor_dest[motor_id], 0, wx.ALIGN_CENTER_VERTICAL, 0)
                grid_sizer_1.Add(self.motor_gobuttons[motor_id], 0, wx.ALIGN_CENTER_VERTICAL, 0)
            self.motor_label[motor_id].Show(show)
            self.motor_pos[motor_id].Show(show)
            self.motor_dest[motor_id].Show(show)
            self.motor_gobuttons[motor_id].Show(show)
            self.motor_gobuttons[motor_id].Enable(show)
        #grid_sizer_1.Add(self.move_all_button, (self.num_motors+1, 2), (1,1), wx.ALIGN_CENTER_VERTICAL, 5)
        grid_sizer_1.Add(spacer)
        grid_sizer_1.Add(spacer)
        grid_sizer_1.Add(self.move_all_button, 0, wx.ALIGN_CENTER_VERTICAL, 5)
        self.SetSizer(grid_sizer_1)
        self.sizer.Fit(self)
        #self.Layout()
        #self.Refresh()
        self.TopLevelParent.Fit()
        #self.TopLevelParent.Layout()
        
        #sizer_1.Add(self, 1, wx.EXPAND, 0)
         
    def motor_go(self, event = None, motor_id = None):
        if motor_id is None:
            return
        try:
            dest = float(self.get_destination(motor_id))
        except ValueError:
            # improperly formatted destination!
            return
        motnum = self.motors[motor_id]['motnum']
        self.drive_motor(motnum, dest)
        self.update_all_motors()
        if DEBUG: print "Driving %s to %f" % (self.motornames[motnum-1], dest)
    
    def move_all(self, event = None):
        motnums = []
        positions = []
        for motor_id in self.motors:
            motor = self.motors[motor_id]
            if motor['visible']:
                try:
                    positions.append(float(self.get_destination(motor_id)))
                    motnums.append(motor['motnum'])
                except ValueError:
                    # improperly formatted destination!
                    pass

        self.drive_multi_motor(motnums, positions)
                       
    def update_position_label(self, motor_id, newpos):
        self.motor_pos[motor_id].SetLabel('%.3f' % newpos)
        #getattr(self, 'motor_pos_%d' % motnum).SetLabel('%.3f' % newpos)
    
    def get_destination(self, motor_id):
        return self.motor_dest[motor_id].GetValue()
        
    def update_destination(self, motor_id, newpos):
        self.motor_dest[motor_id].SetValue('%.3f' % newpos)
        #getattr(self, 'motor_dest_%d' % motnum).SetValue('%.3f' % newpos)
        
    def update_all_motors(self):
        for motor_id in self.motors:
            motnum = self.motors[motor_id]['motnum']
            newpos = self.get_motor_pos(motnum)
            if newpos is not None:
                self.update_position_label(motor_id, newpos)
                self.update_destination(motor_id, newpos)
                label = '%s: %s' % (motor_id, self.motors[motor_id]['label'])
                self.motor_label[motor_id].SetLabel(label)
        self.__do_layout()  
    
    def drive_multi_motor(self, motnums, positions): #override to add functionality
        pass 
    
    def drive_motor(self, motnum, position): # override to add functionality
        pass
        
    def get_motor_pos(self, motnum):
        # use self.update_position_label in overriding function
        return None
        
    def get_num_mots(self):
        # find out how many motors are attached: from server.
        return 0 

class RapidScanPanel(wx.Panel):
    def __init__(self, parent, id = -1, motors_cfg=None):
        wx.Panel.__init__(self, parent, id)
        self.menus = []
        self.buttons = []
        self.visible_motors = []
        self.motors = motors_cfg.motors
        self.motors_cfg = motors_cfg
        
        col_labels = ['Motor', 'Pos', 'Start', 'Stop', '']
        self.col_label = []

        # make title line
        for label in col_labels:
            newlabel = wx.StaticText(self, -1, label)
            self.col_label.append(newlabel)
            newlabel.SetFont(wx.Font(10, wx.DEFAULT, wx.NORMAL, wx.BOLD, 0, ""))
        
        #choices = [motor['label'] for motor in self.motors if motor['visible']]
        self.motor_choice = wx.Choice(self, -1 )
        self.motor_pos = wx.StaticText(self, -1, 'Unknown', size=(80,-1))
        self.motor_start = wx.TextCtrl(self, -1, '%.3f' % 0.0, style=wx.TE_RIGHT)
        self.motor_dest = wx.TextCtrl(self, -1, '%.3f' % 0.0, style=wx.TE_RIGHT)
        self.motor_gobutton = wx.Button(self, -1, "Go")
        self.Bind(wx.EVT_BUTTON, self.run, self.motor_gobutton)
        self.Bind(wx.EVT_CHOICE, self.update_choice_pos, self.motor_choice)
        
        self.buttons.append(self.motor_gobutton)
        self.buttons.append(self.motor_choice)
        
        self.__set_properties()
        self.__do_layout()
        self.update_all_motors()
        
    def __set_properties(self):
        pass
        # begin wxGlade: MyFrame.__set_properties
        # self.SetTitle("frame_1")
        # end wxGlade
    
    def __do_layout(self):
        # begin wxGlade: MyFrame.__do_layout
        #sizer_1 = wx.BoxSizer(wx.VERTICAL)
        spacer = wx.StaticText(self, -1, '')
        grid_sizer_1 = wx.FlexGridSizer(2, 5, 0, 0)
        #grid_sizer_1 = wx.GridBagSizer()
        self.sizer = wx.BoxSizer(wx.VERTICAL)
        for i, label in enumerate(self.col_label):
            #grid_sizer_1.Add(label, (0,i), (1,1), 0, 0)
            grid_sizer_1.Add(label, 0, 0, 0)
        
        motors = self.motors
        self.choice_ids = [motor_id for motor_id in motors if motors[motor_id]['visible'] is True]
        choices = [motors[motor_id]['label'] for motor_id in self.choice_ids]
              
        self.motor_choice.SetItems(choices)
       
        grid_sizer_1.Add(self.motor_choice, 0, wx.ALIGN_CENTER_VERTICAL, 0)
        grid_sizer_1.Add(self.motor_pos, 0, wx.ALIGN_CENTER_VERTICAL, 0)
        grid_sizer_1.Add(self.motor_start, 0, wx.ALIGN_RIGHT|wx.ALIGN_CENTER_VERTICAL, 0)
        grid_sizer_1.Add(self.motor_dest, 0, wx.ALIGN_CENTER_VERTICAL, 0)
        grid_sizer_1.Add(self.motor_gobutton, 0, wx.ALIGN_CENTER_VERTICAL, 0)
        
        rs_label = wx.StaticText(self, -1, 'RAPID SCAN:')
        rs_label.SetFont(wx.Font(10, wx.DEFAULT, wx.NORMAL, wx.BOLD, 0, ""))
        self.sizer.Add(wx.StaticLine(self, -1), 0, wx.EXPAND)
        self.sizer.Add(rs_label, 0,0,0)
        self.sizer.Add(grid_sizer_1)
        
        self.SetSizer(self.sizer)
        self.sizer.Fit(self)
        #self.Layout()
        #self.Refresh()
        self.TopLevelParent.Fit()
        #self.TopLevelParent.Layout()
        
        #sizer_1.Add(self, 1, wx.EXPAND, 0)
    
    def run(self, event = None):
        selection = self.motor_choice.GetCurrentSelection()
        visible_motors = [motor_id for motor_id in self.motors if self.motors[motor_id]['visible'] is True]
        chosen_motor_id = visible_motors[selection]
        motnum = self.motors[chosen_motor_id]['motnum'] 
        
        dest_pos = float(self.motor_dest.GetValue())
        start_pos = float(self.motor_start.GetValue())
        last_rs = {'start_pos': start_pos, 'dest_pos': dest_pos}
        self.motors[chosen_motor_id]['last_RapidScan'] = last_rs
        self.motors_cfg.update_motors_file()
        self.RapidScan(motnum, start_pos, dest_pos)
     
    def RapidScan(self, motnum, start_pos, end_pos): #override to add functionality
        pass
    
    def update_choice_pos(self, evt=None):
        selection = self.motor_choice.GetCurrentSelection()
        visible_motors = [motor_id for motor_id in self.motors if self.motors[motor_id]['visible'] is True]
        chosen_motor_id = visible_motors[selection]
        self.motor_pos.SetLabel('%.3f' % (self.get_motor_pos(self.motors[chosen_motor_id]['motnum'])))
        if 'last_RapidScan' in self.motors[chosen_motor_id]:
            rs = self.motors[chosen_motor_id]['last_RapidScan']
            self.motor_start.SetValue(str(rs.get('start_pos', 0.0)))
            self.motor_dest.SetValue(str(rs.get('dest_pos', 0.0)))
        
    def get_motor_pos(self, motnum):
        # use self.update_position_label in overriding function
        pass
    
    def update_all_motors(self):
        visible_motors = [motor_id for motor_id in self.motors if self.motors[motor_id]['visible'] is True]
        if not self.visible_motors == visible_motors:
            labels = ['%s: %s' % (motor_id, self.motors[motor_id]['label']) for motor_id in visible_motors]
            self.motor_choice.SetItems(labels)
            self.visible_motors = visible_motors
        self.update_choice_pos()

class CountPanel(wx.Panel):
    def __init__(self, parent, id = -1):
        wx.Panel.__init__(self, parent, id)
        self.menus = []
        self.buttons = []

        self.label_1 = wx.StaticText(self, -1, 'Monitor Preset:\n(negative for time)', size=(80,-1))
        self.monitor_entry = wx.TextCtrl(self, -1, '%.3f' % -1.0, style=wx.TE_RIGHT)
        self.count_button = wx.Button(self, -1, "Count")
        self.result = wx.StaticText(self, -1, '')
        
        self.Bind(wx.EVT_BUTTON, self.run, self.count_button)
        
        self.buttons.append(self.count_button)
        
        self.__set_properties()
        self.__do_layout()
        self.update_all_motors()
        
    def __set_properties(self):
        pass
        # begin wxGlade: MyFrame.__set_properties
        # self.SetTitle("frame_1")
        # end wxGlade
    
    def __do_layout(self):
        # begin wxGlade: MyFrame.__do_layout
        self.sizer_1 = wx.BoxSizer(wx.VERTICAL)
        self.sizer_2 = wx.BoxSizer(wx.HORIZONTAL)
        self.sizer_2.Add(self.label_1, 0, wx.ALIGN_CENTER_VERTICAL|wx.ALIGN_RIGHT, 0)
        self.sizer_2.Add(self.monitor_entry, 0, wx.ALIGN_CENTER_VERTICAL, 0)
        self.sizer_2.Add(self.count_button, 0, wx.ALIGN_CENTER_VERTICAL, 0)
        self.sizer_2.Add(self.result, 0, wx.ALIGN_CENTER_VERTICAL|wx.ALIGN_LEFT, 0)
        
        ct_label = wx.StaticText(self, -1, 'COUNT:')
        ct_label.SetFont(wx.Font(10, wx.DEFAULT, wx.NORMAL, wx.BOLD, 0, ""))
        self.sizer_1.Add(ct_label, 0,0,0)
        self.sizer_1.Add(self.sizer_2)
        
        self.SetSizer(self.sizer_1)
        self.sizer_1.Fit(self)
        #self.Layout()
        #self.Refresh()
        self.TopLevelParent.Fit()
        #self.TopLevelParent.Layout()
        
        #sizer_1.Add(self, 1, wx.EXPAND, 0)
    
    def run(self, event = None):
        monitor = float(self.monitor_entry.GetValue())
        self.Count(monitor)
     
    def Count(self, motnum, start_pos, end_pos): #override to add functionality
        pass
    
    def get_last_count(self): # override this to make the thing work!
        pass
    
    def update_all_motors(self):
        self.result.SetLabel(pformat(self.get_last_count()))


class FindPeakPanel(wx.Panel):
    def __init__(self, parent, id = -1, motors_cfg=None):
        wx.Panel.__init__(self, parent, id)
        self.menus = []
        self.buttons = []
        self.visible_motors = []
        self.motors = motors_cfg.motors
        self.motors_cfg = motors_cfg
        
        col_labels = ['Motor', 'Pos', 'Range', 'Step', 'Monitor', '']
        self.col_label = []

        # make title line
        for label in col_labels:
            newlabel = wx.StaticText(self, -1, label)
            self.col_label.append(newlabel)
            newlabel.SetFont(wx.Font(10, wx.DEFAULT, wx.NORMAL, wx.BOLD, 0, ""))
        
        #choices = [motor['label'] for motor in self.motors if motor['visible']]
        self.motor_choice = wx.Choice(self, -1 )
        self.motor_pos = wx.StaticText(self, -1, 'Unknown', size=(80,-1))
        self.motor_range = wx.TextCtrl(self, -1, '%.3f' % 0.0, style=wx.TE_RIGHT)
        self.motor_step = wx.TextCtrl(self, -1, '%.3f' % 0.0, style=wx.TE_RIGHT)
        self.monitor = wx.TextCtrl(self, -1, '%.3f' % 0.0, style=wx.TE_RIGHT)
        self.motor_gobutton = wx.Button(self, -1, "Go")
        self.fit_result = wx.StaticText(self, -1, 'Unknown', size=(250,-1))
        
        self.drive_fit_button = wx.Button(self, -1, "Drive to fit")
        # need to add "last fitted peak" here, along with 
        # "drive to it" button
        
        self.Bind(wx.EVT_BUTTON, self.run, self.motor_gobutton)
        self.Bind(wx.EVT_CHOICE, self.update_choice_pos, self.motor_choice)
        self.Bind(wx.EVT_BUTTON, self.DrivePeak, self.drive_fit_button)
        
        self.buttons.append(self.motor_gobutton)
        self.buttons.append(self.drive_fit_button)
        self.buttons.append(self.motor_choice)
        
        self.__set_properties()
        self.__do_layout()
        self.update_all_motors()
        
    def __set_properties(self):
        pass
        # begin wxGlade: MyFrame.__set_properties
        # self.SetTitle("frame_1")
        # end wxGlade
    
    def __do_layout(self):
        # begin wxGlade: MyFrame.__do_layout
        #sizer_1 = wx.BoxSizer(wx.VERTICAL)
        spacer = wx.StaticText(self, -1, '')
        grid_sizer_1 = wx.FlexGridSizer(2, 6, 0, 0)
        grid_sizer_2 = wx.FlexGridSizer(1, 3, 0, 0)
        #grid_sizer_1 = wx.GridBagSizer()
        self.sizer = wx.BoxSizer(wx.VERTICAL)
        for i, label in enumerate(self.col_label):
            #grid_sizer_1.Add(label, (0,i), (1,1), 0, 0)
            grid_sizer_1.Add(label, 0, 0, 0)
        
        motors = self.motors
        self.choice_ids = [motor_id for motor_id in motors if motors[motor_id]['visible'] is True]
        choices = [motors[motor_id]['label'] for motor_id in self.choice_ids]
              
        self.motor_choice.SetItems(choices)
       
        grid_sizer_1.Add(self.motor_choice, 0, wx.ALIGN_CENTER_VERTICAL, 0)
        grid_sizer_1.Add(self.motor_pos, 0, wx.ALIGN_CENTER_VERTICAL, 0)
        grid_sizer_1.Add(self.motor_range, 0, wx.ALIGN_RIGHT|wx.ALIGN_CENTER_VERTICAL, 0)
        grid_sizer_1.Add(self.motor_step, 0, wx.ALIGN_CENTER_VERTICAL, 0)
        grid_sizer_1.Add(self.monitor, 0, wx.ALIGN_CENTER_VERTICAL, 0)
        grid_sizer_1.Add(self.motor_gobutton, 0, wx.ALIGN_CENTER_VERTICAL, 0)

        grid_sizer_2.Add(wx.StaticText(self, -1, 'Last peak:'), 0, wx.ALIGN_RIGHT|wx.ALIGN_CENTER_VERTICAL, 0)
        grid_sizer_2.Add(self.fit_result, 0, wx.ALIGN_LEFT|wx.ALIGN_CENTER_VERTICAL, 0)
        grid_sizer_2.Add(self.drive_fit_button, 0, wx.ALIGN_CENTER_VERTICAL, 0)

        fp_label = wx.StaticText(self, -1, 'FIND PEAK:')
        fp_label.SetFont(wx.Font(10, wx.DEFAULT, wx.NORMAL, wx.BOLD, 0, ""))
        self.sizer.Add(wx.StaticLine(self, -1), 0, wx.EXPAND)
        self.sizer.Add(fp_label, 0,0,0)
        self.sizer.Add(grid_sizer_1)
        self.sizer.Add(grid_sizer_2, 0, wx.EXPAND)

        self.SetSizer(self.sizer)
        self.sizer.Fit(self)
        #self.Layout()
        #self.Refresh()
        self.TopLevelParent.Fit()
        #self.TopLevelParent.Layout()
        
        #sizer_1.Add(self, 1, wx.EXPAND, 0)
    
    def run(self, event = None):
        selection = self.motor_choice.GetCurrentSelection()
        visible_motors = [motor_id for motor_id in self.motors if self.motors[motor_id]['visible'] is True]
        chosen_motor_id = visible_motors[selection]
        motnum = self.motors[chosen_motor_id]['motnum'] 
        
        range = float(self.motor_range.GetValue())
        step = float(self.motor_step.GetValue())
        monitor = float(self.monitor.GetValue())
        last_fp = {'range': range, 'step': step, 'monitor': monitor}
        self.motors[chosen_motor_id]['last_FindPeak'] = last_fp
        self.motors_cfg.update_motors_file()
        self.FindPeak(motnum, range, step, monitor)
     
    def FindPeak(self, motnum, range, step, monitor): #override to add functionality
        pass
    
    def update_choice_pos(self, evt=None):
        selection = self.motor_choice.GetCurrentSelection()
        visible_motors = [motor_id for motor_id in self.motors if self.motors[motor_id]['visible'] is True]
        chosen_motor_id = visible_motors[selection]
        self.motor_pos.SetLabel('%.3f' % (self.get_motor_pos(self.motors[chosen_motor_id]['motnum'])))
        if 'last_FindPeak' in self.motors[chosen_motor_id]:
            rs = self.motors[chosen_motor_id]['last_FindPeak']
            self.motor_range.SetValue(str(rs.get('range', 0.0)))
            self.motor_step.SetValue(str(rs.get('step', 0.0)))
            self.monitor.SetValue(str(rs.get('monitor', -1)))
        
    def get_motor_pos(self, motnum):
        # use self.update_position_label in overriding function
        pass
    
    def get_last_fitted_peak(self):
        pass
    
    def DrivePeak(self, evt=None):
        pass
    
    def update_all_motors(self):
        visible_motors = [motor_id for motor_id in self.motors if self.motors[motor_id]['visible'] is True]
        if not self.visible_motors == visible_motors:
            labels = ['%s: %s' % (motor_id, self.motors[motor_id]['label']) for motor_id in visible_motors]
            self.motor_choice.SetItems(labels)
            self.visible_motors = visible_motors
        self.update_choice_pos()
        last_fit = self.get_last_fitted_peak()
        self.fit_result.SetLabel(str(self.get_last_fitted_peak()))
        
class AbortPanel(wx.Panel):
    def __init__(self, parent, id = -1):
        wx.Panel.__init__(self, parent, id)        
        self.buttons = [] 
        # don't put the abort button in the buttons list!  
        # this list is used for auto-disable of buttons when running
        self.abort_button = wx.Button(self, -1, 'Abort\nall\nmoves')
        self.Bind(wx.EVT_BUTTON, self.Abort, self.abort_button)
        self.__set_properties()
        self.__do_layout()
        
    def __set_properties(self):
        # begin wxGlade: MyFrame.__set_properties
        self.abort_button.SetBackgroundColour(wx.Colour(255, 0, 0))
        self.abort_button.SetForegroundColour(wx.Colour(255, 255, 255))
        self.abort_button.SetFont(wx.Font(11, wx.DEFAULT, wx.NORMAL, wx.BOLD, 0, ""))
        # self.SetTitle("frame_1")
        # end wxGlade
    
    def __do_layout(self):
        # begin wxGlade: MyFrame.__do_layout
        sizer_1 = wx.GridSizer(1,1,0,0)
        sizer_1.Add(self.abort_button, 0, wx.ALL|wx.ALIGN_CENTER_VERTICAL|wx.ALIGN_CENTER_HORIZONTAL, 10)
        self.SetSizer(sizer_1)
     
    def Abort(self, event=None):
        pass # override in the subclass you actually use

