# Global configuration
Global config via import `from ethomaster import config` via [pyyaml](https://pyyaml.org), which reads the `ethoconfig.yaml` file in the home directory into a dictionary. After parsing, content can be accessed as in a dictionary: `value = config['SECTION']['parameter']`.

```yaml
GENERAL:
  hosts: [localhost] # list all hosts
  services: [DAQ, PTG, THUA]  # list all services - used for checking status of remote services
  services_working_port: [4249, 4248] # ports over which each service is advertised UNUSED?
  services_logging_port: [1449, 1448] # ports over which each service is logs UNUSED?
  user: ncb # default user for starting remote services via ssh
  folder: C:/Users/ncb.UG-MGEN/ # default working directory
  python_exe: C:/Users/ncb.UG-MGEN/miniconda3/python.exe # point to the python executable - used when starting the services. Can point to a python exe in an environment.
HEAD:
  name: localhost # name/IP of head
  playlistfolder: C:/Users/ncb.UG-MGEN/ethoconfig/playlists
  protocolfolder: C:/Users/ncb.UG-MGEN/ethoconfig/protocols
  stimfolder: C:/Users/ncb.UG-MGEN/ethoconfig/stim
  loggingfolder: C:/Users/ncb.UG-MGEN/log

LOGGER:
  portrange: [1420, 1461]

ATTENUATION: # frequency:attenuation factor pairs
  {-1: 1,  0: 1,100: 1,150: 1, 200: 1, 250: 1, 300: 1, 350: 1, 400: 1, 450: 1, 500: 1, 600: 1, 700: 1, 800: 1, 900: 1, 1000: 1, 1500: 1, 2000: 1}
```

## For RPI

```yaml
GENERAL:
  hosts:
    rpi3: 192.168.1.3
    rpi4: 192.168.1.4
    rpi5: 192.168.1.5
    rpi6: 192.168.1.6
    rpi7: 192.168.1.7
    rpi8: 192.168.1.8
    rpi9: 192.168.1.9
  services: [CAM, SND, SLE, SLP, SCM] # list all services
  services_working_port: [4242, 4243, 4245, 4244, 4247]  # ports over which each service is advertised
  services_logging_port: [1442, 1443, 1445, 1444, 1447] # ports over which each service is logs
  user: ncb  # default user
  folder: ~/  # default working directory

HEAD:
  name: 192.169.1.2  # IP of head
  playlistfolder: C:/Users/ncb.UG-MGEN/ethoconfig/playlists
  protocolfolder: C:/Users/ncb.UG-MGEN/ethoconfig/protocols
  stimfolder: C:/Users/ncb.UG-MGEN/ethoconfig/stim
  loggingfolder: C:/Users/ncb.UG-MGEN/log


LOGGER:
 portrange: [1420, 1461]  # NEED TO FIGURE OUT THE CORRECT ONES HERE!!

CAMERA:
  fps: 30
  size: (1000, 1000)

ATTENUATION: # frequency:attenuation factor pairs
  {-1: 1,  0: 1,100: 1,150: 1, 200: 1, 250: 1, 300: 1, 350: 1, 400: 1, 450: 1, 500: 1, 600: 1, 700: 1, 800: 1, 900: 1, 1000: 1, 1500: 1, 2000: 1}
  rpi6: {-1: 1,  0: 1,100: 1,150: 1, 200: 1, 250: 1, 300: 1, 350: 1, 400: 1, 450: 1, 500: 1, 600: 1, 700: 1, 800: 1, 900: 1, 1000: 1, 1500: 1, 2000: 1}
  rpi8: {-1: 1,  0: 1,100: 1,150: 1, 200: 1, 250: 1, 300: 1, 350: 1, 400: 1, 450: 1, 500: 1, 600: 1, 700: 1, 800: 1, 900: 1, 1000: 1, 1500: 1, 2000: 1}

```
