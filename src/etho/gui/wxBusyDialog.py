import wx
import time
from multiprocessing import Process


class BusyDialog(wx.Dialog):
    def __init__(self, *args, **kw):
        super(BusyDialog, self).__init__(*args, **kw)

    def run(self, method, args=[], kwargs=[], message="Busy doing stuff."):
        wx.StaticText(self, label=message)
        self.Show()
        wx.Yield()  # yield to allow wx to display the dialog
        p = Process(target=method, args=args, kwargs=kwargs)  # use process and
        p.start()  # start execution
        p.join()  # join blocks the GUI while the process is running
        self.Destroy()  # properly destroy the dialog


class Example(wx.Frame):
    def __init__(self, *args, **kw):
        super(Example, self).__init__(*args, **kw)
        self.InitUI()

    def InitUI(self):
        self.SetSize((300, 200))
        self.SetTitle("Custom dialog")
        self.Centre()
        self.Show(True)
        bSleep = wx.Button(self, label="kill selected service")
        self.Bind(wx.EVT_BUTTON, self.OnClickSleep, bSleep)

    def OnClickSleep(self, event):
        def sleeper(t=4):
            print("busy sleeping for {0} seconds".format(t))
            time.sleep(t)
            print("done sleeping")

        BusyDialog(self, size=(200, 50)).run(sleeper, (4,))


def main():
    app = wx.App()
    ex = Example(None)
    ex.Show()
    app.MainLoop()


if __name__ == "__main__":
    main()
