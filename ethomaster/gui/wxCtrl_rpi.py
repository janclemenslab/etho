import time
import os
import wx
from ethomaster import config
import ethomaster.head.clientcaller_rpi as clientcaller
import ethomaster.head.clientmanager as clientmanager
from ethomaster.gui.wxDangerDialog import DangerDialog
from ethomaster.gui.wxBusyDialog import BusyDialog
import ethomaster.gui.wxCam as wxCam
import ethomaster.gui.ThuPreview as ThuPreview


def list_path(path='playlists'):
    return [f for f in os.listdir(path) if os.path.isfile(os.path.join(path, f))]


class Frame(wx.Frame):
    def __init__(self, host):
        self.host = host
        style = wx.DEFAULT_FRAME_STYLE & ~wx.RESIZE_BORDER & ~wx.MAXIMIZE_BOX
        super(Frame, self).__init__(
            None, -1, '{0} control'.format(self.host), style=style)

        # create a panel in the frame
        self.playlistfolder = config['HEAD']['playlistfolder']
        self.playlistList = wx.ListBox(self, choices=list_path(self.playlistfolder), style=wx.LB_SINGLE)

        self.protocolfolder = config['HEAD']['protocolfolder']
        self.protocolList = wx.ListBox(self, choices=list_path(self.protocolfolder), style=wx.LB_SINGLE)
        self.protocolList.SetStringSelection("default.txt", True)

        bStart = wx.Button(self, label='start selected')
        self.Bind(wx.EVT_BUTTON, self.OnClickStart, bStart)

        bStatus = wx.Button(self, label='status')
        self.Bind(wx.EVT_BUTTON, self.OnClickStatus, bStatus)

        bCamPreview = wx.Button(self, label='cam preview')
        self.Bind(wx.EVT_BUTTON, self.OnClickCamPreview, bCamPreview)

        bThuPreview = wx.Button(self, label='check temp&hum')
        self.Bind(wx.EVT_BUTTON, self.OnClickThuPreview, bThuPreview)

        bDanger = wx.Button(self, label='DANGER')
        self.Bind(wx.EVT_BUTTON, self.OnClickDanger, bDanger)

        sizerH = wx.BoxSizer(wx.HORIZONTAL)
        sizerH.Add(self.playlistList, 0, 0, 0)
        sizerH.Add(self.protocolList, 0, 0, 0)
        sizerB = wx.BoxSizer(wx.VERTICAL)
        sizerB.Add(bStart, 0, 0, 0)
        sizerB.Add(bStatus, 0, 0, 0)
        sizerB.Add(bCamPreview, 0, 0, 0)
        sizerB.Add(bThuPreview, 0, 0, 0)
        sizerB.Add(bDanger, 0, 0, 0)
        sizerH.Add(sizerB, 0, 0, 0)
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(sizerH, 0, 0, 0)
        self.SetSizer(sizer)

        self.CreateStatusBar()
        self.SetStatusText("ethodrome")

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
            args = (self.host, os.path.join(self.playlistfolder, playlistName),
                               os.path.join(self.protocolfolder, protocolName))
            print(message)
            BusyDialog(self, size=(300,150)).run(clientcaller.clientcaller, args, message=message)
        else:
            print('no controlf file selected')
        # check node status before starting??
        # CALL: startRecording(selectedItemString)

    def OnClickStatus(self, event):
        with BusyDialog(self) as dlg:
            if dlg.ShowModal() == wx.ID_OK:
                # do something here
                self.clientStatus = clientmanager.client_status(self.host)
                print(self.clientStatus)
            else:
                # handle dialog being cancelled or ended by some other button
                pass
    # The dialog is automatically destroyed on exit from the context manager

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
                print('DANGER zone left.')


def main(host):
    app = wx.App()
    frame = Frame(host)
    frame.Center()
    frame.Show()
    app.MainLoop()


if __name__ == '__main__':
    main(host='localhost')
