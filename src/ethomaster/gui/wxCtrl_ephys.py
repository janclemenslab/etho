import time
import os
import wx
from ethomaster import config
import ethomaster.head.client_ephys as client_ephys
from ethomaster.gui.wxBusyDialog import BusyDialog


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

        bSearch = wx.Button(self, label='search')
        self.Bind(wx.EVT_BUTTON, self.OnClickSearch, bSearch)

        bStart = wx.Button(self, label='record')
        bStart.SetBackgroundColour(wx.Colour(255, 64, 64))
        self.Bind(wx.EVT_BUTTON, self.OnClickStart, bStart)

        sizer = wx.FlexGridSizer(wx.VERTICAL)
        sizer.Add(self.playlistList, 0, 0, 0)
        sizer.Add(self.protocolList, 0, 0, 0)
        sizer.Add(bSearch, 0, 0, 0)
        sizer.Add(bStart, 0, 0, 0)
        self.SetSizer(sizer)

        self.CreateStatusBar()
        self.SetStatusText("ethodrome")

        self.Fit()
        self.Bind(wx.EVT_CLOSE, self.OnClose)

    def OnClose(self, event):
        self.Destroy()

    def OnClickSearch(self, event):
        self.call_etho(save=False)

    def OnClickStart(self, event):
        self.call_etho(save=True)

    def call_etho(self, save=False):
        playlistName = self.playlistList.GetStringSelection()
        protocolName = self.protocolList.GetStringSelection()
        if playlistName and protocolName:
            self.SetStatusText("playlist: {0}, prot: {1}".format(playlistName, protocolName))
            message = "starting playlist {0} with prot {1} on {2}".format(playlistName, protocolName, self.host)
            filename = '{0}-{1}'.format('localhost', time.strftime('%Y%m%d_%H%M%S'))

            cmd_args = (filename,
                    0,
                    os.path.join(self.protocolfolder, protocolName),
                    os.path.join(self.playlistfolder, playlistName),
                    save,
                    False,
                    False,)
            print(message)
            BusyDialog(self, size=(300,150)).run(client_ephys.clientcc, cmd_args, message=message)
            # client_ephys.clientcc(*cmd_args)
        else:
            print('no control file selected')


def main(host):
    app = wx.App()
    frame = Frame(host)
    frame.Center()
    frame.Show()
    app.MainLoop()


if __name__ == '__main__':
    main(host='localhost')
