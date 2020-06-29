import cv2
import logging

from ..utils.log_exceptions import for_all_methods, log_exceptions
from . import _register_callback


@for_all_methods(log_exceptions(logging.getLogger(__name__)))
@_register_callback
def disp(displayPipe, frame_width, frame_height, poll_timeout=0.01):
    logging.info("setting up disp")
    cv2.namedWindow('display')
    cv2.resizeWindow('display', frame_width, frame_height)
    RUN = True
    while RUN:
        if displayPipe.poll(poll_timeout):
            image = displayPipe.recv()
            if image is None:
                logging.info('stopping display thread')
                RUN = False
                break
            cv2.imshow('display', image)
            cv2.waitKey(1)
    logging.info("closing display")
    cv2.destroyWindow('display')


@for_all_methods(log_exceptions(logging.getLogger(__name__)))
@_register_callback
def disp_fast(displayPipe, frame_width, frame_height, poll_timeout=0.01):
    logging.info("setting up disp_fast")
    from pyqtgraph.Qt import QtGui
    import pyqtgraph as pg
    from pyqtgraph.widgets.RawImageWidget import RawImageWidget
    pg.setConfigOption('background', 'w')
    pg.setConfigOption('leftButtonPan', False)

    # set up window and subplots
    app = QtGui.QApplication([])
    win = RawImageWidget(scaled=True)
    win.resize(frame_width, frame_height)
    win.show()
    app.processEvents()
    RUN = True
    while RUN:
        if displayPipe.poll(poll_timeout):
            image = displayPipe.recv()
            if image is None:
                logging.info('stopping display thread')
                RUN = False
                break
            win.setImage(image)
            app.processEvents()
    logging.info("closing display")


@for_all_methods(log_exceptions(logging.getLogger(__name__)))
@_register_callback
def save(writeQueue, file_name, frame_rate, frame_width, frame_height):
    logging.info("setting up video writer")
    ovw = cv2.VideoWriter()
    logging.info("   saving to " + file_name + '.avi')
    ovw.open(file_name + '.avi', cv2.VideoWriter_fourcc(*'x264'),
             frame_rate, (frame_width, frame_height), True)
    RUN = True
    while RUN:
        image = writeQueue.get()  # get new frame
        if image is None:
            logging.info('stopping WRITE thread')
            RUN = False
            break
        ovw.write(image)
    logging.info("closing video writer")
    ovw.release()
    ovw = None
    del ovw


@for_all_methods(log_exceptions(logging.getLogger(__name__)))
@_register_callback
def save_fast(writeQueue, file_name, frame_rate, frame_width, frame_height):
    logging.info("setting up video writer")
    import sys
    VPF_bin_path = 'C:/Users/ncb.UG-MGEN/codec/VideoProcessingFramework/bin3.7'
    sys.path.append(VPF_bin_path)
    import PyNvCodec as nvc

    gpuID = 0
    encFile = open(file_name + '.h264',  "wb")
    nvEnc = nvc.PyNvEncoder({'rc':'vbr_hq','profile': 'high', 'cq': '10', 'codec': 'h264', 'bf':'3', 'fps': str(frame_rate), 'temporalaq': '', 'lookahead':'20',  's': f'{frame_width}x{frame_height}'}, gpuID)
    nvUpl = nvc.PyFrameUploader(nvEnc.Width(), nvEnc.Height(), nvc.PixelFormat.YUV420, gpuID)
    nvCvt = nvc.PySurfaceConverter(nvEnc.Width(), nvEnc.Height(), nvc.PixelFormat.YUV420, nvc.PixelFormat.NV12, gpuID)
    logging.info("   saving to " + file_name + '.h264')
    RUN = True
    while RUN:
        image = writeQueue.get()  # get new frame
        if image is None:
            logging.info('stopping WRITE thread')
            RUN = False
            break
        rawFrameYUV420 = cv2.cvtColor(image, cv2.COLOR_RGB2YUV_I420)  # convert to YUV420 - nvenc can't handle RGB inputs
        rawSurfaceYUV420 = nvUpl.UploadSingleFrame(rawFrameYUV420)  # upload YUV420 frame to GPU
        if (rawSurfaceYUV420.Empty()):
            continue  # break
        rawSurfaceNV12 = nvCvt.Execute(rawSurfaceYUV420)  # convert YUV420 to NV12
        if (rawSurfaceNV12.Empty()):
            continue  # break
        encFrame = nvEnc.EncodeSingleSurface(rawSurfaceNV12)  # compres NV12 and download
        if(encFrame.size):
            encByteArray = bytearray(encFrame)  # save compressd byte stream to file
            encFile.write(encByteArray)

    logging.info("closing video writer")
    #Encoder is asyncronous, so we need to flush it
    encFrames = nvEnc.Flush()
    for encFrame in encFrames:
        if(encFrame.size):
            encByteArray = bytearray(encFrame)
            encFile.write(encByteArray)
    encFile.close()
    del encFile