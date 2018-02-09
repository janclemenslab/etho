import logging
import logging.config
import wx
import time
import zmq
# from multiprocessing import Process,  freeze_support
import threading
import logging.handlers
 
########################################################################
class CustomConsoleHandler(logging.StreamHandler):
    """"""
 
    #----------------------------------------------------------------------
    def __init__(self, textctrl):
        """"""
        logging.StreamHandler.__init__(self)
        self.textctrl = textctrl
 
 
    #----------------------------------------------------------------------
    def emit(self, record):
        """Constructor"""
        msg = self.format(record)
        print(msg)
        self.textctrl.WriteText(msg + "\n")
        self.flush()
 
########################################################################
class LoggingPanel(wx.Panel):
    """"""
 
    #----------------------------------------------------------------------
    def __init__(self, parent):
        """Constructor"""
        wx.Panel.__init__(self, parent)
 
        self.logText = wx.TextCtrl(self,
                              style = wx.TE_MULTILINE|wx.TE_READONLY|wx.HSCROLL)
 
        btn = wx.Button(self, label="Press Me")
        # btn.Bind(wx.EVT_BUTTON, self.onPress)
 
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.logText, 1, wx.EXPAND|wx.ALL, 5)
        sizer.Add(btn, 0, wx.ALL, 5)
        self.SetSizer(sizer)
 
    #----------------------------------------------------------------------
 
########################################################################
class MyFrame(wx.Frame):
    """"""
 
    #----------------------------------------------------------------------
    def __init__(self):
        """Constructor"""
        wx.Frame.__init__(self, None, title="Logging test")
        self.panel = LoggingPanel(self)
        self.Show()
 
#----------------------------------------------------------------------

if __name__ == '__main__':
    print(wx.__version__)
    # freeze_support()
    logger = logging.getLogger('')
    logger.setLevel(logging.INFO)
    # __ to console logger
    console = logging.StreamHandler()
    # console.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(name)-12s: %(levelname)-8s %(message)s')
    # tell the handler to use this format
    console.setFormatter(formatter)
    # console.setLevel(logging.INFO)
    # add handler to logger
    logger.addHandler(console)

    # __ set to-file-logger that creates new log file everyday at midnight
    file = logging.handlers.TimedRotatingFileHandler(
        'log/log.txt', 'midnight', 1)
    file.suffix = "%Y-%m-%d"  # or anything else that strftime will allow
    formatter = logging.Formatter('%(name)-12s: %(levelname)-8s %(message)s')
    # tell the handler to use this format
    file.setFormatter(formatter)
    # file.setLevel(logging.INFO)
    # add handler to logger
    logger.addHandler(file)

    # subscribe to all logging ports
    logging_ports = range(14240, 14251)
    ctx = zmq.Context()
    sub = ctx.socket(zmq.SUB)
    sub.setsockopt_string(zmq.SUBSCRIBE, '')
    for port in logging_ports:
        sub.bind('tcp://0.0.0.0:{0}'.format(port))
    # sub.bind('tcp://127.0.0.1:14250')

    app = wx.App(False)
    frame = MyFrame()
    
    txtHandler = CustomConsoleHandler(frame.panel.logText)
    logger.addHandler(txtHandler)

    t = threading.Thread(target=app.MainLoop)
    t.setDaemon(1)
    t.start()
    # appProcess = Process(target=app.MainLoop)
    # appProcess.start()

    # app.MainLoop()
 
    while True:
        # logger publishes logger as multipart: [level, message]
        level, message = sub.recv_multipart()
        # get level-appropriate logging function
        log = getattr(logger, level.decode('utf8').lower())
        log(message.decode('utf8').rstrip())
        time.sleep(0.1)
