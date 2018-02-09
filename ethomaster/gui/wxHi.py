#!/bin/python
import time
from etho.head.clientmanager import *
from etho.utils.SSHRunner import *
from etho import config
import wx
import wxCtrl
from wxBusyDialog import BusyDialog


class Model:
    def __init__(self):
        self.clients = exepool(ping, config['GENERAL']['hosts'])
        print(self.clients)
        self.clients_runningservices = exepool(get_running_services, config['GENERAL']['hosts'])
        print(self.clients_runningservices)

    def rescan(self):
        self.clients = exepool(ping, config['GENERAL']['hosts'])
        print(self.clients)
        self.clients_runningservices = exepool(get_running_services, config['GENERAL']['hosts'])
        print(self.clients_runningservices)


class HelloFrame(wx.Frame):
    """
    A Frame that says Hello World
    """

    def __init__(self, *args, **kw):
        # ensure the parent's __init__ is called
        super(HelloFrame, self).__init__(*args, **kw)

        self.model = Model()

        # create a panel in the frame
        # pnl = wx.Panel(self)

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
            panelButton.SetToolTip(wx.ToolTip(
                str(self.model.clients_runningservices[key])))
            self.Bind(wx.EVT_BUTTON, self.OnClick, panelButton)
            # add info text next to button
            panelText = wx.StaticText(self, wx.ID_ANY, str(
                self.model.clients_runningservices[key]))
            # loyout button and text next to each other
            sizerHorz.Add(panelButton, 0, wx.ALL, 1)
            sizerHorz.Add(panelText, 1, wx.ALL | wx.EXPAND, 1)
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
    app = wx.App()
    frm = HelloFrame(None, title='ethodrome', size=(600, 300))
    frm.Show()
    app.MainLoop()
