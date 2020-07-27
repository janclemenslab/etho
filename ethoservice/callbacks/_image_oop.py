import logging


class BaseCallback():

    def __init__(self):
        self.RUN: bool = False

    def start(self):
        self.RUN = True
        self.run()

    def stop(self):
        self.RUN = False

    def run(self):
        while self.RUN:
            self._loop()
        self._cleanup()

    def _loop(self):
        # single cycle - should poll comms and also handle breakout
        pass

    def _cleanup(self):
        # close everything created during __init__
        pass


class ImageDisplayCV2(BaseCallback):

    def __init__(self, displayPipe, frame_width, frame_height, poll_timeout=0.01):
        super().__init__(self)

        import cv2
        logging.info("setting up disp")
        self.displayPipe = displayPipe
        self.poll_timeout = poll_timeout
        cv2.namedWindow('display')
        cv2.resizeWindow('display', frame_width, frame_height)

    def _loop(self):
        if self.displayPipe.poll(poll_timeout):
            image = self.displayPipe.recv()

            # maybe this is not required anymore
            # since we can call stop() from the outside?
            if image is None:
                logging.info('stopping display thread')
                self.stop() # = False
                # break

            if image is not None:
                cv2.imshow('display', image)
                cv2.waitKey(1)

    def _cleanup(self):
        logging.info("closing display")
        cv2.destroyWindow('display')


class ImageDisplayPQG(BaseCallback):
    def __init__(self, displayPipe, frame_width, frame_height, poll_timeout=0.01):
        super().__init__(self)

        from pyqtgraph.Qt import QtGui
        import pyqtgraph as pg
        from pyqtgraph.widgets.RawImageWidget import RawImageWidget

        logging.info("setting up ImageDisplayPQG")
        self.displayPipe = displayPipe
        self.poll_timeout = poll_timeout

        pg.setConfigOption('background', 'w')
        pg.setConfigOption('leftButtonPan', False)

        # set up window and subplots
        self.app = QtGui.QApplication([])
        self.win = RawImageWidget(scaled=True)
        self.win.resize(frame_width, frame_height)
        self.win.show()
        self.app.processEvents()

    def _loop(self):
        image = self.displayPipe.get(timeout=self.poll_timeout)
        if image is not None:
            self.win.setImage(image)
            self.app.processEvents()
        else:
            self.stop()
        # if self.displayPipe.poll(self.poll_timeout):
        #     image = self.displayPipe.recv()

        #     # maybe this is not required anymore
        #     # since we can call stop() from the outside?
        #     if image is None:
        #         logging.info('stopping display thread')
        #         self.stop()
        #         # break

        #     if image is not None:
        #         self.win.setImage(image)
        #         self.app.processEvents()

    def _cleanup(self):
        logging.info("closing display")
        # close app and windows here?