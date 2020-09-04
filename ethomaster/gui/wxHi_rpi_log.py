#!/bin/python
import time
import wx

from ethomaster.head.clientmanager import *
from ethomaster.utils.SSHRunner import *
from ethomaster import config
import ethomaster.gui.wxCtrl_rpi as wxCtrl_rpi
from ethomaster.gui.wxBusyDialog import BusyDialog


# TODO Run this in background and automatically update gui using pubsub https://wiki.wxpython.org/ModelViewController
class Model:
    def __init__(self):
        # this should happen in config!!
        if isinstance(config['GENERAL']['hosts'], str):
            config['GENERAL']['hosts'] = [config['GENERAL']['hosts']]
        self.hosts = config['GENERAL']['host_ips']
        self.host_ips = config['GENERAL']['host_ips'].values()
        self.host_names = config['GENERAL']['host_ips'].keys()
        self.host_ip2names = {ip: name for ip, name in zip(self.host_ips, self.host_names)}
        self.host_status = exepool(ping, self.host_ips)
        
    def rescan(self):
        print('RESCANNING - listing clients:')
        self.host_status = exepool(ping, config['GENERAL']['hosts'])
        print(self.host_status)
        print('RESCANNING - listing running services:')
        


from threading import Thread
import wx
from pubsub import pub
# from wx.lib.pubsub import pub
import time
import logging
import time
import zmq
import logging
import logging.handlers
from ethomaster import config


class WorkThread(Thread):

    def __init__(self):
        """Init Worker Thread Class."""
        Thread.__init__(self)
        self.stop_work_thread = 0
        
        logger = logging.getLogger('')
        logger.setLevel(logging.INFO)
        # __ to console logger
        console = logging.StreamHandler()
        # console.setLevel(logging.DEBUG)
        # formatter = logging.Formatter('%(name)-12s: %(levelname)-8s %(message)s')
        formatter = logging.Formatter('%(levelname)-8s %(message)s')
        # tell the handler to use this format
        console.setFormatter(formatter)
        console.setLevel(logging.INFO)
        # add handler to logger
        logger.addHandler(console)
       
        # subscribe to all logging ports
        logging_ports = range(int(config['LOGGER']['portrange'][0]), int(config['LOGGER']['portrange'][1]))
        ctx = zmq.Context()
        sub = ctx.socket(zmq.SUB)
        sub.setsockopt_string(zmq.SUBSCRIBE, '')
        for port in logging_ports:
            sub.bind('tcp://0.0.0.0:{0}'.format(port))
        self.sub = sub
        self.logger = logger
        self.start()  # start the thread
        self.val = 0
    
    def run(self):
        print('LISTENING FOR MESSAGES')

        while True:
            if self.stop_work_thread == 1:
                break
            self.val += 1
            # logger publishes logger as multipart: [level, message]
            try:
                level, message = self.sub.recv_multipart(zmq.NOBLOCK)
                # get level-appropriate logging function
                # log = getattr(self.logger, level.decode('utf8').lower())
                # log(message.decode('utf8').rstrip())
                wx.CallAfter(pub.sendMessage, "update", step=message.decode('utf8').rstrip())
            except zmq.error.Again as e:
                pass
            time.sleep(.01)

            # wx.CallAfter(pub.sendMessage, "update", step=self.val)
        wx.CallAfter(pub.sendMessage, "finish")
        return

    def stop(self):
        self.stop_work_thread = 1




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

        self.logger = wx.TextCtrl(self,size=(1000, 2000), style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_DONTWRAP)
        font1 = wx.Font(8, wx.MODERN, wx.NORMAL, wx.NORMAL, False, u'Consolas')
        self.logger.SetFont(font1)

        # text
        self.makeButtonPanel()

        self.logger.Clear()
        pub.subscribe(self.onUpdate, "update")
        pub.subscribe(self.onFinish, "finish")
        self.work = WorkThread()
    

    def makeButtonPanel(self):
        masterSizer = wx.BoxSizer(wx.HORIZONTAL)
        topSizer = wx.BoxSizer(wx.VERTICAL)
        # color based on true value (is_online)
        colors = {True: '#AAFFAA', False: '#FFAAAA'}
        for name in self.model.host_names:
            ip = self.model.hosts[name]
            status = self.model.host_status[ip]
            
            sizerHorz = wx.BoxSizer(wx.HORIZONTAL)
            panelButton = wx.Button(self, label=name)
            # custom `name` field so we can identify button
            panelButton.name = name
            panelButton.ip = ip
            # set color based on online status
            panelButton.SetBackgroundColour(colors[status])
            self.Bind(wx.EVT_BUTTON, self.OnClick, panelButton)
            # add info text next to button
            # loyout button and text next to each other
            sizerHorz.Add(panelButton, 0, wx.ALL, 1)
            # now add button+text
            topSizer.Add(sizerHorz, 0, wx.ALL | wx.EXPAND, 1)

        masterSizer.Add(topSizer)
        masterSizer.Add(self.logger, 0, 0, 0)
        self.SetSizer(masterSizer)        
        

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


    def onUpdate(self, step):
        step = str(step)+'\n'
        self.logger.AppendText(step)

    
    def onCancel(self, event):
        """Cancel thread process"""
        try:
            self.work.stop()
            self.work.join()
        except:
            pass

    def onFinish(self):
        """thread process finished"""
        try:
            pub.unsubscribe(self.onUpdate, "update")
            pub.unsubscribe(self.onFinish, "finish")
        except:
            pass

    def OnExit(self, event):
        self.onCancel(None)
        self.onFinish()
        self.Destroy()
        self.Close(True)

    def OnClose(self, event):
        self.onCancel(None)
        self.onFinish()
        self.Destroy()

    def OnRescan(self, event):
        pass


    def OnClick(self, event):
        name, ip = event.GetEventObject().name, event.GetEventObject().ip
        self.PushStatusText('configure {0}'.format(ip, name))
        wxCtrl_rpi.main(name, ip)
        try:
            self.PopStatusText()
        except:
            pass


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
