import wx
from ethomaster import config
import wx.lib.mixins.listctrl as listmix


# https://stackoverflow.com/questions/40431944/save-edit-from-editable-wx-listctrl-wxpython
class EditableListCtrl(wx.ListCtrl, listmix.TextEditMixin):
    ''' TextEditMixin allows any column to be edited. '''
    def __init__(self, parent, ID=wx.ID_ANY, pos=wx.DefaultPosition,
                 size=wx.DefaultSize, style=0):
        """Constructor"""
        wx.ListCtrl.__init__(self, parent, ID, pos, size, style)
        listmix.TextEditMixin.__init__(self)


class ProtocolEditorFrame(wx.Frame):
    """
    A Frame that says Hello World
    """

    def __init__(self, *args, **kw):
        # ensure the parent's __init__ is called
        super(ProtocolEditorFrame, self).__init__(*args, **kw)

        # create a panel in the frame
        panel = wx.Panel(self)

        # text
        # self.makeButtonPanel()
        self.list_ctrl = EditableListCtrl(panel, size=(-1, 100),
                                          style=wx.LC_REPORT | wx.LC_HRULES | wx.LC_VRULES)

        self.list_ctrl.InsertColumn(0, 'section')
        self.list_ctrl.InsertColumn(1, 'key')
        self.list_ctrl.InsertColumn(2, 'item')
        self.list_ctrl.Bind(wx.EVT_LIST_END_LABEL_EDIT, self.OnEdit)
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.list_ctrl, 0, wx.ALL | wx.EXPAND)
        # sizer.Add(btn, 0, wx.ALL|wx.CENTER, 5)
        # sizer.Add(btn2, 0, wx.ALL|wx.CENTER, 5)
        panel.SetSizer(sizer)
        self.index = 0
        for mainkey, mainvalue in config.items():
            for key, value in mainvalue.items():
                self.add_line(mainkey, key, value)

    def add_line(self, section, key, item):
        self.list_ctrl.InsertStringItem(self.index, section)
        self.list_ctrl.SetStringItem(self.index, 1, str(key))
        self.list_ctrl.SetStringItem(self.index, 2, str(item))
        # self.rowDict = (section, key, item)
        self.index += 1

    def OnEdit(self, event):
        row_id = event.GetIndex() #Get the current row
        col_id = event.GetColumn () #Get the current column
        new_data = event.GetLabel() #Get the changed data
        self.list_ctrl.SetStringItem(row_id,col_id,new_data)

        cols = self.list_ctrl.GetColumnCount() #Get the total number of columns
        rows = self.list_ctrl.GetItemCount() #Get the total number of rows
        #Get the changed item use the row_id and iterate over the columns
        section, key, item = [self.list_ctrl.GetItem(row_id, colu_id).GetText() for colu_id in range(cols)]

        print(" ".join([section, key, item]))
        print("Changed Item:", new_data, "Column:", col_id)
        config[section][key] = item
        print(config)
        # print(event.GetEventObject().name)


if __name__ == '__main__':
    # When this module is run (not imported) then create the app, the
    # frame, show it, and start the event loop.
    app = wx.App()
    frm = ProtocolEditorFrame(None, title='ethodrome', size=(600, 300))
    frm.Show()
    app.MainLoop()
