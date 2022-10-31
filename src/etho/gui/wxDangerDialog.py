import wx
from ..utils.runner import Runner
from .. import config


class DangerDialog(wx.Dialog):

    def __init__(self, host, *args, **kw):
        super(DangerDialog, self).__init__(*args, **kw)
        self.host = host
        self.sr = Runner('{0}@{1}'.format(config['GENERAL']['user'], host))
        self.InitUI()
        self.SetSize((250, 200))
        self.SetTitle("DANGER ZONE")

    def InitUI(self):

        vbox = wx.BoxSizer(wx.VERTICAL)

        hbox0 = wx.BoxSizer(wx.HORIZONTAL)
        self.ctrlList = wx.ListBox(
            self, choices=config['GENERAL']['services'], style=wx.LB_EXTENDED)
        hbox0.Add(self.ctrlList)
        bKillService = wx.Button(self, label='kill selected service')
        hbox0.Add(bKillService)

        hbox1 = wx.BoxSizer(wx.HORIZONTAL)
        bKillAll = wx.Button(self, label='kill ALL services')
        hbox1.Add(bKillAll)
        bKillPython = wx.Button(self, label='kill ALL python processes')
        hbox1.Add(bKillPython)
        bReboot = wx.Button(self, label='reboot')
        hbox1.Add(bReboot)

        hbox2 = self.CreateStdDialogButtonSizer(wx.CLOSE)

        vbox.Add(hbox0, proportion=1,
                 flag=wx.ALL | wx.EXPAND, border=5)
        vbox.Add(hbox1, proportion=1,
                 flag=wx.ALL | wx.EXPAND, border=5)
        vbox.Add(hbox2, proportion=1,
                 flag=wx.ALIGN_CENTER | wx.TOP | wx.BOTTOM, border=10)

        self.SetSizer(vbox)

        self.Bind(wx.EVT_BUTTON, self.OnKillAll, bKillAll)
        self.Bind(wx.EVT_BUTTON, self.OnKillPython, bKillPython)
        self.Bind(wx.EVT_BUTTON, self.OnKillService, bKillService)
        self.Bind(wx.EVT_BUTTON, self.OnReboot, bReboot)

    def OnKillAll(self, e):
        # maybe change this to "kill registered services"?
        print('killing ALL services on {0}'.format(self.host))
        for service in config['GENERAL']['services']:
            print('   find PID for {0}'.format(service))
            print(self.sr.kill_service(service))
            print('      kill PID for {0}'.format(service))

    def OnKillService(self, e):
        indices = self.ctrlList.GetSelections()
        if len(indices):
            print('killing selected services')
        for index in indices:
            service = self.ctrlList.GetString(index)
            print('   find PID for {0}'.format(service))
            print(self.sr.kill_service(service))
            print('      kill PID for {0}'.format(service))

    def OnKillPython(self, e):
        print('killing all python processes on  {0}'.format(self.host))
        print(self.sr.run('pkill python'))

    def OnReboot(self, e):
        print('waiting for reboot of {0}'.format(self.host))
        print(self.sr.reboot(wait=True))

class Example(wx.Frame):

    def __init__(self, *args, **kw):
        super(Example, self).__init__(*args, **kw)

        self.InitUI()

    def InitUI(self):

        depthButton = wx.Button(self, label='Ok')
        depthButton.Bind(wx.EVT_BUTTON, self.OnChangeDepth)

        self.SetSize((300, 200))
        self.SetTitle('Custom dialog')
        self.Centre()
        self.Show(True)

    def OnChangeDepth(self, e):

        with DangerDialog(None, title='Change Color Depth') as dlg:
            if dlg.ShowModal() == wx.ID_CLOSE:
                print('DANGER zone left.')


def main():

    ex = wx.App()
    Example(None)
    ex.MainLoop()


if __name__ == '__main__':
    main()
