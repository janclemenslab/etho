#!/bin/python
import wx
import sys  # for command line args
from CamPreview import *
SIZE = (1000, 500)  # size of preview window


def pil_to_wx(image):
    image.thumbnail(SIZE)  # resize to fit into window - this operation is inplace
    width, height = image.size  # get actual new image size
    buffer = image.convert('RGB').tobytes()  # convert to RGB and byte stream
    bitmap = wx.Bitmap.FromBuffer(width, height, buffer)  # convert byte stream to wx bitmap
    return bitmap


class Panel(wx.Panel):
    def __init__(self, parent, preview):
        super(Panel, self).__init__(parent, -1)
        self.preview = preview  # save instance of preview generator
        self.SetSize(SIZE)
        self.SetBackgroundStyle(wx.BG_STYLE_CUSTOM)
        self.Bind(wx.EVT_PAINT, self.on_paint)
        self.update()  # call `update()` to start the windows refresh cycle

    def update(self):
        self.Update()
        self.Refresh()

    def on_paint(self, event):
        bitmap = pil_to_wx(next(self.preview))  # get next preview frame and convert to wx bitmap
        dc = wx.AutoBufferedPaintDC(self)
        dc.DrawBitmap(bitmap, 0, 0)
        wx.CallLater(100, self.update)  # request new refresh in 1000ms


class Frame(wx.Frame):
    def __init__(self, host):
        style = wx.DEFAULT_FRAME_STYLE & ~wx.RESIZE_BORDER & ~wx.MAXIMIZE_BOX
        super(Frame, self).__init__(None, -1, '{0} preview'.format(host), style=style)
        self.panel = Panel(self, camPreview(host))
        self.Fit()
        self.Bind(wx.EVT_CLOSE, self.OnClose)

    def OnClose(self, event):
        self.panel.preview.close()
        self.Destroy()


def main(host):
    app = wx.App()
    frame = Frame(host)
    frame.Center()
    frame.Show()
    app.MainLoop()


if __name__ == '__main__':
    '''USAGE: `python ./wxCam.py HOSTNAME`'''
    if len(sys.argv)>1:
        host = sys.argv[1]
        main(host)
