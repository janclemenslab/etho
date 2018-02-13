#!/usr/bin/env python
import wx
from ethomaster import config
# Where can we find the ObjectListView module?
from ObjectListView import ObjectListView, ColumnDefn


class MyFrame(wx.Frame):
    def __init__(self, *args, **kwds):
        wx.Frame.__init__(self, *args, **kwds)
        self.Init()

    def Init(self):
        self.InitModel()
        self.InitWidgets()
        self.InitObjectListView()

    def InitModel(self):
        import string
        self.model = list()
        for mainkey, mainvalue in config.items():
            for key, value in mainvalue.items():
                # value = str.join('',[i for i in str(value) if i in string.printable])
                # for item in str(value):
                    # if item not in string.printable:
                        # print(value)
                value = str(value).replace("'", "x").replace("~", "x").replace("/", "x").replace(":", "x")
                self.model.append({'section': mainkey, 'key': key, 'value': "as{}".format(value)})


    def InitWidgets(self):
        panel = wx.Panel(self, -1)
        sizer_1 = wx.BoxSizer(wx.VERTICAL)
        sizer_1.Add(panel, 1, wx.ALL|wx.EXPAND)
        self.SetSizer(sizer_1)

        self.myOlv = ObjectListView(panel, -1,
                                    style=wx.LC_REPORT|wx.SUNKEN_BORDER,
                                    cellEditMode=ObjectListView.CELLEDIT_SINGLECLICK)
        sizer_2 = wx.BoxSizer(wx.VERTICAL)
        sizer_2.Add(self.myOlv, 1, wx.ALL|wx.EXPAND, 4)
        panel.SetSizer(sizer_2)

        self.Layout()

    def InitObjectListView(self):
        self.myOlv.SetColumns([
            ColumnDefn("section", "right", -1, "section", isEditable=False),
            ColumnDefn("key", "right", -1, "key", isEditable=True, valueSetter='key'),
            ColumnDefn("value", "left", -1, 'value', isEditable=True, valueSetter='value')
        ])
        print(self.model)
        self.myOlv.SetObjects(self.model)

if __name__ == '__main__':
    app = wx.App(0)
    frame_1 = MyFrame(None, -1, "ObjectListView Dictionary Example")
    app.SetTopWindow(frame_1)
    frame_1.Show()
    app.MainLoop()
