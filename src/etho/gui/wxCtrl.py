import time
import os
import wx
from .. import config
from ..call import client as client
from .wxDangerDialog import DangerDialog
from .wxBusyDialog import BusyDialog
from . import wxCam
from . import ThuPreview


def list_path(path="playlists"):
    return [f for f in os.listdir(path) if os.path.isfile(os.path.join(path, f))]


class Frame(wx.Frame):
    def __init__(self, host):
        self.host = host
        style = wx.DEFAULT_FRAME_STYLE & ~wx.RESIZE_BORDER & ~wx.MAXIMIZE_BOX
        super(Frame, self).__init__(None, -1, "{0} control".format(self.host), style=style)

        # create a panel in the frame
        self.playlistfolder = config["HEAD"]["playlistfolder"]
        self.playlistList = wx.ListBox(self, choices=list_path(self.playlistfolder), style=wx.LB_SINGLE)

        self.protocolfolder = config["HEAD"]["protocolfolder"]
        self.protocolList = wx.ListBox(self, choices=list_path(self.protocolfolder), style=wx.LB_SINGLE)
        self.protocolList.SetStringSelection("default.txt", True)

        bStart = wx.Button(self, label="start selected")
        self.Bind(wx.EVT_BUTTON, self.OnClickStart, bStart)

        bCamPreview = wx.Button(self, label="cam preview")
        self.Bind(wx.EVT_BUTTON, self.OnClickCamPreview, bCamPreview)

        bThuPreview = wx.Button(self, label="check temp&hum")
        self.Bind(wx.EVT_BUTTON, self.OnClickThuPreview, bThuPreview)

        bDanger = wx.Button(self, label="DANGER")
        self.Bind(wx.EVT_BUTTON, self.OnClickDanger, bDanger)

        sizer = wx.FlexGridSizer(wx.VERTICAL)
        sizer.Add(self.playlistList, 0, 0, 0)
        sizer.Add(self.protocolList, 0, 0, 0)
        sizer.Add(bStart, 0, 0, 0)
        sizer.Add(bCamPreview, 0, 0, 0)
        sizer.Add(bThuPreview, 0, 0, 0)
        sizer.Add(bDanger, 0, 0, 0)
        self.SetSizer(sizer)

        self.CreateStatusBar()
        self.SetStatusText("etho")

        self.Fit()
        self.Bind(wx.EVT_CLOSE, self.OnClose)

    def OnClose(self, event):
        self.Destroy()

    def OnClickStart(self, event):
        playlistName = self.playlistList.GetStringSelection()
        protocolName = self.protocolList.GetStringSelection()
        if playlistName and protocolName:
            self.SetStatusText("playlist: {0}, prot: {1}".format(playlistName, protocolName))
            message = "starting playlist {0} with prot {1} on {2}".format(playlistName, protocolName, self.host)
            args = (os.path.join(self.protocolfolder, protocolName), os.path.join(self.playlistfolder, playlistName))
            kwargs = {'host': self.host}
            print(message)
            BusyDialog(self, size=(300, 150)).run(client.client, args, kwargs, message=message)
        else:
            print("no controlf file selected")
        # check node status before starting??
        # CALL: startRecording(selectedItemString)

    def OnClickCamPreview(self, event):
        print("if running - start cam service and preview, otherwise connect to running service and preview")
        wxCam.main(self.host)
        # if running
        # connect to CAM service and preview
        # else:
        # start and connect service and preview

    def OnClickThuPreview(self, event):
        ThuPreview.main(self.host)

    def OnClickDanger(self, event):
        with DangerDialog(self.host, None, title=self.host) as dlg:
            if dlg.ShowModal() == wx.ID_CLOSE:
                print("DANGER zone left.")


def main(host):
    app = wx.App()
    frame = Frame(host)
    frame.Center()
    frame.Show()
    app.MainLoop()


if __name__ == "__main__":
    main(host="localhost")
