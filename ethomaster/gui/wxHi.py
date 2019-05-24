#!/bin/python
import time
import wx

from ethomaster.head.clientmanager import *
from ethomaster.utils.SSHRunner import *
from ethomaster import config
import ethomaster.gui.wxCtrl as wxCtrl
from ethomaster.gui.wxBusyDialog import BusyDialog


# TODO Run this in background and automatically update gui using pubsub https://wiki.wxpython.org/ModelViewController
class Model:
    def __init__(self):
        # this should happen in config!!
        if isinstance(config['GENERAL']['hosts'], str):
            config['GENERAL']['hosts'] = [config['GENERAL']['hosts']]
        self.clients = exepool(ping, config['GENERAL']['hosts'])
        print(self.clients)
       
    def rescan(self):
        print('RESCANNING - listing clients:')
        self.clients = exepool(ping, config['GENERAL']['hosts'])
        print(self.clients)
        print('RESCANNING - listing running services:')
        self.clients_runningservices = exepool(get_running_services, config['GENERAL']['hosts'])
        print(self.clients_runningservices)


class HelloFrame(wx.Frame):
    """A Frame that says Hello World."""

    def __init__(self, *args, **kw):
        # ensure the parent's __init__ is called
        super(HelloFrame, self).__init__(*args, **kw)

        self.model = Model()

        # create a menu bar
        self.makeMenuBar()

        # and a status bar
        self.CreateStatusBar()
        self.SetStatusText("ethodrome")

        # text
        self.makeButtonPanel()

    def makeButtonPanel(self):
        topSizer = wx.BoxSizer(wx.VERTICAL)
        # color based on true value (is_online)
        colors = {True: '#AAFFAA', False: '#FFAAAA'}
        for key in self.model.clients:
            sizerHorz = wx.BoxSizer(wx.HORIZONTAL)
            panelButton = wx.Button(self, label=key)
            # custom `name` field so we can identify button
            panelButton.name = key
            # set color based on online status
            panelButton.SetBackgroundColour(colors[self.model.clients[key]])
            self.Bind(wx.EVT_BUTTON, self.OnClick, panelButton)
            # add info text next to button
            # loyout button and text next to each other
            sizerHorz.Add(panelButton, 0, wx.ALL, 1)
            # now add button+text
            topSizer.Add(sizerHorz, 0, wx.ALL | wx.EXPAND, 1)
        self.SetSizer(topSizer)

    def makeMenuBar(self):
        """
        A menu bar is composed of menus, which are composed of menu items.
        This method builds a set of menus and binds handlers to be called
        when the menu item is selected.
        """

        # Make a file menu with Hello and Exit items
        fileMenu = wx.Menu()
        # The "\t..." syntax defines an accelerator key that also triggers
        # the same event
        rescanItem = fileMenu.Append(-1, "&Rescan...\tCtrl-R",
                                     "Rescan nodes")
        fileMenu.AppendSeparator()
        # When using a stock ID we don't need to specify the menu item's
        # label
        exitItem = fileMenu.Append(wx.ID_EXIT)

        # Now a help menu for the about item
        helpMenu = wx.Menu()
        aboutItem = helpMenu.Append(wx.ID_ABOUT)

        # Make the menu bar and add the two menus to it. The '&' defines
        # that the next letter is the "mnemonic" for the menu item. On the
        # platforms that support it those letters are underlined and can be
        # triggered from the keyboard.
        menuBar = wx.MenuBar()
        menuBar.Append(fileMenu, "&File")
        menuBar.Append(helpMenu, "&Help")

        # Give the menu bar to the frame
        self.SetMenuBar(menuBar)

        # Finally, associate a handler function with the EVT_MENU event for
        # each of the menu items. That means that when that menu item is
        # activated then the associated handler function will be called.
        self.Bind(wx.EVT_MENU, self.OnRescan, rescanItem)
        self.Bind(wx.EVT_MENU, self.OnExit, exitItem)
        self.Bind(wx.EVT_MENU, self.OnAbout, aboutItem)

    def OnRescan(self, event):
        self.PushStatusText('rescanning clients')
        self.model.rescan()
        self.PopStatusText()

    def OnClick(self, event):
        self.PushStatusText('configure {0}'.format(
            event.GetEventObject().name))
        # wxCam.main(event.GetEventObject().name)
        wxCtrl.main(event.GetEventObject().name)
        try:
            self.PopStatusText()
        except:
            pass

    def OnExit(self, event):
        """Close the frame, terminating the application."""
        self.Close(True)

    def OnHello(self, event):
        """Say hello to the user."""
        wx.MessageBox("Hello again from wxPython")

    def OnAbout(self, event):
        """Display an About Dialog"""
        wx.MessageBox("This is a wxPython Hello World sample",
                      "About Hello World 2",
                      wx.OK | wx.ICON_INFORMATION)


if __name__ == '__main__':
    # When this module is run (not imported) then create the app, the
    # frame, show it, and start the event loop.
    # import ipdb; ipdb.set_trace()
    app = wx.App()
    frm = HelloFrame(None, title='ethodrome', size=(100, 300))
    frm.Show()
    app.MainLoop()
