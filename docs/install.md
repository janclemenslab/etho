# Installation

- install miniconda
- install conda packages: `mamba create python=3.9 cython numpy scipy h5py wxpython opencv pandas pyzmq gevent future pillow msgpack-python pyyaml ipython pyserial pyqtgraph pyside2 pip git defopt flammkuchen msgpack-numpy rich fabric psutil -c conda-forge -n etho -y`
- notes:
   - on the rpi PC install `pandas=0.23` and `python=3.7` instead
   - if you want to use the old flycapture SDK (needed for some older FLIR/PointGrey cameras), install `python=3.6` instead
- service specific callbacks:
   - NI daq mx: `pip install pydaqmx`
   - rpi sound: `pip install pygame`
   - saving videos using vidread: `pip install vidread[core]`
   - ximea cameras: [https://www.ximea.com/support/wiki/apis/python]()
   - flycapture (old FLIR/PointGrey SDK) cameras: [https://www.flir.com/products/flycapture-sdk/]() (only works with python 3.6)
   - spinnaker (new FLIR/PointGrey SDK) cameras: [https://www.flir.eu/products/spinnaker-sdk/]() (only works up to python 3.8)
- install custom repos:
  - zerorpc fork: `pip install git+https://github.com/postpop/zerorpc-python --no-deps`
  - ethodrome: `pip install git+https://github.com/janclemenslab/ethodrome --no-deps`
- control.bat: `C:/Users/ncb/.conda/envs/etho/python.exe -m ethomaster.gui.wxCtrl_ephys` (wxCtrl_ephys will be different)



# Set up passwordless SSH

First, open a terminal and execute the following command to generate public/private RSA key pair:
```
ssh-keygen
```
`ssh-keygen` generates public/private rsa key pair. You can click enter without entering anything for a default file location and empty passphrase.

Your public key has been saved in C:\Users\[username]/.ssh/id_rsa.pub if you didn’t change the file location.
Open id_rsa.pub with a text editor so that we can append the generated SSH public key to existing keys in the destination server.

Connect to the destination server using ssh and your password from PowerShell.
Open the “authorized_keys” file with an editor:
```
code ~/.ssh/authorized_keys
```

Copy the contents of the “id_rsa.pub” (which was open in Notepad++) and append to the “authorized_keys” file in the server.


# Comms via ssh



via https://stackoverflow.com/a/19903649/2301098
```python
import subprocess
ssh = subprocess.Popen(['ssh','-tt', 'ncb@UKME04-13CW'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, universal_newlines=True, bufsize=0)


cmd = 'ping -n 10 -t localhost'
ssh.stdin.write(f"{cmd} \n")
ssh.poll()  # returns None

# need to close the stdint if we want the output
ssh.stdin.close()
for line in ssh.stdout:
    print(line,end="")

ssh.terminate() # kill
ssh.poll()  # now returns 1
```

f'wmic process call create "{cmd}"'

Remote is win?
```
import subprocess
ssh = subprocess.Popen(['ssh','-tt', 'localhost', '"uname"'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
out = ssh.stdout.readlines()
print('STDOUT:', out)
err = ssh.stdout.readlines()
print('STDERR:', err)
ssh.terminate()
```

```python
import subprocess
cmd = 'ping -n 10 -t localhost'
ssh = subprocess.Popen(['ssh','-tt', 'ncb@UKME04-13CW', '-f', cmd], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, shell=True)
result = ssh.stdout.readlines()
print(result)
```

##
```python
import asyncio

async def run(cmd):
    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE)

    stdout, stderr = await proc.communicate()

    print(f'[{cmd!r} exited with {proc.returncode}]')
    if stdout:
        print(f'[stdout]\n{stdout.decode()}')
    if stderr:
        print(f'[stderr]\n{stderr.decode()}')

asyncio.run(run(f'ssh -tt ncb@UKME04-13CW -f "ping -n 10 -t localhost"'))
```

