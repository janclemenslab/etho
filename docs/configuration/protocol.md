# Experimental protocols
For experiment-specific settings.

### Make
[yaml](pyyaml.org) format. The following fields are supported:
```yaml
# define defaults - can be overriden in protocols/headers
NODE: # node-specific parameters and parameters that apply to all service (e.g. maxduration)
  user: ncb # default user
  folder: C:/Users/ncb/ # default working directory
  savefolder: C:/Users/ncb/data # this is where the recordings will be saved
  maxduration: 90 # seconds
  use_services: [GCM, DAQ]  # list services by their 3-letter abbreviations. only these will be run! See service-specific parameters below for valid names
  serializer: pickle  # save default

# SERVICE specific parameters
GCM:
  cam_type: Ximea  # or Spinnaker (FlyCapture is not implemented yet - use PTG service)
  frame_rate: 1000.0 # frames per second
  frame_width: 640 # pixels
  frame_height: 200 ##440 # pixels
  shutter_speed: 50 # ns=1.5ms??
  frame_offx: 78
  frame_offy: 10
  brightness: 0.0
  exposure: 0.0
  gamma: 1.0
  gain: 0.0
  cam_serialnumber: 30959651  # MQ013CG-ON
  callbacks:
    save_avi:  # save frames as avi using opencv VideoWriter (has no params)
    save_avi_fast:  # save frames as avi using GPU-based VideoProcessingFramework (use either `save_avi_fast`, or `save_avi`, NEVER BOTH!!)
       VPF_bin_path: C:/Users/ncb/vpf/bin3.7  # path to the directory containing the binaries for VPF
    save_timestamps:
    disp:  # plot frames using opencv
    disp_fast:  # plot frames using pyqtgraph (faster?)

DAQ:
  clock_source: OnboardClock
  samplingrate: 5000 # Hz
  shuffle: True # block-randomize order of stimuli for playback
  ledamp: 1.0
  analog_chans_in: [ai0]
  analog_chans_out: [ao0, ao1]
  limits: 10.0
  callbacks:
    save_h5:   # save data as hdfs (has no params)
    plot:  # plot traces using matplotlib OR
    plot_fast:  # plot traces using pyqtgraph (much faster!) (use either `plot` or plot_fast`, never both)

THUA:
  pin ???

CAM:  # pi camera
  framerate: 30 # frames per second
  framewidth: 1000 # pixels
  frameheight: 1000 # pixels
  shutterspeed: 10000 # ns=10ms
  annotate_frame_num: False # print frame number in each frame
  # unused but probably useful
  exposuremode: 'fixedfps'
  video_denoise: False

THU: # pi temperature and humidity sensor
  pin: 17 # GPIO PIN for read out
  interval: 20 # seconds, log temperature and humidity every 20 seconds

OPT2:  # pi opto led control
  pin: [25, 24]  # red and green led channel
  playlist_channels: [2, 3]

SND:  # pi sound playback via pygame
  samplingrate: 44100  # Hz
  shuffle: False  # block-randomize order of stimuli for playback
  ledamp: 1300  # amplitude of the IR LED used for syncing audio and video
  playlist_channels: [0, 1]

REL:  # pi relay control (for backlight and illumination)
  pin: 22

DLP:  # DLP projector
  warpfile: 'Z:/#Data/flyball/projector/warpmesh_1140x912.data'
  use_warping: False
  callbacks:
    savedlp_h5:  # save per-frame stimulus parameters to `_dlp.h5`
  runners:
    LED_blinker:
      object: 'Rect'  # should be the classname: `psychopy.visuals.NAME`
      led_frame: 360
      led_duration: 180
```

### Parse
```python
from ethomaster.utils.config import readconfig
prot = readconfig(protocolfile)
```