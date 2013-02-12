import wx
import pyrecs
import pyrecs.drivers
NUM_TC_DRIVERS = len(pyrecs.drivers.temperature_controllers)

class MyDialog(wx.Dialog):
    def __init__(self, *args, **kwds):
        if 'device' in kwds:
            self.device = kwds['device']
        elif 'devicenum' in kwds and kwds['devicenum'] >= 0 and kwds['devicenum'] < NUM_TC_DRIVERS:
            devicenum = kwds['devicenum']
            selection = pyrecs.drivers.temperature_controllers[devicenum]
            driver_module = __import__('pyrecs.drivers.'+selection[1], fromlist=['not_empty'])
            driver = getattr(driver_module, selection[2])
            self.device = driver()
        else:
            msg = wx.MessageDialog(None, 'No valid driver specified', 'error', wx.OK | wx.ICON_ERROR)
            msg.ShowModal()
            msg.Destroy()
            return
        
        if 'device' in kwds: kwds.pop('device')
        if 'devicenum' in kwds: kwds.pop('devicenum')    
        self.keys = self.device.settings.keys()
        # begin wxGlade: MyDialog.__init__
        kwds["style"] = wx.DEFAULT_DIALOG_STYLE
        wx.Dialog.__init__(self, *args, **kwds)
        self.key_labels = {}
        self.value_chooser = {}
        self.reverse_lookup = {}
        for key in self.keys:
            self.key_labels[key] = wx.StaticText(self, -1, key)
            valid_settings = self.device.valid_settings[key]
            self.reverse_lookup[key] = dict([(v,k) for k,v in valid_settings.iteritems()])
            self.value_chooser[key] = wx.Choice(self, -1, choices=valid_settings.values())
        self.cancel_btn = wx.Button(self, -1, "Cancel")
        self.apply_btn = wx.Button(self, -1, "Ok")

        self.__set_properties()
        self.__do_layout()

        self.Bind(wx.EVT_BUTTON, self.onCancel, self.cancel_btn)
        self.Bind(wx.EVT_BUTTON, self.onApply, self.apply_btn)
        # end wxGlade

    def __set_properties(self):
        # begin wxGlade: MyDialog.__set_properties
        self.SetTitle("Configure Device")
        for key in self.keys:
            setting = self.device.settings[key]
            setting_label = self.device.valid_settings[key][setting]
            index = self.value_chooser[key].Items.index(setting_label)
            self.value_chooser[key].SetSelection(index)
            
        # end wxGlade

    def __do_layout(self):
        # begin wxGlade: MyDialog.__do_layout
        sizer_1 = wx.BoxSizer(wx.VERTICAL)
        kv_sizers = {}
        for key in self.keys:
            kv_sizers[key] = wx.BoxSizer(wx.HORIZONTAL)
            kv_sizers[key].Add(self.key_labels[key], 0,wx.ALIGN_CENTER_VERTICAL,0)
            kv_sizers[key].Add(self.value_chooser[key],0,wx.ALIGN_CENTER_VERTICAL,0)
            sizer_1.Add(kv_sizers[key], 0, 0, 0)
        sizer_2 = wx.BoxSizer(wx.HORIZONTAL)
        sizer_2.Add(self.cancel_btn, 0, 0, 0)
        sizer_2.Add(self.apply_btn, 0, 0, 0)
        sizer_1.Add(sizer_2, 1, wx.ALIGN_CENTER_HORIZONTAL, 0)
        self.SetSizer(sizer_1)
        sizer_1.Fit(self)
        self.Layout()
        # end wxGlade

    def onCancel(self, event):  # wxGlade: MyDialog.<event_handler>
        self.Destroy()
        event.Skip()

    def onApply(self, event):  # wxGlade: MyDialog.<event_handler>
        for key in self.keys:
            choice = self.value_chooser[key].GetCurrentSelection()
            label = self.value_chooser[key].Items[choice]
            value = self.reverse_lookup[key][label]
            self.device.settings[key] = value            
        self.Destroy()
        event.Skip()
        

# end of class MyDialog
