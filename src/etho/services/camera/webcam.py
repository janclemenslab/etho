import logging
import math
import platform
import threading
import time

from .base import BaseCam


logger = logging.getLogger(__name__)


_CONTROL_DEFAULTS = {
    "shutter_speed": None,
    "brightness": 0,
    "gamma": 1,
    "gain": 0,
    "binning": 1,
    "optimize_auto_exposure": False,
    "external_trigger": False,
}


def _warn_ignored_controls(params):
    ignored = [name for name, default in _CONTROL_DEFAULTS.items() if params.get(name) not in (None, default)]
    if ignored:
        logger.warning("Webcam ignores unsupported settings: %s.", ", ".join(ignored))


def _input_format():
    input_format = {"Darwin": "avfoundation", "Linux": "v4l2", "Windows": "dshow"}.get(platform.system())
    if input_format is None:
        raise ValueError("Webcam capture is supported on macOS, Linux, and Windows.")
    return input_format


def _webcam_inputs(input_format):
    import av

    try:
        devices = av.enumerate_input_devices(input_format)
    except (ValueError, av.FFmpegError) as exc:
        raise ValueError(f"Could not list webcams using {input_format}: {exc}") from exc

    if input_format == "v4l2":
        # FFmpeg's V4L2 device list does not label its entries with media types.
        return [(device.name, device.description) for device in sorted(devices, key=lambda device: device.name)]

    if input_format == "dshow":
        return [
            (f"video={device.name}", device.description)
            for device in sorted(devices, key=lambda device: device.name)
            if "video" in device.media_types
        ]

    # AVFoundation also includes system audio and screen capture in its device list.
    return [
        (f"{device.name}:none", device.description)
        for device in devices
        if "video" in device.media_types and not device.description.startswith("Capture screen ")
    ]


def list_webcams():
    """Return webcam names in the order used by GCM's zero-based camera numbers."""
    return [description or source for source, description in _webcam_inputs(_input_format())]


class Webcam(BaseCam):
    @staticmethod
    def enumerate_devices():
        return enumerate(list_webcams())

    def __init__(self, serialnumber):
        import av

        super().__init__(serialnumber)
        self._av = av
        self._lock = threading.Lock()
        self._container = None
        self._frames = None
        self._read_timeout = 2.0

    def init(self):
        number = str(self.serialnumber)
        if not number.isascii() or not number.isdecimal():
            raise ValueError("Webcam cam_serialnumber must be a nonnegative integer. Run 'etho hardware' on the camera host.")
        self._format = _input_format()
        inputs = _webcam_inputs(self._format)
        index = int(number)
        if index >= len(inputs):
            raise ValueError(f"Webcam {index} is unavailable ({len(inputs)} found). Run 'etho hardware' on the camera host.")
        self._source, self._name = inputs[index]

    @property
    def roi(self):
        return self._roi

    @roi.setter
    def roi(self, value):
        x, y, width, height = value
        if width <= 0 or height <= 0:
            raise ValueError("Webcam requires a positive frame width and height.")
        self.warn_if_offsets(x, y)
        self._requested_size = (width, height)
        self._roi = (0, 0, width, height)

    @classmethod
    def ignore_unsupported_settings(cls, params):
        cls.warn_if_offsets(params.get("frame_offx"), params.get("frame_offy"))
        _warn_ignored_controls(params)
        params.update(_CONTROL_DEFAULTS, frame_offx=0, frame_offy=0)

    @staticmethod
    def warn_if_offsets(x, y):
        if x or y:
            logger.warning("Frame offsets are ignored for webcams.")

    @property
    def framerate(self):
        return self._framerate

    @framerate.setter
    def framerate(self, value):
        rate = float(value)
        if not math.isfinite(rate) or rate <= 0:
            raise ValueError("Webcam frame_rate must be positive and finite.")
        self._requested_rate = self._framerate = rate

    @BaseCam.exposure.setter
    def exposure(self, value):
        _warn_ignored_controls({"shutter_speed": value})

    @BaseCam.brightness.setter
    def brightness(self, value):
        _warn_ignored_controls({"brightness": value})

    @BaseCam.gamma.setter
    def gamma(self, value):
        _warn_ignored_controls({"gamma": value})

    @BaseCam.gain.setter
    def gain(self, value):
        _warn_ignored_controls({"gain": value})

    @BaseCam.external_trigger.setter
    def external_trigger(self, value):
        _warn_ignored_controls({"external_trigger": value})

    @BaseCam.binning.setter
    def binning(self, value):
        _warn_ignored_controls({"binning": value})

    def optimize_auto_exposure(self):
        _warn_ignored_controls({"optimize_auto_exposure": True})

    def start(self):
        with self._lock:
            if self._container is not None:
                return
            width, height = self._requested_size
            options = {"video_size": f"{width}x{height}", "framerate": str(self._requested_rate)}
            try:
                container = self._av.open(self._source, format=self._format, container_options=options, timeout=(5.0, self._read_timeout))
            except self._av.FFmpegError as exc:
                raise ValueError(f"Could not open webcam {self.serialnumber} ({self._name}) at {width}x{height}, {self._requested_rate:g} fps: {exc}") from exc
            if not container.streams.video:
                container.close()
                raise ValueError(f"Webcam {self.serialnumber} ({self._name}) did not provide a video stream.")
            self._container = container
            self._framerate = float(container.streams.video[0].average_rate or self._requested_rate)
            self._frames = container.decode(video=0)

    def get(self, timeout=None):
        with self._lock:
            if self._container is None:
                raise ValueError("Webcam is stopped.")
            deadline = time.monotonic() + (self._read_timeout if timeout is None else timeout)
            while True:
                try:
                    frame = next(self._frames)
                    break
                except self._av.BlockingIOError:
                    # AVFoundation can report that the next frame is not ready yet.
                    self._frames = self._container.decode(video=0)
                    if time.monotonic() >= deadline:
                        raise ValueError(f"Timed out waiting for a frame from webcam {self.serialnumber}.") from None
                    time.sleep(0.005)
                except (self._av.FFmpegError, StopIteration) as exc:
                    raise ValueError(f"Could not read a frame from webcam {self.serialnumber}: {exc}") from exc

            timestamp = time.time()
            self._roi = (0, 0, frame.width, frame.height)
            # Copy native BGR frames before the device can reclaim its buffers.
            image = frame.to_ndarray(format="bgr24")
            if frame.format.name == "bgr24":
                image = image.copy()
            return image, timestamp, timestamp

    def stop(self):
        with self._lock:
            if self._container is not None:
                self._frames = None
                container, self._container = self._container, None
                container.close()

    close = stop
    reset = stop

    def info_hardware(self):
        return {"Camera model": self._name, "Device number": int(self.serialnumber), "Capture backend": self._format}

    def info_imaging(self):
        _, _, width, height = self.roi
        return {"width": width, "height": height, "offsetX": 0, "offsetY": 0, "framerate": self.framerate}
